# โครงสร้างข้อมูลสำหรับ LLM Agent
## งานกวาดข้อมูล Competitor ระดับลึก รายจังหวัด

เอกสารนี้ใช้เป็นมาตรฐานสำหรับให้ LLM agent ช่วยค้นหา, รวบรวม, และจัดเก็บข้อมูล `competitor EV charging stations` ในจังหวัดที่กำหนด โดยออกแบบให้:
- ใช้ต่อกับงาน `Heat Map`
- audit และตรวจทานได้
- นำเข้า DB ได้ง่าย
- แยก `confirmed` ออกจาก `seed` และ `placeholder` ได้ชัด

---

## 1. เป้าหมายของข้อมูลชุดนี้
ต้องการตอบ 4 คำถามหลัก:

1. ในจังหวัดนี้มีคู่แข่งรายไหนบ้าง
2. อยู่ตรงไหน
3. ขนาดสถานีประมาณไหน
4. สถานะข้อมูลเชื่อถือได้แค่ไหน

ดังนั้นข้อมูลที่เก็บต้องไม่ใช่แค่ “ชื่อสถานี” แต่ต้องมีทั้ง:
- พิกัด
- operator / network
- จำนวนหัวชาร์จ
- กำลังชาร์จ
- สถานะการยืนยัน
- source ที่ย้อนกลับไปตรวจได้

---

## 2. หลักคิดสำคัญ
สำหรับ LLM agent ให้ถือว่า 1 record = 1 สถานีชาร์จ

ถ้าสถานีเดียวกันมีหลายแหล่งข้อมูล:
- ให้รวมเป็น record เดียว
- แต่เก็บ `source_url`, `verification_note`, และ `confidence` ให้ครบ

ถ้ายังไม่แน่ใจว่าเป็นสถานีจริงหรือไม่:
- ให้เก็บได้
- แต่ต้อง mark ว่า `seed_needs_verification` หรือ `placeholder`

---

## 3. โครงสร้างข้อมูลที่แนะนำ
แนะนำให้ LLM agent ส่งออกเป็น `CSV` หรือ `JSON` ที่มี field แบบนี้

| field | ความหมาย | ตัวอย่าง |
|---|---|---|
| `station_id` | รหัสสถานีไม่ซ้ำในจังหวัด | `rayong_elexa_pluakdaeng_001` |
| `province` | จังหวัด | `Rayong` |
| `district` | อำเภอ | `Pluak Daeng` |
| `name` | ชื่อสถานี | `EleXA Charging Station - WHA Eastern Seaboard` |
| `network` | เครือข่าย | `EleXA`, `PEA VOLTA`, `EV Station PluZ` |
| `operator` | ผู้ให้บริการ / เจ้าของเครือ | `EGAT`, `PEA`, `OR` |
| `lat` | ละติจูด | `13.004796` |
| `lon` | ลองจิจูด | `101.144536` |
| `plug_count` | จำนวนหัวชาร์จรวม | `4` |
| `gun_count` | จำนวน gun ที่ใช้งานจริง | `2` |
| `max_kw` | กำลังสูงสุดต่อหัวหรือจุดเด่นหลัก | `120` |
| `total_site_kw` | กำลังรวมทั้งสถานี ถ้าทราบ | `240` |
| `dc_fast` | เป็น DC fast charging หรือไม่ | `true` |
| `price_per_kwh` | ราคาต่อ kWh ถ้าทราบ | `7.5` |
| `open_hours` | เวลาทำการ | `24 hours` |
| `status` | สถานะสถานี | `open`, `coming_soon`, `unknown` |
| `source_url` | URL แหล่งอ้างอิงหลัก | URL ของเว็บจริง |
| `verification_status` | สถานะการตรวจสอบ | ดูหัวข้อด้านล่าง |
| `verification_note` | หมายเหตุการยืนยัน | `Confirmed from operator map on 2026-06-08` |
| `confidence` | ความมั่นใจ | `high`, `medium`, `low` |
| `notes` | หมายเหตุอื่น ๆ | `Inside industrial estate, public access uncertain` |
| `updated_by` | แหล่งที่มาของการอัปเดต | `llm_agent` |
| `active` | ใช้งานในโมเดลหรือไม่ | `true` |

---

## 4. ค่ามาตรฐานที่ควรใช้

### 4.1 `verification_status`
ใช้ค่าเหล่านี้เป็นมาตรฐาน:

- `confirmed_live`
  - ยืนยันได้จาก operator map, official app, official website หรือภาพหน้างานที่เชื่อถือได้
- `seed_needs_verification`
  - มีข้อมูลพอสมควร แต่ยังไม่ได้ยืนยันสุดท้าย
- `placeholder_network_level`
  - รู้ว่ามีเครือข่ายนี้ในจังหวัดหรือ corridor นี้ แต่ยังไม่แน่ใจ exact pin
- `coming_soon`
  - พบว่ากำลังจะเปิด แต่ยังไม่ชัดว่าเปิดจริงแล้ว
- `closed_or_unavailable`
  - เคยมีแต่ปิด หรือไม่เปิดบริการสาธารณะ

### 4.2 `confidence`
- `high` = ยืนยันจาก source ตรงหรือหลายแหล่งสอดคล้องกัน
- `medium` = มี source น่าเชื่อถือพอใช้ แต่รายละเอียดบางส่วนยังไม่ครบ
- `low` = ยังเป็น lead หรือ candidate ที่ควรตรวจต่อ

---

## 5. ลำดับความสำคัญของแหล่งข้อมูล
เวลาสั่ง LLM agent ให้ค้นหา ควรให้น้ำหนัก source ตามลำดับนี้

1. `official operator map / official website`
2. `official app listing`
3. `station network pages`
4. `Google Maps / Waze / Longdo / Apple Maps`
5. `ข่าวประชาสัมพันธ์`
6. `directory / social post`

หลักการคือ:
- ถ้ามี source ทางการ ให้ยึดทางการก่อน
- ถ้าพิกัดไม่ตรงกัน ให้ใช้ source ทางการเป็นหลัก
- ถ้า source ทางการไม่บอกพิกัดชัด ให้ใช้ map listing ช่วยเสริม แต่ต้องใส่ note

---

## 6. รูปแบบไฟล์ที่เหมาะกับการเก็บ

### 6.1 ไฟล์หลักสำหรับ import
แนะนำรูปแบบนี้:

`data/competitors_<province>_detailed.csv`

ตัวอย่าง:
- `data/competitors_phitsanulok_detailed.csv`
- `data/competitors_rayong_detailed.csv`

ใช้สำหรับข้อมูลที่ค่อนข้างพร้อมและจะเข้าระบบจริง

### 6.2 ไฟล์ seed
ถ้ายังเป็นรอบกวาดเบื้องต้น:

`data/competitors_<province>_seed.csv`

ใช้สำหรับ:
- candidate list
- lead ที่ยังต้องตรวจ
- สถานีที่ยังไม่ยืนยันเต็ม

### 6.3 ไฟล์ audit note
ถ้าจังหวัดนั้นซับซ้อนมาก ให้มี note แยก:

`docs/<province>_competitor_audit_notes.md`

เอาไว้เก็บ:
- สถานีที่ยังไม่ชัด
- จุดที่พิกัดชนกัน
- สถานีในเขตปิด
- สถานีที่ควรลงพื้นที่ตรวจ

---

## 7. ตัวอย่าง record ที่ดี

```csv
station_id,province,district,name,network,operator,lat,lon,plug_count,gun_count,max_kw,total_site_kw,dc_fast,price_per_kwh,open_hours,status,source_url,verification_status,verification_note,confidence,notes,updated_by,active
rayong_elexa_wha_001,Rayong,Pluak Daeng,EleXA Charging Station - WHA Eastern Seaboard,EleXA,EGAT,13.004796,101.144536,4,2,120,240,true,7.5,24 hours,open,https://example.com/official-map,confirmed_live,Confirmed from official map and location listing on 2026-06-08,high,Industrial estate access should be rechecked for public users,llm_agent,true
```

---

## 8. สิ่งที่ LLM agent ควรส่งมาพร้อมข้อมูล
นอกจากไฟล์ CSV/JSON ควรให้ agent ส่ง summary สั้น ๆ แบบนี้ด้วย

### 8.1 จังหวัด
เช่น `Rayong`

### 8.2 จำนวนสถานีที่พบ
- confirmed = 8
- seed = 5
- placeholder = 2

### 8.3 cluster สำคัญ
- เมืองหลัก
- ring road / bypass
- industrial corridor
- airport / tourism gateway

### 8.4 จุดที่ยังไม่ชัด
- exact pin ไม่ชัด
- จำนวนหัวไม่ชัด
- public access ไม่ชัด

---

## 9. ข้อกำหนดการตั้งชื่อ `station_id`
แนะนำรูปแบบ:

`<province>_<network>_<area>_<running_number>`

ตัวอย่าง:
- `chiangmai_pea_volta_airport_001`
- `rayong_elexa_pluakdaeng_001`
- `phitsanulok_evstationpluz_central_001`

หลักการ:
- ใช้ lowercase
- คั่นด้วย `_`
- หลีกเลี่ยงช่องว่าง
- อย่าใช้ชื่อที่เปลี่ยนง่ายเกินไป

---

## 10. กรณีที่ควร mark ระวังเป็นพิเศษ
ให้ใส่ note หรือ confidence ต่ำลง ถ้าเป็นกรณีเหล่านี้:

- สถานีอยู่ในเขตปิด / industrial estate ที่คนทั่วไปเข้าไม่ได้
- สถานีอยู่ในพื้นที่โครงการเฉพาะกลุ่ม
- สถานีเพิ่งประกาศเปิด แต่ยังไม่มีหลักฐานใช้งานจริง
- พิกัดอ้างอิงอยู่แค่ระดับห้างหรือปั๊ม แต่ไม่รู้ตำแหน่งจริงในลานจอด
- ข่าวเก่ามากและไม่มี source ใหม่ยืนยัน

---

## 11. Minimum viable structure
ถ้าจะเริ่มกวาดจังหวัดใหม่แบบเร็วที่สุด อย่างน้อยควรมี field เหล่านี้:

- `station_id`
- `province`
- `district`
- `name`
- `network`
- `operator`
- `lat`
- `lon`
- `max_kw`
- `source_url`
- `verification_status`
- `confidence`
- `updated_by`
- `active`

ถ้าขาด field พวกนี้ จะเริ่มใช้ในโมเดลได้ยากและ audit ย้อนกลับลำบาก

---

## 12. ข้อเสนอแนะการใช้งานจริง
ถ้าจะสั่ง LLM agent ทำงานจังหวัดต่อจังหวัด ให้กำหนด output 3 ชิ้นเสมอ:

1. `competitors_<province>_seed.csv` หรือ `detailed.csv`
2. สรุปผล 1 ย่อหน้า
3. รายการ unresolved issues ที่ยังต้องตรวจ

แนวทางนี้จะช่วยให้:
- เอาเข้าระบบได้เร็ว
- ทีมคนตรวจต่อได้ง่าย
- ลดปัญหาข้อมูลลอยหรือเชื่อถือไม่ได้

---

## 13. สรุปสั้นที่สุด
สำหรับงาน `competitor deep sweep` ให้เก็บข้อมูลในรูปแบบ:
- `1 station = 1 row`
- มี `source_url`
- มี `verification_status`
- มี `confidence`
- มี `updated_by`
- มี `active`

และควรแยกชัดว่า record ไหน:
- ยืนยันแล้ว
- ยังเป็น seed
- ยังเป็น placeholder

นี่คือโครงสร้างที่เหมาะที่สุดสำหรับให้ LLM agent ทำงานต่อและให้ทีมเราใช้ใน Heat Map / click analysis / competitor pressure ได้อย่างเป็นระบบ

# เชียงใหม่ pilot: Heat Map, จุดคลิก และการแข่งขัน

วันที่ปรับ: 17 ตุลาคม 2569

## สิ่งที่เปิดใช้

API Heat Map และ Click Analysis ใช้ `method=auto` โดยอ่านจังหวัดที่เปิด pilot จาก `data/charging_behavior_profiles.json` เปิดเฉพาะเชียงใหม่ จังหวัดอื่นยังใช้วิธีเดิม ไม่มีการแก้ข้อมูล POI/DLT/competitor ของจังหวัดอื่น

ใช้โค้ดร่วมใน `th_evi/area_engine.py` ไม่สร้างสูตรคนละชุดตามจังหวัด

- `GET /api/heatmap?...&method=auto`
- `POST /api/click-analysis` ส่ง province/year/scenario/mode/resolution_km ให้ตรงกับแผนที่
- ใช้ `method=legacy` เพื่อเทียบระบบเดิม; หน้าเว็บเปิดด้วย `/planning?method=legacy` หรือ `/?method=legacy`
- `method=pilot` เป็นการระบุใช้แกนเดียวกันกับจังหวัดอื่นเพื่อทดสอบ ไม่ได้แปลว่าข้อมูลจังหวัดนั้นพร้อม

Library functions คง default `legacy` เพื่อไม่เปลี่ยนโมเดลรายงานเดิมโดยเงียบ ๆ รอบนี้รวมเส้นทางเฉพาะ Heat Map/Click API และสองหน้าแผนที่ ไม่ได้เปลี่ยนรายงานการเงินให้เป็นโมเดลใหม่แล้ว

## 1. ฐานเดียวกันของแผนที่และจุดคลิก

คำนวณบน support คงที่ 1 กม. เก็บผลตาม province/year/scenario/mode แล้วให้ขนาด grid ที่แสดงผลเป็นการรวม/แบ่งพื้นที่เดิมด้วย area overlap จุดคลิกอ่าน display cell เดียวกัน ไม่เรียกสูตรประมาณ sessions รายจุดอีกครั้ง

จุดที่อยู่นอก support แม้อยู่ในกรอบ cell ใหญ่เดียวกันจะได้ `outside_support` ไม่ยืมดีมานด์จาก cell ใกล้เคียง ฝั่งแผนที่วาด coverage fragments เพื่อไม่เติมช่องว่างของ mask เมื่อขยาย cell

support ยังอิง activity/exclusion mask จากระบบเดิม และน้ำหนักยังเป็น spatial proxies ไม่ใช่ OD/travel survey ที่สอบเทียบแล้ว การคง mask ไม่ใช่การรับรองว่าขอบพื้นที่/น้ำ/ถนนถูกต้องทุกจุด

## 2. บัญชีรวมไม่เพิ่มตาม POI หรือ display grid

ขณะนี้เชียงใหม่ยังไม่มี input พฤติกรรมครบ จึงใช้ **คะแนนคัดกรองที่ normalize รวม 100% ใน support ที่เลือก** ไม่ใช่งบพลังงานจังหวัด ไม่ใช่สัดส่วนลูกค้า EV จริง และไม่ใช่ความแม่นยำ 100%

POI, business area, zone และ traffic proxy ใช้เป็นน้ำหนักจัดสรรเท่านั้น การเพิ่มน้ำหนัก POI ไม่สร้างงบเพิ่ม ส่วนพื้นที่อื่นอาจได้สัดส่วนลดลง

```text
gross allocated score = competition-pressure allocation + available score
display grid รวม/แบ่งจาก support เดิม จึงไม่สร้างยอดรวมเพิ่ม
```

สีใช้ความหนาแน่นคะแนนต่อพื้นที่ support และ reference maximum เดิม ไม่ปรับตามยอดคะแนนของ cell ใหญ่ที่สะสมมากขึ้นอย่างเดียว

การเปลี่ยน grid จาก 1 เป็น 0.25 กม. เป็นการแบ่งแสดงผล **ไม่ได้ทำให้ข้อมูลต้นทางละเอียดขึ้นเป็น 250 เมตร** ค่าแต่ละ cell เปลี่ยนตามขนาดพื้นที่ได้ แต่ยอดรวมไม่เปลี่ยน

### การเชื่อมงบพลังงานจริง

`configured_spatial_budget` เชื่อม energy accounting ที่ทำไว้กับ fixed support แล้ว แต่เปิดใช้ได้เมื่อมี:

- profile ระบุ `spatial_energy_enabled=true` อย่างชัดแจ้ง
- cohort/พลังงานต่อครั้ง/ประสิทธิภาพครบและผ่าน validation
- evidence fields ครบ (ยังต้องตรวจคุณภาพหลักฐานโดยผู้รับผิดชอบ)
- `spatial_coverage_fraction` ระบุชัด เพื่อแยก travel energy ที่อยู่นอก support ไม่สมมติว่าใช้ในเชียงใหม่ทั้งหมด
- ปีที่ร้องขอตรงกับ observed DLT stock; ยังไม่ extrapolate stock snapshot เป็น forecast ปีอนาคต

เมื่อใช้จริงหน่วยเป็น connector kWh/วัน โดยมี outside/unserved accounting ไม่ปะปนกับคะแนน 100% ทั้งนี้ยังไม่ใช่ยอดขายของสถานีเสนอใหม่ และไม่ได้ validate station capture แล้ว

profile เชียงใหม่ปัจจุบันตั้ง `spatial_energy_enabled=false` และ coverage เป็น null ไม่ใส่ค่าพฤติกรรมที่แต่งขึ้นเพื่อเปิดฟีเจอร์

## 3. การแข่งขัน DC ที่ตรวจสอบได้

ใช้ `th_evi/competition.py` แยกจาก legacy penalty

- ต้องมีข้อมูลระบุชนิด DC และกำลัง จึงมีผลใน direct-DC pressure; AC ไม่ถูกนับเทียบเท่า DC แต่ยังมีผลต่อ charging need ได้ใน upstream energy model
- ไม่ทราบกำลัง = unknown ไม่แทน 120 kW; ไม่ทราบหัว = unknown ไม่แทน 2 หัว
- ตัวเลขที่ถูกบันทึกพร้อมข้อความว่าเป็น interim/modeling assumption ไม่ถูกยกระดับเป็น confirmed power เพราะมีช่องตัวเลขแล้ว
- ไม่ตีความปีข้อมูลหรือ kW รวมทั้งสถานีว่าเป็นกำลังต่อหัว
- เมื่อทราบ power แต่ไม่ทราบจำนวนหัว ใช้เฉพาะ station-level power signal ไม่เพิ่มตัวคูณหัว และ flag missing gun count
- ภายใต้จำนวนหัวและระยะเดียวกัน pressure จาก 25 kW เป็น 25/120 ของ 120 kW ไม่มี power floor เดิม
- ระยะที่ใช้ยังเป็น geodesic distance ไม่ใช่เวลาเดินทางจริง ใช้ decay radius 3 กม. และตัดที่ 9 กม. เป็น screening assumption ไม่ใช่ค่าที่ fit จากลูกค้าจริง
- relative pressure = `(kW/120) × sqrt(known guns or neutral factor) × exp(-(distance/3)^2)`
- competition share = `pressure/(1+pressure)` จึงเกิน 62% ได้ แต่ไม่หักเกิน gross
- unknown stations ไม่ถูกอ้างว่าไม่มีการแข่งขัน; click response ส่ง missing-data warning และสถานะข้อมูล ไม่สร้างค่า power/guns เพื่อบังคับผล

แรงแข่งขันยังไม่ใช่ปริมาณไฟหรือจำนวนลูกค้าที่คู่แข่งครองจริง ยังไม่มีราคา queue, road detour, power sharing หรือ uptime ใน choice model และค่า net อาจสูงเกินจริงหากข้อมูลคู่แข่งไม่ครบ

`/api/chargers` ของเชียงใหม่ใช้ evidence interpretation ชุดเดียวกันในการแสดง power/type/guns แต่ inventory layer อาจมี unverified nationwide KML ที่ไม่ถูกนำเข้าคำนวณ Heat Map ตามกติกาเดิม

## การสื่อสารในหน้าแอพ

- ไม่แปลงคะแนน pilot เป็น `kWh/day`, sessions/day หรือขนาดตู้ที่แนะนำ
- `forecast_available=false`; physical site-forecast fields เป็น null ไม่ใช่ศูนย์
- หน่วยคะแนนระบุเป็นสัดส่วนคะแนนในพื้นที่คัดกรอง
- ไม่ให้สร้างรายงานการลงทุนจาก popup pilot โดยนำคะแนนไปแทนจำนวนรถ
- ยังเปิด Google Maps/Street View และบันทึกพื้นที่ไว้สำรวจได้

## การทดสอบรับงาน

ชุดทดสอบตรวจการคงยอด gross/competition/available เมื่อเปลี่ยน grid 0.25/0.5/0.7/1/1.5/2/5 กม., Heat Map–click parity, mask holes, input units, unknown/assumed competitor data, DC/AC, 25 vs 120 kW, strong competition เกิน 62%, การเชื่อมงบพลังงานเมื่อ input พร้อม และ cache invalidation

Wire format แยก evidence ที่ซ้ำกันออกจากแต่ละ cell และส่งเฉพาะข้อมูลสำหรับแสดงผล; frontend คำนวณเฉพาะสีจาก score/area/reference maximum ไม่คำนวณ demand ใหม่ ต้องตรวจขนาด payload ของ grid ละเอียดก่อน deploy

ผลทดสอบ local กับข้อมูลเชียงใหม่ปี 2026: grid 1/0.5/0.25/2 กม. มี 945/3,458/13,206/283 display cells ตามลำดับ ผลรวม gross ยังคง 100% ภายใน floating-point tolerance และ Heat Map/Click ให้ score ตรงกันทุกขนาดที่ตรวจ ขนาด response ประมาณ 0.49/1.04/3.14/0.34 MB ไม่รวมการบีบอัด ผ่านการทดสอบ browser ทั้ง `/planning` และ `/analysis` ไม่มี JavaScript page errors

ชุดทดสอบที่เกี่ยวข้องหลังแก้ล่าสุดผ่าน 124 tests ส่วน full suite ที่รันระหว่างพัฒนาผ่าน 235 และไม่ผ่าน 5: สี่กรณีเดิม (Chon Buri exclusion, reference-release mock signature, Chiang Mai hotel expectation, DB/CSV fixture ปน nationwide KML) และ Udon Thani surface test ซึ่งทดสอบแยกซ้ำแล้วผ่าน จึงยังไม่อ้างว่า full suite ผ่านทั้งหมด

## สิ่งที่ยังต้องทำก่อนให้คะแนนความแม่นยำสูงขึ้น

เพิ่ม [Travel/SOC preview แบบระบุ input ชัดเจน](travel_soc_preview.md) แล้ว รวมการแก้ click boundary/cache ในหน้า Advanced แต่ยังไม่มี representative travel/SOC เชียงใหม่สำหรับเปิดใช้กับ Heat Map ส่วน OD reconciliation, home/work charging evidence, empirical station choice, queue/capacity และ holdout validation ยังไม่เสร็จ การอนุรักษ์คะแนนและทดสอบตัวจำลองเป็นการปรับหลักการ ไม่ใช่การพิสูจน์ความแม่นยำของจำนวนรถ ณ ทำเล

## การนำขึ้น production

การปรับโมเดลข้างต้นยังไม่เปลี่ยนข้อมูล Neon โดยอัตโนมัติ เมื่อได้รับคำสั่ง publish จึงเพิ่ม `charging_behavior_profile_snapshots` สำหรับเก็บ profile พร้อม SHA-256/engine version/ผู้บันทึก และเพิ่ม `connector_summary`/`power_summary` ให้ competitor records

ใช้ `python scripts/publish_chiang_mai_pilot.py` ตรวจแบบ dry-run และเติม `--apply` เมื่อต้องการเขียนจริง สคริปต์สำรองข้อมูลเชียงใหม่ลง `tmp/` ก่อน ใช้ transaction และเติมเฉพาะ evidence ที่ยังว่าง ไม่เปลี่ยนตัวเลขกำลัง/จำนวนหัว ไม่ทับ evidence ที่แก้ไว้แล้ว และไม่เขียนข้อมูลจังหวัดอื่น

Runtime profile ยังคงอ่านเวอร์ชันที่ bundle มากับโค้ดเพื่อไม่ทำให้วิธีคิดเปลี่ยนเพราะ DB ไม่พร้อม ส่วน Neon เก็บ snapshot ที่ตรวจ hash เทียบกันได้ `/api/charging-demand/basis` ระบุ runtime source และ profile hash ชัดเจน การเก็บ snapshot ไม่ได้เปิด physical energy forecast ที่ข้อมูลยังไม่ครบ

Deployment ใช้ source จาก Git commit โดยไม่รวมไฟล์ `.env`, ข้อมูลสำรอง DB หรือผลลัพธ์รายงานที่ยังไม่ commit

## การประเมินรายสถานีจากข้อมูลอ้างอิง

เพิ่ม [site-demand reference transfer](site_demand_reference_transfer.md) วันที่ 19 ตุลาคม 2569 สำหรับคำนวณครั้งชาร์จเทียบเท่าแบบมีเงื่อนไขจาก Meta Mall ผ่าน `/api/charging-demand/site-preview` โดยรับสเปกและ assumptions ชัดเจน ใช้บัญชี choice pool เดียวก่อน/หลังเพิ่มสถานีและตรวจ capacity ไม่ใช้ AADT fallback เป็นจำนวนลูกค้า โมดูลนี้แยกจากคะแนน Heat Map และยังไม่เปิด `forecast_available` เพราะยังไม่มี holdout ของทำเลใหม่

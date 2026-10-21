# ลำดับเที่ยวรถและ SOC: ขอบเขตส่งมอบข้อ 4

อัปเดต 17 ตุลาคม 2569 โครงสร้างใช้ร่วมทุกจังหวัด แต่ยังไม่ตั้งสมมติฐานพฤติกรรมให้จังหวัดใด

## สิ่งที่ปิดก่อนเริ่ม

หน้า Advanced (`/analysis`) ตรวจการคลิกตาม cell และ coverage fragments จริงของ fixed-support pilot ไม่ยืมคะแนนจาก cell ข้างเคียง หากอยู่นอกพื้นที่รองรับจะแจ้งว่าข้อมูลยังไม่เพียงพอ ไม่สรุปว่าดีมานด์เป็นศูนย์

Cache ใช้ได้เฉพาะจังหวัด ปี scenario โหมด และขนาด grid ที่ตรงกัน ผลลัพธ์เก่าที่มาถึงหลังคลิกใหม่ ปิด popup หรือเริ่มโหลด Heat Map ใหม่ไม่ทับผลล่าสุด การเปลี่ยน resolution ยังไม่เพิ่มยอดคะแนนรวมตามกติกาเดิม

## ตัวจำลองที่เพิ่ม

- `th_evi/travel_soc.py`: จำลองรถหนึ่งคันตาม itinerary ที่ผู้เรียกระบุ ครบ 24 ชั่วโมง และทำซ้ำหลายวัน
- `POST /api/charging-demand/travel-preview`: ตรวจ input และคืน SOC, charging events, บัญชีพลังงาน และเที่ยวที่เดินทางไม่ได้
- ไม่บันทึกข้อมูล ไม่แก้ profile/Neon และไม่เปลี่ยนสูตรหรือผล Heat Map
- ชื่อจังหวัดใน request ใช้เป็นบริบทเท่านั้น ไม่ดึง fleet มาคูณผลรถหนึ่งคันเป็นดีมานด์จังหวัด
- `forecast_available=false` และ `status=assumption_preview_not_calibrated` เสมอ

## ข้อมูลที่ต้องระบุเอง

| กลุ่ม | ช่องข้อมูลและหน่วย |
|---|---|
| รถ | usable battery (kWh), battery kWh/km, initial/reserve SOC (0–1), AC acceptance (kW), DC acceptance bands ตาม SOC |
| เที่ยวรถ | รหัสเที่ยว, เวลาเริ่ม/จบ (ชั่วโมง 0–24), ต้นทาง/ปลายทาง, ระยะทาง (km) |
| การจอด | สถานที่และเวลาจอด, charging opportunity หรือ `null` เมื่อไม่มีโอกาสชาร์จ |
| โอกาสชาร์จ | home/work/public AC/public DC, รหัส charger, AC/DC, connector kW, ประสิทธิภาพรถ/สถานี, trigger/target SOC, เวลาจัดเตรียมก่อนชาร์จ |
| ช่วงจำลอง | จำนวนวันที่วัดผล 1–90 วัน และ warm-up 0–30 วัน |

ไม่มีค่าพฤติกรรมไทยเริ่มต้นแทนข้อมูลที่ขาด ค่าใน unit tests เป็นข้อมูลสังเคราะห์เพื่อพิสูจน์สูตรเท่านั้น ไม่ใช่ profile เชียงใหม่ ไม่ได้สมมติว่า PHEV รองรับ DC

## กติกาทางกายภาพ

1. เที่ยวและการจอดต้องเรียงต่อเนื่อง ไม่ซ้อนหรือเว้นช่วง สถานที่ต้องต่อกัน และ itinerary ที่ทำซ้ำต้องกลับต้นทาง
2. ก่อนออกเดินทาง ต้องมีพลังงานสำหรับทั้งเที่ยวและ reserve ถ้าไม่พอจะไม่เริ่มเที่ยวและหยุด trajectory ไม่มีการแทรก DC ฉุกเฉินหรือให้การชาร์จในอนาคตย้อนกลับมาช่วย
3. SOC ต่อเนื่องข้ามวัน ไม่คืนแบตเตอรี่ให้เต็มทุกเช้า
4. เริ่มชาร์จเมื่อ SOC ต่ำกว่า trigger ไปจนถึง target หรือหมดเวลาจอด เลือกตามลำดับเวลาที่กำหนด ไม่ใช่ optimizer ด้านราคา
5. กำลังจริงถูกจำกัดด้วยทั้งหัวชาร์จและรถ DC ใช้ acceptance bands แบบ piecewise-constant ที่ผู้เรียกส่งมา จึงไม่ถือว่าป้าย 240 kW ทำให้รถทุกคันรับ 240 kW
6. กิจกรรมที่จุดชาร์จเดียวกันและติดกันจริงนับเวลาจัดเตรียมต่อเนื่อง แม้แบ่ง dwell หรือคาบเที่ยงคืน และรวมเป็น charging event เดียวเมื่อชาร์จต่อเนื่อง

```text
traction battery kWh = trip km × battery kWh/km
battery charging kW = min(connector kW, vehicle acceptance kW) × vehicle efficiency
connector kWh = battery charging kWh / vehicle efficiency
grid kWh = connector kWh / station efficiency

start battery + battery charging − traction = end battery
```

`vehicle_efficiency` วัดจาก connector ถึงพลังงานที่เข้าแบตเตอรี่ ส่วน `station_efficiency` วัดจากกริดถึง connector จึงไม่ควรนำการสูญเสียเดียวกันไปใส่สองครั้ง DC acceptance bands ต้องใช้กำลังฝั่ง connector ตามนิยามนี้

## อ่านผลโดยไม่ตีความเกินข้อมูล

- `measurement` ไม่รวมพลังงาน warm-up แต่แสดง battery drawdown เพื่อไม่เข้าใจว่าพลังงานจาก initial SOC เป็น demand ระยะยาว
- `measured_days_simulated` อาจมีวันสุดท้ายที่เดินทางไม่ครบ ต้องอ่าน `all_requested_travel_feasible` และ `failure` ร่วมกัน ห้ามหารเป็น daily forecast โดยไม่ตรวจ
- Charging events ที่ส่งออกครอบคลุมทั้ง warm-up และช่วงวัดผล ส่วนจำนวนเริ่มชาร์จและจำนวน event ที่คาบช่วงวัดผลแยกกัน
- ข้อมูล trace/events ถูกจำกัดขนาดผลลัพธ์ แต่ยอดพลังงานและจำนวน event ใช้การจำลองครบทุกแถว
- สมดุล SOC คงที่สามวันท้ายเป็นเพียง diagnostic ของ itinerary นี้ ไม่พิสูจน์ว่าเป็นอิสระจาก initial SOC (`initial_soc_independence_validated=false`)
- หน่วยพลังงานและจำนวน charging event ของรถหนึ่งคันไม่ใช่จำนวนรถไม่ซ้ำ ไม่ใช่ลูกค้าของสถานีเสนอใหม่ และไม่ใช่ยอดขายสุทธิหลังหักคู่แข่ง

## สิ่งที่ยังต้องหารือก่อนเปิดเป็น forecast

ต้องกำหนด representative travel sample ที่มีแหล่งข้อมูล วันเดินทาง/วันหยุด กลุ่มรถส่วนบุคคล/รับจ้างและรถนอกจังหวัด การเข้าถึง home/work charging, battery/acceptance mix, reserve/target policy และข้อมูลจริงสำหรับตรวจ initial SOC รวมถึง reconcile รถผ่านทางไม่ให้นับซ้ำ

หลังจากนั้นยังต้องเชื่อม station choice, road detour, ราคา, reliability, shared power/queue และทดสอบกับ station-day logs ที่แยกสถานีและช่วงเวลาออกจากชุดปรับโมเดล ตัวจำลองปัจจุบันยังไม่จำลองสิ่งเหล่านี้ และไม่แทนการประเมินกำลังสถานีหลายหัว

ระยะทาง/เวลาเดินทางที่ส่งมายังไม่ได้ตรวจเทียบโครงข่ายถนน และใช้ consumption คงที่ ไม่ได้เปลี่ยนตามความเร็วหรืออากาศ หากต้องการชาร์จระหว่างทางต้องแยกเที่ยวและการจอดชาร์จใน input ไม่ใช่ให้ระบบสร้างจุดพักขึ้นเอง

**ข้อสรุปด้านคะแนน:** เพิ่มความครอบคลุมด้านวิธีคิดได้จริง แต่ยังไม่ให้คะแนนความแม่นยำเพิ่มโดยอาศัย unit tests หากยังใช้เกณฑ์ความพร้อมในการพยากรณ์เชียงใหม่จริง ยังไม่ควรปรับคะแนนจาก 4/10 จนกว่าจะมีตัวอย่างพฤติกรรมที่เป็นตัวแทนและผลตรวจความแม่นยำนอกชุดปรับโมเดล

อัปเดตหลักฐานจากเส้นทางถนน ตัวอย่างครัวเรือน และข้อมูลสถานีจริงใน [pilot เชียงใหม่](chiang_mai_travel_home_ops_evidence.md) แล้ว ส่วนอัตรามี home AC ของเจ้าของ EV แยกตามประเภทที่อยู่อาศัยยังไม่พบตัวเลขที่ยืนยันได้ จึงยังไม่ปรับคะแนนความแม่นยำหรือเปิด forecast

## การตรวจรับ

```powershell
python -m pytest tests/test_travel_soc.py -q
node --test tests/frontend_click_geometry.cjs
node tests/frontend_click_flow.cjs
```

Browser test ต้องมี local server และ Playwright; ตั้ง `PLAYWRIGHT_MODULE`, `CHROMIUM_EXECUTABLE_PATH`, `TH_EVI_BASE_URL` ได้เมื่อ runtime ไม่ได้อยู่ในตำแหน่งมาตรฐาน ทดสอบ cached cell, outside support, context ที่เปลี่ยน, stale response และ popup ที่ปิดแล้ว

ผลตรวจ local รอบนี้: SOC/API ใหม่ผ่าน 43 tests; SOC ร่วมกับ basis API ล่าสุดผ่าน 59 tests; geometry JavaScript ผ่าน 7 tests และ browser click flow ผ่านครบ ชุด regression ที่กว้างขึ้นผ่าน 229 และไม่ผ่าน 1 กรณีเดิม (`test_chiang_mai_poi_loader_excludes_site_specific_noise_categories` คาดว่าไม่มีหมวด hotel) จึงไม่อ้างว่า full suite ผ่านทั้งหมด ไม่แก้หมวดข้อมูลเพียงเพื่อให้ test นี้ผ่าน

ตรวจหน้า `/planning` และ `/analysis` กับข้อมูลจริงแล้วไม่พบ JavaScript page error; grid 0.25/0.5/1/2 กม. ยังคงยอดคะแนนรวม 100% ภายใน floating-point tolerance และ click API ให้ค่าตรงกับ Heat Map ทุกขนาดที่ตรวจ โดยไม่มีการแปลงคะแนนเป็นจำนวนรถ

## หลักการอ้างอิง

- [NREL Regional Charging Infrastructure: individual travel days, dwell และ SOC](https://docs.nlr.gov/docs/fy17osti/67436.pdf)
- [NREL Meeting 2025 ZEV Goals: charging preferences และ power taper](https://docs.nlr.gov/docs/fy19osti/71198.pdf)

อ้างอิงแนวคิดการจำลอง ไม่ได้ใช้ EVI-Pro จริง ไม่คัดลอกสัดส่วนพฤติกรรมสหรัฐฯ เป็นข้อเท็จจริงของไทย และไม่ได้รับรองโดย NREL

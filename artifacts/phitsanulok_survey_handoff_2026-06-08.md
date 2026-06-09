# Phitsanulok Survey Handoff

วันที่จัดทำ: 2026-06-08  
วัตถุประสงค์: เตรียมรายการ `POI` และ `competitor` สำหรับทีม survey ที่ลงพื้นที่พิษณุโลกวันนี้ โดยแยกให้ชัดว่าอะไร `ยืนยันได้ค่อนข้างดีแล้ว` และอะไร `ยังต้องเช็กหน้างาน`

## สรุปสั้น

- ข้อมูล `POI` ของพิษณุโลกฝั่งแกนเมืองหลักค่อนข้างพร้อมแล้ว โดยเฉพาะ `Central`, `สนามบิน`, `Naresuan University`, `Bangkok Hospital`, และ `Wat Yai`
- ข้อมูล `competitor` ที่พร้อมใช้เชิงโมเดลมากที่สุดตอนนี้คือสถานีที่มี `named public listing` ชัด เช่น `PTT Charging Station`, `EleX by EGAT`, `SHARGE`, `MG Super Charge`
- ไฟล์จาก LLM agent บน Desktop มีประโยชน์ในฐานะ `audit-target expansion list` แต่ยังไม่ควรโหลดเข้าชั้น competition ของโมเดลตรง ๆ ทั้งก้อน เพราะหลายจุดยังเป็น `approximate pin / network-level placeholder`

## ระดับความเชื่อมั่นที่ใช้ใน handoff นี้

- `Confirmed anchor`: มีแหล่งทางการหรือแหล่งสาธารณะชัด และพิกัด/ที่อยู่ใช้ลงพื้นที่ได้
- `Named public station`: เป็นสถานีชาร์จที่มีชื่อเฉพาะและมีหน้ารายการสถานีชัด ใช้ลงพื้นที่ได้ แต่ยังควรเช็ก port mix/kW หน้างาน
- `Survey confirm`: มีเหตุผลทางธุรกิจดี แต่พิกัดหรือสถานะยังต้องเช็กหน้างานก่อนใช้เชิงโมเดลเต็ม
- `Do not import yet`: ใช้เป็น watchlist ของทีม survey เท่านั้น ยังไม่ควรดันเข้า competition layer

## POI ที่ควรยืนยันวันนี้

### กลุ่ม A: Confirmed anchor

1. `Central Phitsanulok`
   - ระบบ: `central_phitsanulok`
   - พิกัดใช้งาน: `16.8407, 100.2332`
   - เหตุผล: retail anchor สำคัญสุดของเมือง
   - สิ่งที่ให้ทีมเช็ก: frontage, ทางเข้า-ออก, ที่จอด, dwell-time, สภาพ EV-friendly
   - แหล่ง: Central Pattana ระบุโครงการอยู่บน `Singwat (Highway 12), Plai Chumpol, Muang, Phitsanulok`
   - ลิงก์: https://www.centralpattana.co.th/en/our-business/shopping-center/386/central-phitsanulok

2. `Phitsanulok Airport`
   - ระบบ: `phitsanulok_airport`
   - พิกัดใช้งาน: `16.782933, 100.279125`
   - เหตุผล: airport catchment, rental car, receiver traffic
   - สิ่งที่ให้ทีมเช็ก: pickup/dropoff flow, taxi/ride-hailing frontage, พื้นที่จอดรอ
   - แหล่ง: Department of Airports ระบุ `Aranyik Subdistrict, Mueang Phitsanulok District`
   - ลิงก์: https://www.airports.go.th/backend/uploads/files/309fdf1b73677c8efe55d34b17a384a4.pdf

3. `Naresuan University`
   - ระบบ: `naresuan_university`
   - พิกัดใช้งาน: `16.7406, 100.1880`
   - เหตุผล: education anchor ใหญ่และมี daily recurring demand
   - สิ่งที่ให้ทีมเช็ก: ประตูหลัก, visitor parking, retail frontage รอบมหาวิทยาลัย
   - แหล่ง: NU official contact page ระบุ `99 Moo 9, Thapo Sub-district, Muang District, Phitsanulok`
   - ลิงก์: https://english.nu.ac.th/?page_id=2871

4. `Bangkok Hospital Phitsanulok`
   - ระบบ: `bangkok_hospital_phitsanulok`
   - พิกัดใช้งาน: `16.8089, 100.3048`
   - เหตุผล: private hospital anchor ฝั่งเมืองตะวันออก
   - สิ่งที่ให้ทีมเช็ก: ทางเข้า, จอดรถคนไข้, ร้านค้า/ร้านอาหารรอบรั้ว
   - แหล่ง: official contact page ระบุ `138 ถนนพระองค์ดำ ตำบลในเมือง อำเภอเมือง จังหวัดพิษณุโลก 65000`
   - ลิงก์: https://www.bangkokhospitalphitsanulok.com/contact-us/

5. `Wat Phra Si Rattana Mahathat (Wat Yai)`
   - ระบบ: `wat_yai_phitsanulok`
   - พิกัดใช้งาน: `16.823572, 100.262789`
   - เหตุผล: heritage/tourism anchor ของ core เมืองเก่า
   - สิ่งที่ให้ทีมเช็ก: parking behavior, tour bus, market frontage รอบวัด
   - แหล่ง: Tourism Authority of Thailand
   - ลิงก์: https://www.tourismthailand.org/Articles/phitsanulok-your-gateway-to-great-shopping

### กลุ่ม B: Survey confirm

6. `Phitsanulok Bus Terminal 2`
   - ระบบ: `phitsanulok_bus_terminal_2`
   - พิกัดใช้งาน: `16.81266, 100.33007`
   - หมายเหตุ: พิกัดในระบบตรงกับหลาย travel directory ค่อนข้างดี (`16.812717, 100.330068`) แต่ยังไม่ใช่แหล่งทางการตรง
   - สิ่งที่ให้ทีมเช็ก: ที่ตั้งป้าย/อาคารหลัก, จุดจอดรถโดยสารจริง, ร้านค้าและเวลาคึก

7. `Buddhachinaraj Phitsanulok Hospital`
   - ระบบ: `buddhachinaraj_hospital`
   - พิกัดใช้งาน: `16.808436, 100.263549`
   - หมายเหตุ: ใช้ต่อได้ แต่ควรยืนยัน frontage กับจุดจอดจริงอีกที
   - อ้างอิงที่อยู่ที่พบ: `90 Srithammatraipidok Road, Nai Mueang`
   - สิ่งที่ให้ทีมเช็ก: พื้นที่จอด, อาคาร OPD/IPD, ร้านสะดวกซื้อ/ร้านกาแฟรอบหน้าโรงพยาบาล

8. `Big C Supercenter Phitsanulok`
   - ระบบ: `big_c_phitsanulok`
   - พิกัดใช้งาน: `16.81581, 100.28966`
   - หมายเหตุ: เป็น retail anchor สำคัญ แต่วันนี้ให้ทีมเช็กตำแหน่ง frontage และความคึกจริงเพื่อใช้ fine-tune

9. `Makro Phitsanulok`
   - ระบบ: `makro_phitsanulok`
   - พิกัดใช้งาน: `16.79381, 100.23196`
   - หมายเหตุ: เหมาะเป็น wholesale/service trip anchor, ควรเช็กการใช้งานช่วงเช้า-สาย

10. `Thai Watsadu Phitsanulok`
    - ระบบ: `thai_watsadu_phitsanulok`
    - พิกัดใช้งาน: `16.8458, 100.3447`
    - หมายเหตุ: ฝั่ง Samo Khae / bypass growth น่าสนใจ แต่เป็นจุดที่ควรเช็ก frontage จริงหน้างาน

## Competitor ที่ควรยืนยันวันนี้

### กลุ่ม A: Named public station

1. `PTT Charging Station (Wat Chan)`
   - ระบบ: `ptt_charging_station_phitsanulok`
   - พิกัดใช้งาน: `16.8044707, 100.2449184`
   - เหตุผล: เป็น competitor ฝั่งเมืองชั้นในที่สำคัญ
   - สิ่งที่ให้ทีมเช็ก: จำนวนหัวชาร์จ, kW, เวลาทำการ, ป้าย network จริง, รูปหัวชาร์จ
   - แหล่ง: SpotMyCharge ระบุ `171 Thanon Borom Trailokkanat, Nai Mueang`
   - ลิงก์: https://www.spotmycharge.com/charging-station/ptt-station-ev-phitsanulok-1

2. `PTT Charging Station - Phitsanulok-2`
   - ระบบ: `ptt_charging_station_phitsanulok_2`
   - พิกัดใช้งาน: `16.8697625, 100.2093594`
   - เหตุผล: competitor สำคัญฝั่ง Singhawat / Ban Krang / northwest approach
   - แหล่ง: SpotMyCharge ระบุ `V695+WP5, Singhawat Rd, Tambon Ban Krang`
   - ลิงก์: https://www.spotmycharge.com/charging-station/ptt-charging-station-phitsanulok-2

3. `PTT Charging Station - Phitsanulok-3`
   - ระบบ: `ptt_charging_station_phitsanulok_3`
   - พิกัดใช้งาน: `16.8283375, 100.4145781`
   - เหตุผล: east gateway / Wang Thong competitor
   - แหล่ง: SpotMyCharge ระบุ `RCH7+8RP Mittraphap Road Tambon Wang Thong`
   - ลิงก์: https://www.spotmycharge.com/charging-station/ptt-charging-station-phitsanulok-3

4. `EleX by EGAT Charging Station`
   - ระบบ: `elexa_tha_pho`
   - พิกัดใช้งาน: `16.7594625, 100.1897656`
   - เหตุผล: competitor สำคัญฝั่ง Tha Pho / Naresuan University cluster
   - แหล่ง: SpotMyCharge ระบุ `Q55Q+QWJ, Tha Pho`
   - ลิงก์: https://www.spotmycharge.com/charging-station/elex-by-egat-charging-station-phitsanulok

5. `SHARGE Charging Station`
   - ระบบ: `sharge_phitsanulok`
   - พิกัดใช้งาน: `16.8260875, 100.2686719`
   - เหตุผล: competitor สำคัญฝั่ง old city / inner core
   - แหล่ง: SpotMyCharge ระบุ `R7G9+CFM, Phaya Suea Rd, Tambon Nai Mueang`
   - ลิงก์: https://www.spotmycharge.com/charging-station/sharge-charging-station-phitsanulok

6. `MG Super Charge Charging Station`
   - ระบบ: `mg_supercharge_city`
   - พิกัดใช้งาน: `16.8060, 100.2720`
   - เหตุผล: competitor ฝั่ง inner city / hospital side
   - แหล่ง: SpotMyCharge ระบุ `36 2, Amphoe Mueang Phitsanulok`
   - ลิงก์: https://www.spotmycharge.com/charging-station/mg-super-charge-charging-station-phitsanulok

### กลุ่ม B: Audit target จากไฟล์ LLM agent (ยังไม่ควร import เข้าระบบตรง ๆ)

1. `PEA VOLTA - PEA Phitsanulok Head Office`
   - จากไฟล์ Desktop
   - พิกัดเบื้องต้น: `16.823, 100.261`
   - สถานะ: `Do not import yet`
   - เหตุผล: เป็น approximate pin ใกล้ core เมืองเกินไป และยังไม่มี named public-station page ระดับเดียวกับกลุ่มด้านบน
   - สิ่งที่ให้ทีมเช็ก: มี charger จริงหรือไม่, public access หรือเฉพาะองค์กร

2. `EV Station PluZ - PTT Station Highway 11 / bypass / Naresuan area`
   - จากไฟล์ Desktop หลาย record
   - สถานะ: `Do not import yet`
   - เหตุผล: ใช้ได้เป็น watchlist แต่ยังซ้ำ/ทับกับ PTT named station ใน detailed file

3. `EA Anywhere / EVolt / Rever Sharger`
   - จากไฟล์ Desktop
   - สถานะ: `Do not import yet`
   - เหตุผล: เป็น network-level placeholder มากกว่าสถานีที่ยืนยันแล้ว
   - สิ่งที่ให้ทีมเช็ก: มีป้าย/หัวชาร์จจริงหรือไม่, อยู่ใน dealer หรือ public site, kW เท่าไร

## คำแนะนำให้ทีม survey เก็บอะไรบ้าง

### POI

- รูป frontage และทางเข้าออก
- ขนาดลานจอดโดยคร่าว
- ลักษณะคนใช้: retail / hospital / student / traveler / tourist
- ช่วงเวลาคึกโดยประมาณ
- ร้านค้า/คาเฟ่/บริการรอบจุด

### Competitor

- รูปป้ายสถานีและหัวชาร์จ
- network/operator จริงที่หน้าสถานี
- จำนวนหัวชาร์จและหัวแบบไหน
- กำลังชาร์จสูงสุดที่เห็นหน้างาน
- เวลาทำการ / เข้าถึง 24 ชม. หรือไม่
- อยู่ในปั๊ม / dealer / ห้าง / โรงพยาบาล / มหาวิทยาลัย

## ข้อเสนอเชิงโมเดล

- ให้คง `competitors_phitsanulok_detailed.csv` เป็นฐาน competition หลักต่อไป
- ใช้ไฟล์ Desktop เป็น `survey expansion list` ไม่ใช่ production competitor list ในทันที
- หลังทีม survey กลับมา ค่อย promote เฉพาะจุดที่ยืนยันแล้วเข้า DB ด้วย `verification_status` ที่เข้มขึ้น

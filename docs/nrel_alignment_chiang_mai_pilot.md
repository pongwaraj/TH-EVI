# Chiang Mai pilot: ปรับหลักการ TH-EVI เทียบกับ NREL EVI-X

ทบทวนโค้ด ณ 17 ตุลาคม 2569 เริ่มจากเชียงใหม่ ใช้โครงสร้างเดียวกันทุกจังหวัด

อัปเดตรอบถัดมา: เชื่อม fixed-support screening กับ Heat Map/Click API สำหรับเชียงใหม่และเพิ่ม DC competition evidence แล้ว ดู [รายละเอียด pilot และข้อจำกัดปัจจุบัน](chiang_mai_fixed_support_pilot.md) เนื้อหาด้านล่างบันทึกการตรวจและงานฐานคำนวณก่อนเชื่อม pilot

อัปเดตข้อ 4: เพิ่ม [ตัวจำลอง itinerary/SOC แบบระบุ input ชัดเจน](travel_soc_preview.md) สำหรับทดสอบหลักการแล้ว ยังไม่เชื่อมเป็น forecast เชียงใหม่และไม่ปรับสมมติฐานพฤติกรรมโดยไม่มีหลักฐาน

อัปเดตหลักฐาน: เพิ่ม [เส้นทางถนน ตัวแทนครัวเรือน log สถานี และการทดสอบเดือนกันยายน](chiang_mai_travel_home_ops_evidence.md) พร้อม evidence-preview ที่ทำ sensitivity แบบระบุสมมติฐาน ผล holdout ยืนยันเฉพาะค่า kWh ต่อรายการที่ Meta Mall ยังไม่ยืนยันการเลือกสถานีหรือจำนวนลูกค้าเชียงใหม่

## 1. ข้อสรุป

TH-EVI มีองค์ประกอบช่วยคัดกรองทำเลหลายด้าน แต่ยังไม่เทียบเท่า EVI-Pro ในการจำลองความต้องการชาร์จจากการเดินทางจริง ตัวเลขที่จุดหนึ่งบน Heat Map ยังไม่ใช่จำนวนลูกค้าที่สถานีนั้นจะได้รับ และไม่ควรบวกรวมจุดทั้งหมดเป็นดีมานด์จังหวัด

การปรับครั้งนี้เริ่มแก้ที่ฐานพลังงานและสัญญาข้อมูล ไม่เพิ่มดีมานด์เพื่อให้ผลตอบแทนดูดีขึ้น และไม่ใช้ความเห็นว่าเชียงใหม่ควร Hot ตรงไหนเป็นข้อมูลสำหรับสอบเทียบ โมเดลต้องยอมให้ผลสูงหรือต่ำกว่าความคาดหมายได้เมื่อมีหลักฐานรองรับ

แนวทาง NREL ไม่ใช่สูตรเดียว EVI-Pro เน้นการเดินทางประจำวัน ส่วนการเดินทางไกลและรถรับจ้างมี EVI-RoadTrip และ EVI-OnDemand แยกหน้าที่ จึงต้องเทียบทั้งสายงาน ไม่ใช่เฉพาะ S-curve การเพิ่มจำนวน EV หรือแผนที่ POI

## 2. ช่องว่างที่ตรวจพบจากเส้นทางคำนวณจริง

| ประเด็น | TH-EVI ปัจจุบัน | สิ่งที่ยังขาดและผลกระทบ | แนวทางแก้ร่วมทุกจังหวัด |
|---|---|---|---|
| จำนวนรถฐาน | `adoption.py` มี S-curve และ fleet anchor เชียงใหม่ ข้อมูล DLT ล่าสุดมีใน `data.py` | รถจดทะเบียนไม่ใช่รถที่อยู่ในพื้นที่ ณ วันนั้น และจำนวนที่อ่านมาใหม่ไม่ใช่การพยากรณ์อนาคตโดยอัตโนมัติ | แยก observed stock ตามเดือน/ประเภทรถ ออกจาก adoption forecast และรถเดินทางเข้าพื้นที่ |
| ประเภทรถ | การคำนวณใช้ passenger BEV เป็นหลัก | PHEV ไม่ควรสมมติว่าใช้ DC ได้ และรถรับจ้าง/รถส่วนบุคคลมีการใช้งานต่างกัน | ระบุขอบเขตรถและ charging compatibility ให้ชัด แบ่ง cohort ไม่ซ้ำกัน |
| พลังงานจากการเดินทาง | `LocationDemandModel` ใช้ AADT × BEV share × charge probability ตามประเภททำเล | ไม่มี daily travel distance และ consumption เชื่อมกับการชาร์จจริง ความน่าจะเป็นคงที่แทนความต้องการพลังงาน | เริ่มจาก vehicle-days × km/day × battery kWh/km แล้วตรวจการอนุรักษ์พลังงาน |
| บ้านและที่ทำงาน | มี constants แต่ไม่ได้หักความต้องการในเส้นทาง Heat Map หลัก | ผู้มีที่ชาร์จบ้านกับผู้ไม่มีถูกแทนด้วยค่าเดียว ความต้องการ DC อาจสูงหรือต่ำเกินจริง | แบ่งกลุ่มตาม access, dwell time, effective power และพฤติกรรมการเลือกชาร์จ |
| ลำดับเที่ยวและ SOC | ยังไม่มี itinerary/SOC simulator ในเส้นทางหลัก | ยอดพลังงานทั้งวันเพียงพอไม่ได้แปลว่ารถไปถึงปลายทางก่อนชาร์จได้ และรถบางคันไม่ชาร์จทุกวัน | จำลอง trip start/end, location, battery capacity, SOC และ reserve หลายวันเพื่อไม่บิดผลจาก initial SOC |
| ชาร์จเร็วเพราะความสะดวก | probability ตามทำเล ไม่ใช่ revealed preference | วิธี home-first อย่างเดียวอาจประเมินผู้เลือก DC แม้ชาร์จบ้านได้ต่ำเกินไป | สำรวจ/fit preference cohort จากข้อมูลไทย ไม่คัดลอกสัดส่วนสหรัฐฯ มาใช้เป็นข้อเท็จจริง |
| รถผ่านทางและนับซ้ำ | มี `demand_streams.py` แต่ยังไม่เป็นบัญชีพลังงานเดียวกับ Heat Map; overlap discount คงที่ | รถคนเดียวอาจถูกนับทั้ง resident, POI, corridor, ride-hailing หรือหลายจุดนับรถ | แยก resident/nonresident และ trip purpose ด้วย OD หรือกติกา reconciliation ที่ตรวจสอบได้ |
| AADT | highway lookup ใช้ตัวแทนถนน/กรอบพื้นที่ มี fallback นอกทางหลวง | AADT เป็นรถผ่านจุดนับ ไม่ใช่ unique EV และไม่ใช่ผู้ซื้อการชาร์จ ไม่มีทิศทาง/ทางเข้า/ระยะอ้อมจริงครบ | ผูกจุดนับกับ road segment, ปีข้อมูล, ทิศทาง, vehicle class และ OD; ไม่ใช้ AADT เป็นยอดลูกค้าโดยตรง |
| POI/ประชากร | `compose_area_demand` ผสม POI/zone/business/district เป็น sessions | ปัจจัยที่อาจแทนคนกลุ่มเดียวกันถูกบวกเป็นดีมานด์ใหม่; Heat Map ใช้ `supportive_context_sessions` ไม่ใช่ส่วน spatial boost ที่ลด overlap แล้ว | ให้ POI/DOPA เป็นตัวจัดสรรงบพลังงานและอธิบายปลายทาง ไม่สร้างพลังงานเพิ่มเอง |
| หน่วยและความละเอียด Heat Map | `generate_province_heatmap` คำนวณคะแนนแต่ละจุดอิสระ และมี `score_semantics` เตือนแล้ว | จำนวนจุดมากขึ้นเมื่อย่อ grid; ผลรวมคะแนนจึงเปลี่ยน ไม่ใช่ยอดขายของ pixel | คำนวณบน fixed spatial support แล้ว aggregate สำหรับแสดงผล; ไม่คำนวณดีมานด์ใหม่ทุก display pixel |
| gross / net / capture | click ใช้ gross จากองค์ประกอบพื้นที่ แล้วหัก penalty; หักได้ไม่เกิน 62% | คู่แข่งไม่ใช่ยอดขายที่ยืนยันแล้ว เพดานหักทำให้พื้นที่อิ่มตัวอาจยังดูมีโอกาส; ผลไม่เท่ากับ Heat Map | แยก area energy, allocations ไปสถานีเดิม, outside/unserved และ capture ของสถานีเสนอใหม่อย่างชัดเจน |
| คุณภาพ competitor | `spatial.py` มี distance/power/guns/status/confidence | เมื่อไม่ทราบกำลัง/หัว มี fallback 120 kW/2 หัว; ไม่มี choice model ที่แยก AC/DC, detour, price, queue, reliability ครบ | เก็บ unknown เป็น unknown พร้อม sensitivity; ใช้ประเภทและเวลาชาร์จจริง ไม่ถือ low-power DC เท่ากับ high-power DC |
| กำลังและคิว | `site.py` มี service ceiling; `temporal.py` มี hourly templates/Erlang-C | ยังไม่เชื่อม arrival, vehicle acceptance, SOC taper, power sharing และ uptime กับการเลือกสถานีในพื้นที่เดียวกัน | เริ่มจาก charger/vehicle compatibility และ load profile ก่อนประเมิน queue, balking และ service level |
| สอบเทียบ | validation แยก adoption กับ station และระบุข้อจำกัดเมื่อข้อมูลน้อย | station ground truth ปัจจุบันมีหนึ่งตัวอย่างหลัก; ตัวคูณระดับ station ไม่ใช่การ validate Heat Map รายจุด | เก็บ dated station-day logs; แยก train/test ตามสถานีและเวลา รายงาน bias/MAE/WAPE รวมทั้ง kWh และ sessions |
| ความไม่แน่นอน | มี scenario multiplier และ confidence จากหลักฐานเชิงพื้นที่ | ไม่ใช่ prediction interval และไม่ทราบ error เฉพาะจุด; POI ครบไม่ได้แปลว่าดีมานด์แม่น | ทำ sensitivity ของ input มีหลักฐาน ใช้ช่วงคาดการณ์หลัง backtest และไม่เรียก data confidence ว่าความแม่นยำ |
| การเงิน | รายงานคูณ sessions × kWh/session และคิดต้นทุน | ยอดพื้นที่อาจถูกใช้แทนยอดสถานี; kWh ที่ขายไม่ใช่ kWh ที่ซื้อจากกริด; session ไม่จำเป็นต้องเป็นรถไม่ซ้ำ | ส่งออก station-served connector kWh ก่อน ค่อยคำนวณค่าไฟจาก grid kWh และแยก CAPEX/operating cash flow |

อีกจุดหนึ่งใน `LocationDemandModel.estimate` คือ `charging_sessions_per_day` ใช้ขั้นต่ำ 1 แม้ `daily_ev_visits` เป็น 0 แกนใหม่ต้องอนุญาตศูนย์จริง แต่ครั้งนี้ยังไม่เปลี่ยนสัญญาของ endpoint เดิมโดยไม่ตรวจผลต่อผู้เรียกใช้

## 3. สิ่งที่ลงมือทำในรอบนี้

### 3.1 บัญชีพลังงานร่วมทุกจังหวัด

เพิ่ม `th_evi/charging_energy.py` ไม่มีชื่อจังหวัดหรือค่า behavior ของเชียงใหม่ฝังในสูตร

สำหรับ cohort แต่ละกลุ่ม:

```text
active vehicles = observed BEV fleet × fleet share × active-day share
traction battery kWh/day = active vehicles × daily km × battery kWh/km
available battery energy per vehicle = effective input kW × dwell hours × efficiency × use fraction

traction battery energy = home + work + public AC + residual public DC
DC connector kWh = DC battery kWh / vehicle-side DC efficiency
DC grid kWh = DC connector kWh / station efficiency
DC session equivalents = DC connector kWh / average connector kWh per session
```

- `fleet_share` ต้องรวมเป็น 1 กลุ่มต่าง ๆ จึงแบ่งรถฐานชุดเดียว ไม่บวกรถซ้ำ
- การเข้าถึง charger ให้แบ่ง cohort ไม่ใช้ home-access fraction เป็นการลดกำลังไฟของรถทุกคัน
- หน้าต่างชาร์จทั้งหมดต้องไม่เกิน 24 ชั่วโมง แต่ยังไม่ได้พิสูจน์ลำดับเวลาหรือความเป็นไปได้ของเที่ยวรถ
- การจัดสรรตามลำดับ home/work/public AC/DC เป็น baseline ที่ระบุชัด ไม่ใช่สมมติฐานว่า EV ไทยทุกคนเลือกแบบนี้ ผู้เลือก DC แม้ชาร์จบ้านได้ต้องมี cohort และหลักฐานแยก
- `use_fraction` เป็นส่วนเวลาชาร์จที่เลือกใช้ใน representative day ไม่ใช่สัดส่วนคนเข้าถึงที่ชาร์จ
- ไม่มีค่าเริ่มต้นระยะทาง สัดส่วนชาร์จบ้าน พลังงานต่อครั้ง หรือประสิทธิภาพที่ถือว่าเป็นข้อเท็จจริงของเชียงใหม่
- ค่าที่ส่งเข้าโมเดลยังเป็น daily aggregate ไม่ใช่ NREL EVI-Pro simulator และไม่รับประกันว่าไม่ต้องชาร์จระหว่างเที่ยว

### 3.2 การจัดสรรที่ไม่สร้างดีมานด์ใหม่

เพิ่ม `allocate_energy_budget` รับงบ kWh ที่กำหนดไว้แล้ว น้ำหนักปลายทาง coverage fraction และ optional capacity

```text
input kWh = served allocations + capacity-unserved kWh + outside-coverage kWh
```

เพิ่ม POI หรือคูณน้ำหนักทุกจุดด้วยค่าคงที่ต้องไม่เพิ่มงบจังหวัด ส่วนที่เกินกำลังรับยังเป็น unserved ไม่โยนให้โครงการเราอัตโนมัติ ไม่มี capacity input จะระบุชัดว่าไม่ได้ enforce capacity นี่เป็นตัวจัดสรรพื้นฐาน ยังไม่ใช่ station-choice model

ยังไม่ได้สร้าง fixed grid/road network หรือเชื่อม allocator เข้ากับ Heat Map เดิม การทดสอบ conservation ในโมดูลนี้ไม่ใช่หลักฐานว่า Heat Map เดิมอนุรักษ์พลังงานแล้ว

### 3.3 สถานะข้อมูลและ sandbox คำนวณ

- `data/charging_behavior_profiles.json`: เปิด profile เฉพาะเชียงใหม่ ข้อมูล behavior ที่ยังไม่มีหลักฐานเป็น `null`/รายการว่าง ไม่มีการคัดลอกค่าเชียงใหม่ให้จังหวัดอื่น
- `GET /api/charging-demand/basis?province=Chiang%20Mai`: แสดง DLT source month/vehicle segment และข้อมูลที่ยังขาด ไม่แสดงค่าพยากรณ์ที่แต่งขึ้น
- `POST /api/charging-demand/preview`: คำนวณจาก assumptions ที่ระบุครบกับ DLT passenger-car BEV ของจังหวัดนั้นโดยตรง ถ้าไม่พบ DLT ให้ error แทนการใช้ fleet จังหวัดอื่น
- Preview เป็น `assumption_preview_not_calibrated` ไม่บันทึกข้อมูล ไม่ publish และไม่เปลี่ยน Heat Map
- Heat Map metadata ระบุ `production_method=legacy_spatial_screening` และ `energy_budget_enforced=false` เพิ่มเติมจาก score semantics เดิม

`inputs_supplied` ใน basis หมายถึงมี input และ evidence fields ส่งมา ไม่ใช่การรับรองหลักฐานหรืออนุมัติใช้งานจริง มีการตรวจสูตรและประเภทข้อมูลก่อนถึงสถานะนี้ แต่ผู้ตรวจยังต้องตรวจคุณภาพแหล่งอ้างอิง

## 4. ข้อมูลเชียงใหม่ที่ต้องเติมก่อนใช้โมเดลใหม่แทนของเดิม

| ชุดข้อมูล | สิ่งที่ต้องเก็บ | หลักฐาน/เหตุผล |
|---|---|---|
| DLT ฐานรถ | เดือนอ้างอิง ประเภทรถ เชื้อเพลิง จำนวนรถทั้งหมด/BEV/PHEV และนิยามขอบเขต | ใช้ snapshot เดียวกันทั้งตัวตั้ง/ตัวหาร ไม่แปลง PHEV เป็น DC demand อัตโนมัติ |
| พฤติกรรมเดินทาง | km/วัน, active days, กลุ่มผู้ใช้, weekday/weekend, เวลาเริ่ม/จบเที่ยว, ต้นทาง/ปลายทาง, รถทะเบียนนอกจังหวัด | แยก resident demand ออกจาก incoming travel; ไม่ใช้ DOPA แทนจำนวน EV โดยตรง |
| การเข้าถึงการชาร์จ | home/work/public AC access, dwell, power จริง, การเลือกใช้ DC แม้มีทางเลือกอื่น | แบ่ง cohort พร้อม sample size, วันที่สำรวจ และวิธีถ่วงน้ำหนัก |
| คุณสมบัติรถ | model mix, battery usable kWh, consumption, connector, acceptance curve/SOC, อุณหภูมิ/เส้นทาง | ให้กำลังตู้และเวลาชาร์จสัมพันธ์กับรถ ไม่ใช้ nameplate เป็นกำลังรับจริงทุกคัน |
| ถนนและ AADT | จุด/ช่วงนับรถ ปีข้อมูล ทิศทาง class ของรถ ทางเข้า/กลับรถ ระยะอ้อม เวลาเดินทาง | นับรถผ่านซ้ำหลายจุดได้ ต้องมี OD/reconciliation ก่อนรวมเข้ากับ resident demand |
| POI | ร้านเปิดจริง เวลาเปิด ที่จอด/รถเข้า dwell จุดทางเข้า เส้นทางเดินถึงร้าน ไม่ใช้ชื่อหมวดอย่างเดียว | ให้น้ำหนักตามพฤติกรรมแวะ ไม่ให้ POI สร้างลูกค้าใหม่ลอย ๆ |
| Competitors | พิกัดเข้าจอด AC/DC power sharing จำนวนช่องใช้พร้อมกัน ราคา เวลาเปิด สถานะจริง uptime คิว/การใช้งาน | แยกมีสถานีอยู่จากขายไฟได้จริง; เก็บ verification date/source ทุกแถว |
| Station logs | วันที่ sessions, connector kWh, start/end time, downtime, price/promotion, จำนวนหัวพร้อมใช้ | สำหรับ calibration และ holdout ไม่ใช้ยอดพยากรณ์จาก proposal เป็น ground truth |
| การเชื่อมกริด | site power limit, transformer, availability, station losses | ประเมิน served energy ไม่ใช่ demand ทั้งหมดจะขายได้เสมอ |

หลักฐานใน profile ควรเก็บ `source_url` หรือเอกสารต้นทาง, `observed_from/to`, `retrieved_at`, `sample_size`, `population_scope`, `method`, `reviewer` และข้อจำกัด โดย version เดียวกันต้องใช้ได้จาก local/Vercel/DB ภายหลัง ขั้นนี้ยังเป็น JSON registry ใน Git ไม่ได้เพิ่มหรือ migrate ตาราง Neon

ข้อมูลที่มีในเครื่องเป็น DLT รย.1 ล่าสุดกันยายน 2569 สำหรับเชียงใหม่ 17,002 BEV เป็นฐาน reference-day ของ preview ไม่ใช่รถ EV ทุกประเภท ไม่ใช่จำนวนรถที่ใช้งานพร้อมกัน และไม่ใช่จำนวนลูกค้า DC

ไม่ตั้งค่า 35 kWh/ครั้งเป็นข้อเท็จจริงโดยอัตโนมัติ หากใช้ในการนำเสนอต้องระบุเป็น assumption จนมี session logs รองรับ และไม่แทนคำว่า session ด้วยรถไม่ซ้ำโดยไม่มีข้อมูลเชื่อม

## 5. ลำดับงานและเกณฑ์เปิดใช้งาน

### ขั้น 1: ฐานคำนวณและตรวจความพร้อม (รอบนี้)

ส่งมอบ energy balance, normalized allocator, Chiang Mai missing-input registry, diagnostic/preview API และ unit/API tests ทดสอบอนุรักษ์พลังงาน ช่วงค่า inputs การแบ่ง cohort ประสิทธิภาพ หน่วย outside option และไม่ fallback ข้ามจังหวัด

ยังใช้ Heat Map เดิมสำหรับ screening และไม่รับรองความแม่นยำของ site forecast

### ขั้น 2: เติมหลักฐานและ representative travel/SOC เชียงใหม่

สร้าง sample ที่มี home/work access, daily travel และ vehicle mix จากข้อมูลมีหลักฐาน แยก weekend/weekday และรถรับจ้าง ตรวจ SOC feasibility และพฤติกรรมไม่ชาร์จทุกวัน เปรียบเทียบ home-first กับ preference cohorts โดยไม่ใช้ค่าพฤติกรรมสหรัฐฯ เป็นค่าไทย

เกณฑ์ผ่าน: input มีขอบเขต/วันที่/แหล่งอ้างอิงครบ; energy balance ปิด; แยก observed กับ assumed; แสดง unmet travel และผลไวต่อสมมติฐานได้

### ขั้น 3: จัดสรรเชิงพื้นที่และการแข่งขัน

สร้าง fixed spatial support และ road access เชื่อม OD/AADT ที่ไม่ซ้ำกับ resident fleet ใช้ POI เพื่อจัดสรร destination และ demand choice ไปสถานีเดิม/ใหม่/outside option รวม capacity/price/queue/reliability ให้ Heat Map, click และ report เรียกผลชุดเดียวกัน

เกณฑ์ผ่าน: display resolution ไม่เพิ่มยอดรวม; gross = allocations + outside/unserved ตามนิยามเดียวกัน; AC/low-power DC ไม่เป็นคู่แข่ง DC กำลังสูงแบบอัตโนมัติ; การเพิ่มหัวชาร์จไม่สร้าง traction energy

### ขั้น 4: สอบเทียบและเปิดใช้เป็น forecast

ขอ logs หลายสถานี หลายประเภทพื้นที่ และช่วงเวลาต่อเนื่อง แยกสถานี/ช่วงเวลาที่ไม่ใช้ฝึกโมเดล วัด sessions และ kWh พร้อมรายงาน signed bias, MAE และ WAPE; ใช้ MAPE อย่างระวังเมื่อยอดจริงใกล้ศูนย์ ห้ามรายงาน in-sample fit ว่าเป็น site forecast accuracy

เกณฑ์ยอมรับความคลาดเคลื่อนต้องกำหนดก่อนปรับโมเดลจากเป้าหมายธุรกิจและข้อผิดพลาดของ baseline ไม่กำหนดคะแนนความแม่นยำล่วงหน้าโดยไม่มีผลทดสอบ

เมื่อผ่านจึงเปลี่ยน production engine ด้วย method/data version และ release manifest ที่รวม behavior, spatial inputs และ observed validation version; เก็บ legacy view สำหรับเทียบและ rollback ไม่เปลี่ยนข้อมูลจังหวัดอื่นใน pilot นี้

## 6. ขอบเขตที่ยังไม่ใช่การส่งมอบรอบนี้

ยังไม่ได้เปลี่ยน logic competitor เดิม, AADT snapping, adoption forecast ทุกจังหวัด, site report/การเงิน, frontend daily kWh, ฐานข้อมูล behavior หรือการควบคุมสิทธิ์ admin; ไม่ได้ commit/push/deploy การแก้ครั้งนี้โดยอัตโนมัติ

การทดสอบชุดใหม่พิสูจน์กติกาทางคณิตศาสตร์และ API ไม่ใช่ความแม่นยำเชิงสถิติของเชียงใหม่ และไม่ได้แก้ baseline test failures ที่พบในการ audit ก่อนหน้า

ผลตรวจรอบนี้: ชุดทดสอบใหม่ร่วมกับ adoption/data/location/demand streams/site/temporal/validation และ Heat Map metadata ที่เกี่ยวข้อง **85 tests ผ่าน** มีหนึ่ง dependency deprecation warning ไม่ได้รัน full suite ซ้ำ; local `/planning` และ basis endpoint ตอบ HTTP 200

## 7. แหล่งอ้างอิงหลัก

- [NREL/NLR EVI-Pro: ข้อมูลการเดินทาง คุณสมบัติรถ และสถานี รวมความแตกต่างของพฤติกรรม](https://nrel.sitefinity.cloud/transportation/evi-pro)
- [NREL EVI-X: แยก network planning, site design และ financial analysis; รวม EVI-OnDemand/RoadTrip](https://www.nrel.gov/transportation/evi-x.html)
- [Regional Charging Infrastructure for Plug-In Electric Vehicles: individual travel days, dwell, charging options และ SOC](https://docs.nlr.gov/docs/fy17osti/67436.pdf)
- [Meeting 2025 Zero Emission Vehicle Goals: charging preferences และ charging power taper](https://docs.nlr.gov/docs/fy19osti/71198.pdf)
- [The 2030 National Charging Network: home/destination/DC และ preference cohort เป็นสมมติฐานของการศึกษานั้น](https://docs.nlr.gov/docs/fy23osti/85654.pdf)
- [EVI-Pro Lite API: representative-day fleet load profiles ระดับ 15 นาที ไม่ใช่ site-sales oracle](https://developer.nlr.gov/docs/transportation/evi-pro-lite-v1/)

เอกสารนี้เปรียบเทียบหลักการ ไม่อ้างว่า TH-EVI ได้รับการรับรองจาก NREL หรือเรียกใช้ EVI-Pro จริง

# จังหวัดพิษณุโลก — Competitor EV Charging Station Deep Sweep (Seed Data)

**วันที่:** 2026-06-08
**จัดทำโดย:** Hermes Agent (llm_agent)
**สถานะ:** SEED — ยังไม่ยืนยันจากแหล่งข้อมูลสด (web search blocked)

---

## 📊 สรุป

| ประเภท | จำนวน |
|---|---|
| **Seed ที่ต้อง Verify** | 7 สถานี |
| **Placeholder (Network พบในจังหวัด)** | 5 สถานี |
| **รวม** | **13 records** |

## 🏢 แบ่งตามเครือข่าย

| Network | จำนวน | สถานะ |
|---|---|---|
| **PEA VOLTA** | 3 | seed (PEA HQ + 2 district offices) |
| **EV Station PluZ** (PTT OR) | 4 | seed (PTT stations บน highway) |
| **PTT EV Station** | 1 | placeholder |
| **EA Anywhere** | 1 | placeholder |
| **MG Charge** | 1 | seed (MG dealer) |
| **Rever Sharger** | 1 | seed (BYD dealer) |
| **EVolt** | 1 | placeholder |
| **EleXA** | 1 | placeholder (candidate) |

## 🗺️ จุดสำคัญ

| Cluster | คำอธิบาย |
|---|---|
| **เมืองพิษณุโลก** | พื้นที่หนาแน่นที่สุด: PEA VOLTA HQ, PTT EV, MG, Rever, EVolt |
| **Highway 12 Bypass** | PTT Station บนถนนเลี่ยงเมือง (Mitraphap Road) |
| **Highway 11** | เส้นทาง Phitsanulok-Uttaradit |
| **Highway 12 East** | เส้นทางไป Lom Sak / หล่มสัก |

## ⚠️ Unresolved Issues

1. **🔴 ไม่มีข้อมูลจาก Google Maps / แอป official** — เนื่องจาก web search ถูก block จาก terminal ข้อมูลทั้งหมดเป็น seed ที่ต้อง verify
2. **🔴 พิกัดทั้งหมดเป็น approximate** — อ้างอิงจากตำแหน่งที่รู้จัก (PEA office, PTT station, dealer) ไม่ใช่ pin จริงของหัวชาร์จ
3. **🔴 จำนวนหัวชาร์จและกำลังไฟไม่ทราบ** — ต้อง verify จาก official app ของแต่ละเครือข่าย
4. **🟡 Public access ไม่แน่ใจ** — บางสถานีอาจอยู่ในเขตจำกัด (PEA office, dealer) ต้องตรวจสอบว่า public เข้าได้จริง
5. **🟡 ราคาค่าชาร์จ** — ต้องกรอกจากแอปของแต่ละเครือข่าย
6. **🟡 EA Anywhere / EVolt / EleXA** — เป็น placeholder ทั้งหมด ยังไม่รู้ exact pin ในพิษณุโลก
7. **🔴 ยังไม่ได้ตรวจอำเภออื่น** — นครไทย, ชาติตระการ, เนินมะปราง, วัดโบสถ์, พรหมพิราม, บางกระทุ่ม

## ✅ ขั้นตอนต่อไป (แนะนำ)

1. เปิด Google Maps ค้นหา "EV charging station near Phitsanulok" → ตรวจพิกัด + ถ่าย screenshot
2. เปิดแอป PEA VOLTA → เช็คสถานีในพิษณุโลก → บันทึกจำนวนหัว, kW, พิกัดจริง
3. เปิดแอป EV Station PluZ → เช็คสถานีในพิษณุโลก
4. เปิดแอป EA Anywhere, EVolt, MG Charge → เช็คสถานีเพิ่มเติม
5. ใช้ Plugshare (plugshare.com) ค้นหาสถานีในพิษณุโลก
6. อัปเดตไฟล์ CSV โดยเปลี่ยน `verification_status` เป็น `confirmed_live` และ `confidence` เป็น `high`

---

## 📁 ไฟล์

- `data/competitors_phitsanulok_seed.csv` — ข้อมูล seed 13 records
- `docs/phitsanulok_competitor_audit_notes.md` — บันทึกฉบับนี้

# Wasabi Park DC Fast Charging Hub — Proposal Data Pack

**Document Version:** 1.0
**Last Updated:** 2026-06-10
**Project Code:** TH-EVI / TCE-PROP-WP-001
**Prepared for:** Wasabi Park Owner
**Prepared by:** TCE Project Co., Ltd.

---

## 1. Project Metadata

| Field | Value |
|-------|-------|
| **Project Name** | Wasabi Park DC Fast Charging Hub |
| **Site Name** | Wasabi Park |
| **Subtitle** | ยกระดับ Community Mall สู่ Fast Charging Destination บนถนนมหิดล |
| **Address** | Mahidol Rd, Tambon Nong Hoi, Mueang Chiang Mai District, Chiang Mai 50000 |
| **Latitude** | 18.759778 |
| **Longitude** | 99.017645 |
| **Province** | เชียงใหม่ (Chiang Mai) |
| **District** | Mueang Chiang Mai |
| **Subdistrict** | Nong Hoi |
| **Site Type** | Community Mall |
| **Existing EV Charger** | AC 22 kW (already on site) |
| **Landmark ID** | `wasabi_park` (proposed) |

---

## 2. Location Analysis

### 2.1 Traffic & AADT

| Field | Value | Source |
|-------|-------|--------|
| AADT (Mahidol Rd) | ~12,000 | Estimated (municipal road) |
| Closest DOH highway | Route 1141 (Airport Rd) | `aadt_2566.csv` |
| Route 1141 AADT | 118,853 | DOH |
| Road type | Local / municipal | Field |
| Hot zone membership | Saraphi/Lamphun Route 106 (rank 9, base=140) | `hot_zones_chiang_mai.csv` |

### 2.2 Nearby Schools (Demand Boosters)

| School Name | Distance (km) | Students | Address |
|-------------|:-------------:|:--------:|---------|
| **โรงเรียนวารีเชียงใหม่** | **0.33** | 2,500 | Nong Hoi subdistrict |
| **โรงเรียนมงฟอร์ตวิทยาลัย (มัธยม)** | **0.64** | 3,200 | Pa Daet subdistrict |
| โรงเรียนมงฟอร์ตวิทยาลัย (ประถม) | 2.22 | 2,400 | Charoenprathet Rd |
| **Total within 2 km** | — | **5,700** | — |

**Demand Boost Factor:** +12% (from school parent/teacher/student traffic)

### 2.3 Nearby Hospitals (Demand Boosters)

| Hospital | Distance (km) | Type |
|----------|:-------------:|------|
| Rajavej Chiang Mai Hospital | 1.6 | Hospital |
| Central Memorial Hospital | 2.5 | Hospital |
| Chiangmai Klaimor Hospital | 4.7 | Hospital |
| Maharaj Nakorn CM Hospital | 5.6 | Major hospital |
| Chiang Mai Airport | 5.8 | Airport |

### 2.4 Nearby Competitors (12 stations within 5 km)

| Rank | Name | Distance (km) | Guns | Power (kW) | Brand | Corridor |
|:----:|------|:-------------:|:----:|:----------:|:-----:|:--------:|
| 1 | Shell Recharge Montfort | 1.0 | 4 | 180 | Shell | No |
| 2 | MG Super Charge Lamphun Rd | 1.1 | 2 | 50 | MG | Yes |
| 3 | PTT EV Don Chan | 1.1 | 2 | 120 | PTT | Yes |
| 4 | **PEA Volta Hub Chiang Mai** | **1.9** | **10** | **180** | PEA | **Yes** |
| 5 | Pumpcharge PEA Region 1 | 1.9 | 4 | 22 (AC) | PEA | Yes |
| 6 | EV Station PluZ city | 3.7 | 2 | 120 | PTT | No |
| 7 | BYD charger city | 3.9 | 4 | 120 | BYD | No |
| 8 | ReverSharger 95 Mahidol | 4.0 | 2 | 120 | Rever | No |
| 9 | ReverSharger 227 Mahidol | 4.0 | 4 | 120 | Rever | No |
| 10 | MG Super Charge city | 4.0 | 2 | 50 | MG | No |
| 11 | **Super EV Hub Cultural Center** | **4.2** | **12** | **180** | Hub | **No** |
| 12 | EleXA PT Chiang Mai 8 | 4.5 | 2 | 125 | EGAT | No |

**Competitor Pressure Factor:** -10% (12 stations, 2 major hubs within 5 km)

---

## 3. Demand Model (TH-EVI)

### 3.1 Model Parameters

| Parameter | Value |
|-----------|-------|
| Location type | `destination` |
| Charge probability | 20% |
| Fleet EV share (2030) | 4.17% |
| AADT used | 12,000 |
| Readiness multiplier | 1.05 (community_mall format) |

### 3.2 Scenario Factors (Applied to Raw Demand)

| Scenario | Factor | School Boost | Competitor Pressure | Net Factor |
|----------|:------:|:------------:|:-------------------:|:----------:|
| Conservative | 0.75 | +12% | -10% | 0.81 |
| **Base** | 1.00 | +12% | -10% | 1.08 |
| **Confident (recommended)** | **1.125** | **+12%** | **-10%** | **1.22** |
| Upside | 1.25 | +12% | -10% | 1.35 |

### 3.3 Base Scenario Output (without adjustments)

| Metric | Value |
|--------|-------|
| Raw sessions/day (2030) | 100.0 |
| Raw kWh/day (2030) | 1,500 |
| Capture share (model) | 17.3% |
| Captured sessions/day (2030) | 18.1 |
| Captured kWh/day (2030) | 580 |
| Captured revenue/day (2030) | 3,771 THB |

### 3.4 Confident Scenario Output (with school + and competitor -)

| Metric | Value |
|--------|-------|
| Raw sessions/day (2030) | 100.0 |
| Adjusted sessions/day (2030) | 122.0 (× 1.22) |
| After competition: Captured sessions/day (2030) | **20.6** |
| Captured kWh/day (2030) | 658 |
| Captured revenue/day (2030) | **4,276 THB** |

---

## 4. 10-Year Financial Projection (Confident Scenario)

### 4.1 Annual Demand & Revenue

| Year | Raw EV/day | Confident Sessions/day | kWh/day | THB/day | Recommended Ports |
|:----:|:----------:|:----------------------:|:-------:|:-------:|:-----------------:|
| 2026 | 49.0 | **10.1** | 322 | 2,095 | 4 |
| 2027 | 59.0 | **12.1** | 388 | 2,523 | 4 |
| 2028 | 71.0 | **14.6** | 467 | 3,036 | 4 |
| 2029 | 85.0 | **17.5** | 559 | 3,635 | 4 |
| **2030** | **100.0** | **20.6** | **658** | **4,276** | **4** |
| 2031 | 116.0 | 23.8 | 763 | 4,961 | 4 |
| 2032 | 131.0 | 26.9 | 862 | 5,602 | 4 |
| 2033 | 148.0 | 30.4 | 974 | 6,329 | 4 |
| 2034 | 165.0 | 33.9 | 1,086 | 7,056 | 4 |
| **2035** | **184.0** | **37.8** | **1,211** | **7,869** | **4** |

### 4.2 CAPEX (1 unit 180 kW, 2 connectors, standalone)

| Item | Cost (THB) | Source |
|------|----------:|--------|
| SINEXEL INT-S-2-180 (180 kW x2 guns) | 2,163,300 | `evhub_sinexcel_price_list.csv` |
| Installation + Electrical work | 500,000 | Estimate |
| Signage + Branding | 150,000 | Estimate |
| Contingency (~10%) | 200,000 | Estimate |
| **Total CAPEX** | **3,013,300** | — |

### 4.3 OPEX Assumptions

| Item | Value |
|------|-------|
| Variable OPEX (% of revenue) | 40% |
| Fixed OPEX (THB/year) | 60,000 |
| Components | Electricity, demand charge, maintenance, platform fees |

### 4.4 10-Year Cash Flow

| Year | Sessions | Revenue/Y | OPEX/Y | Net CF | Cumul CF | Note |
|:----:|:--------:|----------:|-------:|-------:|---------:|------|
| 2026 | 10.1 | 764,675 | 365,870 | 398,805 | -2,614,495 | Start-up |
| 2027 | 12.1 | 920,895 | 428,358 | 492,537 | -2,121,958 | |
| 2028 | 14.6 | 1,108,140 | 503,256 | 604,884 | -1,517,074 | |
| 2029 | 17.5 | 1,326,775 | 590,710 | 736,065 | -781,009 | |
| **2030** | **20.6** | **1,560,740** | **684,296** | **876,444** | **95,435** | **Payback ✓** |
| 2031 | 23.8 | 1,810,765 | 784,306 | 1,026,459 | 1,121,894 | |
| 2032 | 26.9 | 2,044,730 | 877,892 | 1,166,838 | 2,288,732 | |
| 2033 | 30.4 | 2,310,085 | 984,034 | 1,326,051 | 3,614,783 | |
| 2034 | 33.9 | 2,575,440 | 1,090,176 | 1,485,264 | 5,100,047 | |
| **2035** | **37.8** | **2,872,185** | **1,208,874** | **1,663,311** | **6,763,358** | |

### 4.5 Key Financial Metrics

| Metric | Value |
|--------|------:|
| **Payback period** | **~3.08 years** (early 2030) |
| 10-year net cash flow | 9,776,658 THB |
| 10-year gross revenue | 17,294,430 THB |
| 10-year total OPEX | 7,517,772 THB |
| Net ROI (10 years) | 324.5% |
| Total sessions (10 years) | 83,110 |
| Average sessions/port/day (2030) | 5.2 |

---

## 5. Recommended Configuration

### 5.1 Phase 1 (Year 0-3): Pilot

| Spec | Value |
|------|-------|
| Charger type | DC Fast Charger 180 kW |
| Quantity | 1 unit |
| Charging connectors | 2 (CCS2) |
| Parking spaces required | 2 EV bays |
| Architecture | Standalone cabinets |
| Cabinet config | 180 kW x 2 cabinets |
| Total site power | 360 kW |
| Max power per gun | 180 kW |
| CAPEX | 3,013,300 THB |
| Timeline | Install in 2026, operating by Q3 2026 |

### 5.2 Phase 2 (Year 3+): Expansion (Optional)

| Spec | Value |
|------|-------|
| Additional units | 1 unit (180 kW) |
| Total Phase 2 config | 2 units, 4 connectors, 4 EV bays |
| Additional CAPEX | ~2,800,000 THB |
| Trigger | Sessions > 15/day consistently for 3 months |

---

## 6. Business Model Options

### 6.1 Model A — Owner-Funded Turnkey

| Aspect | Detail |
|--------|--------|
| Investment | Owner funds 100% of CAPEX (3,013,300 THB) |
| TCE role | Design, install, commission, O&M support |
| Revenue | 100% to owner |
| O&M cost | ~40% of revenue (paid to PEA/EGAT + platform) |
| Owner net | ~60% of gross revenue |
| Best for | Owners wanting maximum long-term cash flow |

### 6.2 Model B — Revenue Sharing

| Aspect | Detail |
|--------|--------|
| Investment | TCE or investor funds 100% CAPEX |
| Owner role | Provide space, basic electrical infrastructure |
| Revenue share | Owner 15-25%, TCE/investor 75-85% |
| Lease option | Fixed monthly rent per bay (e.g., 8,000-15,000 THB/bay/month) |
| Best for | Owners wanting zero CAPEX exposure |

### 6.3 Model C — Hybrid

| Aspect | Detail |
|--------|--------|
| Investment | Owner 30-50%, TCE 50-70% |
| Revenue share | Proportional to investment |
| Joint operation | TCE manages operations, owner provides oversight |
| Best for | Risk-sharing, partnership approach |

---

## 7. Customer Segments (Target Demand)

| Segment | Description | Estimated Share | Dwell Time |
|---------|-------------|:---------------:|:----------:|
| School parents/teachers | Drop-off, pick-up, school events | 25% | 15-30 min |
| Mall visitors (food/café) | Existing community mall footfall | 30% | 20-40 min |
| Airport travelers | Pre/post flight charging (5.8 km from airport) | 15% | 30-60 min |
| Hospital visitors/staff | Rajavej (1.6 km), Memorial (2.5 km) | 10% | 30-90 min |
| Local EV owners | Convenience charging vs home | 10% | 15-45 min |
| Highway pass-through | Route 1141 traffic detour | 10% | 15-30 min |

---

## 8. Implementation Roadmap

| Step | Activity | Duration |
|:----:|----------|:--------:|
| 1 | Site Audit (electrical, transformer, MDB, parking) | 3-7 days |
| 2 | Feasibility & Layout Proposal (load assessment, CAPEX, revenue) | 7-14 days |
| 3 | Commercial Agreement (model selection) | Negotiation period |
| 4 | Equipment Procurement | 30-45 days |
| 5 | Installation & Commissioning | 30-60 days |
| 6 | Soft Launch & Monitoring | 30 days |
| **Total** | **Signing to operation** | **~4-6 months** |

---

## 9. Strategic Benefits to Wasabi Park

| Benefit | Impact |
|---------|--------|
| Capture 5,700+ students + parents/teachers as recurring customers | High |
| Increase mall footfall from EV-owning segment | High |
| Differentiate from nearby community malls (no DC charge) | Medium |
| Green/modern brand positioning | Medium |
| Convert existing parking into revenue-generating asset | High |
| Marketing message: "Fast Charging Stop on Mahidol Road" | Medium |
| Future-proofing for EV adoption growth in Chiang Mai | High |

---

## 10. Why TCE

| Capability | Description |
|------------|-------------|
| **Site Survey & Feasibility** | Electrical inspection, load assessment, traffic pattern analysis |
| **Electrical Engineering Design** | Grid impact, transformer, MDB, safety systems |
| **Turnkey Installation** | Equipment supply, installation, commissioning |
| **Platform & Operations** | Payment system, monitoring, monthly reporting |
| **Maintenance & After-sales** | Preventive maintenance, spare parts, technical support |
| **Reference Sites** | TCE EV STATION @META MALL (6 guns, 240 kW) — verified operational |

---

## 11. Comparison with Project Cases (2030 Base)

| Rank | Site | Sessions/day | THB/day | Ports |
|:----:|------|:------------:|:-------:|:-----:|
| 1 | Central Airport CM | 150.0 | 28,500 | 12 |
| 2 | UD Town | 60.0 | 11,400 | 6 |
| 3 | U Park Ubon | 58.0 | 11,000 | 6 |
| 4 | MeeChok Plaza | 55.0 | 10,500 | 6 |
| 5 | Sunee Grand Ubon | 50.0 | 9,500 | 6 |
| 6 | Fairy Plaza KK | 48.0 | 9,100 | 4 |
| 7 | Mahachok Park CM | 38.0 | 7,200 | 4 |
| **8** | **Wasabi Park (Confident 2030)** | **20.6** | **4,276** | **4** |
| 9 | Punn Suk CM | 25.0 | 4,800 | 4 |

**Ranking Position:** 8 of 9 (small-scale, but with strong school demand boost)

---

## 12. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|------------|
| 12 competitors capture majority demand | High | High | Differentiate via AC upgrade (was 22kW), location, customer service |
| School traffic insufficient | Medium | Medium | Phase 1 pilot to validate before Phase 2 |
| Transformer capacity insufficient | Medium | High | Site audit in Step 1 to confirm before commitment |
| Lower-than-expected utilization (Year 1) | Medium | Medium | Confident scenario already conservative; monitor quarterly |
| New competitor opens nearby | Medium | High | First-mover advantage + AC + DC bundle |
| EV adoption slower than projected | Low | Medium | Confident scenario uses mid-point, not upside |

---

## 13. Information Required from Owner

| # | Item | Purpose |
|:-:|------|---------|
| 1 | Single Line Diagram (SLD) | Electrical design |
| 2 | Transformer capacity (kVA) | Load feasibility |
| 3 | MDB configuration and capacity | Load feasibility |
| 4 | Current electricity tariff type & rate | OPEX calculation |
| 5 | Parking lot layout & EV bay candidates | Site design |
| 6 | Existing AC charger contract terms | Compatibility check |
| 7 | Mall visitor data (footfall, peak hours) | Demand validation |
| 8 | Owner's objective: revenue / brand / service | Business model selection |
| 9 | Decision timeline | Project scheduling |
| 10 | Available budget envelope | CAPEX alignment |

---

## 14. Key Talking Points (for Presentation)

### 14.1 Opening

> "Wasabi Park มี charger อยู่แล้ว แปลว่าทำเลนี้เข้าใจ EV แล้ว แต่ของเดิมเป็น AC 22 kW ซึ่งตอบโจน์คนจอดนาน ขณะที่ DC Fast Charge ของ TCE จะตอบโจน์ลูกค้าอีกกลุ่มหนึ่ง คือคนที่ต้องการชาร์จเร็วระหว่างแวะกินข้าว ซื้อกาแฟ หรือเดินทางผ่านถนนมหิดล"

### 14.2 Why Now

- โรงเรียน 2 แห่ง (5,700 นักเรียน) ในรัศมี 1 กม.
- ถนนมหิดลเชื่อมสนามบิน-ตัวเมือง
- EV adoption เชียงใหม่เติบโต ~15% ต่อปี
- คู่แข่ง DC ใกล้สุด 3.7 กม. (ยังมีช่องว่าง)

### 14.3 The Math

- CAPEX: 3.0M THB
- Year 1 revenue: ~765K THB
- Payback: ~3 ปี
- 10-year net: ~9.8M THB
- ROI: 324%

### 14.4 Risk Reversal

- ไม่ต้องลงทุนเอง (Model B/C)
- Phase 1 เป็น pilot 1 ตู้ ขยายได้
- TCE รับประกัน performance 6 เดือน

---

## 15. Next Steps (for TCE)

| Step | Action | Owner | Deadline |
|:----:|--------|-------|:--------:|
| 1 | Present this proposal to Wasabi Park owner | TCE Sales | Week 1 |
| 2 | Site audit if owner expresses interest | TCE Engineering | Week 2-3 |
| 3 | Detailed load assessment | TCE Engineering | Week 3-4 |
| 4 | Final proposal with site-specific CAPEX | TCE Sales | Week 4-5 |
| 5 | Contract negotiation | TCE Legal | Week 5-8 |
| 6 | Procurement & installation | TCE Operations | Month 3-6 |

---

## 16. Model Validation Reference

| Layer | Status | Notes |
|-------|--------|-------|
| Adoption model | MAPE 8.5% | Calibrated to FTI 2023-2025 data |
| Station model | Just-identified (n=1) | Need 4+ more station-days |
| Location model | Operational | 11 Chiang Mai landmarks |
| Site model | Operational | Competitor + readiness + ramp-up |
| Temporal model | Operational | Queue analysis |

**Source code:** `D:\Work\TH-EVI\th_evi\` (adoption.py, location.py, site.py, temporal.py)

---

## 17. Glossary

| Term | Definition |
|------|------------|
| CAPEX | Capital Expenditure (upfront investment) |
| OPEX | Operating Expenditure (recurring costs) |
| AADT | Average Annual Daily Traffic |
| CCS2 | Combined Charging System Type 2 (DC standard) |
| O&M | Operations & Maintenance |
| SLD | Single Line Diagram (electrical) |
| MDB | Main Distribution Board |
| TCE | TCE Project Co., Ltd. (proponent) |
| kVA | Kilovolt-Ampere (transformer capacity) |
| kWh | Kilowatt-hour (energy) |
| DC | Direct Current (fast charging) |
| AC | Alternating Current (slow charging) |

---

## 18. Document Control

| Version | Date | Author | Changes |
|:-------:|:----:|--------|---------|
| 1.0 | 2026-06-10 | TCE Engineering | Initial proposal data pack |

**Generated by:** TH-EVI Model v0.2.0
**Project:** TH-EVI / Wasabi Park Analysis
**Data Sources:** TH-EVI model + OpenStreetMap + DLT/DOPA/DOH CSVs in `D:\Work\TH-EVI\data\`

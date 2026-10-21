(function (root) {
  'use strict';
  const storageKey = 'th-evi.site-visit-assumptions.v1';
  const defaults = { enabled: true, power: 120, cabinets: 1, bays: 2, hours: 24,
    availability: 97, activeKw: 60, overhead: 5, sessionKwh: '', radius: 3,
    outside: 1, access: 1, openShare: 100, publicAccess: true };
  let settings = { ...defaults }, active = null;
  const cache = new Map();
  try { settings = { ...defaults, ...JSON.parse(localStorage.getItem(storageKey) || '{}') }; } catch (_) {}

  function input(name, label, type, attributes = '') {
    return `<label>${label}<input data-sf="${name}" type="${type}" ${attributes}></label>`;
  }

  function mountSettings(container) {
    if (!container) return;
    container.classList.add('site-forecast-settings');
    container.innerHTML = `<h2>ประเมินรถเข้าชาร์จ</h2>
      <label class="sf-toggle"><input data-sf="enabled" type="checkbox">แสดงรถเข้าชาร์จโดยประมาณ</label>
      <div data-sf-fields><div class="sf-grid">
        <label>กำลังรวมต่อตู้ (kW)<select data-sf="power">${[30,60,120,180,240,360,720,960].map(n => `<option value="${n}">${n}</option>`).join('')}</select></label>
        ${input('cabinets','จำนวนตู้','number','min="1" max="10" step="1"')}
        ${input('bays','ช่องจอดที่ชาร์จพร้อมกันได้','number','min="1" max="40" step="1"')}
        ${input('hours','เปิดบริการ (ชั่วโมง/วัน)','number','min="1" max="24" step="1"')}
      </div><details><summary>สมมติฐานสถานี</summary><div class="sf-grid">
        ${input('availability','ความพร้อมใช้งาน (%)','number','min="1" max="100" step="1"')}
        ${input('activeKw','กำลังชาร์จเฉลี่ยต่อคัน (kW)','number','min="1" max="960" step="1"')}
        ${input('overhead','เวลาเข้าออกช่องจอด (นาที)','number','min="0" max="120" step="1"')}
        ${input('sessionKwh','พลังงานต่อครั้ง (kWh)','number','min="1" step="0.5" placeholder="ข้อมูลสถานีอ้างอิง"')}
        ${input('radius','ระยะดึงดูดลูกค้า (กม.)','number','min="0.1" max="10" step="0.1"')}
        ${input('access','แรงดึงดูดของจุดติดตั้ง (1 = มาตรฐาน)','number','min="0" max="2" step="0.05"')}
        ${input('outside','น้ำหนักทางเลือกอื่น (1 = มาตรฐาน)','number','min="0.1" max="100" step="0.1"')}
        ${input('openShare','สัดส่วนดีมานด์ในเวลาเปิด (%)','number','min="0" max="100" step="1"')}
      </div><label class="sf-toggle" style="margin-top:10px"><input data-sf="publicAccess" type="checkbox">เปิดให้บุคคลทั่วไปเข้าชาร์จ</label></details></div>`;
    container.querySelectorAll('[data-sf]').forEach(element => {
      const key = element.dataset.sf;
      if (element.type === 'checkbox') element.checked = Boolean(settings[key]);
      else element.value = settings[key];
      element.addEventListener('change', () => {
        settings[key] = element.type === 'checkbox' ? element.checked : element.value;
        if (key === 'cabinets') {
          settings.bays = Math.min(40, Math.max(1, Number(settings.cabinets) * 2));
          container.querySelector('[data-sf="bays"]').value = settings.bays;
        }
        if (key === 'hours') {
          settings.openShare = Number(settings.hours) === 24 ? 100 : Math.round(Number(settings.hours) / 24 * 100);
          container.querySelector('[data-sf="openShare"]').value = settings.openShare;
        }
        if (key === 'power' && Number(settings.activeKw) > Number(settings.power)) {
          settings.activeKw = Number(settings.power);
          container.querySelector('[data-sf="activeKw"]').value = settings.activeKw;
        }
        container.querySelector('[data-sf-fields]').hidden = !settings.enabled;
        try { localStorage.setItem(storageKey, JSON.stringify(settings)); } catch (_) {}
        cache.clear();
        if (active?.container.isConnected) renderInto(active.container, active.context, active.onUpdate);
      });
    });
    container.querySelector('[data-sf-fields]').hidden = !settings.enabled;
  }

  function payload(context) {
    const number = (key, min, max, integer = false) => {
      const value = Number(settings[key]);
      if (!Number.isFinite(value) || String(settings[key]).trim() === '' || value < min || value > max || (integer && !Number.isInteger(value))) {
        throw new Error('กรุณาตรวจค่าที่ตั้งไว้ในสมมติฐานสถานี');
      }
      return value;
    };
    const power = number('power', 1, 960), cabinets = number('cabinets', 1, 10, true);
    const activeKw = number('activeKw', 1, 960);
    if (activeKw > power) throw new Error('กำลังชาร์จเฉลี่ยต่อคันต้องไม่เกินกำลังต่อตู้');
    const hours = number('hours', 1, 24);
    return { province: context.province, lat: context.lat, lon: context.lon, year: context.year,
      station: { guns: number('bays', 1, 40, true), total_site_kw: power * cabinets,
        max_kw_per_gun: power, operating_hours: hours,
        availability: number('availability', 1, 100) / 100, mean_active_kw: activeKw,
        plug_overhead_minutes: number('overhead', 0, 120),
        demand_in_open_hours_share: hours === 24 ? 1 : number('openShare', 0, 100) / 100 },
      average_session_kwh: settings.sessionKwh === '' ? null : number('sessionKwh', 1, 200),
      kernel_radius_km: number('radius', 0.1, 10), outside_option_weight: number('outside', 0.1, 100),
      scenarios: [{ name: 'base', relative_access_attractiveness: number('access', 0, 2), market_multiplier: 1 }],
      public_access_assumed: Boolean(settings.publicAccess) };
  }

  function status(container, message, warning = false) {
    container.replaceChildren();
    const line = document.createElement('div');
    line.className = warning ? 'sf-detail sf-warning' : 'sf-detail';
    line.textContent = message;
    container.append(line);
  }

  async function renderInto(container, context, onUpdate = () => {}) {
    if (!container) return;
    if (active?.controller) active.controller.abort();
    const current = { container, context, onUpdate, controller: new AbortController() };
    active = current;
    container.classList.add('site-forecast-result');
    container.hidden = !settings.enabled;
    container.dataset.estimateStatus = 'loading';
    if (!settings.enabled) { container.dataset.estimateStatus = 'disabled'; onUpdate(); return; }
    let request;
    try { request = payload(context); } catch (error) {
      status(container, error.message, true); container.dataset.estimateStatus = 'unavailable'; onUpdate(); return;
    }
    if (!request.public_access_assumed) {
      status(container, 'ยังไม่ประเมิน: สถานีไม่ได้เปิดให้บุคคลทั่วไปเข้าชาร์จ', true);
      container.dataset.estimateStatus = 'unavailable'; onUpdate(); return;
    }
    status(container, 'กำลังประเมินรถเข้าชาร์จ…');
    onUpdate();
    const key = JSON.stringify(request);
    const timer = setTimeout(() => current.controller.abort(), 60000);
    try {
      let result = cache.get(key);
      if (!result) {
        const response = await fetch('/api/charging-demand/site-preview', { method: 'POST',
          headers: { 'Content-Type': 'application/json' }, body: key, signal: current.controller.signal });
        result = await response.json();
        if (!response.ok) {
          const detail = typeof result.detail === 'string' ? result.detail : '';
          if (/outside.*support/i.test(detail)) throw new Error('พิกัดนี้อยู่นอกพื้นที่ข้อมูลรองรับ จึงยังประเมินคัน/วันไม่ได้');
          if (/calendar year/i.test(detail)) throw new Error('ปีที่เลือกยังไม่มีข้อมูลสถานีอ้างอิงรองรับการประเมิน');
          if (/reference|profile|energy|province/i.test(detail)) throw new Error('จังหวัดนี้ยังไม่มีข้อมูลสถานีอ้างอิงเพียงพอสำหรับประเมินคัน/วัน');
          throw new Error('ยังประเมินไม่ได้ กรุณาตรวจสมมติฐานสถานีหรือทดลองใหม่');
        }
        if (cache.size >= 50) cache.delete(cache.keys().next().value);
        cache.set(key, result);
      }
      if (active !== current || !container.isConnected) return;
      const row = result.scenarios?.[0];
      if (!result.estimate_available || !Number.isFinite(row?.estimated_charging_visits_per_day)) throw new Error('ยังไม่มีผลประเมินรถเข้าชาร์จสำหรับจุดนี้');
      const visits = row.estimated_charging_visits_per_day;
      container.innerHTML = '<div>รถเข้าชาร์จโดยประมาณ</div><div class="sf-number"><strong data-sf-visits></strong><span>คัน/วัน</span></div><div class="sf-detail" data-sf-spec></div><div class="sf-detail" data-sf-energy></div><div class="sf-detail sf-warning" data-sf-limit></div><div class="sf-detail">ยังไม่ยืนยันความแม่นยำรายทำเล นับการเข้าชาร์จซ้ำแยกครั้ง</div>';
      container.querySelector('[data-sf-visits]').textContent = visits > 0 && visits < 0.5 ? 'น้อยกว่า 1' : Math.round(visits).toLocaleString('th-TH');
      container.querySelector('[data-sf-spec]').textContent = `${request.station.max_kw_per_gun} kW × ${settings.cabinets} ตู้ | ${request.station.guns} ช่องจอด | ${request.station.operating_hours} ชม./วัน`;
      if (request.station.operating_hours < 24) container.querySelector('[data-sf-spec]').textContent += ` | สมมติลูกค้าอยู่ในเวลาเปิด ${Math.round(request.station.demand_in_open_hours_share * 100)}%`;
      container.querySelector('[data-sf-energy]').textContent = `${Math.round(row.site_served_connector_kwh_per_day).toLocaleString('th-TH')} kWh/วัน | เฉลี่ย ${result.assumptions.average_session_kwh} kWh/ครั้ง`;
      container.querySelector('[data-sf-limit]').textContent = row.capacity_limited ? 'จำนวนที่ให้บริการถูกจำกัดด้วยกำลังไฟและช่องจอด' : 'อ้างอิงการใช้งานสถานีจริงและแบบจำลองส่วนแบ่งลูกค้า';
      if (result.missing_competitor_evidence?.length) {
        const note = document.createElement('div'); note.className = 'sf-detail sf-warning';
        note.textContent = 'ข้อมูลคู่แข่งบางแห่งยังไม่ครบ ผลประเมินอาจเปลี่ยนได้'; container.append(note);
      }
      container.dataset.estimateStatus = 'ready';
    } catch (error) {
      if (active !== current || !container.isConnected) return;
      status(container, error.name === 'AbortError' ? 'คำนวณเกินเวลา กรุณาลองใหม่' : error.message, true);
      container.dataset.estimateStatus = 'unavailable';
    } finally {
      clearTimeout(timer);
      if (active === current && container.isConnected) onUpdate();
    }
  }

  root.THEVISiteForecast = { mountSettings, renderInto, enabled: () => Boolean(settings.enabled), payload };
})(window);

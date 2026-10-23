(function (root) {
  'use strict';
  const storageKey = 'th-evi.map-layer-visibility.v1';
  const words = {
    th: { title: 'ชั้นข้อมูล', heat: 'Heat Map', pois: 'POI ของเรา', competitors: 'สถานีคู่แข่ง',
      candidates: 'พื้นที่ที่บันทึก', loading: 'กำลังโหลด', empty: 'ไม่มีข้อมูล', failed: 'โหลดไม่สำเร็จ',
      retry: 'ลองใหม่', maps: 'Google Maps', street: 'Street View', power: 'กำลังสูงสุด',
      unknownPower: 'ยังไม่ยืนยันกำลังไฟ', unknownType: 'ยังไม่ยืนยันชนิดหัวชาร์จ', bays: 'หัวชาร์จ',
      status: 'สถานะข้อมูล', unverified: 'ยังไม่ยืนยัน', source: 'แหล่งข้อมูล' },
    en: { title: 'Map layers', heat: 'Heat Map', pois: 'Our POIs', competitors: 'Competitors',
      candidates: 'Saved sites', loading: 'Loading', empty: 'No data', failed: 'Load failed',
      retry: 'Retry', maps: 'Google Maps', street: 'Street View', power: 'Maximum power',
      unknownPower: 'Power not confirmed', unknownType: 'Connector type not confirmed', bays: 'connectors',
      status: 'Data status', unverified: 'Not verified', source: 'Source' }
  };
  function mount({ map, heatLayers, poiLayer, competitorLayer, candidateLayer = null }) {
    let language = 'th', province = null;
    const visible = { heat: true, pois: false, competitors: false, candidates: true };
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
      for (const key of Object.keys(visible)) if (typeof saved?.[key] === 'boolean') visible[key] = saved[key];
    } catch (_) {}
    const groups = { heat: heatLayers, pois: [poiLayer], competitors: [competitorLayer] };
    if (candidateLayer) groups.candidates = [candidateLayer];
    const states = Object.fromEntries(['pois', 'competitors'].map(key => [key,
      { status: 'idle', count: 0, controller: null, generation: 0, cache: new Map() }]));
    if (!map.getPane('referenceMarkers')) map.createPane('referenceMarkers').style.zIndex = '450';
    const control = L.control({ position: 'topright' }), rows = {};
    let details, title;
    const t = key => words[language][key];
    function updateLabels() {
      title.textContent = t('title');
      Object.entries(rows).forEach(([key, row]) => {
        row.name.textContent = t(key); row.input.checked = visible[key];
        const state = states[key];
        row.count.textContent = !state || !visible[key] || state.status === 'idle' ? '' :
          state.status === 'ready' ? (state.count ? String(state.count) : t('empty')) :
          t(state.status === 'loading' ? 'loading' : 'failed');
        row.retry.textContent = t('retry');
        row.retry.hidden = !(visible[key] && state?.status === 'error');
      });
    }
    function applyVisibility(key) {
      groups[key].forEach(layer => visible[key] ? layer.addTo(map) : map.removeLayer(layer));
    }
    function save() { try { localStorage.setItem(storageKey, JSON.stringify(visible)); } catch (_) {} }
    control.onAdd = () => {
      details = L.DomUtil.create('details', 'map-layers-control'); details.open = true;
      title = document.createElement('summary'); details.append(title);
      for (const key of Object.keys(groups)) {
        const row = document.createElement('div'); row.className = 'map-layer-row';
        const label = document.createElement('label');
        const input = document.createElement('input'); input.type = 'checkbox'; input.dataset.mapLayer = key;
        const swatch = document.createElement('span'); swatch.className = `map-layer-swatch swatch-${key}`; swatch.setAttribute('aria-hidden', 'true');
        const name = document.createElement('span');
        const count = document.createElement('span'); count.className = 'map-layer-count'; count.setAttribute('aria-live', 'polite');
        const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'map-layer-retry'; retry.hidden = true;
        label.append(input, swatch, name); row.append(label, count, retry); details.append(row);
        rows[key] = { input, name, count, retry };
        input.addEventListener('change', () => {
          visible[key] = input.checked; applyVisibility(key); save(); updateLabels();
          if (states[key] && visible[key]) load(key);
          if (!visible[key]) groups[key].forEach(layer => layer.eachLayer?.(marker => marker.closePopup?.()));
        });
        retry.addEventListener('click', () => load(key, true));
      }
      L.DomEvent.disableClickPropagation(details); L.DomEvent.disableScrollPropagation(details);
      L.DomEvent.on(details, 'keydown', L.DomEvent.stopPropagation);
      return details;
    };
    control.addTo(map);
    Object.keys(groups).forEach(applyVisibility); updateLabels();

    function popup(row, key) {
      const host = document.createElement('div'); host.className = 'map-reference-popup';
      const heading = document.createElement('h3'); heading.textContent = row.name || t(key); host.append(heading);
      function line(value) { const el = document.createElement('div'); el.textContent = value; host.append(el); }
      if (key === 'pois' && row.category) line(row.category);
      if (key === 'competitors') {
        if (row.network || row.operator) line(row.network || row.operator);
        const power = Number(row.max_kw);
        line(Number.isFinite(power) && power > 0 ? `${t('power')}: ${power} kW` : t('unknownPower'));
        const guns = Number(row.guns ?? row.capacity);
        if (Number.isInteger(guns) && guns > 0) line(`${guns} ${t('bays')}`);
        line(['dc', 'ac'].includes(row.charging_type) ? row.charging_type.toUpperCase() : t('unknownType'));
      }
      line(`${t('status')}: ${row.verification_status || t('unverified')}`);
      line(`${Number(row.lat).toFixed(6)}, ${Number(row.lon).toFixed(6)}`);
      const links = document.createElement('div'); links.className = 'map-reference-links'; host.append(links);
      function link(text, href) {
        const anchor = document.createElement('a'); anchor.textContent = text; anchor.href = href;
        anchor.target = '_blank'; anchor.rel = 'noopener noreferrer'; links.append(anchor);
      }
      link(t('maps'), `https://www.google.com/maps/search/?api=1&query=${row.lat},${row.lon}`);
      link(t('street'), `https://www.google.com/maps?layer=c&cbll=${row.lat},${row.lon}&cbp=12,0,0,0,0`);
      try { const url = new URL(row.source_url); if (['https:', 'http:'].includes(url.protocol)) link(t('source'), url.href); } catch (_) {}
      return host;
    }
    function draw(key, data) {
      const group = groups[key][0]; group.clearLayers();
      for (const row of data) {
        const lat = Number(row.lat), lon = Number(row.lon);
        if (row.lat == null || row.lon == null || !Number.isFinite(lat) || !Number.isFinite(lon) || lat < 5 || lat > 21 || lon < 97 || lon > 106) continue;
        const color = key === 'pois' ? '#087e8b' : '#7c3aed';
        const marker = L.circleMarker([lat, lon], { pane: 'referenceMarkers', radius: key === 'pois' ? 6 : 7,
          color: '#ffffff', weight: 2, fillColor: color, fillOpacity: .95 });
        const tooltip = document.createElement('span'); tooltip.textContent = row.name || t(key);
        marker.bindTooltip(tooltip, { direction: 'top' });
        marker.bindPopup(() => popup(row, key), { maxWidth: 280, maxHeight: 250 });
        marker.addTo(group);
      }
      states[key].count = group.getLayers().length;
    }
    async function load(key, force = false) {
      if (!province) return;
      const state = states[key], requestedProvince = province;
      if (!force && ['loading', 'ready'].includes(state.status)) return;
      state.controller?.abort();
      const generation = ++state.generation, controller = new AbortController(); state.controller = controller;
      state.status = 'loading'; updateLabels();
      const timer = setTimeout(() => controller.abort(), 45000);
      try {
        let data = !force && state.cache.get(requestedProvince);
        if (!data) {
          const endpoint = key === 'pois' ? 'pois' : 'chargers';
          const response = await fetch(`/api/${endpoint}?province=${encodeURIComponent(requestedProvince)}`, { signal: controller.signal });
          if (!response.ok) throw new Error('Reference layer unavailable');
          const result = await response.json(); data = key === 'pois' ? result.pois : result.stations;
          if (!Array.isArray(data)) throw new Error('Invalid reference layer');
          if (state.cache.size >= 6) state.cache.delete(state.cache.keys().next().value);
          state.cache.set(requestedProvince, data);
        }
        if (generation !== state.generation || province !== requestedProvince) return;
        draw(key, data); state.status = 'ready';
      } catch (_) {
        if (generation !== state.generation || province !== requestedProvince) return;
        groups[key][0].clearLayers(); state.status = 'error'; state.count = 0;
      } finally {
        clearTimeout(timer);
        if (generation === state.generation) { state.controller = null; updateLabels(); }
      }
    }
    return {
      setProvince(value) {
        if (province !== value) {
          province = value;
          Object.entries(states).forEach(([key, state]) => {
            state.generation++; state.controller?.abort(); state.controller = null;
            state.status = 'idle'; state.count = 0; groups[key][0].clearLayers();
          });
          updateLabels();
        }
        return Promise.all(Object.keys(states).filter(key => visible[key]).map(key => load(key)));
      },
      setLanguage(value) { language = value === 'en' ? 'en' : 'th'; updateLabels(); }
    };
  }
  root.THEVIMapLayers = { mount };
})(window);

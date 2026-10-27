(function (root) {
  "use strict";
  const NUMBER = "[+-]?(?:\\d+(?:\\.\\d+)?|\\.\\d+)";
  const PAIR = new RegExp(`^\\s*(${NUMBER})(?:\\s*,\\s*|\\s+)(${NUMBER})\\s*$`);

  function fail(code) { throw new Error(code); }

  function parse(text) {
    let value = String(text || "").trim().replace(/\u2212/g, "-").replace(/\uff0c/g, ",");
    let source = "coordinates";
    if (/^https?:\/\//i.test(value)) {
      let url;
      try { url = new URL(value); } catch (_) { fail("invalid"); }
      const google = /^(?:www\.|maps\.)?google\.(?:com|co\.th)$/.test(url.hostname);
      if (url.hostname === "maps.app.goo.gl" || url.hostname === "goo.gl") fail("short_url");
      if (!google || /\/maps\/dir(?:\/|$)/.test(url.pathname)) fail("invalid");
      const place = /!3d([+-]?\d+(?:\.\d+)?)!4d([+-]?\d+(?:\.\d+)?)/.exec(url.href);
      const query = url.searchParams.get("query") || url.searchParams.get("q") || url.searchParams.get("ll") || url.searchParams.get("cbll");
      const center = /\/@([+-]?\d+(?:\.\d+)?),([+-]?\d+(?:\.\d+)?)(?:,|\/|$)/.exec(url.pathname);
      if (place) value = `${place[1]},${place[2]}`;
      else if (query) value = query;
      else if (center) { value = `${center[1]},${center[2]}`; source = "map_center"; }
      else fail("invalid");
    }
    if ((value.startsWith("(") && value.endsWith(")")) || (value.startsWith("[") && value.endsWith("]"))) {
      value = value.slice(1, -1);
    }
    const match = PAIR.exec(value);
    if (!match) fail("invalid");
    const lat = Number(match[1]), lon = Number(match[2]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) fail("invalid");
    return { lat, lon, source };
  }

  const COPY = {
    th: {
      label: "ค้นหาสถานที่หรือพิกัด", go: "ค้นหาหรือไปยังพิกัด", selected: "จุดที่เลือก",
      placeholder: "ชื่อสถานที่ หรือ lat, lon", searching: "กำลังค้นหา...", noResults: "ไม่พบสถานที่",
      searchUnavailable: "ค้นหาไม่สำเร็จ กรุณาลองอีกครั้ง", partial: "แสดงผลจากข้อมูลที่ค้นหาได้ในขณะนี้",
      partialEmpty: "ค้นหาข้อมูลได้ไม่ครบ กรุณาลองอีกครั้ง",
      provinceUnavailable: "พบตำแหน่งแล้ว แต่ยังระบุจังหวัดสำหรับโหลด Heat Map ไม่ได้",
      poi: "POI", competitor: "สถานีชาร์จ", saved: "พื้นที่ที่บันทึก", place: "สถานที่",
      invalid: "พิกัดไม่ถูกต้อง กรุณาระบุละติจูดและลองจิจูดให้ครบ",
      short_url: "ลิงก์แบบย่อยังระบุพิกัดไม่ได้ กรุณาคัดลอกตัวเลขพิกัดจาก Google Maps",
      outside: "พิกัดอยู่นอกขอบเขตแผนที่ประเทศไทย กรุณาตรวจลำดับ lat, lon",
      unloaded: "ยังไม่มีข้อมูล Heat Map ของจังหวัดที่เลือก",
      outOfCoverage: "จุดนี้อยู่นอกขอบเขตข้อมูล Heat Map ที่โหลด กรุณาตรวจจังหวัดและพื้นที่ข้อมูล",
      loading: "กำลังโหลด Heat Map ของจังหวัดที่เลือก", center: "ตำแหน่งกึ่งกลางแผนที่จากลิงก์",
      failed: "เลื่อนไปยังพิกัดแล้ว แต่โหลด Heat Map ไม่สำเร็จ", maps: "Google Maps", street: "Street View"
    },
    en: {
      label: "Search places or coordinates", go: "Search or go to coordinates", selected: "Selected location",
      placeholder: "Place name or lat, lon", searching: "Searching...", noResults: "No places found",
      searchUnavailable: "Search unavailable. Please try again.", partial: "Showing currently available results",
      partialEmpty: "Some sources are unavailable. Please try again.",
      provinceUnavailable: "Location found, but its province could not be resolved for the heat map",
      poi: "POI", competitor: "Charging station", saved: "Saved site", place: "Place",
      invalid: "Enter a valid latitude and longitude pair",
      short_url: "Short links do not contain coordinates. Copy the coordinate numbers from Google Maps.",
      outside: "Outside the Thailand map extent. Check the lat, lon order.",
      unloaded: "No heat map loaded for the selected province",
      outOfCoverage: "Outside the loaded heat map extent. Check the province and data coverage.",
      loading: "Loading the selected province's heat map", center: "Map center from the URL",
      failed: "Location selected, but the heat map could not be loaded", maps: "Google Maps", street: "Street View"
    }
  };

  function mount({ container, map, bounds, getHeatmap, onNavigate, onPoint, getProvince = () => '' }) {
    const doc = container.ownerDocument;
    const strings = () => COPY[doc.documentElement.lang === "en" ? "en" : "th"];
    container.classList.add("coordinate-search");
    const label = doc.createElement("label");
    const form = doc.createElement("form");
    const input = doc.createElement("input");
    const button = doc.createElement("button");
    const status = doc.createElement("div");
    input.id = "map-coordinate-input";
    input.type = "text";
    input.placeholder = strings().placeholder;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("autocapitalize", "off");
    input.setAttribute("enterkeyhint", "go");
    input.setAttribute("aria-describedby", "map-coordinate-status");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", "map-place-results");
    label.htmlFor = input.id;
    button.type = "submit";
    button.textContent = "\u2192";
    status.id = "map-coordinate-status";
    status.className = "coordinate-search-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const resultsBox = doc.createElement('div'); resultsBox.className = 'place-search-results'; resultsBox.hidden = true;
    const list = doc.createElement('ul'); list.id = 'map-place-results'; list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', strings().label); resultsBox.append(list);
    const credit = doc.createElement('div'); credit.className = 'place-search-credit'; credit.hidden = true;
    for (const [text, href] of [['\u00a9 MapTiler', 'https://www.maptiler.com/copyright/'], ['\u00a9 OpenStreetMap contributors', 'https://www.openstreetmap.org/copyright']]) {
      const a = doc.createElement('a'); a.textContent = text; a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; credit.append(a);
    }
    form.append(input, button);
    container.append(label, form, resultsBox, credit, status);
    let target = null, marker = null, generation = 0, loading = false;
    let suggestions = [], active = -1, searchGeneration = 0, searchTimer, searchController, composing = false;
    const places = root.THEVIPlaceSearch?.create({ getProvince, getCenter: () => map.getCenter() });

    function hideResults() {
      resultsBox.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant');
      active = -1; credit.hidden = target?.source !== 'maptiler';
    }
    function cancelSearch() {
      clearTimeout(searchTimer); searchGeneration++; searchController?.abort(); searchController = null;
    }
    function setActive(index) {
      active = index;
      Array.from(list.children).forEach((item, i) => item.setAttribute('aria-selected', String(i === active)));
      if (active >= 0) {
        input.setAttribute('aria-activedescendant', list.children[active].id);
        list.children[active].scrollIntoView({ block: 'nearest' });
      }
    }
    function showResults(rows) {
      suggestions = rows; list.replaceChildren(); active = -1;
      rows.forEach((row, index) => {
        const item = doc.createElement('li'); item.id = `map-place-option-${index}`;
        item.setAttribute('role', 'option'); item.setAttribute('aria-selected', 'false');
        const name = doc.createElement('strong'); name.textContent = row.name;
        const detail = doc.createElement('span'); detail.textContent = row.address ||
          [row.district, doc.documentElement.lang === 'en' ? row.province : row.province_th || row.province, strings()[row.kind]].filter(Boolean).join(' · ');
        item.append(name, detail);
        item.addEventListener('mousedown', event => event.preventDefault());
        item.addEventListener('click', () => navigate(row)); list.append(item);
      });
      resultsBox.hidden = !rows.length; input.setAttribute('aria-expanded', String(Boolean(rows.length)));
      credit.hidden = target?.source !== 'maptiler' && !rows.some(row => row.source === 'maptiler');
    }
    function coordinateInput(value) {
      const text = value.trim();
      return /^https?:\/\//i.test(text) || (/^[\s\d.,+\-()[\]]+$/.test(text) && /[,\s.()[\]]/.test(text));
    }
    async function search() {
      cancelSearch(); hideResults();
      const query = input.value.trim();
      if (Array.from(query).length < 2 || !places) return false;
      const request = searchGeneration, controller = new AbortController(); searchController = controller;
      const timer = setTimeout(() => controller.abort(), 12000);
      message(strings().searching);
      try {
        const result = await places.search(query, controller.signal);
        if (request !== searchGeneration || input.value.trim() !== query) return false;
        showResults(result.results);
        message(result.results.length ? (result.partial ? strings().partial : '') :
          (result.partial ? strings().partialEmpty : strings().noResults), result.partial ? 'warning' : '');
        return true;
      } catch (_) {
        if (request === searchGeneration) message(strings().searchUnavailable, 'warning');
        return false;
      } finally { clearTimeout(timer); if (request === searchGeneration) searchController = null; }
    }

    function message(text, kind = "") {
      status.textContent = text;
      status.className = `coordinate-search-status ${kind}`.trim();
    }

    function refresh() {
      const copy = strings();
      label.textContent = copy.label;
      button.title = copy.go;
      button.setAttribute("aria-label", copy.go);
      input.placeholder = copy.placeholder;
      if (!target) return;
      if (loading) { message(copy.loading); return; }
      const data = getHeatmap();
      const extent = data?.bounds;
      if (!data) { message(copy.unloaded, "warning"); return; }
      // Bounds describe loaded coverage, not whether the point has demand.
      if (extent && !(target.lat >= extent.lat_min && target.lat <= extent.lat_max &&
                       target.lon >= extent.lon_min && target.lon <= extent.lon_max)) {
        message(copy.outOfCoverage, "warning");
      } else {
        message(`${target.lat.toFixed(6)}, ${target.lon.toFixed(6)}${target.source === "map_center" ? ` | ${copy.center}` : ""}`);
      }
    }

    function popup(point) {
      const copy = strings();
      const box = doc.createElement("div");
      const title = doc.createElement("strong");
      title.textContent = point.name || (point.source === "map_center" ? copy.center : copy.selected);
      const coordinates = doc.createElement("div");
      coordinates.textContent = `${point.lat.toFixed(6)}, ${point.lon.toFixed(6)}`;
      const links = doc.createElement("div");
      links.className = "coordinate-popup-links";
      for (const [text, href] of [
        [copy.maps, `https://www.google.com/maps/search/?api=1&query=${point.lat},${point.lon}`],
        [copy.street, `https://www.google.com/maps?layer=c&cbll=${point.lat},${point.lon}&cbp=12,0,0,0,0`]
      ]) {
        const link = doc.createElement("a");
        link.textContent = text;
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        links.append(link);
      }
      box.append(title, coordinates, links);
      return box;
    }

    async function navigate(selected = null) {
      let point;
      try {
        point = selected ? { ...selected, lat: Number(selected.lat), lon: Number(selected.lon) } : parse(input.value);
        if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon)) fail('invalid');
        if (!root.L.latLngBounds(bounds).contains([point.lat, point.lon])) fail("outside");
      } catch (err) {
        input.setAttribute("aria-invalid", "true");
        message(strings()[err.message] || strings().invalid, "error");
        return false;
      }
      cancelSearch(); hideResults();
      const request = ++generation;
      target = point;
      credit.hidden = point.source !== 'maptiler';
      input.removeAttribute("aria-invalid");
      input.value = point.name || `${point.lat.toFixed(6)}, ${point.lon.toFixed(6)}`;
      if (marker) marker.remove();
      marker = root.L.marker([point.lat, point.lon], { title: strings().selected, alt: strings().selected, zIndexOffset: 1000 }).addTo(map);
      marker.bindPopup(popup(point));
      map.stop();
      map.setView([point.lat, point.lon], Math.max(15, map.getZoom()), { animate: false });
      if (onPoint) onPoint(point);
      loading = true;
      refresh();
      try {
        await onNavigate(point);
        if (request !== generation) return true;
        loading = false;
        refresh();
      } catch (error) {
        if (request !== generation) return true;
        loading = false;
        message(strings()[error.message] || strings().failed, "warning");
      }
      return true;
    }

    form.addEventListener("submit", event => {
      event.preventDefault();
      if (composing) return;
      if (!resultsBox.hidden && active >= 0) navigate(suggestions[active]);
      else if (coordinateInput(input.value)) navigate();
      else if (target?.name === input.value) navigate(target);
      else search();
    });
    input.addEventListener("paste", event => {
      const text = event.clipboardData?.getData("text");
      if (!text) return;
      event.preventDefault();
      input.value = text.trim();
      cancelSearch(); hideResults();
      if (coordinateInput(input.value)) navigate(); else search();
    });
    input.addEventListener("input", () => {
      generation++; loading = false; cancelSearch(); hideResults();
      input.removeAttribute("aria-invalid");
      message("");
      if (!composing && input.value.trim().length >= 2 && !coordinateInput(input.value)) searchTimer = setTimeout(search, 350);
    });
    input.addEventListener('compositionstart', () => { composing = true; cancelSearch(); hideResults(); });
    input.addEventListener('compositionend', () => { composing = false; input.dispatchEvent(new Event('input')); });
    input.addEventListener('keydown', event => {
      if (event.isComposing || composing) return;
      if (event.key === 'Escape') { event.preventDefault(); cancelSearch(); hideResults(); message(''); }
      if (!resultsBox.hidden && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault();
        setActive(active < 0 ? (event.key === 'ArrowDown' ? 0 : suggestions.length - 1) :
          (active + (event.key === 'ArrowDown' ? 1 : -1) + suggestions.length) % suggestions.length);
      }
    });
    doc.addEventListener('pointerdown', event => { if (!container.contains(event.target)) { cancelSearch(); hideResults(); } });
    input.addEventListener('blur', () => { setTimeout(() => { if (!container.contains(doc.activeElement)) { cancelSearch(); hideResults(); } }, 120); });
    new root.MutationObserver(refresh).observe(doc.documentElement, { attributes: true, attributeFilter: ["lang"] });
    refresh();
    return {
      navigate, refresh, getTarget: () => target,
      clear() {
        generation++; cancelSearch(); hideResults(); suggestions = [];
        target = null;
        credit.hidden = true;
        loading = false;
        if (marker) marker.remove();
        marker = null;
        input.value = "";
        input.removeAttribute("aria-invalid");
        message("");
      }
    };
  }

  const api = { parse, mount };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.MapCoordinates = api;
})(typeof window === "undefined" ? globalThis : window);

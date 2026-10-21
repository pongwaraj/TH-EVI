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
      label: "พิกัด Google Maps", go: "ไปยังพิกัด", selected: "จุดที่เลือก",
      invalid: "พิกัดไม่ถูกต้อง กรุณาระบุละติจูดและลองจิจูดให้ครบ",
      short_url: "ลิงก์แบบย่อยังระบุพิกัดไม่ได้ กรุณาคัดลอกตัวเลขพิกัดจาก Google Maps",
      outside: "พิกัดอยู่นอกขอบเขตแผนที่ประเทศไทย กรุณาตรวจลำดับ lat, lon",
      unloaded: "ยังไม่มีข้อมูล Heat Map ของจังหวัดที่เลือก",
      outOfCoverage: "จุดนี้อยู่นอกขอบเขตข้อมูล Heat Map ที่โหลด กรุณาตรวจจังหวัดและพื้นที่ข้อมูล",
      loading: "กำลังโหลด Heat Map ของจังหวัดที่เลือก", center: "ตำแหน่งกึ่งกลางแผนที่จากลิงก์",
      failed: "เลื่อนไปยังพิกัดแล้ว แต่โหลด Heat Map ไม่สำเร็จ", maps: "Google Maps", street: "Street View"
    },
    en: {
      label: "Google Maps coordinates", go: "Go to coordinates", selected: "Selected location",
      invalid: "Enter a valid latitude and longitude pair",
      short_url: "Short links do not contain coordinates. Copy the coordinate numbers from Google Maps.",
      outside: "Outside the Thailand map extent. Check the lat, lon order.",
      unloaded: "No heat map loaded for the selected province",
      outOfCoverage: "Outside the loaded heat map extent. Check the province and data coverage.",
      loading: "Loading the selected province's heat map", center: "Map center from the URL",
      failed: "Location selected, but the heat map could not be loaded", maps: "Google Maps", street: "Street View"
    }
  };

  function mount({ container, map, bounds, getHeatmap, onNavigate, onPoint }) {
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
    input.placeholder = "18.829376, 99.005497";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("autocapitalize", "off");
    input.setAttribute("enterkeyhint", "go");
    input.setAttribute("aria-describedby", "map-coordinate-status");
    label.htmlFor = input.id;
    button.type = "submit";
    button.textContent = "\u2192";
    status.id = "map-coordinate-status";
    status.className = "coordinate-search-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    form.append(input, button);
    container.append(label, form, status);
    let target = null, marker = null, generation = 0, loading = false;

    function message(text, kind = "") {
      status.textContent = text;
      status.className = `coordinate-search-status ${kind}`.trim();
    }

    function refresh() {
      const copy = strings();
      label.textContent = copy.label;
      button.title = copy.go;
      button.setAttribute("aria-label", copy.go);
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
      title.textContent = point.source === "map_center" ? copy.center : copy.selected;
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

    async function navigate() {
      let point;
      try {
        point = parse(input.value);
        if (!root.L.latLngBounds(bounds).contains([point.lat, point.lon])) fail("outside");
      } catch (err) {
        input.setAttribute("aria-invalid", "true");
        message(strings()[err.message] || strings().invalid, "error");
        return false;
      }
      const request = ++generation;
      target = point;
      input.removeAttribute("aria-invalid");
      input.value = `${point.lat.toFixed(6)}, ${point.lon.toFixed(6)}`;
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
      } catch (_) {
        if (request !== generation) return true;
        loading = false;
        message(strings().failed, "warning");
      }
      return true;
    }

    form.addEventListener("submit", event => { event.preventDefault(); navigate(); });
    input.addEventListener("paste", event => {
      const text = event.clipboardData?.getData("text");
      if (!text) return;
      event.preventDefault();
      input.value = text.trim();
      navigate();
    });
    input.addEventListener("input", () => {
      input.removeAttribute("aria-invalid");
      message("");
    });
    new root.MutationObserver(refresh).observe(doc.documentElement, { attributes: true, attributeFilter: ["lang"] });
    refresh();
    return {
      navigate, refresh, getTarget: () => target,
      clear() {
        generation++;
        target = null;
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

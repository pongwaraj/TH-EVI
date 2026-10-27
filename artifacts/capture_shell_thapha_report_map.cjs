const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const out = path.resolve('outputs/shell_thapha_owner_area_analysis');
  fs.mkdirSync(out, { recursive: true });
  const chrome = process.env.CHROMIUM_EXECUTABLE_PATH || path.join(
    process.env.ProgramFiles || 'C:/Program Files', 'Google/Chrome/Application/chrome.exe');
  const browser = await chromium.launch({ headless: true,
    ...(fs.existsSync(chrome) ? { executablePath: chrome } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1700, height: 1050 } });
    await page.goto('http://127.0.0.1:8000/planning', { waitUntil: 'networkidle' });
    await page.addStyleTag({ content: `
      body > :not(#map) { display: none !important; }
      #map { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; }
      .leaflet-control:not(.leaflet-control-scale):not(.leaflet-control-attribution) { display: none !important; }
      .leaflet-tooltip.report-label { font: bold 32px 'TH Sarabun New',Arial,sans-serif; border: 1px solid #b9c5cc; border-radius: 3px; padding: 5px 12px; box-shadow:none; color: #111; background: white; }
      .leaflet-control-attribution { font-size: 18px !important; background: white !important; }
      .leaflet-control-scale-line { font: 20px Arial,sans-serif !important; line-height: 24px !important; }
    `});
    await page.evaluate(() => {
      map.eachLayer(layer => { if (!(layer instanceof L.TileLayer)) map.removeLayer(layer); });
      map.invalidateSize();
      const markers = [
        { lat:17.650561, lon:99.249117, label:'S  เชลล์ ท่าผา', color:'#ef5b16', side:'right', radius:13 },
        { lat:17.637890, lon:99.239540, label:'P1  โรงพยาบาลเถิน', color:'#00828c', side:'left', radius:9 },
        { lat:17.621402, lon:99.236659, label:'P2  จุดขึ้นรถโดยสารเถิน', color:'#00828c', side:'right', radius:9 },
        { lat:17.6198278,lon:99.2336486,color:'#702790',radius:8 },
        { lat:17.618580,lon:99.234230,color:'#702790',radius:8 },
        { lat:17.617992,lon:99.232432,color:'#702790',radius:8 },
        { lat:17.578923,lon:99.210652,label:'C4  Spark เถิน นภา',color:'#702790',side:'right',radius:9 },
      ];
      for (const m of markers) {
        const dot = L.circleMarker([m.lat,m.lon], { radius:m.radius, color:'#fff', weight:3,
          fillColor:m.color, fillOpacity:1 }).addTo(map);
        if (m.label) dot.bindTooltip(m.label,{ permanent:true,direction:m.side,
          offset:[m.side === 'left' ? -12 : 12,0],className:'report-label' });
      }
      L.marker([17.6186,99.2324],{opacity:0,interactive:false}).addTo(map)
        .bindTooltip('C1-C3  กลุ่มสถานีชาร์จเถิน',{permanent:true,direction:'left',offset:[-18,22],className:'report-label'});
      L.control.scale({ imperial:false, maxWidth:180 }).addTo(map);
      map.fitBounds(markers.map(m=>[m.lat,m.lon]),{padding:[85,65],maxZoom:14,animate:false});
    });
    await page.waitForTimeout(2200);
    const tiles = await page.locator('.leaflet-tile').evaluateAll(rows => rows.filter(r => r.complete && r.naturalWidth > 0).length);
    assert(tiles > 5, 'Real map tiles must load');
    await page.locator('#map').screenshot({ path:path.join(out,'site_context_map.png') });
    console.log(JSON.stringify({tiles,zoom:await page.evaluate(()=>map.getZoom()),output:path.join(out,'site_context_map.png')}));
  } finally { await browser.close(); }
})().catch(error=>{ console.error(error);process.exitCode=1; });

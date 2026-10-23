const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.TH_EVI_BASE_URL || 'http://127.0.0.1:8000';
const output = path.resolve('outputs/map-layers-qa');
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    for (const workspace of ['planning', 'analysis']) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ignoreHTTPSErrors: true });
      const page = await context.newPage();
      const errors = [], mutations = [], requests = [];
      let failPois = false;
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', async route => {
        const request = route.request(), url = new URL(request.url()), province = url.searchParams.get('province');
        if (request.method() !== 'GET') mutations.push(url.pathname);
        if (url.pathname === '/api/pois') {
          requests.push(`pois:${province}`);
          if (failPois) return route.fulfill({ status: 503, json: { detail: 'Offline test' } });
          if (province === 'Chiang Rai') await new Promise(resolve => setTimeout(resolve, 350));
          return route.fulfill({ json: { province, pois: province === 'Phayao' ? [] : [
            { poi_id: 'retail', name: `${province} Mall`, category: 'community_mall', lat: 18.8, lon: 99.01, verification_status: 'verified' },
            { poi_id: 'unsafe', name: '<img src=x onerror="window.__xss=true">', category: 'cafe', lat: 18.81, lon: 99.02 },
            { poi_id: 'invalid', name: 'Invalid', lat: null, lon: 99 },
          ] } });
        }
        if (url.pathname === '/api/chargers') {
          requests.push(`chargers:${province}`);
          return route.fulfill({ json: { province, stations: [
            { station_id: 'charger', name: `${province} Charger`, network: 'Test', lat: 18.802, lon: 99.012,
              max_kw: null, capacity: 2, charging_type: 'unknown', verification_status: 'unverified' },
          ] } });
        }
        let json = {};
        if (url.pathname === '/api/reference/meta') json = { layers: { pois: { label_th: 'POI', form_fields: [] } } };
        else if (url.pathname.startsWith('/api/reference/')) json = { records: [], total: 0 };
        else if (url.pathname === '/api/sites' || url.pathname === '/api/planning-shortlist') json = { sites: [] };
        return route.fulfill({ json });
      });
      await page.goto(`${base}/${workspace}`, { waitUntil: 'networkidle' });
      const pois = page.locator('[data-map-layer="pois"]'), chargers = page.locator('[data-map-layer="competitors"]');
      const heat = page.locator('[data-map-layer="heat"]');
      assert.equal(await pois.isChecked(), false);
      assert.equal(await chargers.isChecked(), false);
      assert.equal(requests.length, 0, 'Reference markers load only when enabled');
      await page.evaluate(() => {
        map.setView([18.8, 99.01], 14, { animate: false });
        L.rectangle([[18.79, 99], [18.82, 99.03]], { color: '#f8961e' }).addTo(heatmapLayer);
      });
      await pois.check();
      await page.waitForFunction(workspace => (workspace === 'planning' ? poiLayer : landmarkLayer).getLayers().length === 2, workspace);
      const before = await page.evaluate(() => [map.getCenter().lat, map.getCenter().lng, map.getZoom()]);
      await chargers.check();
      await page.waitForFunction(workspace => (workspace === 'planning' ? competitorLayer : chargerLayer).getLayers().length === 1, workspace);
      assert.deepEqual(await page.evaluate(() => [map.getCenter().lat, map.getCenter().lng, map.getZoom()]), before);
      assert.equal(await page.evaluate(() => map.getPane('referenceMarkers').style.zIndex), '450');
      await heat.uncheck();
      assert.equal(await page.evaluate(() => map.hasLayer(heatmapLayer)), false);
      assert.equal(await page.evaluate(() => heatmapLayer.getLayers().length), 1, 'Hiding heat keeps its data');
      await heat.check();
      await page.evaluate(workspace => (workspace === 'planning' ? competitorLayer : chargerLayer).getLayers()[0].fire('click'), workspace);
      await page.getByRole('link', { name: 'Google Maps', exact: true }).waitFor();
      const popupText = await page.locator('.map-reference-popup').textContent();
      assert.match(popupText, /ยังไม่ยืนยันกำลังไฟ/);
      assert.doesNotMatch(popupText, /2 kW/);
      assert.match(await page.getByRole('link', { name: 'Google Maps', exact: true }).getAttribute('href'), /18.802,99.012/);
      assert.match(await page.getByRole('link', { name: 'Street View', exact: true }).getAttribute('href'), /cbll=18.802,99.012/);
      await page.evaluate(workspace => {
        map.closePopup();
        (workspace === 'planning' ? poiLayer : landmarkLayer).getLayers()[1].fire('click');
      }, workspace);
      await page.waitForTimeout(350);
      assert.equal(await page.locator('.map-reference-popup img').count(), 0);
      assert.equal(await page.evaluate(() => window.__xss), undefined);
      await page.evaluate(() => map.closePopup());
      await page.waitForTimeout(350);
      await pois.uncheck(); await pois.check();
      assert.equal(requests.filter(value => value.startsWith('pois:')).length, 1, 'Toggling a loaded layer uses memory');
      await page.screenshot({ path: path.join(output, `${workspace}-desktop.png`) });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.evaluate(() => map.invalidateSize());
      await page.waitForTimeout(300);
      assert.equal(await page.locator('.map-layers-control').evaluate(el => {
        const box = el.getBoundingClientRect(), map = document.getElementById('map').getBoundingClientRect();
        return box.left >= map.left && box.right <= map.right && box.bottom <= map.bottom;
      }), true, 'Layer controls fit on mobile');
      await page.screenshot({ path: path.join(output, `${workspace}-mobile.png`) });
      await page.locator('.map-layers-control summary').click();
      assert.equal(await pois.isVisible(), false);
      await page.locator('.map-layers-control summary').click();

      // Clear old markers immediately and ignore late responses after province changes.
      await page.evaluate(() => { mapLayers.setProvince('Chiang Rai'); });
      assert.equal(await page.evaluate(workspace => (workspace === 'planning' ? poiLayer : landmarkLayer).getLayers().length, workspace), 0);
      await page.evaluate(() => mapLayers.setProvince('Lampang'));
      await page.waitForTimeout(400);
      assert.match(await page.evaluate(workspace => (workspace === 'planning' ? poiLayer : landmarkLayer).getLayers()[0].getTooltip().getContent().textContent, workspace), /^Lampang/);
      await page.evaluate(() => mapLayers.setProvince('Phayao'));
      assert.match(await page.locator('.map-layers-control').textContent(), /ไม่มีข้อมูล/);
      failPois = true;
      await page.evaluate(() => mapLayers.setProvince('Nan'));
      assert.match(await page.locator('.map-layers-control').textContent(), /โหลดไม่สำเร็จ/);
      failPois = false;
      await page.getByRole('button', { name: 'ลองใหม่', exact: true }).click();
      await page.waitForFunction(workspace => (workspace === 'planning' ? poiLayer : landmarkLayer).getLayers().length === 2, workspace);
      assert.deepEqual(errors, []);
      assert.deepEqual(mutations, []);
      await page.reload({ waitUntil: 'networkidle' });
      assert.equal(await pois.isChecked(), true, 'Layer visibility survives a reload');
      assert.equal(await chargers.isChecked(), true);
      console.log(`PASS ${workspace}: toggles, lazy/cache, popups, safe text, stale provinces, retry/empty, desktop/mobile, persistence`);
      await context.close();
    }
    if (process.env.TH_EVI_LIVE_LAYERS === '1') {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ignoreHTTPSErrors: true });
      const page = await context.newPage();
      await page.goto(`${base}/planning`, { waitUntil: 'networkidle' });
      await page.locator('[data-map-layer="pois"]').check();
      await page.locator('[data-map-layer="competitors"]').check();
      await page.waitForFunction(() => poiLayer.getLayers().length > 0 && competitorLayer.getLayers().length > 0, null, { timeout: 60000 });
      await page.evaluate(() => loadHeatmap());
      await page.evaluate(() => map.setView([18.81, 99.015], 13, { animate: false }));
      await page.waitForTimeout(700);
      assert.equal(await page.evaluate(() => map.hasLayer(poiLayer) && map.hasLayer(competitorLayer) && heatmapLayer.getLayers().length > 0), true);
      console.log('PASS live Chiang Mai:', await page.evaluate(() => ({ pois: poiLayer.getLayers().length, competitors: competitorLayer.getLayers().length })));
      await page.screenshot({ path: path.join(output, 'planning-live-chiang-mai.png') });
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

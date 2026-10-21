// Run against a local TH-EVI server; browser/runtime paths can be overridden.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.TH_EVI_BASE_URL || 'http://127.0.0.1:8000';
const output = path.resolve('outputs/site-forecast-qa');
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    for (const workspace of ['planning', 'analysis']) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ignoreHTTPSErrors: true });
      const page = await context.newPage();
      const requests = [], errors = [], mutations = [];
      let mode = 'ready';
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.pathname === '/api/charging-demand/site-preview') {
          const body = request.postDataJSON(); requests.push(body);
          if (mode === 'unsupported') return route.fulfill({ status: 422, json: { detail: 'No reference profile for province' } });
          if (mode === 'slow') await new Promise(resolve => setTimeout(resolve, body.lat === 18.83 ? 400 : 20));
          return route.fulfill({ json: { estimate_available: true, forecast_available: false,
            assumptions: { average_session_kwh: 27 }, missing_competitor_evidence: [],
            scenarios: [{ estimated_charging_visits_per_day: body.lat === 18.83 ? 99.1 : 12.6,
              site_served_connector_kwh_per_day: 340.2, capacity_limited: false }] } });
        }
        if (request.method() !== 'GET') mutations.push(url.pathname);
        let json = {};
        if (url.pathname === '/api/reference/meta') json = { layers: { pois: { label_th: 'POI', form_fields: [] } }, provinces: [{ en: 'Chiang Mai', th: 'เชียงใหม่' }] };
        else if (url.pathname.startsWith('/api/reference/')) json = { records: [], total: 0 };
        else if (url.pathname === '/api/landmarks') json = [];
        else if (url.pathname === '/api/chargers') json = { stations: [] };
        else if (url.pathname === '/api/sites' || url.pathname === '/api/planning-shortlist') json = { sites: [] };
        return route.fulfill({ json });
      });
      await page.goto(`${base}/${workspace}`, { waitUntil: 'networkidle' });
      assert.equal(await page.locator('[data-sf="power"]').inputValue(), '120');
      assert.equal(await page.locator('[data-sf="cabinets"]').inputValue(), '1');
      assert.equal(await page.locator('[data-sf="bays"]').inputValue(), '2');
      const openPoint = async lat => page.evaluate(({ workspace, lat }) => {
        const point = { lat, lon: 99.005497, display_intensity: .6, demand_score: 1.23, competition_score: .4,
          net_opportunity_score: .83, forecast_available: false, score_semantics: 'normalized_screening_share_percent' };
        if (workspace === 'planning') {
          const data = { province: 'Chiang Mai', year: 2026, lat_step_deg: .009, lon_step_deg: .009,
            metadata: { score_semantics: 'normalized_screening_share_percent' }, max_scores: { demand: 2, net: 2 } };
          latestHeatmapData = data;
          heatmapLayer.clearLayers();
          map.setView([lat, 99.005497], 15);
          attachCell(point, data);
          heatmapLayer.getLayers()[0].fire('click', { latlng: L.latLng(lat + .0001, 99.005597) });
        } else {
          map.setView([lat, 99.005497], 15);
          showAreaDemandPopup(lat, 99.005497, point);
        }
      }, { workspace, lat });
      await openPoint(18.829376);
      await page.waitForTimeout(400);
      await page.waitForSelector('[data-estimate-status="ready"]');
      assert.equal(await page.locator('[data-sf-visits]').textContent(), '13');
      assert.equal(requests[0].station.total_site_kw, 120);
      assert.equal(requests[0].station.guns, 2);
      assert.equal(requests[0].average_session_kwh, null);
      if (workspace === 'planning') assert.ok(Math.abs(requests[0].lat - 18.829476) < 1e-10);
      await page.locator('[data-sf="cabinets"]').fill('2');
      await page.locator('[data-sf="cabinets"]').dispatchEvent('change');
      await page.waitForFunction(() => document.querySelector('[data-sf-spec]')?.textContent.includes('4 ช่องจอด'));
      assert.equal(requests.at(-1).station.total_site_kw, 240);
      assert.equal(requests.at(-1).station.guns, 4);
      await page.screenshot({ path: path.join(output, `${workspace}-desktop.png`) });
      await page.locator('[data-sf="enabled"]').uncheck();
      assert.equal(await page.locator('[data-site-forecast]').isVisible(), false);
      await page.locator('[data-sf="enabled"]').check();
      await page.waitForSelector('[data-estimate-status="ready"]');
      mode = 'unsupported';
      await page.locator('[data-sf="power"]').selectOption('180');
      await page.waitForSelector('[data-estimate-status="unavailable"]');
      assert.equal(await page.locator('[data-sf-visits]').count(), 0);
      assert.match(await page.locator('[data-site-forecast]').textContent(), /ยังไม่มีข้อมูลสถานีอ้างอิง/);

      // Request races must not replace the latest clicked point with an older response.
      mode = 'slow';
      await page.evaluate(() => {
        const root = document.querySelector('[data-site-forecast]');
        THEVISiteForecast.renderInto(root, { province: 'Chiang Mai', year: 2026, lat: 18.83, lon: 99 });
      });
      await page.waitForTimeout(50);
      await page.evaluate(() => THEVISiteForecast.renderInto(document.querySelector('[data-site-forecast]'),
        { province: 'Chiang Mai', year: 2026, lat: 18.84, lon: 99 }));
      await page.waitForSelector('[data-estimate-status="ready"]');
      await page.waitForTimeout(450);
      assert.equal(await page.locator('[data-sf-visits]').textContent(), '13');
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator('#site-forecast-settings').scrollIntoViewIfNeeded();
      assert.equal(await page.locator('#site-forecast-settings').evaluate(host =>
        [...host.querySelectorAll('input,select')].filter(el => el.getClientRects().length)
          .every(el => el.getBoundingClientRect().right <= host.getBoundingClientRect().right + 1)), true);
      await page.locator('#site-forecast-settings').screenshot({ path: path.join(output, `${workspace}-mobile-settings.png`) });
      await page.evaluate(() => map.invalidateSize());
      await openPoint(18.829376);
      await page.waitForTimeout(400);
      await page.waitForSelector('[data-estimate-status="ready"]');
      await page.waitForTimeout(300);
      assert.equal(await page.locator('.leaflet-popup').evaluate(popup => {
        const bounds = popup.getBoundingClientRect(), mapBounds = document.getElementById('map').getBoundingClientRect();
        return bounds.left >= mapBounds.left && bounds.right <= mapBounds.right && bounds.top >= mapBounds.top;
      }), true, 'Mobile popup stays within the map');
      await page.locator('.leaflet-popup').screenshot({ path: path.join(output, `${workspace}-mobile-popup.png`) });
      await page.locator('details:has([data-sf="activeKw"])').evaluate(el => { el.open = true; });
      await page.locator('[data-sf="power"]').selectOption('30');
      assert.equal(await page.locator('[data-sf="activeKw"]').inputValue(), '30');
      await page.locator('[data-sf="publicAccess"]').uncheck();
      await page.waitForSelector('[data-estimate-status="unavailable"]');
      assert.match(await page.locator('[data-site-forecast]').textContent(), /ไม่ได้เปิดให้บุคคลทั่วไป/);
      assert.deepEqual(errors, []);
      assert.deepEqual(mutations, [], 'Estimates must not create candidate records');
      console.log(`PASS ${workspace}: station defaults, exact coordinates, settings, units, unsupported data, races, mobile, no mutations`);
      await context.close();
    }
    if (process.env.TH_EVI_LIVE_SITE_FORECAST === '1') {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ignoreHTTPSErrors: true });
      const page = await context.newPage();
      await page.goto(`${base}/planning`, { waitUntil: 'networkidle' });
      await page.evaluate(() => loadHeatmap());
      const response = page.waitForResponse(r => r.url().includes('/api/charging-demand/site-preview'), { timeout: 90000 });
      await page.evaluate(() => {
        const lat = 18.829376, lon = 99.005497;
        map.setView([lat, lon], 15);
        const rectangle = heatmapLayer.getLayers().find(layer => layer.getBounds().contains([lat, lon]));
        if (!rectangle) throw new Error('Tanawan Park must have an actual heat cell');
        rectangle.fire('click', { latlng: L.latLng(lat, lon) });
      });
      const result = await (await response).json();
      await page.waitForSelector('[data-estimate-status="ready"]', { timeout: 90000 });
      assert.equal(result.forecast_available, false);
      assert.equal(result.assumptions.station.total_site_kw, 120);
      assert.equal(await page.locator('[data-sf-visits]').textContent(),
        Math.round(result.scenarios[0].estimated_charging_visits_per_day).toLocaleString('th-TH'));
      await page.screenshot({ path: path.join(output, 'planning-live-tanawan.png') });
      console.log(`PASS live Tanawan Park: ${result.scenarios[0].estimated_charging_visits_per_day.toFixed(2)} visits/day, default 120 kW / 2 bays`);
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.TH_EVI_BASE_URL || 'http://127.0.0.1:8000';
const output = path.resolve('outputs/place-search-qa');
fs.mkdirSync(output, { recursive: true });
const cm = { id: 'cm', name: 'กาดฝรั่ง แม่ริม', province: 'Chiang Mai', province_th: 'เชียงใหม่',
  lat: 18.901599, lon: 98.948483, district: 'แม่ริม', kind: 'poi', source: 'th_evi' };
const cr = { ...cm, id: 'cr', name: 'Mall Chiang Rai', province: 'Chiang Rai', province_th: 'เชียงราย',
  lat: 19.91, lon: 99.84, district: 'เมืองเชียงราย' };

function heat(url) {
  const p = new URL(url).searchParams;
  return { province: p.get('province'), year: Number(p.get('year')), scenario: p.get('scenario'),
    mode: p.get('mode'), resolution_km: Number(p.get('resolution_km')),
    bounds: { lat_min: 18, lat_max: 21, lon_min: 98, lon_max: 101 }, lat_step_deg: .009, lon_step_deg: .01,
    point_count: 1, max_scores: { demand: 70, net: 50 }, max_heat_score: 50, district_summaries: [], zones: [],
    metadata: { production_method: 'fixed_support_area_v1', density_max_scores: { demand: 70, net: 50, competition: 20 } },
    points: [{ lat: cm.lat, lon: cm.lon, cell_id: 'a', support_ids: ['a'], demand_score: 70, competition_score: 20, net_opportunity_score: 50 }] };
}

async function selected(page, point) {
  await page.waitForFunction(p => Math.abs(map.getCenter().lat - p.lat) < .0001 &&
    Math.abs(map.getCenter().lng - p.lon) < .0001, point);
}

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    for (const workspace of ['planning', 'analysis']) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ignoreHTTPSErrors: true });
      const page = await context.newPage(), errors = [], mutations = [], searches = [], heatRequests = [];
      let external = false;
      page.on('pageerror', e => errors.push(e.message));
      await page.route('**/api/**', async route => {
        const req = route.request(), url = new URL(req.url());
        if (req.method() !== 'GET') mutations.push(req.method() + ' ' + url.pathname);
        let json = {};
        if (url.pathname === '/api/place-search/config') json = { external: external ? { provider: 'maptiler', public_key: 'test-public' } : null };
        else if (url.pathname === '/api/place-search') {
          const q = url.searchParams.get('q'); searches.push(q);
          if (q === 'offline') return route.fulfill({ status: 503, json: {} });
          if (q === 'slow') await new Promise(resolve => setTimeout(resolve, 700));
          let results = q === 'none' || q === 'external' ? [] : q === 'cross' ? [cr] : [cm];
          if (q.includes('Kad Farang')) results = [{ ...cm, name: 'The Kad Farang Mae Rim' }];
          if (q === 'unsafe') results = [{ ...cm, name: '<img src=x onerror="window.__placeXss=true">' }];
          return route.fulfill({ json: { results, partial: false } }).catch(() => {});
        } else if (url.pathname === '/api/heatmap') {
          heatRequests.push(url.searchParams.get('province')); json = heat(req.url());
        } else if (url.pathname === '/api/reference/meta') json = { layers: { pois: { form_fields: [] } } };
        else if (url.pathname.startsWith('/api/reference/')) json = { records: [], total: 0 };
        else if (url.pathname === '/api/sites' || url.pathname === '/api/planning-shortlist') json = { sites: [] };
        else if (url.pathname === '/api/chargers') json = { stations: [] };
        else if (url.pathname === '/api/pois') json = { pois: [] };
        return route.fulfill({ json });
      });
      await page.route('https://api.maptiler.com/**', route => {
        const url = new URL(route.request().url());
        assert.equal(url.searchParams.get('country'), 'th');
        return route.fulfill({ json: { features: [{ id: 'poi.example', text: 'External Cafe',
          place_name: 'External Cafe, Chiang Rai, Thailand', center: [cr.lon, cr.lat], place_type: ['poi'],
          context: [{ id: 'region.cr', text: 'Chiang Rai' }] }] } });
      });
      await page.goto(`${base}/${workspace}`, { waitUntil: 'networkidle' });
      const input = page.locator('#map-coordinate-input'), list = page.locator('#map-place-results');
      const before = await page.evaluate(() => [map.getCenter().lat, map.getCenter().lng]);
      await input.fill('กาดฝรั่ง แม่ริม');
      await page.getByRole('option', { name: /กาดฝรั่ง/ }).waitFor();
      assert.deepEqual(await page.evaluate(() => [map.getCenter().lat, map.getCenter().lng]), before, 'Suggestions never move the map');
      await input.press('ArrowDown'); await input.press('Enter');
      await selected(page, cm);
      assert.equal(await input.inputValue(), cm.name);
      assert.equal(await input.getAttribute('aria-expanded'), 'false');
      await page.waitForFunction(() => latestHeatmapData?.point_count === 1);

      if (workspace === 'analysis') await page.locator('#lang-en').click();
      await input.fill('Kad Farang Mae Rim');
      await page.getByRole('option', { name: /The Kad Farang Mae Rim/ }).waitFor();
      await input.press('ArrowUp'); await input.press('Enter'); await selected(page, cm);
      if (workspace === 'analysis') {
        assert.equal(await page.locator('label[for="map-coordinate-input"]').textContent(), 'Search places or coordinates');
        await page.locator('#lang-th').click();
      }

      await input.fill('cross'); await page.getByRole('option', { name: /Mall Chiang Rai/ }).click();
      await selected(page, cr);
      await page.waitForFunction(() => latestHeatmapData?.province === 'Chiang Rai');
      assert(heatRequests.includes('Chiang Rai'));
      assert.equal(await page.locator(workspace === 'planning' ? '#province' : '#heatmap-province').inputValue(), 'เชียงราย');

      await input.fill('none');
      await page.waitForFunction(() => document.getElementById('map-coordinate-status').textContent === 'ไม่พบสถานที่');
      assert.equal(await list.isVisible(), false);
      await selected(page, cr);
      await input.fill('offline');
      await page.waitForFunction(() => document.getElementById('map-coordinate-status').textContent.includes('ค้นหาไม่สำเร็จ'));
      assert.equal(await list.isVisible(), false);

      await input.fill('slow'); await page.waitForTimeout(400); await input.fill('fast');
      await page.getByRole('option', { name: /กาดฝรั่ง/ }).waitFor();
      await page.waitForTimeout(750);
      assert.equal(await input.inputValue(), 'fast');
      await input.press('Escape');
      assert.equal(await input.getAttribute('aria-expanded'), 'false');
      await input.fill('unsafe'); await page.getByRole('option', { name: /img src/ }).waitFor();
      assert.equal(await list.locator('img').count(), 0);
      assert.equal(await page.evaluate(() => window.__placeXss), undefined);

      // Thai IME composition must finish before querying.
      const count = searches.length;
      await input.evaluate(el => {
        el.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
        el.value = 'ไทย'; el.dispatchEvent(new Event('input', { bubbles: true }));
      });
      await page.waitForTimeout(450); assert.equal(searches.length, count);
      await input.evaluate(el => el.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
      await page.getByRole('option', { name: /กาดฝรั่ง/ }).waitFor();
      await input.fill('7-11'); await page.getByRole('option', { name: /กาดฝรั่ง/ }).waitFor();
      assert(searches.includes('7-11'), 'Numeric store names are searched, not mistaken for coordinates');

      await input.fill('กาดฝรั่ง'); await page.getByRole('option', { name: /กาดฝรั่ง/ }).waitFor();
      await page.screenshot({ path: path.join(output, `${workspace}-desktop.png`) });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator('#coordinate-search').scrollIntoViewIfNeeded();
      assert.equal(await page.locator('#coordinate-search').evaluate(el => el.scrollWidth <= el.clientWidth + 1), true);
      await page.locator('#coordinate-search').screenshot({ path: path.join(output, `${workspace}-mobile-control.png`) });
      await page.getByRole('option', { name: /กาดฝรั่ง/ }).click(); await selected(page, cm);

      external = true;
      await page.reload({ waitUntil: 'networkidle' });
      await input.fill('external'); await page.getByRole('option', { name: /External Cafe/ }).waitFor();
      assert.equal(await page.locator('.place-search-credit').isVisible(), true);
      await page.getByRole('option', { name: /External Cafe/ }).click(); await selected(page, cr);
      assert.equal(await page.locator('.place-search-credit').isVisible(), true);
      assert.equal(await page.evaluate(() => Object.keys(localStorage).some(k => /place-search/.test(k))), false);
      assert.deepEqual(errors, []); assert.deepEqual(mutations, []);
      console.log(`PASS ${workspace}: Thai/English UI, explicit selection, cross-province heat, empty/error, stale/IME/XSS, mobile, optional external attribution`);
      await context.close();
    }
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await page.goto(`${base}/planning`, { waitUntil: 'networkidle' });
    await page.locator('#map-coordinate-input').fill('กาดฝรั่ง แม่ริม');
    await page.getByRole('option', { name: /กาดฝรั่ง แม่ริม/ }).first().waitFor({ timeout: 30000 });
    await page.screenshot({ path: path.join(output, 'planning-live-local-results.png') });
    await page.getByRole('option', { name: /กาดฝรั่ง แม่ริม/ }).first().click();
    await selected(page, cm);
    await page.waitForFunction(() => latestHeatmapData?.point_count > 0 && heatmapLayer.getLayers().length > 0,
      null, { timeout: 60000 });
    await page.screenshot({ path: path.join(output, 'planning-live-selected.png') });
    await page.close();
    console.log('PASS live local bilingual inventory');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

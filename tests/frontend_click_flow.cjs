// Run against a local server with Playwright installed. Optional overrides:
// PLAYWRIGHT_MODULE, CHROMIUM_EXECUTABLE_PATH, TH_EVI_BASE_URL.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? {executablePath: process.env.CHROMIUM_EXECUTABLE_PATH} : {})});
  try {
    const page = await browser.newPage({ignoreHTTPSErrors: true, viewport: {width: 1440, height: 1000}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${process.env.TH_EVI_BASE_URL || 'http://127.0.0.1:8000'}/analysis`, {waitUntil: 'domcontentloaded'});
    await page.waitForFunction(() => typeof quickEstimate === 'function' && typeof map !== 'undefined');
    await page.evaluate(() => {
      document.getElementById('show_point_forecast').checked = false;
      document.getElementById('year').value = '2026';
      document.getElementById('heatmap_resolution').value = '1';
      document.getElementById('scenario').value = 'base';
      document.getElementById('heatmap_mode').value = 'urban';
      latestHeatmapData = {
        province: apiProvinceValue(), year: 2026, scenario: 'base', mode: 'urban', resolution_km: 1,
        lat_step_deg: 0.1, lon_step_deg: 0.1,
        metadata: {production_method: 'fixed_support_area_v1'},
        points: [{lat: 18.85, lon: 99.05, cell_id: '188:990',
          coverage_fragments: [[[18.8,99],[18.9,99.1]]], forecast_available: false,
          score_semantics: 'normalized_screening_share_percent', demand_score: 77,
          competition_score: 7, net_opportunity_score: 70}]
      };
    });
    let requests = 0;
    let hold = false;
    let heldRoute;
    let onHeld;
    const outside = {forecast_available: false, eligibility_status: 'outside_support',
      demand_score: 0, competition_score: 0, net_opportunity_score: 0,
      score_semantics: 'normalized_screening_share_percent', resolution_km: 1};
    await page.route('**/api/click-analysis', async route => {
      requests++;
      if (hold) { heldRoute = route; onHeld(); return; }
      await route.fulfill({json: outside});
    });
    const popup = () => page.evaluate(() => estimateMarker.getPopup().getContent());
    await page.evaluate(() => quickEstimate(18.85, 99.05));
    assert.equal(requests, 0, 'Covered pilot cell should reuse its own cached score');
    assert.match(await popup(), /77/);

    await page.evaluate(() => quickEstimate(18.85, 99.101));
    assert.equal(requests, 1, 'Outside click must query backend, not borrow a neighbouring score');
    assert.match(await popup(), /พิกัดนี้อยู่นอกพื้นที่/);
    assert.doesNotMatch(await popup(), /77/);

    await page.evaluate(() => { document.getElementById('year').value = '2027'; });
    await page.evaluate(() => quickEstimate(18.85, 99.05));
    assert.equal(requests, 2, 'A different year must not reuse cached scores');
    await page.evaluate(() => { document.getElementById('year').value = '2026'; });

    hold = true;
    let held = new Promise(resolve => { onHeld = resolve; });
    await page.evaluate(() => { window.pendingClick = quickEstimate(18.85, 99.101); });
    await held;
    await page.evaluate(() => quickEstimate(18.85, 99.05));
    await heldRoute.fulfill({json: {...outside, demand_score: 999}});
    await page.evaluate(() => window.pendingClick);
    assert.match(await popup(), /77/, 'Older response must not overwrite a newer cached click');
    assert.doesNotMatch(await popup(), /999/);

    held = new Promise(resolve => { onHeld = resolve; });
    await page.evaluate(() => { window.pendingClick = quickEstimate(18.85, 99.101); });
    await held;
    await page.evaluate(() => closeEstimate());
    await heldRoute.fulfill({json: outside});
    await page.evaluate(() => window.pendingClick);
    assert.equal(await page.evaluate(() => estimateMarker === null && !map._popup?.isOpen()), true,
      'Closing the popup must invalidate an in-flight request');
    assert.deepEqual(errors, []);
    console.log('PASS: actual browser cached cell, outside support, changed year, stale response, closed popup');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

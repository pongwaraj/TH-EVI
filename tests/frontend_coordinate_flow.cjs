// Run with TH_EVI_BASE_URL and PLAYWRIGHT_MODULE overrides when needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.TH_EVI_BASE_URL || 'http://127.0.0.1:8000';
const output = path.resolve('outputs/coordinate-search-qa');
fs.mkdirSync(output, {recursive:true});

function surface(url) {
  const p = new URL(url).searchParams;
  return {
    province:p.get('province'), year:Number(p.get('year')), scenario:p.get('scenario'),
    mode:p.get('mode'), resolution_km:Number(p.get('resolution_km')),
    bounds:{lat_min:18.65,lat_max:18.95,lon_min:98.9,lon_max:99.15},
    lat_step_deg:.009,lon_step_deg:.0095,point_count:2,
    max_scores:{demand:70,net:50},max_heat_score:50,district_summaries:[],zones:[],
    metadata:{production_method:'fixed_support_area_v1',score_semantics:'normalized_screening_share_percent',
      density_max_scores:{demand:70,net:50,competition:20},heatmap_exclusion_count:0},
    points:[{lat:18.829376,lon:99.005497,cell_id:'a',support_ids:['a'],demand_score:70,competition_score:20,net_opportunity_score:50},
      {lat:18.831,lon:99.011,cell_id:'b',support_ids:['b'],demand_score:45,competition_score:15,net_opportunity_score:30}]
  };
}

async function paste(page, value) {
  await page.locator('#map-coordinate-input').evaluate((input, value) => {
    const clipboardData = new DataTransfer();
    clipboardData.setData('text/plain', value);
    input.focus();
    input.dispatchEvent(new ClipboardEvent('paste', {clipboardData,bubbles:true,cancelable:true}));
  }, value);
}

async function locationIs(page, lat, lon) {
  await page.waitForFunction(({lat,lon}) => Math.abs(map.getCenter().lat-lat)<.0001 &&
    Math.abs(map.getCenter().lng-lon)<.0001, {lat,lon});
}

(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? {executablePath:process.env.CHROMIUM_EXECUTABLE_PATH} : {})});
  try {
    for (const workspace of ['planning','analysis']) {
      const context = await browser.newContext({viewport:{width:1440,height:1000},ignoreHTTPSErrors:true});
      const page = await context.newPage();
      let heatRequests=0, failHeat=false;
      const errors=[], mutations=[];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', async route => {
        const request=route.request(), url=new URL(request.url());
        if (request.method()!=='GET') mutations.push(request.method()+' '+url.pathname);
        if (url.pathname==='/api/heatmap') {
          heatRequests++;
          await new Promise(resolve => setTimeout(resolve, 150));
          return route.fulfill(failHeat ? {status:500,body:'offline test'} : {json:surface(request.url())});
        }
        let json={};
        if (url.pathname==='/api/reference/meta') json={layers:{pois:{label_th:'POI',form_fields:[]}},provinces:[{en:'Chiang Mai',th:'เชียงใหม่'}]};
        else if (url.pathname.startsWith('/api/reference/')) json={records:[],total:0};
        else if (url.pathname==='/api/landmarks') json=[];
        else if (url.pathname==='/api/chargers') json={stations:[]};
        else if (url.pathname==='/api/planning-shortlist') json={sites:[]};
        else if (url.pathname==='/api/sites') json={sites:[]};
        return route.fulfill({json});
      });
      await page.goto(`${base}/${workspace}`,{waitUntil:'networkidle'});
      await page.waitForSelector('#map-coordinate-input');
      const existingMarkers = await page.evaluate(() => Object.values(map._layers).filter(l => l instanceof L.Marker).length);
      await paste(page,'18.829376, 99.005497');
      await locationIs(page,18.829376,99.005497);
      await page.waitForFunction(() => latestHeatmapData?.point_count===2);
      await page.waitForFunction(() => !document.getElementById('map-coordinate-status').textContent.includes('กำลังโหลด'));
      await locationIs(page,18.829376,99.005497);
      assert.equal(heatRequests,1,'Pasting without data loads the selected heat map');
      assert.equal(await page.evaluate(() => heatmapLayer.getLayers().length>0),true);
      assert.equal(await page.evaluate(() => map.getZoom()>=15),true);

      await paste(page,'(18.831000, 99.011000)');
      await locationIs(page,18.831,99.011);
      assert.equal(heatRequests,1,'A loaded province surface is retained');
      assert.equal(await page.evaluate(() => Object.values(map._layers).filter(l => l instanceof L.Marker).length),existingMarkers+1);

      await page.locator('#map-coordinate-input').fill('18.829376\t99.005497');
      await page.locator('#map-coordinate-input').press('Enter');
      await locationIs(page,18.829376,99.005497);
      await page.locator('#map-coordinate-input').fill('18.831,99.011');
      await page.getByRole('button',{name:'ค้นหาหรือไปยังพิกัด',exact:true}).click();
      await locationIs(page,18.831,99.011);

      await paste(page,'99.005497, 18.829376');
      assert.equal(await page.locator('#map-coordinate-input').getAttribute('aria-invalid'),'true');
      await locationIs(page,18.831,99.011);
      await paste(page,'0, 0');
      assert.match(await page.locator('#map-coordinate-status').textContent(),/นอกขอบเขต/);
      await paste(page,'https://maps.app.goo.gl/example');
      assert.match(await page.locator('#map-coordinate-status').textContent(),/ลิงก์แบบย่อ/);
      assert.equal(heatRequests,1,'Invalid input must not fetch or move the map');

      await paste(page,'https://www.google.com/maps/place/site/@18.1,99.1,14z/data=!3d18.829376!4d99.005497');
      await locationIs(page,18.829376,99.005497);
      await page.locator('.leaflet-marker-icon[title="จุดที่เลือก"]').click();
      await page.getByRole('link',{name:'Google Maps',exact:true}).waitFor();
      assert.match(await page.getByRole('link',{name:'Google Maps',exact:true}).getAttribute('href'),/18.829376,99.005497/);
      assert.match(await page.getByRole('link',{name:'Street View',exact:true}).getAttribute('href'),/cbll=18.829376,99.005497/);
      await page.evaluate(() => map.closePopup());

      await page.screenshot({path:path.join(output,`${workspace}-desktop.png`)});
      await page.setViewportSize({width:390,height:844});
      await page.locator('#coordinate-search').scrollIntoViewIfNeeded();
      await page.waitForTimeout(250);
      assert.equal(await page.evaluate(() => {
        const host=document.getElementById('coordinate-search').getBoundingClientRect();
        const input=document.getElementById('map-coordinate-input').getBoundingClientRect();
        const button=document.querySelector('#coordinate-search button').getBoundingClientRect();
        return host.right<=window.innerWidth && input.right<=button.left && button.right<=host.right+1;
      }),true,'Coordinate field and button fit on mobile');
      await page.screenshot({path:path.join(output,`${workspace}-mobile.png`)});
      await page.locator('#coordinate-search').screenshot({path:path.join(output,`${workspace}-mobile-control.png`)});

      await page.setViewportSize({width:1440,height:1000});
      await paste(page,'16.813823,100.234686');
      await locationIs(page,16.813823,100.234686);
      await page.waitForFunction(() => document.getElementById('map-coordinate-status').classList.contains('warning'));
      assert.match(await page.locator('#map-coordinate-status').textContent(),/นอกขอบเขตข้อมูล/);
      assert.equal(await page.evaluate(() => heatmapLayer.getLayers().length>0),true);

      // A reload must not pull the view away from the selected point.
      await page.evaluate(workspace => workspace==='planning' ? loadHeatmap() : loadHeatMap(),workspace);
      await locationIs(page,16.813823,100.234686);
      failHeat=true;
      await page.evaluate(() => { latestHeatmapData=null; });
      await paste(page,'18.829376,99.005497');
      await page.waitForFunction(() => document.getElementById('map-coordinate-status').classList.contains('warning'));
      await locationIs(page,18.829376,99.005497);
      failHeat=false;
      await paste(page,'18.829376,99.005497');
      await page.waitForFunction(() => latestHeatmapData?.point_count===2);
      await locationIs(page,18.829376,99.005497);
      if (workspace==='planning') {
        await page.locator('#reset-btn').click();
        assert.equal(await page.evaluate(() => coordinateSearch.getTarget()),null);
      } else {
        await page.locator('#lang-en').click();
        await page.getByRole('button',{name:'Search or go to coordinates',exact:true}).waitFor();
      }
      assert.deepEqual(errors,[],`${workspace} JavaScript errors`);
      assert.deepEqual(mutations,[],'Map navigation must not create or save candidate records');
      console.log(`PASS ${workspace}: paste, Enter/button, validation, links, heat retention, coverage warning, reload/failure/retry, desktop/mobile`);
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});

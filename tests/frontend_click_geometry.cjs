const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
const html = fs.readFileSync('th_evi/static/index.html', 'utf8');
const source = html.slice(html.indexOf('function approxKmBetween('), html.indexOf('function openGoogleMaps('));
const context = {latestHeatmapData:null};
vm.createContext(context);
vm.runInContext(source + '\nthis.api = {nearestHeatPoint, heatPointContains, heatmapMatchesSelection};', context);
const {api} = context;
function data(points, extra={}) {
  return {province:'Chiang Mai',year:2026,scenario:'base',mode:'urban',resolution_km:1,
    lat_step_deg:1,lon_step_deg:1,metadata:{production_method:'fixed_support_area_v1'},points,...extra};
}
test('pilot never borrows a nearby cell outside its bounds', () => {
  const p = {lat:0.5,lon:0.5,cell_id:'0:0'};
  context.latestHeatmapData = data([p]);
  assert.equal(api.nearestHeatPoint(0.5,1.001), null);
  assert.equal(api.nearestHeatPoint(0.5,0.5), p);
});
test('a hole in the same coarse cell stays outside support', () => {
  const p = {lat:0.15,lon:0.15,cell_id:'0:0',coverage_fragments:[[[0,0],[0.3,0.3]],[[0.7,0.7],[1,1]]]};
  context.latestHeatmapData = data([p]);
  assert.equal(api.nearestHeatPoint(0.5,0.5), null);
  assert.equal(api.nearestHeatPoint(0.8,0.8), p);
});
test('cell membership, not distance to a shifted representative, wins', () => {
  const a = {lat:0.1,lon:0.1,cell_id:'0:0',coverage_fragments:[[[0,0],[1,1]]]};
  const b = {lat:0.9,lon:1.1,cell_id:'0:1'};
  context.latestHeatmapData = data([a,b]);
  assert.equal(api.nearestHeatPoint(0.9,0.99), a);
});
test('half-open boundaries select only the right cell', () => {
  const a={lat:0.5,lon:0.5,cell_id:'0:0'}, b={lat:0.5,lon:1.5,cell_id:'0:1'};
  context.latestHeatmapData=data([a,b]);
  assert.equal(api.nearestHeatPoint(0.5,1), b);
});
test('province/year/scenario/mode/resolution changes invalidate cached scores', () => {
  const d=data([]);
  assert.equal(api.heatmapMatchesSelection(d,'Chiang Mai',2026,'base','urban',1),true);
  for (const args of [['Chiang Rai',2026,'base','urban',1],['Chiang Mai',2030,'base','urban',1],
    ['Chiang Mai',2026,'upside','urban',1],['Chiang Mai',2026,'base','district',1],
    ['Chiang Mai',2026,'base','urban',0.25]]) {
    assert.equal(api.heatmapMatchesSelection(d,...args), false);
  }
});
test('legacy nearest-point behaviour is retained for non-pilot views', () => {
  const p={lat:18,lon:99};
  context.latestHeatmapData=data([p],{metadata:{production_method:'legacy_spatial_screening'}});
  assert.equal(api.nearestHeatPoint(18.001,99),p);
});
test('empty data and invalid coordinates do not produce pilot matches', () => {
  context.latestHeatmapData=data([]);
  assert.equal(api.nearestHeatPoint(0,0),null);
  assert.equal(api.heatPointContains(NaN,1,{lat:0.5,lon:0.5}),false);
});

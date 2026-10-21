const assert = require('node:assert/strict');
const {test} = require('node:test');
const {parse} = require('../th_evi/static/map-coordinates.js');

for (const value of [
  '18.829376, 99.005497', ' 18.829376 99.005497 ',
  '18.829376\n99.005497', '18.829376\t99.005497',
  '(18.829376, 99.005497)', '[18.829376, 99.005497]',
  '18.829376\uff0c 99.005497', '18.829376,\u00a099.005497',
  'https://www.google.com/maps/search/?api=1&query=18.829376%2C99.005497',
  'https://maps.google.com/?q=18.829376,99.005497',
  'https://www.google.co.th/maps?ll=18.829376,99.005497',
  'https://www.google.com/maps/place/test/@18.7,98.9,14z/data=!4m2!3d18.829376!4d99.005497',
]) {
  test(`coordinate pair: ${value}`, () => {
    assert.deepEqual(parse(value), {lat:18.829376, lon:99.005497, source:'coordinates'});
  });
}

test('URL viewport centers are labelled, not confused with a place pin', () => {
  assert.deepEqual(parse('https://www.google.com/maps/@18.829376,99.005497,15z'),
    {lat:18.829376,lon:99.005497,source:'map_center'});
});
test('global coordinates parse independently of the Thailand UI extent', () => {
  assert.deepEqual(parse('\u221233.1, +151.2'), {lat:-33.1,lon:151.2,source:'coordinates'});
  assert.deepEqual(parse('0, 0'), {lat:0,lon:0,source:'coordinates'});
});
for (const value of ['', '18.829376', '99.005497, 18.829376', 'NaN,99', 'Infinity,99',
  '91,99', '18,181', '18,99,15', '(18,99', '18,99)', '18.8;99.0', '18.8foo,99',
  'House 18, street 99', '1e1,99', 'https://evil.example/?q=18.8,99',
  'https://www.google.com.evil.example/maps?q=18.8,99',
  'https://www.google.com/maps/dir/18,99/19,100', 'javascript:alert(18,99)',
  'https://www.google.com/maps/search/?api=1&query=Tanawan+Park']) {
  test(`reject malformed/ambiguous input: ${value}`, () => assert.throws(() => parse(value), /invalid/));
}
for (const value of ['https://maps.app.goo.gl/abc', 'https://goo.gl/maps/abc']) {
  test(`short URLs require actual coordinates: ${value}`, () => assert.throws(() => parse(value), /short_url/));
}

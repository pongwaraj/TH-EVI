(function (root) {
  'use strict';
  function create({ getProvince = () => '', getCenter }) {
    let configPromise;
    function config() {
      if (!configPromise) {
        const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 5000);
        configPromise = fetch('/api/place-search/config', { signal: controller.signal })
          .then(response => { if (!response.ok) throw new Error('config'); return response.json(); })
          .catch(error => { configPromise = null; throw error; })
          .finally(() => clearTimeout(timer));
      }
      return configPromise;
    }
    async function search(query, signal) {
      const params = new URLSearchParams({ q: query, province: getProvince(), limit: '8' });
      let local, localFailed = false;
      try {
        const response = await fetch(`/api/place-search?${params}`, { signal });
        if (!response.ok) throw new Error('local');
        local = await response.json();
        if (!Array.isArray(local.results)) throw new Error('local');
      } catch (error) {
        if (signal.aborted) throw error;
        local = { results: [] }; localFailed = true;
      }
      let external, externalFailed = false;
      try { external = (await config()).external; }
      catch (error) { if (signal.aborted) throw error; externalFailed = true; }
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      const rows = [...local.results];
      if (external?.provider === 'maptiler' && external.public_key && rows.length < 8) {
        try {
          const options = new URLSearchParams({ key: external.public_key, country: 'th',
            language: /[\u0e00-\u0e7f]/.test(query) ? 'th,en' : 'en,th', autocomplete: 'true', limit: '5' });
          const center = getCenter(); options.set('proximity', `${center.lng},${center.lat}`);
          // Provider data stays in the browser; never persist it as a model POI.
          const response = await fetch(`https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json?${options}`, { signal });
          if (!response.ok) throw new Error('external');
          const result = await response.json();
          if (!Array.isArray(result.features)) throw new Error('external');
          for (const feature of result.features) {
            const [lon, lat] = feature.center || feature.geometry?.coordinates || [];
            if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < 5 || lat > 21 || lon < 97 || lon > 106) continue;
            if (rows.some(row => Math.abs(Number(row.lat) - lat) < .0003 && Math.abs(Number(row.lon) - lon) < .0003)) continue;
            const region = feature.place_type?.includes('region') ? feature :
              feature.context?.find(item => item.id?.startsWith('region.'));
            rows.push({ id: `maptiler:${feature.id}`, name: feature.text || feature.place_name || query,
              address: feature.place_name || '', lat, lon, province: region?.text || '', kind: 'place', source: 'maptiler' });
          }
        } catch (error) { if (signal.aborted) throw error; externalFailed = true; }
      }
      if (!rows.length && (localFailed || externalFailed)) throw new Error('searchUnavailable');
      return { results: rows.slice(0, 8), partial: Boolean(local.partial || localFailed || externalFailed) };
    }
    return { search };
  }
  root.THEVIPlaceSearch = { create };
})(window);

// Collects the live numbers for the link-preview images, using the site's own indicators.js,
// so the images always show exactly what the pages show. Writes og/og.json.
// Run from the repo root: node scripts/og_data.js
const fs = require('fs');
global.window = {};
global.fetch = f => Promise.resolve({ ok: fs.existsSync(f), text: () => Promise.resolve(fs.readFileSync(f, 'utf8')) });
eval(fs.readFileSync('indicators.js', 'utf8'));

// page -> indicator id, title on the card, and optional overrides for the headline number
const PAGES = {
  air:         { id: 'air',  title: 'Global air temperature', big: r => r.pre12.replace(/^(\d)/, '+$1'), label: () => 'last 12 months, above pre-industrial (1850–1900)' },
  sst:         { id: 'sst',  title: 'Sea surface temperature' },
  nino:        { id: 'nino', title: 'El Niño and La Niña (Niño 3.4)' },
  'land-ice':  { id: 'land', title: 'Land ice: glaciers and ice sheets' },
  pdo:         { id: 'pdo',  title: 'Pacific Decadal Oscillation (PDO)' },
  sun:         { id: 'sun',  title: 'The Sun: solar cycle' },
  ohc:         { id: 'ohc',  title: 'Ocean heat content' },
  'sea-level': { id: 'sl',   title: 'Global sea level' },
  'sea-ice':   { id: 'ice',  title: 'Arctic sea ice extent' },
  co2:         { id: 'co2',  title: 'Carbon dioxide (CO₂)' },
  ch4:         { id: 'ch4',  title: 'Methane' },
  eei:         { id: 'eei',  title: "Earth's energy imbalance" },
};

(async () => {
  const out = {};
  for (const [page, p] of Object.entries(PAGES)) {
    try {
      const r = await window.EI.get(p.id), t = r.tile;
      out[page] = {
        title: p.title,
        big: p.big ? p.big(r) : t.v,
        label: p.label ? p.label(r) : t.l,
        spark: (t.spark || []).map(q => typeof q === 'number' ? q : q.y),
        sparkLabel: t.sparkLabel || '',
        source: r.src || '',
        through: r.through || '',
      };
    } catch (e) { console.error(page, 'failed:', e); }
  }
  fs.writeFileSync('og/og.json', JSON.stringify(out, null, 1));
  console.log('wrote og/og.json for', Object.keys(out).join(', '));
})();

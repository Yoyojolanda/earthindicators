// Shared script for every tracker page: navigation, export button placement, back-to-top button, chart legends,
// small-screen axis labels and JPG export. Load it right after <nav class="nav" id="nav">.
// To add a page: add one line to PAGES. Nothing else needs to change.
(function () {
  // ---- theme: 'light', 'dark', or automatic (follows the device). The choice is stored in this browser only.
  const THEMES = ['auto', 'light', 'dark'];
  const stored = (() => { try { return localStorage.getItem('ei-theme') || 'auto'; } catch (e) { return 'auto'; } })();
  const dark = stored === 'dark' || (stored === 'auto' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
  if (stored !== 'auto') document.documentElement.dataset.theme = stored; else delete document.documentElement.dataset.theme;
  // colours for charts; pages read window.THEME, so grids, bands and dark lines stay visible in both themes
  window.THEME = dark
    ? { dark, ink: '#e9e4d8', mut: '#a8a090', grid: 'rgba(255,255,255,.14)', band1: '#26313e', band2: '#3b4f66', clim: '#cfc8b8', fill0: 'rgba(40,30,25,.6)',
        deep1: '#ff8a80', deep2: '#7fb3e8', bar: '#6f8fb3', trend: '#9cc2ec', card: '#1d1a15', zero: 'rgba(255,255,255,.55)', thin: '#4f6580' }
    : { dark, ink: '#1c1c1c', mut: '#555', grid: 'rgba(0,0,0,.18)', band1: '#dce6f0', band2: '#a9c0d8', clim: '#333', fill0: 'rgba(255,245,240,.6)',
        deep1: '#7a0000', deep2: '#0f3f6b', bar: '#8fa9c4', trend: '#1f3f66', card: '#fff', zero: 'rgba(0,0,0,.6)', thin: '#b8c7d9' };
  const themeLabel = { auto: 'Theme: automatic (follows your device)', light: 'Theme: light', dark: 'Theme: dark' };
  const themeIcon = t => t === 'light'
    ? '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="4.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'
    : t === 'dark'
    ? '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>'
    : '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/></svg>';

  const GH = 'https://github.com/yoyojolanda/earthindicators';
  const PAGES = [
    ['index.html',     'Overview'],
    ['claims.html',    'Common claims', 'nb-claims'],   // third field: extra class for a nav button that stands out
    ['air.html',       'Air temp'],
    ['nino.html',      'El Niño'],
    ['pdo.html',       'PDO'],
    ['sun.html',       'The Sun'],
    ['sst.html',       'Sea surface temp'],
    ['ohc.html',       'Ocean heat'],
    ['sea-level.html', 'Sea level'],
    ['sea-ice.html',   'Sea ice'],
    ['land-ice.html',  'Land ice'],
    ['co2.html',       'CO₂'],
    ['ch4.html',       'Methane'],
    ['eei.html',       'Energy imbalance'],
    ['slow.html',      'Slow signals'],
  ];

  // ---- site header: logo, name and tagline, with the menu next to it (a hamburger menu on narrow screens).
  //      A slim copy (.mini) slides in at the top when the reader scrolls back up, and hides again when scrolling down.
  const here = location.pathname.split('/').pop() || 'index.html';
  const main = document.querySelector('main');
  const nav = document.getElementById('nav');            // old button row: now only a holder for the export button
  if (main && !document.querySelector('.site-head')) {
    const link = ([href, label], cls) => '<a href="' + href + '"' + (cls ? ' class="' + cls + '"' : '') +
      (href === here ? ' aria-current="page"' : '') + '>' + label + '</a>';
    const ind = PAGES.filter(p => !['index.html', 'claims.html'].includes(p[0]));
    const onInd = ind.some(p => p[0] === here);
    const claimIcon = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7 5.6c.2-.7.8-1 1.4-.9.7.1 1.1.6 1 1.2-.1.7-1.2.8-1.3 1.6M8.1 8.8v.1" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>';
    const headHTML = (cls, menuId) =>
      '<header class="site-head' + cls + '">' +
      '<a class="brand" href="index.html" aria-label="Earth Indicators, overview"><img src="img/logo.svg" alt="" width="56" height="52">' +
      '<span><span class="wm">Earth Indicators</span><span class="tag">Earth’s vital signs, measured</span></span></a>' +
      '<button class="burger" type="button" aria-expanded="false" aria-controls="' + menuId + '" aria-label="Menu">' +
      '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>' +
      '<nav class="menu" id="' + menuId + '" aria-label="Site">' +
      link(PAGES[0]) +
      '<div class="dd"><button class="dd-btn' + (onInd ? ' on' : '') + '" type="button" aria-expanded="false">Indicators' +
      '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<div class="dd-list"><span class="dd-label">Indicators</span>' + ind.map(p => link(p)).join('') + '</div></div>' +
      link([PAGES[1][0], claimIcon + PAGES[1][1]], 'm-claims') +
      '</nav><button class="theme-btn" type="button" title="' + themeLabel[stored] + '" aria-label="' + themeLabel[stored] + '">' + themeIcon(stored) + '</button></header>';
    // dropdown and hamburger behaviour, for either header
    const wire = head => {
      const burger = head.querySelector('.burger'), dd = head.querySelector('.dd'), ddBtn = head.querySelector('.dd-btn');
      const setDd = open => { dd.classList.toggle('open', open); ddBtn.setAttribute('aria-expanded', open); };
      const setMenu = open => { head.classList.toggle('open', open); burger.setAttribute('aria-expanded', open); };
      ddBtn.addEventListener('click', e => { e.stopPropagation(); setDd(!dd.classList.contains('open')); });
      burger.addEventListener('click', () => setMenu(!head.classList.contains('open')));
      document.addEventListener('click', e => { if (!dd.contains(e.target)) setDd(false); });
      document.addEventListener('keydown', e => { if (e.key === 'Escape') { setDd(false); setMenu(false); } });
      return { close: () => { setDd(false); setMenu(false); } };
    };
    main.insertAdjacentHTML('afterbegin', headHTML('', 'menu'));
    // theme button: auto -> light -> dark -> auto. Reloads the page so the charts are redrawn in the new colours.
    document.addEventListener('click', e => {
      const b = e.target.closest('.theme-btn'); if (!b) return;
      const next = THEMES[(THEMES.indexOf(stored) + 1) % THEMES.length];
      try { if (next === 'auto') localStorage.removeItem('ei-theme'); else localStorage.setItem('ei-theme', next); } catch (err) {}
      location.reload();
    });
    const head = main.querySelector('.site-head');
    wire(head);

    // slim header: shown when scrolling up (past the real header), hidden when scrolling down or back at the top
    document.body.insertAdjacentHTML('beforeend', '<div class="mini-wrap" aria-hidden="true">' + headHTML(' mini', 'menu-mini') + '</div>');
    const wrap = document.body.lastElementChild, mini = wrap.querySelector('.site-head'), miniCtl = wire(mini);
    wrap.inert = true;                                     // not reachable with Tab while hidden
    let lastY = window.scrollY, ticking = false;
    const setMini = on => { if (wrap.classList.contains('show') === on) return;
      wrap.classList.toggle('show', on); wrap.inert = !on; wrap.setAttribute('aria-hidden', !on); if (!on) miniCtl.close(); };
    window.addEventListener('scroll', () => {
      if (ticking) return; ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY, past = head.getBoundingClientRect().bottom < 0;
        if (!past) setMini(false);
        else if (y < lastY - 6) setMini(true);            // scrolling up
        else if (y > lastY + 6) setMini(false);           // scrolling down
        if (Math.abs(y - lastY) > 6) lastY = y;
        ticking = false;
      });
    }, { passive: true });
  }

  // ---- visitor statistics: GoatCounter (no cookies, no personal data; dashboard at yoyojolanda.goatcounter.com).
  //      It ignores visits from localhost, so testing on your own computer is not counted.
  const gcReady = new Promise(ok => {
    const s = document.createElement('script');
    s.async = true; s.src = 'https://gc.zgo.at/count.js';
    s.dataset.goatcounter = 'https://yoyojolanda.goatcounter.com/count';
    s.onload = ok; document.head.appendChild(s);
  });
  // events on the claims page: which answers are opened, copied, and reached through a shared link
  const gcEvent = (path, title) => gcReady.then(() => window.goatcounter && window.goatcounter.count &&
    window.goatcounter.count({ path, title, event: true }));
  if (here === 'claims.html') {
    const title = id => { const h = document.querySelector('#' + CSS.escape(id) + ' summary'); return h ? h.textContent.trim() : id; };
    const hookClaims = () => {
      const h = decodeURIComponent(location.hash.slice(1));
      if (h && document.getElementById(h)) gcEvent('claim-link/' + h, title(h));          // arrived through a shared link
      document.querySelectorAll('details.claim').forEach(d => {
        d.addEventListener('toggle', () => { if (d.open) gcEvent('claim-open/' + d.id, title(d.id)); });
        const b = d.querySelector('.cp'); if (b) b.addEventListener('click', () => gcEvent('claim-copy/' + d.id, title(d.id)));
      });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hookClaims); else hookClaims();
  }

  const START = 2026, now = new Date().getFullYear(), years = now > START ? START + '–' + now : String(START);   // 2026, then 2026–2027, …
  // ---- stretch the tagline's letter-spacing so it is exactly as wide as the site name (depends on fonts and screen size)
  const fitTag = () => {
    const wm = document.querySelector('.site-head .wm'), tag = document.querySelector('.site-head .tag');
    if (!wm || !tag) return;
    tag.style.letterSpacing = '0'; tag.style.marginRight = '0';
    const extra = wm.getBoundingClientRect().width - tag.getBoundingClientRect().width, n = tag.textContent.length;
    // widens the tagline, or tightens it slightly if it is the longer one
    if (n > 1) { const ls = extra / (n - 1); tag.style.letterSpacing = ls + 'px'; tag.style.marginRight = -ls + 'px'; }
  };
  fitTag();
  if (document.fonts) document.fonts.ready.then(fitTag);
  window.addEventListener('resize', fitTag);

  // ---- footer (added once the whole page has loaded: this script runs near the top of <main>, before the content exists)
  // footer menu: every page, so readers who reach the bottom can go straight on to the next one
  const footNav = () => {
    const a = ([href, label]) => '<a href="' + href + '"' + (href === here ? ' aria-current="page"' : '') + '>' + label + '</a>';
    const ind = PAGES.filter(p => !['index.html', 'claims.html'].includes(p[0]));
    return '<nav class="foot-nav" aria-label="Site, footer">' +
      '<div><h2>Earth Indicators</h2>' + a(PAGES[0]) + a(PAGES[1]) + a(['methods.html', 'How the numbers are made']) +
      '<a href="' + GH + '">Source code on GitHub</a></div>' +
      '<div class="ind"><h2>Indicators</h2>' + ind.map(a).join('') + '</div></nav>';
  };
  const addFoot = () => { if (main && !document.querySelector('.site-foot')) main.insertAdjacentHTML('beforeend', '<footer class="site-foot">' + footNav() + '<p>© ' + years + ' Earth Indicators. Text and charts are licensed under ' +
      '<a href="https://creativecommons.org/licenses/by/4.0/" rel="license">CC BY 4.0</a>: share and adapt them freely, with credit to Earth Indicators and a link to this site. ' +
      'The logo and drawings are not included in that license. Drawings by Jolanda: a dying dandelion, for what is happening to our planet, and in the logo its seeds blowing in the wind, held in a heart, for life, love and care.</p>' +
      '<p>The data comes from NOAA, NASA, NSIDC and the Copernicus Climate Change Service and stays under their terms. <a href="methods.html">How the numbers are made</a> lists the exact datasets, processing steps and checks for every chart; all code is <a href="' + GH + '">public on GitHub</a>. <a href="https://yoyojolanda.goatcounter.com">Visitor statistics</a> are public, counted without cookies.</p></footer>'); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addFoot); else addFoot();

  // ---- export button: pages put #exp inside the nav; move it to its own row under the nav so it reads as an action, not a page link
  const exp = document.getElementById('exp');
  if (exp && nav) {
    const bar = document.createElement('div'); bar.className = 'tools';
    nav.after(bar); bar.appendChild(exp);
    exp.className = 'act';
    exp.innerHTML = '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><path d="M8 1.5v8.5M4.5 6.5 8 10l3.5-3.5M2 11.5v2.5h12v-2.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Export charts as JPG</span>';
    exp.title = 'Download all charts on this page as one image';
  }

  // ---- "Data and method" line on data pages: exact dataset, what this site does, links to the full method, code and data.
  //      Full details per indicator live in methods.html (anchor = page name without .html).
  const HOW = {
    'air.html': ['Copernicus ERA5 daily 2 m temperature (<a href="https://doi.org/10.24381/cds.4991cf48">doi:10.24381/cds.4991cf48</a>).',
      'World history is Copernicus\'s published series; newer days and the regions are averaged here from the ERA5 grid with the same method, and checked against Copernicus.',
      ['scripts/build_era5.py', 'scripts/build_era5_regions.py'], 'data/era5_t2_global_daily.csv'],
    'nino.html': ['NOAA OISST v2.1 daily sea surface temperature (<a href="https://doi.org/10.25921/RE9P-PT57">doi:10.25921/RE9P-PT57</a>). Hurricanes: NOAA NCEI IBTrACS v04r01 (<a href="https://doi.org/10.25921/82ty-9e16">doi:10.25921/82ty-9e16</a>).',
      'Averaged here over 5°S–5°N, 170°W–120°W (area-weighted) and checked against Climate Reanalyzer\'s independent series. Hurricane energy (ACE) is added up here from every 6-hourly storm position and checked against published season totals.',
      ['scripts/build_nino34.py', 'scripts/build_ace.py'], ['data/nino34_daily_sst.csv', 'data/ace_daily.csv']],
    'sst.html': ['NOAA OISST v2.1 daily sea surface temperature (<a href="https://doi.org/10.25921/RE9P-PT57">doi:10.25921/RE9P-PT57</a>).',
      'Averaged here over each region, area-weighted, with the same code as the El Niño page.',
      ['scripts/build_nino34.py'], 'data/world_daily_sst.csv'],
    'ohc.html': ['NOAA NCEI Global Ocean Heat Content, 0–700 m and 0–2000 m.',
      'NOAA\'s values are shown unchanged; trends and heating rates are calculated by this page.', ['ohc.html'], 'data/h22-w0-2000m.dat'],
    'sea-level.html': ['NASA-SSH Global Mean Sea Level, version 1 (<a href="https://doi.org/10.5067/NSIND-GMSV1">doi:10.5067/NSIND-GMSV1</a>).',
      'NASA\'s values are shown with the average seasonal cycle removed; trends are calculated by this page.', ['sea-level.html'], 'data/NASA_SSH_GMSL_INDICATOR.txt'],
    'sea-ice.html': ['Extent: NSIDC Sea Ice Index, version 4 (<a href="https://doi.org/10.7265/a98x-0f50">doi:10.7265/a98x-0f50</a>). Second extent record for the standard-deviation chart: JAXA AMSR2 via NIPR ViSHOP (Japan). Volume: Copernicus Marine, Mercator GLORYS12 ocean reanalysis and CryoSat-2 + SMOS satellite thickness.',
      'NSIDC\'s daily extent, shown as a 5-day mean; anomalies and standard deviations are calculated by this page. Volume (thickness × concentration × area) is calculated here from the Copernicus grids.',
      ['sea-ice.html', 'scripts/build_seaice_volume.py'], ['data/N_seaice_extent_daily_v4.0.csv', 'data/seaice_volume_glorys.csv', 'data/seaice_volume_cs2smos.csv']],
    'co2.html': ['NOAA Global Monitoring Laboratory, Mauna Loa daily mean CO₂.',
      'NOAA\'s daily values are shown unchanged; monthly means, trend and growth are calculated by this page.', ['co2.html'], 'data/co2_daily_mlo.txt'],
    'ch4.html': ['NOAA Global Monitoring Laboratory, globally averaged marine surface methane.',
      'NOAA\'s monthly means, trend and annual increases are shown unchanged.', ['ch4.html'], 'data/ch4_mm_gl.txt'],
    'land-ice.html': ['Ice sheets: NASA JPL GRACE/GRACE-FO mascon time series, release 06.3 v4: Greenland (<a href="https://doi.org/10.5067/TEMSC-GT634">doi:10.5067/TEMSC-GT634</a>) and Antarctica (<a href="https://doi.org/10.5067/TEMSC-AT634">doi:10.5067/TEMSC-AT634</a>). Glaciers: WGMS gridded glacier mass change, Copernicus Climate Data Store (<a href="https://doi.org/10.24381/cds.ba597449">doi:10.24381/cds.ba597449</a>). Greenland ice core: Kobashi et al. 2011 (<a href="https://doi.org/10.1029/2011GL049444">doi:10.1029/2011GL049444</a>) and Alley 2000 (<a href="https://doi.org/10.1016/S0277-3791(99)00062-1">doi:10.1016/S0277-3791(99)00062-1</a>), via NOAA paleoclimatology; measured summit temperature: Copernicus ERA5.',
      'NASA\'s monthly mass values are shown relative to the first 12 months; trends, yearly changes and the sea-level equivalent (362 Gt = 1 mm) are calculated by this page; the world glacier total per year is added up from the grid by this site. The ice-core reconstructions are shown as published; the ERA5 summit series is shifted so its 2001–2010 average matches the ice-core value for that decade, and the 10-year comparisons are calculated by this page.', ['land-ice.html', 'scripts/build_glaciers.py', 'scripts/build_greenland_icecore.py'], ['data/grace_greenland.txt', 'data/grace_antarctica.txt', 'data/glaciers_global.csv', 'data/gisp2_kobashi2011.csv', 'data/gisp2_alley2000.csv', 'data/greenland_summit_era5.csv']],
    'pdo.html': ['NOAA NCEI Pacific Decadal Oscillation index, based on ERSST.',
      'NOAA\'s monthly values are shown unchanged; the 12-month and decade averages are calculated by this page.', ['pdo.html'], 'data/pdo_ncei.dat'],
    'sun.html': ['WDC-SILSO, Royal Observatory of Belgium, International Sunspot Number version 2 (<a href="https://doi.org/10.24414/qnza-ac80">doi:10.24414/qnza-ac80</a>).',
      'SILSO\'s monthly and 13-month smoothed values are shown unchanged; cycle minima and maxima and the yearly averages are calculated by this page.', ['sun.html'], ['data/SN_m_tot_V2.0.csv', 'data/SN_ms_tot_V2.0.csv']],
    'eei.html': ['NASA CERES EBAF-TOA Edition 4.2.1 (<a href="https://doi.org/10.5067/TERRA-AQUA-NOAA20/CERES/EBAF-TOA_L3B004.2.1">doi:10.5067/TERRA-AQUA-NOAA20/CERES/EBAF-TOA_L3B004.2.1</a>).',
      'NASA\'s own global monthly means; the imbalance is absorbed solar minus outgoing longwave radiation. Running means are calculated by this page.', ['scripts/build_ceres.py'], 'data/ceres_ebaf_global.csv'],
    'slow.html': ['Fossil CO₂: Global Carbon Project, fossil CO₂ emissions dataset (Andrew and Peters, Zenodo). Ocean pH: Hawaii Ocean Time-series, Station ALOHA. AMOC: RAPID-MOCHA-WBTS array at 26.5°N (<a href="https://rapid.ac.uk/">rapid.ac.uk</a>). Red List Index: IUCN and BirdLife International, via the UN SDG database (indicator 15.5.1). Tree cover loss: University of Maryland and Global Forest Watch, via Our World in Data. Crop yields: FAO, FAOSTAT. Cherry blossom: Y. Aono, via the GMU cherry blossom prediction competition.',
      'Emissions, pH and the Red List Index are shown unchanged; RAPID\'s twice-daily transports are averaged here to months. Trends, 12-month averages and changes are calculated by this page.', ['scripts/build_slow.py'], ['data/fossil_co2_global.csv', 'data/hot_surface_ph.csv', 'data/amoc_rapid_monthly.csv', 'data/redlist_index_world.csv', 'data/tree_cover_loss_world.csv', 'data/fao_crop_yields_world.csv', 'data/kyoto_cherry_blossom.csv']],
  };
  const how = HOW[here];
  if (how && nav) {
    const [src, what, code, file] = how, name = f => f.split('/').pop();
    const box = document.createElement('section'); box.className = 'how';
    box.innerHTML = '<h2>Data and method</h2><p><b>Source:</b> ' + src + ' ' + what + '</p><p class="links">' +
      '<a href="methods.html#' + here.replace('.html', '') + '">Full method and checks</a>' +
      code.map(c => '<a href="' + GH + '/blob/main/' + c + '">Code: ' + name(c) + '</a>').join('') +
      [].concat(file).map(f => '<a href="' + f + '">Data: ' + name(f) + '</a>').join('') + '</p>';   // one data file or several
    (document.querySelector('.tools') || nav).after(box);
  }

  // ---- "In short" box on data pages. The text lives in inshort.js, the live numbers in indicators.js.
  const page = location.pathname.split('/').pop() || 'index.html';
  const load = src => new Promise((ok, no) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = no; document.head.appendChild(s); });
  if (nav && !['index.html', 'claims.html'].includes(page)) {
    load('inshort.js').then(() => {
      const it = window.IN_SHORT && window.IN_SHORT[page];
      if (!it) return;
      return (window.EI ? Promise.resolve() : load('indicators.js')).then(() => {
        const box = document.createElement('section'); box.className = 'inshort';
        const live = t => t.replace(/\{(\w+\.\w+)\}/g, '<span class="live" data-k="$1">…</span>');
        box.innerHTML = '<h2>In short</h2>' + it.text.map(t => '<p>' + live(t) + '</p>').join('') +
          (it.units ? '<p class="units"><b>In everyday terms:</b> ' + live(it.units) + '</p>' : '') +
          (it.claims && it.claims.length ? '<div class="rel"><span>Related claims, answered:</span><ul>' + it.claims.map(c => '<li><a href="claims.html#' + c + '">' + (window.CLAIMS[c] || c) + '</a></li>').join('') + '</ul></div>' : '') +
          '<p class="stamp"></p>';
        (document.querySelector('.tools') || nav).after(box);
        const ids = [...new Set([...box.querySelectorAll('[data-k]')].map(e => e.dataset.k.split('.')[0]))];
        EI.fill(box);
        Promise.allSettled(ids.map(id => EI.get(id).then(r => r.src + ', data through ' + r.through))).then(R => {
          box.querySelector('.stamp').textContent = [...new Set(R.filter(r => r.status === 'fulfilled').map(r => r.value))].join('; ');
        });
      });
    }).catch(e => console.error('In short box:', e));
  }

  // ---- back-to-top button, appears after scrolling down a bit
  const top = document.createElement('button');
  top.type = 'button'; top.id = 'totop'; top.textContent = '↑';
  top.title = 'Back to top'; top.setAttribute('aria-label', 'Back to top');
  document.body.appendChild(top);
  // its outline fills up (clockwise) with how far down the page the reader is
  const toggle = () => {
    top.classList.toggle('show', window.scrollY > 400);
    const h = document.documentElement.scrollHeight - window.innerHeight;
    top.style.setProperty('--p', h > 0 ? Math.min(1, window.scrollY / h).toFixed(3) : 0);
  };
  window.addEventListener('scroll', toggle, { passive: true }); window.addEventListener('resize', toggle); toggle();

  // ---- links to other websites open in a new tab (also links added later by page scripts)
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[href]');
    if (a && a.hostname && a.hostname !== location.hostname && !a.target) { a.target = '_blank'; a.rel = 'noopener'; }
  }, true);
  top.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  // ---- section menu on wide screens: the page's sections down the empty right-hand side, as a timeline whose dot
  //      turns red for the section being read. Built from the page itself, so new sections appear in it by themselves;
  //      rebuilt when page scripts show sections or fill in chart titles after their data has loaded.
  if (nav && page !== 'claims.html') {                      // the overview gets one too: its five groups
    const side = document.createElement('nav');
    side.className = 'secnav'; side.setAttribute('aria-label', 'Sections on this page');
    document.body.appendChild(side);
    const main = document.querySelector('main');
    const shown = el => el && el.offsetParent !== null && el.getClientRects().length > 0;
    // short label: up to the first colon; if still long, up to the first comma; then cut at a word
    const short = t => {
      t = t.replace(/\s+/g, ' ').trim();
      if (t.indexOf(':') > 0) t = t.slice(0, t.indexOf(':'));
      if (t.length > 34 && t.indexOf(',') > 0) t = t.slice(0, t.indexOf(','));
      if (t.length > 40) t = t.slice(0, 38).replace(/\s+\S*$/, '') + '…';
      return t;
    };
    let items = [];
    const build = () => {
      const found = [], seen = new Set();
      const add = (target, label, full) => {
        if (!target || seen.has(target) || !label || !shown(target)) return;
        seen.add(target); found.push({ target, label, full: full || label });
      };
      add(document.querySelector('.inshort'), 'In short');
      const sec = [...main.querySelectorAll('h2.sec')];
      if (sec.length) sec.forEach(h => add(h.closest('section') || h, short(h.textContent), h.textContent));   // pages grouped in sections
      else main.querySelectorAll('h2').forEach(h => {                                                         // otherwise every chart and heading
        if (h.closest('.inshort, .how, .site-head, .foot-nav, .secnav')) return;
        const box = h.closest('.box') || h;                         // data-nav="…" on a box sets its menu label by hand
        add(box, box.dataset.nav || short(h.textContent), h.textContent.trim());
      });
      add(document.querySelector('.how'), 'Data and method');
      found.sort((a, b) => a.target.compareDocumentPosition(b.target) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);
      const key = found.map(f => f.label).join('|');
      if (key === side.dataset.key) return;
      side.dataset.key = key; items = found;
      side.innerHTML = '<ol>' + found.map((f, i) => '<li><a href="#" data-i="' + i + '" title="' + f.full.replace(/"/g, '&quot;') + '"><span></span>' + f.label + '</a></li>').join('') + '</ol>';
      mark();
    };
    // the section being read: the last one whose top has passed 35% of the window height (the first at the top)
    const mark = () => {
      if (!items.length) return;
      let cur = 0;
      items.forEach((f, i) => { if (f.target.getBoundingClientRect().top < window.innerHeight * 0.35) cur = i; });
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) cur = items.length - 1;   // at the very bottom
      side.querySelectorAll('a').forEach((a, i) => a.classList.toggle('on', i === cur));
    };
    side.addEventListener('click', e => {
      const a = e.target.closest('a'); if (!a) return;
      e.preventDefault();
      const f = items[+a.dataset.i]; if (f) f.target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    let tick = false, wait;
    window.addEventListener('scroll', () => { if (!tick) { tick = true; requestAnimationFrame(() => { tick = false; mark(); }); } }, { passive: true });
    window.addEventListener('resize', mark);
    new MutationObserver(recs => { if (recs.every(r => side.contains(r.target))) return; clearTimeout(wait); wait = setTimeout(build, 250); })
      .observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['class'] });
    build();
  }

  // ---- everything below needs Chart.js. Pages may load it with "defer" (the overview does, so the page can be drawn
  //      before the chart library arrives): then this part waits until the deferred scripts have run, and pages wait
  //      for window.chartReady before drawing charts. With a normal script tag it all runs straight away, as before.
  const chartSetup = () => {
  if (!window.Chart) return;
  if (dark) {                            // light mode keeps Chart.js's own defaults
    Chart.defaults.color = THEME.mut;
    Chart.defaults.borderColor = THEME.grid;
    document.documentElement.classList.add('charts-dark');   // printing flips these charts back to light (site.css)
  }

  // ---- small screens: diagonal x-axis labels so they never overlap
  const NARROW = 640, fixedTicks = new WeakMap();
  function rotate(ch, w) {
    const x = ch.config.options.scales && ch.config.options.scales.x;
    if (!x) return;
    const t = x.ticks || (x.ticks = {});
    if (!fixedTicks.has(ch)) fixedTicks.set(ch, t.autoSkip === false);   // charts that show only selected labels (months, years)
    if (fixedTicks.get(ch)) { const r = w < NARROW ? 45 : 0; t.minRotation = r; t.maxRotation = r; }
    else t.maxRotation = 45;                                            // auto-skipping axes: rotate up to 45° when needed
  }

  // ---- HTML legends in a left-aligned grid (replaces Chart.js's centered canvas legend)
  const LG = new WeakMap();
  function items(ch) {
    const st = LG.get(ch);
    // bars get a filled box in their own colour; bars coloured per value (e.g. positive/negative) get a box split
    // in two showing both colours; lines get a line sample
    return ch.data.datasets.map((ds, i) => {
      const bar = (ds.type || ch.config.type) === 'bar', bg = ds.backgroundColor;
      const cols = Array.isArray(bg) ? [...new Set(bg)] : null;
      const fill = typeof bg === 'string' ? bg : cols && cols.length > 1 ? `linear-gradient(90deg,${cols[0]} 50%,${cols[1]} 50%)` : cols ? cols[0] : null;
      return { text: ds.label, datasetIndex: i, hidden: !ch.isDatasetVisible(i),
        color: typeof ds.borderColor === 'string' ? ds.borderColor : '#888', fill,
        line: !bar && (ds.borderWidth === undefined || ds.borderWidth > 0), dash: !!(ds.borderDash && ds.borderDash.length) }; })
      .filter(it => it.text && (!st.filter || st.filter(it, ch.data)));
  }
  function renderLegend(ch) {
    const st = LG.get(ch); if (!st) return;
    st.items = items(ch);
    const sig = JSON.stringify(st.items);
    if (sig === st.sig) return; st.sig = sig;
    st.box.innerHTML = '';
    st.items.forEach(it => {
      const b = document.createElement('button');
      b.type = 'button'; b.title = 'Click to show or hide'; b.setAttribute('aria-pressed', String(!it.hidden));
      if (it.hidden) b.className = 'off';
      const sw = document.createElement('span');
      if (it.line) { sw.className = 'sw'; sw.style.borderTopColor = it.color; if (it.dash) sw.style.borderTopStyle = 'dashed'; }
      else { sw.className = 'bx'; sw.style.background = it.fill || it.color; }
      const tx = document.createElement('span'); tx.className = 'tx'; tx.textContent = it.text;
      b.append(sw, tx);
      b.onclick = () => { ch.setDatasetVisibility(it.datasetIndex, !ch.isDatasetVisible(it.datasetIndex)); ch.update(); };
      st.box.appendChild(b);
    });
  }

  Chart.register({
    id: 'siteCommon',
    beforeInit(ch) {
      rotate(ch, ch.canvas.parentNode ? ch.canvas.parentNode.clientWidth : 1000);
      const o = ch.config.options, p = o.plugins || (o.plugins = {}), l = p.legend || (p.legend = {});
      if (l.display === false) return;          // charts that hide their legend keep it hidden
      l.display = false;
      const box = document.createElement('div'); box.className = 'lgd';
      const wrap = ch.canvas.parentNode; wrap.parentNode.insertBefore(box, wrap);
      LG.set(ch, { box, filter: l.labels && l.labels.filter });
    },
    resize(ch, args) { rotate(ch, args.size.width); },
    afterUpdate: renderLegend,
    afterInit(ch) { if (ch.resetZoom) ch.canvas.addEventListener('dblclick', () => ch.resetZoom()); },
    afterDestroy(ch) { const st = LG.get(ch); if (st) { st.box.remove(); LG.delete(ch); } }
  });

  // ---- day-of-year axes (index 0 = 1 January, 365 days): month names on the whole year, and real dates once a
  //      chart is zoomed in to a few weeks, so a zoomed axis never ends up with no labels or labels outside the chart.
  //      Category axes: ticks.callback = dayTick (with autoSkip off). Linear axes: also afterBuildTicks = dayTicks.
  const DMS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334], DML = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dayStep = span => span > 100 ? 0 : span > 45 ? 7 : span > 20 ? 3 : span > 8 ? 2 : 1;   // 0 = month starts only
  const dayName = i => { let m = 11; while (DMS[m] > i) m--; return DML[m] + ' ' + (i - DMS[m] + 1); };
  window.dayTick = function (v) {
    const i = Math.round(v), st = dayStep(this.max - this.min);
    if (!st) return DMS.includes(i) ? DML[DMS.indexOf(i)] : '';
    return i % st === 0 ? dayName(i) : '';
  };
  window.dayTicks = ax => {
    const st = dayStep(ax.max - ax.min), t = [];
    if (!st) DMS.forEach(v => { if (v >= ax.min && v <= ax.max) t.push({ value: v }); });
    else for (let v = Math.ceil(ax.min / st) * st; v <= ax.max; v += st) t.push({ value: v });
    ax.ticks = t;
  };

  // ---- zoom: drag a rectangle with the mouse, or pinch with two fingers on a phone or tablet. Shift-drag (mouse) or a
  //      sideways swipe (touch) moves a zoomed chart; double-click or the "Reset zoom" button shows the whole chart again.
  //      Needs hammer.js and chartjs-plugin-zoom, loaded right after Chart.js (not on the overview, whose charts are static).
  //      On touch screens the chart's vertical axis stays as it is, so a pinch only stretches time.
  const touch = !!(window.matchMedia && matchMedia('(pointer: coarse)').matches);
  if (window.ChartZoom) {
    if (window.Hammer) Hammer.defaults.touchAction = 'pan-y';      // an up-and-down swipe over a chart still scrolls the page
    const zoomState = ({ chart: ch }) => {                         // show "Reset zoom" only while the chart is zoomed or moved
      const wrap = ch.canvas.parentNode;
      let b = wrap.querySelector(':scope > .zreset');
      if (!b) {
        b = document.createElement('button'); b.type = 'button'; b.className = 'nb zreset'; b.textContent = 'Reset zoom';
        b.onclick = () => ch.resetZoom(); wrap.appendChild(b);
      }
      const zoomed = ch.isZoomedOrPanned();
      b.hidden = !zoomed;
      // a fixed tick step (every 5 years, say) leaves a zoomed-in axis with one tick or none, and Chart.js would label the
      // zoomed edges with long decimals. While zoomed, ticks are put at round values inside the visible range (whole
      // numbers only if the page's step was whole); after a reset the page's own step is used again.
      const sx = ch.options.scales && ch.options.scales.x;
      if (sx && sx.ticks && (sx.ticks.stepSize != null || STEP.has(ch))) {
        if (!STEP.has(ch)) STEP.set(ch, sx.ticks.stepSize);
        const st = STEP.get(ch);
        if (zoomed !== !!sx.afterBuildTicks) {
          sx.ticks.stepSize = zoomed ? undefined : st;
          sx.afterBuildTicks = zoomed ? ax => {
            const raw = (ax.max - ax.min) / (innerWidth < 600 ? 5 : 9), p = Math.pow(10, Math.floor(Math.log10(raw)));
            let step = [1, 2, 5, 10].map(m => m * p).find(v => v >= raw);
            if (st >= 1) step = Math.max(1, Math.round(step));
            const t = []; for (let v = Math.ceil(ax.min / step) * step; v <= ax.max + 1e-9; v += step) t.push({ value: +v.toFixed(6) });
            ax.ticks = t;
          } : undefined;
          ch.update('none');
        }
      }
    };
    const STEP = new WeakMap();
    Chart.helpers.merge(Chart.defaults.plugins.zoom, {
      limits: { x: { min: 'original', max: 'original', minRange: 2 }, y: { min: 'original', max: 'original' } },   // x: at least 2 units (years, months, days)
      zoom: { mode: touch ? 'x' : 'xy', wheel: { enabled: false }, pinch: { enabled: true },
        drag: { enabled: true, threshold: 8, backgroundColor: 'rgba(31,111,181,.12)', borderColor: 'rgba(31,111,181,.7)', borderWidth: 1 },
        onZoomComplete: zoomState },
      pan: { enabled: true, mode: touch ? 'x' : 'xy', modifierKey: 'shift', threshold: 10, onPanComplete: zoomState }
    });
    const addHint = () => document.querySelectorAll('.hint').forEach(h => h.insertAdjacentText('beforeend', touch
      ? ' Tap a chart to see its values; pinch to zoom in.'
      : ' Drag across a chart to zoom in, shift-drag to move it, double-click to zoom out.'));
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addHint); else addHint();
  }

  // ---- touch screens: values appear on a tap, not whenever a finger slides over a chart while scrolling,
  //      and the tooltip goes away when the page scrolls or the reader taps somewhere else
  if (touch && window.Chart) {
    Chart.defaults.events = ['click'];
    const clear = () => Object.values(Chart.instances).forEach(ch => {
      if (!ch.tooltip || !ch.tooltip.getActiveElements().length) return;
      ch.setActiveElements([]); ch.tooltip.setActiveElements([], { x: 0, y: 0 }); ch.update('none');
    });
    window.addEventListener('scroll', clear, { passive: true });
    document.addEventListener('touchstart', e => { if (!(e.target instanceof HTMLCanvasElement)) clear(); }, { passive: true });
  }

  // ---- JPG export of several charts with their titles and legends
  // sections: [[chart, titleElementId, showBandKey], ...]
  window.siteExport = function (sections, filename) {
    const r = sections[0][0].currentDevicePixelRatio || 1, pad = 16 * r, tH = 24 * r, kH = 22 * r, gap = 20 * r, rowH = 18 * r, colW = 175 * r;
    const W = Math.max(...sections.map(s => s[0].canvas.width)) + pad * 2, cols = Math.max(1, Math.floor((W - 2 * pad) / colW));
    const leg = sections.map(([ch]) => { const st = LG.get(ch); return st ? items(ch).filter(i => !i.hidden) : []; });
    const H = pad * 2 + gap * (sections.length - 1) + sections.reduce((h, [ch, , key], n) =>
      h + tH + (key ? kH : 0) + (leg[n].length ? Math.ceil(leg[n].length / cols) * rowH + 6 * r : 0) + ch.canvas.height, 0);
    const o = document.createElement('canvas'); o.width = W; o.height = H;
    const x = o.getContext('2d'), font = (px, b) => x.font = (b ? '600 ' : '') + px * r + 'px system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
    x.fillStyle = THEME.card; x.fillRect(0, 0, W, H); x.textBaseline = 'top';
    let y = pad;
    sections.forEach(([ch, tid, key], n) => {
      if (n) y += gap;
      font(15, 1); x.fillStyle = THEME.ink; x.fillText(document.getElementById(tid).textContent, pad, y); y += tH;
      font(12);
      if (key) {
        let kx = pad;
        [[THEME.band1, 'Range of prior years (min–max)'], [THEME.band2, 'Middle 80% of prior years']].forEach(([c, t]) => {
          x.fillStyle = c; x.fillRect(kx, y + 2 * r, 14 * r, 10 * r); x.fillStyle = THEME.mut; x.fillText(t, kx + 20 * r, y);
          kx += 20 * r + x.measureText(t).width + 18 * r;
        });
        y += kH;
      }
      leg[n].forEach((it, k) => {
        const lx = pad + (k % cols) * colW, ly = y + Math.floor(k / cols) * rowH;
        if (it.line) { x.strokeStyle = it.color; x.lineWidth = 3 * r; x.setLineDash(it.dash ? [4 * r, 3 * r] : []);
          x.beginPath(); x.moveTo(lx, ly + 7 * r); x.lineTo(lx + 22 * r, ly + 7 * r); x.stroke(); x.setLineDash([]); }
        else { x.fillStyle = it.fill || it.color; x.fillRect(lx, ly + 2 * r, 22 * r, 11 * r); }
        x.fillStyle = THEME.mut; x.fillText(it.text, lx + 29 * r, ly);
      });
      if (leg[n].length) y += Math.ceil(leg[n].length / cols) * rowH + 6 * r;
      x.drawImage(ch.canvas, pad, y); y += ch.canvas.height;
    });
    const a = document.createElement('a'); a.download = filename; a.href = o.toDataURL('image/jpeg', .92);
    document.body.appendChild(a); a.click(); a.remove();
  };
  };
  window.chartReady = new Promise(done => {
    const go = () => { chartSetup(); done(); };
    if (window.Chart || document.readyState !== 'loading') go(); else document.addEventListener('DOMContentLoaded', go);
  });
})();

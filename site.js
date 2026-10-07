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
  if (window.Chart && dark) {            // light mode keeps Chart.js's own defaults
    Chart.defaults.color = THEME.mut;
    Chart.defaults.borderColor = THEME.grid;
    document.documentElement.classList.add('charts-dark');   // printing flips these charts back to light (site.css)
  }
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
    'nino.html': ['NOAA OISST v2.1 daily sea surface temperature (<a href="https://doi.org/10.25921/RE9P-PT57">doi:10.25921/RE9P-PT57</a>).',
      'Averaged here over 5°S–5°N, 170°W–120°W (area-weighted) and checked against Climate Reanalyzer\'s independent series.',
      ['scripts/build_nino34.py'], 'data/nino34_daily_sst.csv'],
    'sst.html': ['NOAA OISST v2.1 daily sea surface temperature (<a href="https://doi.org/10.25921/RE9P-PT57">doi:10.25921/RE9P-PT57</a>).',
      'Averaged here over each region, area-weighted, with the same code as the El Niño page.',
      ['scripts/build_nino34.py'], 'data/world_daily_sst.csv'],
    'ohc.html': ['NOAA NCEI Global Ocean Heat Content, 0–700 m and 0–2000 m.',
      'NOAA\'s values are shown unchanged; trends and heating rates are calculated by this page.', ['ohc.html'], 'data/h22-w0-2000m.dat'],
    'sea-level.html': ['NASA-SSH Global Mean Sea Level, version 1 (<a href="https://doi.org/10.5067/NSIND-GMSV1">doi:10.5067/NSIND-GMSV1</a>).',
      'NASA\'s values are shown with the average seasonal cycle removed; trends are calculated by this page.', ['sea-level.html'], 'data/NASA_SSH_GMSL_INDICATOR.txt'],
    'sea-ice.html': ['Extent: NSIDC Sea Ice Index, version 4 (<a href="https://doi.org/10.7265/a98x-0f50">doi:10.7265/a98x-0f50</a>). Volume: Copernicus Marine, Mercator GLORYS12 ocean reanalysis and CryoSat-2 + SMOS satellite thickness.',
      'NSIDC\'s daily extent, shown as a 5-day mean; anomalies and standard deviations are calculated by this page. Volume (thickness × concentration × area) is calculated here from the Copernicus grids.',
      ['sea-ice.html', 'scripts/build_seaice_volume.py'], ['data/N_seaice_extent_daily_v4.0.csv', 'data/seaice_volume_glorys.csv', 'data/seaice_volume_cs2smos.csv']],
    'co2.html': ['NOAA Global Monitoring Laboratory, Mauna Loa daily mean CO₂.',
      'NOAA\'s daily values are shown unchanged; monthly means, trend and growth are calculated by this page.', ['co2.html'], 'data/co2_daily_mlo.txt'],
    'ch4.html': ['NOAA Global Monitoring Laboratory, globally averaged marine surface methane.',
      'NOAA\'s monthly means, trend and annual increases are shown unchanged.', ['ch4.html'], 'data/ch4_mm_gl.txt'],
    'land-ice.html': ['NASA JPL GRACE/GRACE-FO mascon time series, release 06.3 v4: Greenland (<a href="https://doi.org/10.5067/TEMSC-GT634">doi:10.5067/TEMSC-GT634</a>) and Antarctica (<a href="https://doi.org/10.5067/TEMSC-AT634">doi:10.5067/TEMSC-AT634</a>).',
      'NASA\'s monthly mass values are shown relative to the first 12 months; trends, yearly changes and the sea-level equivalent (362 Gt = 1 mm) are calculated by this page.', ['land-ice.html'], ['data/grace_greenland.txt', 'data/grace_antarctica.txt']],
    'pdo.html': ['NOAA NCEI Pacific Decadal Oscillation index, based on ERSST.',
      'NOAA\'s monthly values are shown unchanged; the 12-month and decade averages are calculated by this page.', ['pdo.html'], 'data/pdo_ncei.dat'],
    'sun.html': ['WDC-SILSO, Royal Observatory of Belgium, International Sunspot Number version 2 (<a href="https://doi.org/10.24414/qnza-ac80">doi:10.24414/qnza-ac80</a>).',
      'SILSO\'s monthly and 13-month smoothed values are shown unchanged; cycle minima and maxima and the yearly averages are calculated by this page.', ['sun.html'], ['data/SN_m_tot_V2.0.csv', 'data/SN_ms_tot_V2.0.csv']],
    'eei.html': ['NASA CERES EBAF-TOA Edition 4.2.1 (<a href="https://doi.org/10.5067/TERRA-AQUA-NOAA20/CERES/EBAF-TOA_L3B004.2.1">doi:10.5067/TERRA-AQUA-NOAA20/CERES/EBAF-TOA_L3B004.2.1</a>).',
      'NASA\'s own global monthly means; the imbalance is absorbed solar minus outgoing longwave radiation. Running means are calculated by this page.', ['scripts/build_ceres.py'], 'data/ceres_ebaf_global.csv'],
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
  const toggle = () => top.classList.toggle('show', window.scrollY > 400);
  window.addEventListener('scroll', toggle, { passive: true }); toggle();
  top.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  if (!window.Chart) return;

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
    return ch.data.datasets.map((ds, i) => ({ text: ds.label, datasetIndex: i, hidden: !ch.isDatasetVisible(i),
      color: typeof ds.borderColor === 'string' ? ds.borderColor : '#888',
      fill: typeof ds.backgroundColor === 'string' ? ds.backgroundColor : null,
      line: ds.borderWidth === undefined || ds.borderWidth > 0, dash: !!(ds.borderDash && ds.borderDash.length) }))
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
    afterDestroy(ch) { const st = LG.get(ch); if (st) { st.box.remove(); LG.delete(ch); } }
  });

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
})();

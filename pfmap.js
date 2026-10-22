// Permafrost map (slow signals page): ground temperature at 10 m depth from ESA Permafrost_cci, a MODELLED product,
// drawn from data/permafrost_map.json (scripts/build_permafrost.py) on a view of the northern hemisphere from above
// the North Pole (Lambert azimuthal equal-area, so areas are not distorted), down to 25°N to include the Tibetan Plateau.
// Like the sea-surface maps (sstmap.js), it is a Chart.js chart whose hidden axes are the map's flat coordinates, so the
// site's zoom, "Add to image" and share links work on it; a plugin paints it pixel by pixel from the 0.5° grid.
(function () {
  const D = 180 / Math.PI, LONC = -45, LATMIN = 25;              // 45°W at the bottom: Greenland below the pole
  const RMAX = 2 * Math.sin((90 - LATMIN) / 2 / D);
  const proj = (lon, lat) => { const r = 2 * Math.sin((90 - lat) / 2 / D), l = (lon - LONC) / D; return [r * Math.sin(l), -r * Math.cos(l)]; };
  const unproj = (x, y) => { const r = Math.hypot(x, y); if (r > RMAX) return null;
    return [((LONC + Math.atan2(x, -y) * D) % 360 + 540) % 360 - 180, 90 - 2 * Math.asin(r / 2) * D]; };
  const FULL = { x0: -RMAX * 1.02, x1: RMAX * 1.02, y0: -RMAX * 1.02, y1: RMAX * 1.02 };

  // blue = still frozen (permafrost), from deep cold to just below 0 °C; tan to brown = not frozen at 10 m
  const SCALES = {
    temp: { lo: -15, hi: 7, stops: [[-15, '#0b1f4d'], [-8, '#1f4e99'], [-4, '#4a8bd0'], [-2, '#9ccaea'], [-.5, '#d6ecf6'], [0, '#f3e3bd'], [3, '#e0a35a'], [7, '#9a5a17']],
      ticks: [-15, -10, -5, -2, 0, 5], label: 'at 10 m depth:', fmt: v => (v < 0 ? '−' : '') + Math.abs(v) + (v === 5 ? ' °C' : '') },
    change: { lo: -2.25, hi: 2.25, stops: [[-2.25, '#18498a'], [-1, '#5a9bcc'], [-.4, '#cfe3ef'], [-.1, '#f4f4f4'], [.1, '#f7f7f7'], [.4, '#fbd6c3'], [1, '#f4a582'], [1.6, '#d6604d'], [2.25, '#7f0f1e']],
      ticks: [-2, -1, 0, 1, 2], label: 'change since 1997–2006:', fmt: v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v) + (v === 2 ? ' °C' : '') }
  };
  const hex = h => [1, 3, 5].map(k => parseInt(h.slice(k, k + 2), 16));
  const colorAt = (S, v) => { const st = S.stops; if (v <= st[0][0]) return hex(st[0][1]); if (v >= st[st.length - 1][0]) return hex(st[st.length - 1][1]);
    let i = 1; while (st[i][0] < v) i++; const [a, ca] = st[i - 1], [b, cb] = st[i], t = (v - a) / (b - a), A = hex(ca), B = hex(cb);
    return A.map((x, k) => Math.round(x + (B[k] - x) * t)); };
  const LUTN = 1024;
  Object.values(SCALES).forEach(S => { S.lut = new Uint8Array(LUTN * 3); for (let k = 0; k < LUTN; k++) S.lut.set(colorAt(S, S.lo + (S.hi - S.lo) * k / (LUTN - 1)), k * 3); });

  const CH = Array.from({ length: 92 }, (_, i) => String.fromCharCode(35 + i)).filter(c => c !== '\\').join('');
  const decode = o => { const s = o.codes, v = new Float32Array(s.length); for (let i = 0; i < s.length; i++) v[i] = s[i] === ' ' ? NaN : o.lo + CH.indexOf(s[i]) * o.step; return v; };

  // land mask, 0.25° (1440 × 720), from the Natural Earth outline the sea-surface maps use: land without a value is
  // grey (ice sheets, large lakes), sea is a plain background
  const land = () => fetch('data/land_110m.json').then(r => r.json()).then(L => {
    const W = 1440, H = 720, c = document.createElement('canvas'); c.width = W; c.height = H; const x = c.getContext('2d'); x.fillStyle = '#000';
    L.rings.forEach(r => { const p = []; let prev = null;
      for (let i = 0; i < r.length; i += 2) { let lo = r[i]; if (prev != null) lo += Math.round((prev - lo) / 360) * 360; p.push([lo, r[i + 1]]); prev = lo; }
      const back = p[0][0] - p[p.length - 1][0], total = p[p.length - 1][0] - p[0][0] + back - Math.round(back / 360) * 360;
      if (Math.abs(total) > 180) { const pole = p.reduce((s, q) => s + q[1], 0) < 0 ? -90 : 90; p.push([p[p.length - 1][0], pole], [p[0][0], pole]); }
      [-360, 0, 360].forEach(sh => { x.beginPath(); p.forEach(([lo, la], k) => { const X = (lo + sh + 180) * 4, Y = (90 - la) * 4; k ? x.lineTo(X, Y) : x.moveTo(X, Y); }); x.closePath(); x.fill(); }); });
    const d = x.getImageData(0, 0, W, H).data, m = new Uint8Array(W * H); for (let i = 0; i < m.length; i++) m[i] = d[i * 4 + 3] > 127 ? 1 : 0; return m;
  }).catch(() => null);

  const latLab = v => Math.abs(v) + '°N';
  const lonLab = v => { v = ((Math.round(v) % 360) + 540) % 360 - 180; return v === 0 ? '0°' : Math.abs(v) === 180 ? '180°' : Math.abs(v) + (v < 0 ? '°W' : '°E'); };
  const sg = v => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(1);

  function chart(id, M, o) {
    o = o || {};
    const G = M.grid, V = { temp: decode(M.temp), change: decode(M.change) };
    let kind = o.kind || 'temp', mask = null, cache = null, hov = null, ch;
    land().then(m => { mask = m; cache = null; if (ch) ch.draw(); });
    const at = (A, lon, lat) => {                     // blended value of the four nearest grid points with a value
      const gy = (lat - G.lat0) / G.step, gx = (lon - G.lon0) / G.step; if (gy < -.5 || gy > G.nlat - .5) return NaN;
      const j0 = Math.max(0, Math.min(G.nlat - 1, Math.floor(gy))), j1 = Math.min(G.nlat - 1, j0 + 1), fy = Math.max(0, Math.min(1, gy - j0));
      const f0 = Math.floor(gx), fx = gx - f0, i0 = ((f0 % G.nlon) + G.nlon) % G.nlon, i1 = (i0 + 1) % G.nlon;
      let sw = 0, sv = 0; const add = (j, i, w) => { const v = A[j * G.nlon + i]; if (v === v) { sw += w; sv += v * w; } };
      add(j0, i0, (1 - fx) * (1 - fy)); add(j0, i1, fx * (1 - fy)); add(j1, i0, (1 - fx) * fy); add(j1, i1, fx * fy);
      return sw > .2 ? sv / sw : NaN; };
    function paint(a, sx, sy) {
      const s = Math.min(window.devicePixelRatio || 1, 1.5), w = Math.max(1, Math.round((a.right - a.left) * s)), h = Math.max(1, Math.round((a.bottom - a.top) * s));
      const key = [sx.min, sx.max, sy.min, sy.max, w, h, kind, THEME.dark, !!mask].join();
      if (cache && cache.key === key) return cache.c;
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const x = c.getContext('2d'), img = x.createImageData(w, h), px = img.data, S = SCALES[kind], A = V[kind], k = (LUTN - 1) / (S.hi - S.lo);
      const LAND = THEME.dark ? [78, 78, 78] : [190, 190, 190], SEA = THEME.dark ? [34, 40, 46] : [233, 238, 242];
      for (let j = 0; j < h; j++) {
        const y = sy.max - (j + .5) / h * (sy.max - sy.min);
        for (let i = 0; i < w; i++) {
          const p = unproj(sx.min + (i + .5) / w * (sx.max - sx.min), y); if (!p) continue;
          const q = (j * w + i) * 4, v = at(A, p[0], p[1]); let col;
          if (v === v) { const t = Math.max(0, Math.min(LUTN - 1, Math.round((v - S.lo) * k))) * 3; px[q] = S.lut[t]; px[q + 1] = S.lut[t + 1]; px[q + 2] = S.lut[t + 2]; px[q + 3] = 255; continue; }
          col = mask && mask[Math.min(719, Math.floor((90 - p[1]) * 4)) * 1440 + Math.min(1439, Math.floor((p[0] + 180) * 4))] ? LAND : SEA;
          px[q] = col[0]; px[q + 1] = col[1]; px[q + 2] = col[2]; px[q + 3] = 255;
        }
      }
      x.putImageData(img, 0, 0); cache = { key, c }; return c;
    }
    const line = (ctx, sx, sy, pts) => { ctx.beginPath(); pts.forEach(([lo, la], n) => { const [X, Y] = proj(lo, la); const a = sx.getPixelForValue(X), b = sy.getPixelForValue(Y); n ? ctx.lineTo(a, b) : ctx.moveTo(a, b); }); };
    const plug = { id: 'pfmap',
      beforeDatasetsDraw(c) {
        const { ctx, chartArea: a, scales: { x: sx, y: sy } } = c;
        ctx.save(); ctx.beginPath(); ctx.rect(a.left, a.top, a.right - a.left, a.bottom - a.top); ctx.clip();
        ctx.drawImage(paint(a, sx, sy), a.left, a.top, a.right - a.left, a.bottom - a.top);
        ctx.strokeStyle = THEME.dark ? 'rgba(255,255,255,.22)' : 'rgba(0,0,0,.2)'; ctx.lineWidth = .7; ctx.setLineDash([2, 3]);
        [30, 45, 60, 75].forEach(la => { line(ctx, sx, sy, Array.from({ length: 181 }, (_, n) => [-180 + 2 * n, la])); ctx.stroke(); });
        for (let L = -180; L < 180; L += 30) { line(ctx, sx, sy, [[L, LATMIN], [L, 89.5]]); ctx.stroke(); }
        ctx.setLineDash([]); ctx.strokeStyle = THEME.mut; ctx.lineWidth = 1; line(ctx, sx, sy, Array.from({ length: 181 }, (_, n) => [-180 + 2 * n, LATMIN])); ctx.stroke();
        ctx.font = '10px system-ui,sans-serif'; ctx.fillStyle = THEME.mut; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const halo = THEME.dark ? 'rgba(0,0,0,.55)' : 'rgba(255,255,255,.75)', txt = (t, X, Y) => { ctx.strokeStyle = halo; ctx.lineWidth = 3; ctx.strokeText(t, X, Y); ctx.fillText(t, X, Y); };
        [45, 60, 75].forEach(la => { const [X, Y] = proj(LONC + 180 + 15, la); txt(latLab(la), sx.getPixelForValue(X), sy.getPixelForValue(Y)); });
        for (let L = -180; L < 180; L += 30) { const [X, Y] = proj(L, LATMIN + 2.5); txt(lonLab(L), sx.getPixelForValue(X), sy.getPixelForValue(Y)); }
        if (hov) { const [X, Y] = proj(hov[0], hov[1]); ctx.strokeStyle = THEME.ink; ctx.lineWidth = 2; ctx.strokeRect(sx.getPixelForValue(X) - 4, sy.getPixelForValue(Y) - 4, 8, 8); }
        ctx.restore();
      },
      afterDraw(c) {
        if (hov && hov[2]) {                          // the value at the pointer, in a box on the map itself
          const { ctx, chartArea: a, scales: { x: sx, y: sy } } = c, [X, Y] = proj(hov[0], hov[1]);
          const px = sx.getPixelForValue(X), py = sy.getPixelForValue(Y), L = hov[2];
          ctx.save(); ctx.font = '12px system-ui,sans-serif';
          const w = Math.max(...L.map(t => ctx.measureText(t).width)) + 16, h = 17 * L.length + 8;
          let bx = px + 12, by = py - h - 8; if (bx + w > a.right - 2) bx = px - w - 12; if (bx < a.left + 2) bx = a.left + 2; if (by < a.top + 2) by = py + 12;
          ctx.fillStyle = THEME.dark ? 'rgba(20,18,14,.92)' : 'rgba(255,255,255,.94)'; ctx.strokeStyle = THEME.mut; ctx.lineWidth = .8;
          ctx.beginPath(); ctx.rect(bx, by, w, h); ctx.fill(); ctx.stroke();
          ctx.fillStyle = THEME.ink; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
          L.forEach((t, k) => { ctx.font = (k === 1 ? '600 ' : '') + '12px system-ui,sans-serif'; ctx.fillText(t, bx + 8, by + 5 + 17 * k); });
          ctx.restore();
        }
        const S = SCALES[kind], { ctx, chartArea: a } = c, w = Math.min(260, a.right - a.left - 150), x0 = a.right - w, y0 = 6; if (w < 60) return;
        const t0 = S.ticks[0], t1 = S.ticks[S.ticks.length - 1];
        ctx.save();
        for (let n = 0; n < w; n++) { ctx.fillStyle = `rgb(${colorAt(S, t0 + (t1 - t0) * n / (w - 1)).join(',')})`; ctx.fillRect(x0 + n, y0, 1.2, 9); }
        ctx.strokeStyle = THEME.mut; ctx.lineWidth = .5; ctx.strokeRect(x0, y0, w, 9);
        ctx.fillStyle = THEME.ink; ctx.font = '11px system-ui,sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
        S.ticks.forEach(v => ctx.fillText(S.fmt(v), x0 + (v - t0) / (t1 - t0) * w, y0 + 11));
        ctx.textAlign = 'right'; ctx.fillText(S.label, x0 - 8, y0 + 1); ctx.restore();
      } };
    ch = new Chart(document.getElementById(id), { type: 'scatter', plugins: [plug], data: { datasets: [{ data: [], pointRadius: 0 }] },
      options: { animation: false, maintainAspectRatio: true, aspectRatio: 1.05, layout: { padding: { top: 30 } },
        onHover: (e, el, c) => {
          const { x: sx, y: sy } = c.scales, a = c.chartArea, rd = o.readout || (() => {});
          const p = !(e.type === 'mouseout' || e.x < a.left || e.x > a.right || e.y < a.top || e.y > a.bottom) && unproj(sx.getValueForPixel(e.x), sy.getValueForPixel(e.y));
          if (!p) { if (hov) { hov = null; rd(''); c.draw(); } return; }
          const j = Math.round((p[1] - G.lat0) / G.step), i = ((Math.round((p[0] - G.lon0) / G.step) % G.nlon) + G.nlon) % G.nlon;
          if (j < 0 || j >= G.nlat) { if (hov) { hov = null; rd(''); c.draw(); } return; }
          const n = j * G.nlon + i, t = V.temp[n], d = V.change[n], B = G.lat0 + j * G.step, L = G.lon0 + i * G.step;
          const place = `${B.toFixed(2)}°N ${Math.abs(L).toFixed(2)}${L < 0 ? '°W' : '°E'}`;
          hov = [L, B, [place, t !== t ? 'no value (sea, ice sheet or outside the model)' : kind === 'change'
            ? (d === d ? `${sg(d)} °C since ${M.base}` : '') + ` · now ${t.toFixed(1).replace('-', '−')} °C (${t < 0 ? 'frozen' : 'not frozen'})`
            : `${t.toFixed(1).replace('-', '−')} °C at 10 m (${t < 0 ? 'frozen' : 'not frozen'})` + (d === d ? ` · ${sg(d)} since ${M.base}` : ''),
            ...(t === t ? [`modelled, ${M.year}`] : [])]];
          rd(`${B.toFixed(2)}°N ${lonLab(L) === '0°' ? '0°' : Math.abs(L).toFixed(2) + (L < 0 ? '°W' : '°E')}: ` + (t !== t ? 'no value here (outside the area the model covers, sea or ice sheet)' :
            `${t.toFixed(1)} °C at 10 m in ${M.year} (${t < 0 ? 'frozen' : 'not frozen'})` + (d === d ? `, ${sg(d)} °C since ${M.base}` : '') + ' · modelled'));
          c.draw();
        },
        plugins: { legend: { display: false }, tooltip: { enabled: false },
          zoom: { limits: { x: { min: FULL.x0, max: FULL.x1, minRange: .08 }, y: { min: FULL.y0, max: FULL.y1, minRange: .08 } },
            zoom: { mode: 'xy', drag: { maintainAspectRatio: true, drawTime: 'afterDraw', backgroundColor: 'rgba(255,255,255,.28)', borderColor: THEME.dark ? '#fff' : '#111', borderWidth: 2 } }, pan: { mode: 'xy' } } },
        scales: { x: { type: 'linear', display: false, min: FULL.x0, max: FULL.x1 }, y: { type: 'linear', display: false, min: FULL.y0, max: FULL.y1 } } } });
    ch.$set = k => { kind = k; cache = null; hov = null; (o.readout || (() => {}))(''); ch.draw(); };
    return ch;
  }
  window.PFMap = { chart };
})();

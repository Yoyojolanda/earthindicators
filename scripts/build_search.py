#!/usr/bin/env python3
"""Build search.json, the index for the site-wide search (magnifying glass in the header).

One entry per thing a reader can land on:
  - each page as a whole: menu name, <title>, meta description and its "In short" text (inshort.js)
  - each chart box on a data page (div.box): its section-menu name (data-nav) and its fixed text
  - each answer on claims.html (details.claim): the claim, the answer, the evidence and the extra words in data-also
  - each heading with an id elsewhere (e.g. methods.html)
Chart titles are set by each page's script: the fixed part of each title is read from there (live numbers
and dates are left out). Each chart section also gets its section-menu name as extra search words.

Entry: {"u": url with #anchor, "p": page name, "t": title, "x": text (shortened), "a": extra search words}
Run from the repo root: python3 scripts/build_search.py
"""
import html.parser, json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAXX = 1500                                   # characters of text kept per entry (enough to match and quote)

site_js = (ROOT / 'site.js').read_text(encoding='utf-8')
PAGES = re.findall(r"\['([\w-]+\.html)',\s*'([^']+)'", site_js.split('const PAGES')[1].split('];')[0])
NAMES = dict(PAGES)
NAMES.setdefault('methods.html', 'Data and methods')

def js_strings(s):
    return [re.sub(r"\\(.)", r"\1", m) for m in re.findall(r"'((?:[^'\\]|\\.)*)'", s)]

# "In short" text per page; {air.now}-style live numbers are dropped
inshort = (ROOT / 'inshort.js').read_text(encoding='utf-8').split('window.IN_SHORT')[1]
IN_SHORT = {}
for page, body in re.findall(r"\n  '([\w-]+\.html)': \{(.*?)\n  \}", inshort, re.S):
    parts = re.findall(r"(?:text|units):\s*(\[.*?\]|'(?:[^'\\]|\\.)*')", body, re.S)
    txt = ' '.join(t for p in parts for t in js_strings(p))
    IN_SHORT[page] = re.sub(r'\s+', ' ', re.sub(r'\{[\w.]+\}', '', txt)).strip()

SKIP = {'script', 'style', 'svg', 'canvas', 'nav', 'noscript', 'button', 'select', 'template'}
VOID = {'br', 'img', 'input', 'meta', 'link', 'hr', 'source', 'wbr', 'col', 'area', 'base', 'embed', 'param', 'track'}

class Page(html.parser.HTMLParser):
    def __init__(self, name):
        super().__init__(convert_charrefs=True)
        self.name, self.skip, self.stack = name, 0, []
        self.title, self.desc, self.in_title = '', '', False
        self.units = [{'u': name, 't': '', 'x': [], 'a': ''}]   # first one: the page as a whole
        self.head = None          # unit whose title is being read from a heading

    def new(self, anchor, title='', also=''):
        self.units.append({'u': self.name + ('#' + anchor if anchor else ''), 't': title, 'x': [], 'a': also})

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls = (a.get('class') or '').split()
        if tag not in VOID: self.stack.append(tag)
        if tag == 'title': self.in_title = True
        if tag == 'meta' and a.get('name') == 'description': self.desc = a.get('content', '')
        if self.skip or tag in SKIP:
            if tag in SKIP and tag not in VOID: self.skip += 1
            return
        if tag == 'details' and 'claim' in cls and a.get('id'):
            self.new(a['id'], '', a.get('data-also', '')); self.units[-1]['claim'] = True
        elif tag == 'div' and 'box' in cls:
            self.new(a.get('id'), a.get('data-nav', '')); self.units[-1]['box'] = True; self.units[-1]['ids'] = [a.get('id')]
        elif tag == 'h3' and 'ct' in cls and self.units[-1].get('claim') and not self.units[-1]['t']:
            self.head = ('h3', len(self.stack))
        elif tag in ('h2', 'h3') and a.get('id'):
            u = self.units[-1]
            if u.get('box'):
                u['ids'].append(a['id'])
                if not u['u'].count('#'): u['u'] += '#' + a['id']     # box without its own id
            elif not u.get('box') and not u.get('claim'):
                self.new(a['id']); self.head = (tag, len(self.stack))

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag in SKIP and self.skip: self.skip -= 1
        if self.head and tag == self.head[0] and len(self.stack) == self.head[1]: self.head = None
        if self.stack and tag not in VOID:
            while self.stack and self.stack.pop() != tag: pass

    def handle_data(self, d):
        if self.in_title: self.title += d; return
        if self.skip or not d.strip(): return
        u = self.units[-1]
        if self.head: u['t'] += d
        else: u['x'].append(d)

def clean(s): return re.sub(r'\s+', ' ', s).strip()

# chart titles set by a page's script: $('t1').textContent=`...` or document.getElementById('t1').textContent='...'
TSET = re.compile(r"(?:\$|getElementById)\(\s*['\"](\w+)['\"]\s*\)\.textContent\s*=\s*([`'\"])(.*?)(?<!\\)\2", re.S)
TAIL = re.compile(r"\s*(,|:|;|\bto|\bin|\bfor|\bsince|\band|\bvs|\bwhich ends|–|-|\()\s*$")
def script_titles(src):
    out = {}
    for i, _, t in TSET.findall(src):
        # live parts (${...}) are dropped, with the words and punctuation that only made sense next to them
        H = '\x00'
        t = re.sub(r'\$\{[^}]*\}', H, t)
        t = re.sub(H + r'(s|[,.\d]+)', H, t)                              # ${d}s, ${n},000
        t = re.sub(H + r'\s*[–-]\s*' + H, H, t)                           # ranges
        t = re.sub(r'\(\s*' + H + r'\s*\)', '', t)
        t = re.sub(r'\b(of|over|since|to|in|for|ending)\s+' + H, '', t)
        t = t.replace(H, ' ')
        t = re.sub(r'(\d)–(?=\s|$|\))', r'\1', t)                          # 1850–${y} -> 1850
        for _ in range(3):
            t = re.sub(r'\(\s*\)|\s+–\s*(?=[:,;(]|$)|^[\s:,;–-]+', '', t)
            t = re.sub(r'\s+([,:;)])', r'\1', t)
            t = re.sub(r'([,:;])\s*([,:;])', r'\2', t)
            t = re.sub(r',\s*\(', ' (', t); t = re.sub(r'\(\s*-(\w)', r'(\1', t)
            t = clean(t)
        while TAIL.search(t): t = TAIL.sub('', t)
        t = t[:1].upper() + t[1:]
        if len(t) > 6 and t not in out.setdefault(i, []): out[i].append(t)
    return out

out = []
for f in sorted(ROOT.glob('*.html')):
    name = f.name
    if name not in NAMES: continue
    src = f.read_text(encoding='utf-8')
    titles = script_titles(src)
    p = Page(name); p.feed(src)
    pname = NAMES[name]
    first = p.units[0]
    first['t'] = clean(p.title.split('|')[0]) or pname
    first['x'] = [p.desc, IN_SHORT.get(name, '')] + first['x']
    for u in p.units:
        t, x = clean(u['t']), clean(' '.join(u['x']))
        st = [v for i in u.get('ids', []) if i for v in titles.get(i, [])]
        if st:              # the chart's own title first; section name and other versions of the title as extra words
            u['a'] = clean(' '.join([t] + st + [u['a']]))
            if not t or len(st[0]) >= 25: t = st[0]       # a short, generic chart title: keep the section name
        if not t and not x: continue
        if not t: t = pname
        e = {'u': u['u'], 'p': pname, 't': t, 'x': x[:MAXX]}
        if u['a']: e['a'] = clean(u['a'])
        out.append(e)

(ROOT / 'search.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(len(out), 'entries,', (ROOT / 'search.json').stat().st_size // 1024, 'kB')

# -*- coding: utf-8 -*-
"""Build consolidated reading data JSON from a KOReader statistics.sqlite3 + epub cover folder.

Usage:
  python build_data.py --db <statistics.sqlite3> --epub-root <folder> \
      --out <reading_data.json> \
      [--threshold 300] \
      [--merge '{"1":6}'] \
      [--covers '{"6":"cover.jpg","13":"cover.jpg"}'] \
      [--names '{"6":"短名"}'] \
      [--colors '{"6":"#hex"}'] \
      [--fallback-dir <dir>]

Arguments:
  --db          KOReader statistics database path (required)
  --epub-root   Folder containing epub books (recursively scanned for covers) (required)
  --out         Output JSON path (required)
  --threshold   Minimum reading time in seconds to include a book (default 300 = 5min)
  --merge       JSON map alias book id -> canonical book id, for merging different editions
  --covers      JSON map canonical book id -> cover image filename (relative to --epub-root scan
                or absolute path). If omitted, auto-match covers by book title/epub metadata.
  --names       JSON map book id -> short display title. Falls back to a smart-truncated book title.
  --colors      JSON map book id -> hex accent color. Falls back to a generated palette color.
  --fallback-dir  Folder with pre-generated covers to use when epub has no embedded cover.

Output JSON structure:
  {meta, stats, books:[{id,title,shortTitle,author,seconds,minutes,pages,readPages,
    language,firstDay,lastDay,activeDays,cover(base64 data URI),color,mergedFrom}],
   calendar:{ 'YYYY-MM-DD': [{bookId,seconds,minutes}, ...] }}
"""
import argparse, sqlite3, os, io, json, datetime, collections, base64, zipfile, re, sys
import xml.etree.ElementTree as ET

# ---------- cover extraction from epub ----------
NS = {'dc':'http://purl.org/dc/elements/1.1/',
      'opf':'http://www.idpf.org/2007/opf',
      'container':'urn:oasis:names:tc:opendocument:xmlns:container'}

def _find_opf(z):
    try:
        c = ET.fromstring(z.read('META-INF/container.xml'))
        for rf in c.findall('.//container:rootfile', NS):
            return rf.get('full-path')
    except Exception:
        pass
    for n in z.namelist():
        if n.lower().endswith('.opf'):
            return n
    return None

def _cover_href(opf_path, z):
    root = ET.fromstring(z.read(opf_path))
    md = root.find('opf:metadata', NS); manifest = root.find('opf:manifest', NS)
    cid = None
    if md is not None:
        for m in md.findall('opf:meta', NS):
            if (m.get('name') or '').lower() == 'cover':
                cid = m.get('content')
    if cid and manifest is not None:
        for it in manifest.findall('opf:item', NS):
            if it.get('id') == cid:
                return it.get('href')
    if manifest is not None:
        for it in manifest.findall('opf:item', NS):
            if 'image' in (it.get('media-type') or '') and ('cover' in (it.get('properties') or '').lower() or 'cover' in (it.get('id') or '').lower()):
                return it.get('href')
    return None

def scan_epub_covers(epub_root):
    """Return list of {path, title, authors, cover_bytes}."""
    out = []
    for dp, dns, fns in os.walk(epub_root):
        for fn in fns:
            if not fn.lower().endswith('.epub'):
                continue
            p = os.path.join(dp, fn)
            try:
                z = zipfile.ZipFile(p)
                opf = _find_opf(z)
                title, authors, href = '', [], None
                if opf:
                    root = ET.fromstring(z.read(opf))
                    md = root.find('opf:metadata', NS)
                    if md is not None:
                        t = md.find('dc:title', NS)
                        if t is not None and t.text: title = t.text.strip()
                        authors = [c.text.strip() for c in md.findall('dc:creator', NS) if c.text]
                    href = _cover_href(opf, z)
                cand = []
                if opf and href:
                    from urllib.parse import unquote
                    href = unquote(href.split('#')[0])
                    base = opf.rsplit('/',1)[0] if '/' in opf else ''
                    cand.append((base+'/'+href) if base else href)
                cand += ['cover.jpeg','cover.jpg','cover.png','images/cover.jpg','Images/cover.jpg']
                names = z.namelist()
                data = None
                for c in cand:
                    m = c if c in names else next((n for n in names if n.lower()==c.lower()), None)
                    if not m: continue
                    try:
                        data = z.read(m); break
                    except Exception:
                        continue
                z.close()
                out.append({'path':p, 'file':os.path.basename(p), 'title':title,
                            'authors':authors, 'cover':data})
            except Exception as e:
                print('  [warn] epub read failed:', fn, str(e), file=sys.stderr)
    return out

def norm(s):
    s = re.sub(r'\(.*?\)|（.*?）|\[.*?\]|【.*?】', ' ', s or '')  # strip brackets/parens
    s = re.sub(r'z-?library|1lib|z-lib|omnibus|box set|全集|套装|典藏版|出品|\d+册', ' ', s, flags=re.I)
    s = re.sub(r'[^\w\u4e00-\u9fff]+', '', s)
    return s.lower()

def auto_match_cover(book, epubs):
    """Fuzzy-match a book to an epub cover by title tokens + author."""
    bt = norm(book['title'])
    best, best_score = None, 0.0
    for e in epubs:
        if not e['cover']: continue
        et = norm(e['title'])
        if not et: continue
        # containment + token overlap
        score = 0.0
        if bt and (bt in et or et in bt):
            score = 0.9 + 0.1*min(len(bt),len(et))/max(len(bt),len(et))
        else:
            common = len(set(bt) & set(et))
            score = common / max(len(set(bt)), len(set(et)), 1)
        if book.get('author') and e['authors']:
            if norm(book['author']) and norm(book['author']) in ' '.join(norm(a) for a in e['authors']):
                score += 0.15
        if score > best_score:
            best, best_score = e, score
    return (best, best_score) if best_score >= 0.55 else (None, best_score)

DEFAULT_PALETTE = ['#8B5E3C','#2F4858','#3E5CA8','#B0441E','#2E7D7B','#B08A3E',
                   '#6C4A6E','#4C7A4B','#7A6BA8','#B23A2E','#C4962E','#4A6070','#7A5230','#3B6B5E']

def img_to_datauri(data, width=210, quality=82):
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert('RGB')
    if im.width > width:
        im = im.resize((width, round(im.height*width/im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=quality, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')

def smart_short(title, maxlen=14):
    t = re.sub(r'[（(].*?[)）]', '', title or '')
    t = re.sub(r'：.*', '', t).strip()
    return (t[:maxlen] + '…') if len(t) > maxlen else (t or '未命名')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--epub-root', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--threshold', type=int, default=300)
    ap.add_argument('--merge', default='{}')
    ap.add_argument('--covers', default='{}')
    ap.add_argument('--names', default='{}')
    ap.add_argument('--colors', default='{}')
    ap.add_argument('--fallback-dir', default='')
    a = ap.parse_args()

    MERGE   = {int(k):int(v) for k,v in json.loads(a.merge).items()}
    COVERS  = {int(k):v for k,v in json.loads(a.covers).items()}
    NAMES   = {int(k):v for k,v in json.loads(a.names).items()}
    COLORS  = {int(k):v for k,v in json.loads(a.colors).items()}

    conn = sqlite3.connect(a.db); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    # sanity check schema
    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    if 'book' not in tables or 'page_stat_data' not in tables:
        raise SystemExit('DB schema error: need book + page_stat_data tables (KOReader statistics.sqlite3)')

    rows = cur.execute('''SELECT id,title,authors,total_read_time,total_read_pages,pages,language
        FROM book WHERE COALESCE(total_read_time,0)>=? ORDER BY total_read_time DESC''',(a.threshold,)).fetchall()
    if not rows:
        raise SystemExit('No books above threshold; lower --threshold')

    print('Scanning epub covers in', a.epub_root, '...', file=sys.stderr)
    epubs = scan_epub_covers(a.epub_root)
    print('  found', len(epubs), 'epub files,', sum(1 for e in epubs if e['cover']), 'with covers', file=sys.stderr)

    def canon(bid): return MERGE.get(bid, bid)

    daily = collections.defaultdict(lambda: collections.defaultdict(int))
    for r in cur.execute('SELECT id_book,start_time,duration FROM page_stat_data'):
        day = datetime.datetime.fromtimestamp(r['start_time']).date().isoformat()
        daily[day][canon(r['id_book'])] += int(r['duration'] or 0)

    canon_ids = {canon(r['id']) for r in rows}
    book_days = collections.defaultdict(set)
    for day,bks in daily.items():
        for bid in bks:
            if bid in canon_ids: book_days[bid].add(day)

    grouped = collections.defaultdict(list)
    for r in rows: grouped[canon(r['id'])].append(r)

    # fallback cover files map by filename
    fallback_files = {}
    if a.fallback_dir and os.path.isdir(a.fallback_dir):
        for fn in os.listdir(a.fallback_dir):
            fallback_files[fn.lower()] = os.path.join(a.fallback_dir, fn)

    books = []
    for idx,(bid,grp) in enumerate(sorted(grouped.items(), key=lambda kv:-sum(int(r['total_read_time'] or 0) for r in kv[1]))):
        primary = max(grp, key=lambda r: r['total_read_time'] or 0)
        seconds = sum(int(r['total_read_time'] or 0) for r in grp)
        pages = max(int(r['pages'] or 0) for r in grp)
        read_pages = sum(int(r['total_read_pages'] or 0) for r in grp)
        days = sorted(book_days[bid])

        # resolve cover bytes
        cdata = None
        if bid in COVERS:
            ref = COVERS[bid]
            if os.path.isabs(ref) and os.path.exists(ref):
                cdata = open(ref,'rb').read()
            else:
                m = next((e for e in epubs if e['file'].lower()==os.path.basename(ref).lower()), None)
                if m and m['cover']: cdata = m['cover']
                elif ref.lower() in fallback_files: cdata = open(fallback_files[ref.lower()],'rb').read()
                elif os.path.exists(ref): cdata = open(ref,'rb').read()
        if cdata is None:
            match,score = auto_match_cover(dict(primary), epubs)
            if match and match['cover']:
                cdata = match['cover']
                print(f'  auto-cover: {bid} <- {match["file"]} (score {score:.2f})', file=sys.stderr)
        if cdata is None:
            print(f'  [warn] no cover for book {bid}: {primary["title"][:40]} — use --covers or --fallback-dir', file=sys.stderr)
            cdata = _blank_cover()

        books.append({
            'id':bid, 'title':primary['title'],
            'shortTitle':NAMES.get(bid) or smart_short(primary['title']),
            'author':primary['authors'] or '',
            'seconds':seconds, 'minutes':round(seconds/60),
            'pages':pages, 'readPages':read_pages,
            'language':primary['language'],
            'firstDay':days[0] if days else None, 'lastDay':days[-1] if days else None,
            'activeDays':len(days),
            'cover':img_to_datauri(cdata),
            'color':COLORS.get(bid) or DEFAULT_PALETTE[idx % len(DEFAULT_PALETTE)],
            'mergedFrom':[r['id'] for r in grp] if len(grp)>1 else None,
        })

    calendar = {}
    for day in sorted(daily):
        entries=[{'bookId':bid,'seconds':sec,'minutes':round(sec/60,1)}
                 for bid,sec in daily[day].items() if bid in canon_ids]
        if entries: calendar[day]=sorted(entries,key=lambda e:-e['seconds'])

    all_days=[d for d,e in calendar.items() if sum(x['seconds'] for x in e)>0]
    first_day,last_day=min(calendar),max(calendar)
    total_sec=sum(b['seconds'] for b in books)
    excluded=cur.execute('SELECT COUNT(*) FROM book WHERE COALESCE(total_read_time,0)<?',(a.threshold,)).fetchone()[0]

    data={
      'meta':{'source':'KOReader statistics.sqlite3','generated':datetime.date.today().isoformat(),
              'thresholdSeconds':a.threshold,'firstDay':first_day,'lastDay':last_day,
              'excludedBooks':excluded,'mergedEditions':sum(1 for b in books if b['mergedFrom'])},
      'stats':{'bookCount':len(books),'totalSeconds':total_sec,'totalMinutes':round(total_sec/60),
               'totalHours':round(total_sec/3600,1),'activeDays':len(all_days),
               'spanDays':(datetime.date.fromisoformat(last_day)-datetime.date.fromisoformat(first_day)).days+1},
      'books':books,'calendar':calendar}

    with open(a.out,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,separators=(',',':'))
    print(f'\nDone: {len(books)} books, {len(calendar)} reading days, {data["stats"]["totalHours"]}h -> {a.out}')
    conn.close()

def _blank_cover():
    from PIL import Image, ImageDraw
    im=Image.new('RGB',(180,270),(230,225,214)); d=ImageDraw.Draw(im)
    d.rectangle([20,20,160,250],outline=(150,145,135),width=2)
    return _img_bytes(im)

def _img_bytes(im):
    import io
    b=io.BytesIO(); im.save(b,'JPEG',quality=80); return b.getvalue()

if __name__=='__main__':
    main()

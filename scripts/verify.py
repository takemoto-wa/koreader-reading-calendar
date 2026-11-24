# -*- coding: utf-8 -*-
"""Verify a rendered reading-calendar HTML for structural correctness.

Usage:
  python verify.py --html <index.html> [--data <reading_data.json>] [--screenshot <out.png>]
"""
import argparse, re, json, os

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--html',required=True)
    ap.add_argument('--data',default='')
    ap.add_argument('--screenshot',default='')
    a=ap.parse_args()

    h=open(a.html,encoding='utf-8').read()
    ok=True
    def check(label,cond,extra=''):
        nonlocal ok
        ok = ok and cond
        print(('[OK]  ' if cond else '[FAIL]')+' '+label+((' — '+extra) if extra else ''))

    check('no unresolved placeholder', '__DATA_JSON__' not in h)
    check('no external http(s) references', len(re.findall(r'https?://',h))==0)
    m=re.search(r'const DATA = (\{.*?\});\n',h)
    check('embedded DATA found', bool(m))
    if m:
        d=json.loads(m.group(1))
        bs=d['books']; cal=d['calendar']
        check('books count matches stats', len(bs)==d['stats']['bookCount'], f'{len(bs)} books')
        check('all covers embedded', all(b.get('cover','').startswith('data:image/jpeg;base64,') for b in bs))
        check('calendar non-empty', len(cal)>0, f'{len(cal)} days')
        ids={b['id'] for b in bs}
        orphan=set()
        for day in cal.values():
            for e in day:
                if e['bookId'] not in ids: orphan.add(e['bookId'])
        check('calendar bookIds all map to books', not orphan, f'orphans={sorted(orphan)}')
        if a.data:
            src=json.load(open(a.data,encoding='utf-8'))
            check('matches source data', src==d)
    check('key UI strings present', all(s in h for s in ['阅读日历','阅读时长排行','正在看：','平方根缩放']))
    check('CSS variables present', all(v in h for v in ['--accent','--canvas','--shadow-2']))

    if a.screenshot:
        import subprocess, glob
        cands=glob.glob(r'C:\Program Files\Google\Chrome\Application\chrome.exe')+glob.glob(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
        if not cands:
            print('[warn] no Chrome/Edge found; skip screenshot')
        else:
            url='file:///'+a.html.replace('\\','/')
            cmd=[cands[0],'--headless=new','--disable-gpu','--no-sandbox','--hide-scrollbars',
                 '--virtual-time-budget=5000','--window-size=1440,2300',f'--screenshot={a.screenshot}',url]
            subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            check('screenshot created', os.path.exists(a.screenshot))

    print('\nRESULT:', 'PASS' if ok else 'FAIL')
    raise SystemExit(0 if ok else 1)

if __name__=='__main__': main()

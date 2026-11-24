# -*- coding: utf-8 -*-
"""Render the self-contained HTML by injecting reading_data.json into template.html.

Usage:
  python render_html.py --data <reading_data.json> \
      --template <skill>/assets/template.html --out <index.html>
"""
import argparse, json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--template', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    data = json.load(open(a.data, encoding='utf-8'))
    tpl = open(a.template, encoding='utf-8').read()
    assert '__DATA_JSON__' in tpl, 'template missing __DATA_JSON__ placeholder'

    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = tpl.replace('__DATA_JSON__', data_json, 1)
    assert '__DATA_JSON__' not in html

    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Rendered {a.out} ({len(html.encode("utf-8"))} bytes)')

if __name__ == '__main__':
    main()

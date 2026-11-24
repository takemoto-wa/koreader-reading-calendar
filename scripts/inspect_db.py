# -*- coding: utf-8 -*-
"""Inspect a KOReader statistics.sqlite3: schema sanity, candidate books, date range.

Usage:
  python inspect_db.py --db "<statistics.sqlite3>" [--threshold 300]
"""
import argparse, sqlite3, datetime

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',required=True)
    ap.add_argument('--threshold',type=int,default=300)
    a=ap.parse_args()

    conn=sqlite3.connect(a.db); conn.row_factory=sqlite3.Row; cur=conn.cursor()
    tables={r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    print('Tables/views:', ', '.join(sorted(tables)))
    if 'book' not in tables or 'page_stat_data' not in tables:
        raise SystemExit('Schema error: need book + page_stat_data tables')

    total=cur.execute('SELECT COUNT(*) FROM book').fetchone()[0]
    qual=cur.execute('SELECT COUNT(*) FROM book WHERE COALESCE(total_read_time,0)>=?',(a.threshold,)).fetchone()[0]
    print(f'Books total: {total} | above threshold ({a.threshold}s = {a.threshold/60:.0f}min): {qual}')

    rng=cur.execute('SELECT MIN(start_time),MAX(start_time) FROM page_stat_data').fetchone()
    if rng[0]:
        print('Reading span:',datetime.datetime.fromtimestamp(rng[0]).date(),'->',
              datetime.datetime.fromtimestamp(rng[1]).date())

    print('\nCandidate books (id | minutes | title):')
    for r in cur.execute('''SELECT id,total_read_time,title FROM book
                            WHERE COALESCE(total_read_time,0)>=? ORDER BY total_read_time DESC''',(a.threshold,)):
        print(f"  {r['id']:>3} | {r['total_read_time']/60:>8.1f}min | {r['title'][:60]}")
    print('\nBelow threshold (excluded):')
    for r in cur.execute('''SELECT id,total_read_time,title FROM book
                            WHERE COALESCE(total_read_time,0)<? ORDER BY total_read_time DESC''',(a.threshold,)):
        print(f"  {r['id']:>3} | {r['total_read_time']/60:>8.1f}min | {r['title'][:60]}")
    conn.close()

if __name__=='__main__': main()

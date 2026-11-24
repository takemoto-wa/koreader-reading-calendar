# -*- coding: utf-8 -*-
"""Generate an elegant typographic fallback cover for a book with no available cover art.

Usage:
  python gen_cover.py --title "The Martian" --author "Andy Weir" \
      --out cover.jpg [--theme space|ember|violet|forest|gold|auto] [--width 360]

Themes are color harmonies chosen by keyword when theme=auto.
"""
import argparse, os, math, random, io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W_H = (360, 540)
THEMES = {
    'space':  ((8,10,30),(26,20,66),(86,130,220)),
    'ember':  ((28,8,6),(120,40,16),(196,88,40)),
    'violet': ((10,6,26),(48,20,70),(200,150,90)),
    'forest': ((6,24,18),(18,58,42),(120,180,130)),
    'gold':   ((28,22,8),(70,54,16),(220,190,90)),
    'slate':  ((18,20,24),(44,48,56),(150,160,175)),
}
KEYWORDS = {
    'martian':'ember','mars':'ember','fire':'ember','火星':'ember',
    'hail':'space','space':'space','star':'space','project':'space','宇宙':'space','挽救':'space',
    'egg':'violet','gold':'gold','人民币':'gold','春雪':'violet',
    'forest':'forest','green':'forest','silk':'forest',
}
FONT_DIR = r'C:\Windows\Fonts'

def font(name, size, italic=False):
    fb = {'serif':'georgiab.ttf','serif_i':'georgiai.ttf','sans':'arialbd.ttf','sans_r':'arial.ttf'}
    path = os.path.join(FONT_DIR, fb.get(name, 'georgiab.ttf'))
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()

def lerp(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

def vgrad(c1,c2):
    im=Image.new('RGB',W_H); px=im.load()
    for y in range(W_H[1]):
        c=lerp(c1,c2,y/(W_H[1]-1))
        for x in range(W_H[0]): px[x,y]=c
    return im

def stars(im,seed,count=170,top_only=False):
    random.seed(seed); d=ImageDraw.Draw(im,'RGBA')
    ymax=int(W_H[1]*0.72) if top_only else W_H[1]
    for _ in range(count):
        x=random.randint(0,W_H[0]); y=random.randint(0,ymax); r=random.choice([.6,.8,1,1.2,1.6])
        d.ellipse([x-r,y-r,x+r,y+r],fill=(255,255,255,random.randint(90,230)))

def orb(im,cx,cy,r,color,glow=55):
    g=Image.new('RGBA',W_H,(0,0,0,0)); gd=ImageDraw.Draw(g)
    gd.ellipse([cx-r,cy-r,cx+r,cy+r],fill=(*color,210))
    g=g.filter(ImageFilter.GaussianBlur(glow)); im=Image.alpha_composite(im.convert('RGBA'),g)
    d=ImageDraw.Draw(im,'RGBA')
    for i in range(r,0,-1):
        c=lerp(color,tuple(min(255,v+55) for v in color),1-i/r)
        d.ellipse([cx-i,cy-i,cx+i,cy+i],fill=(*c,255))
    return im

def ctext(d,text,cy,fnt,fill=(255,255,255),maxw=W_H[0]-56):
    lines=[]; cur=''
    for w in text.split():
        t=(cur+' '+w).strip()
        if d.textlength(t,font=fnt)<=maxw or not cur: cur=t
        else: lines.append(cur); cur=w
    if cur: lines.append(cur)
    lh=fnt.size*1.18; total=lh*len(lines); y=cy-total/2
    for ln in lines:
        d.text(((W_H[0]-d.textlength(ln,font=fnt))/2,y),ln,font=fnt,fill=fill); y+=lh
    return len(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--title',required=True); ap.add_argument('--author',default='')
    ap.add_argument('--out',required=True); ap.add_argument('--theme',default='auto')
    ap.add_argument('--width',type=int,default=360); ap.add_argument('--seed',type=int,default=7)
    a=ap.parse_args()

    theme=a.theme
    if theme=='auto':
        key=a.title.lower()
        theme=next((v for k,v in KEYWORDS.items() if k in key),'slate')
    c1,c2,accent=THEMES[theme]

    im=vgrad(c1,c2); stars(im,a.seed,180)
    im=orb(im,180,160,80,accent,glow=55)
    d=ImageDraw.Draw(im,'RGBA')
    d.rectangle([10,10,W_H[0]-10,W_H[1]-10],outline=(255,255,255,55),width=1)
    d=ImageDraw.Draw(im,'RGBA')
    if a.author:
        d.text((W_H[0]/2,300),a.author.upper(),font=font('sans',18),fill=(235,235,235,250),anchor='mm')
    words=a.title.split()
    if len(words)>2:
        mid=len(words)//2
        ctext(d,' '.join(words[:mid]),360,font('serif',38))
        ctext(d,' '.join(words[mid:]),416,font('serif',38))
    else:
        ctext(d,a.title,388,font('serif',42))
    d.text((W_H[0]/2,500),'A  R E A D I N G  R E C O R D',font=font('sans_r',11),fill=(210,210,210,200),anchor='mm')

    im=im.convert('RGB')
    if im.width!=a.width:
        im=im.resize((a.width,round(im.height*a.width/im.width)),Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)),exist_ok=True)
    im.save(a.out,'JPEG',quality=90)
    print('Generated fallback cover:',a.out,'theme=',theme)

if __name__=='__main__': main()

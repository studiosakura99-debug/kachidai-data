#!/usr/bin/env python3
# 指定IDのリポートを確実にCSVへ取り込む（遅い間隔＋シェル検出リトライ）
import re, csv, os, sys, time, html as H, urllib.request, datetime, collections
ROOT="https://min-repo.com"; UA="KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"
IV=float(os.environ.get("KD_INTERVAL","3.0"))
TITLE=re.compile(r'(?is)<h1[^>]*>(.*?)</h1>'); DR=re.compile(r'([0-9]{1,2})/([0-9]{1,2})\([^)]*\)')
PUB=re.compile(r'datePublished["\']*[:=]["\']+(20[0-9]{2})-([0-9]{2})-([0-9]{2})')
ROW=re.compile(r'(?is)<tr[^>]*>(.*?)</tr>'); CELL=re.compile(r'(?is)<td[^>]*>(.*?)</td>')
TAGS=re.compile(r'<[^>]+>'); CG=re.compile(r"content_group['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]")
MASK={"","-","－","−","―","–","--","‒"}
HEADER=["business_date","hall","machine","machine_number","difference","games","payout_rate","source_url"]
def text(s): return H.unescape(TAGS.sub(" ",s)).strip().replace("\n"," ")
def fetch(u):
    for a in range(5):
        try:
            rq=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja,en;q=0.5"})
            with urllib.request.urlopen(rq,timeout=45) as r: b=r.read().decode("utf-8","replace")
            if len(b)<40000 and "<tr" not in b:
                time.sleep(8); continue
            return b
        except Exception:
            time.sleep(8)
    return None
def ti(s):
    s=(s or "").strip()
    if s in MASK: return None
    m=re.search(r'[-−－]?[0-9][0-9,]*',s); return None if not m else int(m.group(0).replace(",",""))
def td_(s):
    s=(s or "").strip()
    if s in MASK: return None
    m=re.search(r'[-−－]?[0-9][0-9,]*(\.[0-9]+)?',s); return None if not m else float(m.group(0).replace(",",""))
def parse(page,url):
    tm=TITLE.search(page); title=text(tm.group(1)) if tm else ""
    dm=DR.search(title)
    if not dm: return []
    mo,da=int(dm.group(1)),int(dm.group(2)); yr=datetime.date.today().year
    pm=PUB.search(page)
    if pm:
        yr=int(pm.group(1))
        if mo==12 and int(pm.group(2))==1: yr-=1
    ds="%04d-%02d-%02d"%(yr,mo,da); hall=title[dm.end():].strip(); out=[]
    for r in ROW.finditer(page):
        cells=[text(c) for c in CELL.findall(r.group(1))]
        if len(cells)<5 or not re.search(r'[0-9]',cells[1] or ''): continue
        no=ti(cells[1])
        if not no or no<=0: continue
        out.append([ds,hall,cells[0],no,ti(cells[2]),ti(cells[3]),td_(cells[4]),url])
    return out
def rid(u):
    m=re.search(r'/(\d+)/',u or ""); return m.group(1) if m else ""
ids=[l.strip() for l in open("fill_ids.txt",encoding="utf-8") if l.strip() and l.strip().isdigit()]
rows=list(csv.DictReader(open("latest.csv",encoding="utf-8"))) if os.path.exists("latest.csv") else []
have=set(rid(r["source_url"]) for r in rows)
print("既存 %d行 / 対象 %d件"%(len(rows),len(ids)))
added=0
for i in ids:
    if i in have: print("%s 既に有り"%i); continue
    url="%s/%s/?kishu=all"%(ROOT,i)
    page=fetch(url)
    if page is None:
        print("%s 取得不可(ブロック)"%i); time.sleep(IV); continue
    g=(CG.findall(page) or [""])[0].strip()
    rs=parse(page,url)
    if g!="宮城県" or not rs:
        print("%s SKIP group=%s rows=%d"%(i,g or "無し",len(rs))); time.sleep(IV); continue
    rows.extend(dict(zip(HEADER,[str(x) if x is not None else '' for x in r])) for r in rs)
    have.add(i); added+=len(rs); print("%s OK %s %d行"%(i,rs[0][0],len(rs)))
    time.sleep(IV)
cutoff=(datetime.date.today()-datetime.timedelta(days=90)).isoformat()
rows=[r for r in rows if (r.get('business_date') or '')>=cutoff]
seen=set(); ded=[]
for r in sorted(rows,key=lambda x:(x.get('business_date',''),x.get('hall',''),x.get('machine',''),str(x.get('machine_number',''))),reverse=True):
    k=(r.get('business_date'),r.get('hall'),r.get('machine_number'))
    if k in seen: continue
    seen.add(k); ded.append(r)
with open("latest.csv","w",encoding="utf-8",newline="\n") as f:
    w=csv.DictWriter(f,fieldnames=HEADER); w.writeheader()
    for r in ded: w.writerow({k:(r.get(k) or '') for k in HEADER})
days=collections.Counter(r['business_date'] for r in ded); newest={}
for r in ded:
    h=r['hall']
    if h not in newest or r['business_date']>newest[h]: newest[h]=r['business_date']
lat=max(days); gap=[h for h in {r['hall'] for r in ded} if newest.get(h)!=lat]
print("追加%d行 合計%d行 %d店舗 日付%s"%(added,len(ded),len({r['hall'] for r in ded}),dict(sorted(days.items(),reverse=True)[:4])))
print("最新日(%s)に無い店: %d %s"%(lat,len(gap),gap[:10]))

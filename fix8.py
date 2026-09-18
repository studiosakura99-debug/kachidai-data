import re, csv, time, html as H, urllib.request, datetime, collections
ROOT="https://min-repo.com"; UA="KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"; IV=1.4
TITLE=re.compile(r'(?is)<h1[^>]*>(.*?)</h1>'); DR=re.compile(r'([0-9]{1,2})/([0-9]{1,2})\([^)]*\)')
PUB=re.compile(r'datePublished["\']*[:=]["\']+(20[0-9]{2})-([0-9]{2})-([0-9]{2})')
ROW=re.compile(r'(?is)<tr[^>]*>(.*?)</tr>'); CELL=re.compile(r'(?is)<td[^>]*>(.*?)</td>')
TAGS=re.compile(r'<[^>]+>'); CG=re.compile(r"content_group['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]")
MASK={"","-","－","−","―","–","--","‒"}
HEADER=["business_date","hall","machine","machine_number","difference","games","payout_rate","source_url"]
def text(s): return H.unescape(TAGS.sub(" ",s)).strip().replace("\n"," ")
def fetch(u):
    for a in range(4):
        try:
            rq=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja,en;q=0.5"})
            with urllib.request.urlopen(rq,timeout=45) as r:
                b=r.read().decode("utf-8","replace")
            if len(b)<40000 and "<tr" not in b:
                print("   shell?",len(b)); time.sleep(5); continue
            return b
        except Exception as e:
            if a==3: raise
            time.sleep(5)
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
    if not dm: return [],"no-date"
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
    return out,hall
def rid(u):
    m=re.search(r'/(\d+)/',u or ""); return m.group(1) if m else ""
ids={"多賀城ひまわり":"3357858","パラディソ1000泉店":"3357610","パラディソ沖野店":"3357138",
     "パチンコタイガー松森店":"3357637","メルヘンワールド亘理店":"3356952","メルヘンワールド涌谷店":"3357557"}
rows=list(csv.DictReader(open("latest.csv",encoding="utf-8")))
have=set(rid(r["source_url"]) for r in rows)
added=0
for name,i in ids.items():
    url="%s/%s/?kishu=all"%(ROOT,i)
    try: page=fetch(url)
    except Exception as e:
        print("%-20s 取得失敗 %s"%(name,e)); continue
    g=(CG.findall(page) or [""])[0].strip()
    rs,hall=parse(page,url)
    print("%-20s group=%s hall=%s 行=%d %s"%(name,g or "無し",hall,len(rs), rs[0][0] if rs else "-"))
    if g=="宮城県" and rs:
        if i in have: print("   すでにCSVに有り")
        else:
            rows.extend(dict(zip(HEADER,[str(x) if x is not None else '' for x in r])) for r in rs)
            have.add(i); added+=len(rs)
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
print("="*44)
print("追加%d行 合計%d行 %d店舗"%(added,len(ded),len({r['hall'] for r in ded})))
print("日付",dict(sorted(days.items(),reverse=True)[:4]))
print("最新日(%s)にデータが無い店: %d"%(lat,len(gap)),gap[:10])

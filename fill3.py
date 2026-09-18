import re, csv, time, html as H, urllib.request, urllib.parse, datetime, collections
ROOT="https://min-repo.com"; UA="KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"; IV=1.2
# 相対hrefにも対応（サイドバーの最新リポート欄は /ID/ 形式）
A=re.compile(r'href="(?:https?://min-repo\.com)?/(\d+)/"[^>]*>(.*?)</a>', re.S)
TD=re.compile(r'^\s*([0-9]{1,2}/[0-9]{1,2}\([^)]*\))\s*(.+)$')
TITLE=re.compile(r'(?is)<h1[^>]*>(.*?)</h1>'); DR=re.compile(r'([0-9]{1,2})/([0-9]{1,2})\([^)]*\)')
PUB=re.compile(r'datePublished["\']*[:=]["\']+(20[0-9]{2})-([0-9]{2})-([0-9]{2})')
ROW=re.compile(r'(?is)<tr[^>]*>(.*?)</tr>'); CELL=re.compile(r'(?is)<td[^>]*>(.*?)</td>')
TAGS=re.compile(r'<[^>]+>'); CG=re.compile(r"content_group['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]")
MASK={"","-","－","−","―","–","--","‒"}
HEADER=["business_date","hall","machine","machine_number","difference","games","payout_rate","source_url"]
def text(s): return H.unescape(TAGS.sub(" ",s)).strip().replace("\n"," ")
def fetch(u):
    for a in range(3):
        try:
            rq=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja,en;q=0.5"})
            with urllib.request.urlopen(rq,timeout=45) as r: return r.read().decode("utf-8","replace")
        except Exception:
            if a==2: raise
            time.sleep(4)
def ti(s):
    s=(s or "").strip()
    if s in MASK: return None
    m=re.search(r'[-−－]?[0-9][0-9,]*',s); return None if not m else int(m.group(0).replace(",",""))
def td_(s):
    s=(s or "").strip()
    if s in MASK: return None
    m=re.search(r'[-−－]?[0-9][0-9,]*(\.[0-9]+)?',s); return None if not m else float(m.group(0).replace(",",""))
def dk(t):
    m=re.match(r'^\s*([0-9]{1,2})/([0-9]{1,2})',t or "")
    return "%02d/%02d"%(int(m.group(1)),int(m.group(2))) if m else "00/00"
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
targets=["ひまわり宮城岩沼店","ハードロック仙台一番町店","パチンコタイガー松森店","パラディソ1000泉店",
         "パラディソ沖野店","メルヘンワールド亘理店","メルヘンワールド涌谷店","多賀城ひまわり"]
rows=list(csv.DictReader(open("latest.csv",encoding="utf-8")))
have=set(rid(r["source_url"]) for r in rows)
print("開始 %d行"%len(rows))
added=0
for name in targets:
    body=fetch(ROOT+"/?s="+urllib.parse.quote(name))
    cands=[]
    for m in A.finditer(body):
        t=text(m.group(2)); mm=TD.match(t)
        if mm and name.replace(" ","") in mm.group(2).replace(" ",""):
            cands.append((dk(mm.group(1)), mm.group(2).strip(), m.group(1)))
    cands=sorted(set(cands), reverse=True)
    print("%-20s 候補%d 最上位=%s"%(name,len(cands),cands[:2]))
    for d,store,rid_ in cands[:2]:
        if rid_ in have: continue
        try: page=fetch("%s/%s/?kishu=all"%(ROOT,rid_))
        except Exception as e:
            print("   fetch fail",rid_,e); continue
        g=(CG.findall(page) or [""])[0].strip()
        if g!="宮城県":
            print("   SKIP %s (%s)"%(store,g or "無し")); have.add(rid_); continue
        rs=parse(page,"%s/%s/?kishu=all"%(ROOT,rid_))
        if rs:
            rows.extend(dict(zip(HEADER,[str(x) if x is not None else '' for x in r])) for r in rs)
            have.add(rid_); added+=len(rs); print("   +%s %s %d件"%(store,rs[0][0],len(rs)))
        time.sleep(IV)
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
    h=r['hall']; d=r['business_date']
    if h not in newest or d>newest[h]: newest[h]=d
latest=max(days); gap=sorted(h for h in {r['hall'] for r in ded} if newest.get(h)!=latest)
print("="*46)
print("追加%d行 合計%d行 %d店舗"%(added,len(ded),len({r['hall'] for r in ded})))
print("日付",dict(sorted(days.items(),reverse=True)[:5]))
print("最新営業日(%s)にデータが無い店: %d"%(latest,len(gap)), gap[:12])

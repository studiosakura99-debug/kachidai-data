#!/usr/bin/env python3
# KachiDai 自動収集装置 v4
#  1) 店舗ごとに「その店の最新リポート」を必ず取る（全店カバレッジ保証）
#  2) その後、カテゴリ/新着で残り枠を埋める（取得予算内）
#  3) 宮城県厳密ゲート + 増分 + 90日ローリング
import re, sys, time, html as H, urllib.request, urllib.parse, urllib.error, datetime, os, csv

ROOT = "https://min-repo.com"
UA = "KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"
INTERVAL = float(os.environ.get("KD_INTERVAL", "1.2"))
BUDGET = int(os.environ.get("KD_BUDGET", "260"))     # この実行で取得する最大リポート数
PER_STORE = int(os.environ.get("KD_PER_STORE", "3")) # 店舗ごとに取る最大リポート数
KEEP_DAYS = 90
CSV_PATH = "latest.csv"; VERDICTS = "id_verdicts.txt"; STORES = "stores_miyagi.txt"
WARDS = [ROOT + p for p in [
    "/category/%e4%bb%99%e5%8f%b0%e5%b8%82%e9%9d%92%e8%91%89%e5%8c%ba/",
    "/category/%e4%bb%99%e5%8f%b0%e5%b8%82%e5%ae%ae%e5%9f%8e%e9%87%8e%e5%8c%ba/",
    "/category/%e4%bb%99%e5%8f%b0%e5%b8%82%e8%8b%a5%e6%9e%97%e5%8c%ba/",
    "/category/%e4%bb%99%e5%8f%b0%e5%b8%82%e5%a4%aa%e7%99%bd%e5%8c%ba/",
    "/category/%e4%bb%99%e5%8f%b0%e5%b8%82%e6%b3%89%e5%8c%ba/",
    "/category/%e5%ae%ae%e5%9f%8e%e7%9c%8c/",
]]
ANCHOR = re.compile(r'href="https?://[^"]*/(\d+)/"[^>]*>([^<]+)</a>')
TITLE_DATE = re.compile(r'^\s*([0-9]{1,2}/[0-9]{1,2}\([^)]*\))\s*(.+)$')
TITLE = re.compile(r'(?is)<h1[^>]*>(.*?)</h1>')
DATE_R = re.compile(r'([0-9]{1,2})/([0-9]{1,2})\([^)]*\)')
PUBLISHED = re.compile(r'datePublished["\']*[:=]["\']+(20[0-9]{2})-([0-9]{2})-([0-9]{2})')
ROW = re.compile(r'(?is)<tr[^>]*>(.*?)</tr>')
CELL = re.compile(r'(?is)<td[^>]*>(.*?)</td>')
TAGS = re.compile(r'<[^>]+>')
CG = re.compile(r"content_group['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]")
MASK = {"", "-", "－", "−", "―", "–", "--", "‒"}
HEADER = ["business_date","hall","machine","machine_number","difference","games","payout_rate","source_url"]

def text(s): return H.unescape(TAGS.sub("", s)).strip()

def fetch(url):
    last = None
    for a in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
            with urllib.request.urlopen(req, timeout=45) as r:
                b = r.read().decode("utf-8", "replace")
            if len(b) < 40000 and "<tr" not in b:
                last = "shell(%dB)" % len(b); time.sleep(2); continue
            return b
        except urllib.error.HTTPError as e:
            last = e.code
            if e.code in (403, 429, 503):
                time.sleep(3); continue
            raise
        except Exception as e:
            last = e; time.sleep(3)
    raise RuntimeError("fetch failed: %s" % last)

def to_int(s):
    s=(s or "").strip()
    if s in MASK: return None
    m=re.search(r'[-−－]?[0-9][0-9,]*', s)
    return None if not m else int(m.group(0).replace(",","").replace("−","-").replace("－","-"))

def to_dec(s):
    s=(s or "").strip()
    if s in MASK: return None
    m=re.search(r'[-−－]?[0-9][0-9,]*(\.[0-9]+)?', s)
    return None if not m else float(m.group(0).replace(",","").replace("−","-").replace("－","-"))

def date_key(t):
    m=re.match(r'^\s*([0-9]{1,2})/([0-9]{1,2})', t or "")
    return "%02d/%02d"%(int(m.group(1)),int(m.group(2))) if m else "00/00"

def parse_report(page,url):
    tm=TITLE.search(page); title=text(tm.group(1)) if tm else ""
    dm=DATE_R.search(title)
    if not dm: return []
    mo,da=int(dm.group(1)),int(dm.group(2))
    yr=datetime.date.today().year
    pm=PUBLISHED.search(page)
    if pm:
        yr=int(pm.group(1))
        if mo==12 and int(pm.group(2))==1: yr-=1
    ds="%04d-%02d-%02d"%(yr,mo,da)
    hall=title[dm.end():].strip()
    out=[]
    for r in ROW.finditer(page):
        cells=[text(c) for c in CELL.findall(r.group(1))]
        if len(cells)<5 or not re.search(r'[0-9]',cells[1] or ''): continue
        no=to_int(cells[1])
        if not no or no<=0: continue
        out.append([ds,hall,cells[0],no,to_int(cells[2]),to_int(cells[3]),to_dec(cells[4]),url])
    return out

def rid_of(u): 
    m=re.search(r'/(\d+)/', u or ""); return m.group(1) if m else ""

def load_verdicts():
    d={}
    if os.path.exists(VERDICTS):
        for line in open(VERDICTS,encoding='utf-8'):
            p=line.split()
            if len(p)==2: d[p[0]]=p[1]
    return d

def load_rows():
    if os.path.exists(CSV_PATH):
        return list(csv.DictReader(open(CSV_PATH,encoding='utf-8')))
    return []

def write_rows(rows):
    cutoff=(datetime.date.today()-datetime.timedelta(days=KEEP_DAYS)).isoformat()
    rows=[r for r in rows if (r.get('business_date') or '')>=cutoff and rid_of(r.get('source_url',''))]
    seen=set(); ded=[]
    for r in sorted(rows,key=lambda x:(x.get('business_date',''),x.get('hall',''),x.get('machine',''),str(x.get('machine_number',''))),reverse=True):
        k=(r.get('business_date'),r.get('hall'),r.get('machine_number'))
        if k in seen: continue
        seen.add(k); ded.append(r)
    with open(CSV_PATH,'w',encoding='utf-8',newline='\n') as f:
        w=csv.DictWriter(f,fieldnames=HEADER); w.writeheader()
        for r in ded: w.writerow({k:(r.get(k) or '') for k in HEADER})
    return ded

def newest_of(rows):
    d={}
    for r in rows:
        h=r['hall']; day=r['business_date']
        if h not in d or day>d[h]: d[h]=day
    return d

def main():
    v=load_verdicts(); rows=load_rows(); have=set(rid_of(r['source_url']) for r in rows)
    print("既存 rows=%d verdicts=%d"%(len(rows),len(v)))
    stores=[l.strip() for l in open(STORES,encoding='utf-8')] if os.path.exists(STORES) else []
    budget=BUDGET; got_total=0; added_rows=0
    cur=newest_of(rows)

    # ---- 第1段: 店舗ごとに最新リポートを必ず取る ----
    per_store_log=[]
    for name in stores:
        if budget<=0: print("予算切れ: 店舗パス途中で終了"); break
        q=urllib.parse.quote(name); best=[]
        try: body=fetch(ROOT+"/?s="+q)
        except Exception as e:
            print("search fail",name,e,file=sys.stderr); continue
        for m in ANCHOR.finditer(body):
            rid=m.group(1); title=H.unescape(m.group(2)).strip()
            tm=TITLE_DATE.match(title)
            if tm: best.append((date_key(tm.group(1)),tm.group(2).strip(),rid))
        best.sort(reverse=True)
        picked=0
        for dk,store,rid in best:
            if picked>=PER_STORE or budget<=0: break
            if rid in have: continue
            url="%s/%s/?kishu=all"%(ROOT,rid)
            try: page=fetch(url)
            except Exception as e: print("  fetch fail",rid,e,file=sys.stderr); continue
            budget-=1
            g=(CG.findall(page) or [""])[0].strip()
            v[rid]="miyagi" if g=="宮城県" else ("outside" if g else "unknown")
            if v[rid]!="miyagi":
                print("  SKIP %s: %s"%(store,g or "group無し")); time.sleep(INTERVAL); continue
            rs=parse_report(page,url)
            if rs:
                rows.extend(dict(zip(HEADER,[str(x) if x is not None else '' for x in r])) for r in rs)
                have.add(rid); picked+=1; added_rows+=len(rs); got_total+=1
                v[rid]="miyagi"
            time.sleep(INTERVAL)
        per_store_log.append((name,picked,best[0][0] if best else "-"))
    print("第1段(店舗別): %d 店舗処理 / 取得 %d リポート / %d 行"%(len(per_store_log),got_total,added_rows))
    miss=[x for x in per_store_log if x[1]==0]
    print("最新リポートを取れなかった店: %d"%len(miss))
    for m in miss[:20]: print("   -",m[0],"最新=",m[2])

    # ---- 第2段: カテゴリの新着で残り予算を埋める ----
    tasks=[]; seen=set(have)
    for ward in WARDS:
        if budget<=0: break
        for page in range(1,4):
            u=ward if page==1 else ward[:-1]+"/page/%d/"%page
            try: body=fetch(u)
            except Exception: break
            n=0
            for m in ANCHOR.finditer(body):
                n+=1; rid=m.group(1); title=H.unescape(m.group(2)).strip()
                tm=TITLE_DATE.match(title)
                if tm and rid not in seen:
                    seen.add(rid); tasks.append((rid,tm.group(2).strip(),date_key(tm.group(1))))
            if n==0: break
            time.sleep(INTERVAL)
    tasks.sort(key=lambda t:t[2],reverse=True)
    catgot=0
    for rid,store,dk in tasks:
        if budget<=0: break
        url="%s/%s/?kishu=all"%(ROOT,rid)
        try: page=fetch(url)
        except Exception: continue
        budget-=1
        g=(CG.findall(page) or [""])[0].strip()
        v[rid]="miyagi" if g=="宮城県" else ("outside" if g else "unknown")
        if v[rid]!="miyagi": time.sleep(INTERVAL); continue
        rs=parse_report(page,url)
        if rs:
            rows.extend(dict(zip(HEADER,[str(x) if x is not None else '' for x in r])) for r in rs)
            catgot+=1; added_rows+=len(rs)
        time.sleep(INTERVAL)
    print("第2段(カテゴリ): %d リポート / 合計 %d 行追加"%(catgot,added_rows))

    out=[k for k,x in v.items() if x=="outside"]
    with open("outside_ids.txt","w",encoding='utf-8',newline='\n') as f:
        for k in sorted(out): f.write(k+"\n")
    rows=[r for r in rows if v.get(rid_of(r.get('source_url','')),"unknown")!="outside"]
    ded=write_rows(rows)
    with open(VERDICTS,'w',encoding='utf-8',newline='\n') as f:
        for k in sorted(v): f.write("%s %s\n"%(k,v[k]))
    days={}; stores_in=set()
    for r in ded:
        days[r['business_date']]=days.get(r['business_date'],0)+1; stores_in.add(r['hall'])
    print("書き込み %d 行 / %d 日 / %d 店舗 / outside %d"%(len(ded),len(days),len(stores_in),len(out)))
    for d in sorted(days,reverse=True)[:5]: print("  %s : %d"%(d,days[d]))
    newest=newest_of(ded)
    latest=max(days) if days else "-"
    gap=[h for h in stores_in if newest.get(h)!=latest]
    print("最新営業日(%s)にデータが無い店: %d"%(latest,len(gap)))
    for h in sorted(gap)[:20]: print("   -",h,newest.get(h))

main()

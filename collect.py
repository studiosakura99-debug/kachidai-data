#!/usr/bin/env python3
# KachiDai 自動収集装置 v3
#  - 宮城県限定（content_group 厳密ゲート）
#  - 増分収集（未取得リポートだけ取得して累積CSVに追記）
#  - 既存行の県外判定キャッシュ（id_verdicts.txt）で再判定コストを最小化
#  - 90日でローリング
import re, sys, time, html as H, urllib.request, urllib.parse, urllib.error, datetime, os, csv

ROOT = "https://min-repo.com"
UA = "KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"
INTERVAL = float(os.environ.get("KD_INTERVAL", "2.0"))
MAX_NEW = int(os.environ.get("KD_MAX_NEW", "450"))
PER_STORE = int(os.environ.get("KD_PER_STORE", "8"))
CSV_PATH = "latest.csv"
VERDICTS = "id_verdicts.txt"
KEEP_DAYS = 90
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
    for a in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read().decode("utf-8", "replace")
            if len(b) < 40000 and "<tr" not in b:
                last = "shell(%dB)" % len(b); time.sleep(3*(a+1)); continue
            return b
        except urllib.error.HTTPError as e:
            last = e.code
            if e.code in (403, 429, 503):
                time.sleep(5*(a+1)); continue
            raise
        except Exception as e:
            last = e; time.sleep(5*(a+1))
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

def load_verdicts():
    d={}
    if os.path.exists(VERDICTS):
        for line in open(VERDICTS,encoding='utf-8'):
            p=line.strip().split()
            if len(p)==2: d[p[0]]=p[1]
    return d

def save_verdicts(d):
    with open(VERDICTS,'w',encoding='utf-8',newline='\n') as f:
        for k in sorted(d): f.write("%s %s\n"%(k,d[k]))

def load_rows():
    rows=[]
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH,encoding='utf-8') as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows

def rid_of(u):
    m=re.search(r'/(\d+)/', u or "")
    return m.group(1) if m else ""

def write_rows(rows):
    cutoff=(datetime.date.today()-datetime.timedelta(days=KEEP_DAYS)).isoformat()
    rows=[r for r in rows if (r.get('business_date') or '')>=cutoff and rid_of(r.get('source_url','')) ]
    seen=set(); ded=[]
    for r in sorted(rows,key=lambda x:(x.get('business_date',''),x.get('hall',''),x.get('machine',''),str(x.get('machine_number',''))),reverse=True):
        k=(r.get('business_date'),r.get('hall'),r.get('machine_number'))
        if k in seen: continue
        seen.add(k); ded.append(r)
    with open(CSV_PATH,'w',encoding='utf-8',newline='\n') as f:
        w=csv.DictWriter(f,fieldnames=HEADER); w.writeheader()
        for r in ded:
            w.writerow({k:(r.get(k) or '') for k in HEADER})
    return ded

def main():
    v=load_verdicts(); rows=load_rows()
    print("既存: rows=%d verdicts=%d"%(len(rows),len(v)))
    # 1) 既存CSVに入っているIDの県外判定（未判定のものだけ実ページ確認）
    need=sorted({rid_of(r.get('source_url','')) for r in rows} - set(v.keys()))
    print("既存IDの未判定: %d 件"%(len(need)))
    for rid in need:
        url="%s/%s/?kishu=all"%(ROOT,rid)
        try:
            g=(CG.findall(fetch(url)) or [""])[0].strip()
            v[rid]="miyagi" if g=="宮城県" else ("outside" if g else "unknown")
        except Exception as e:
            v[rid]="unknown"; print("  verify fail",rid,e,file=sys.stderr)
        print("  %s -> %s"%(rid,v[rid])); time.sleep(INTERVAL)
    before=len(rows)
    rows=[r for r in rows if v.get(rid_of(r.get('source_url','')),"unknown")!="outside"]
    out_ids=[k for k,x in v.items() if x=="outside"]
    with open("outside_ids.txt","w",encoding='utf-8',newline='\n') as f:
        for k in sorted(out_ids): f.write(k+"\n")
    print("既存から県外削除: %d 行 / outside=%d"%(before-len(rows),len(out_ids)))

    # 2) 新着IDの列挙
    tasks=[]; seen=set(rid_of(r.get('source_url','')) for r in rows)
    for ward in WARDS:
        for page in range(1,13):
            u=ward if page==1 else ward[:-1]+"/page/%d/"%page
            try: body=fetch(u)
            except Exception as e:
                print("cat fail",u,e,file=sys.stderr); break
            n=0
            for m in ANCHOR.finditer(body):
                n+=1; rid=m.group(1); title=H.unescape(m.group(2)).strip()
                tm=TITLE_DATE.match(title)
                if tm and rid not in seen:
                    seen.add(rid); tasks.append((rid,tm.group(2).strip(),date_key(tm.group(1))))
            if n==0: break
            time.sleep(INTERVAL)
    # 2b) 店舗検索（?s=店名）— カテゴリ一覧に載らない店のリポートを拾う
    stores=[]
    if os.path.exists("stores_miyagi.txt"):
        stores=[l.strip() for l in open("stores_miyagi.txt",encoding="utf-8") if l.strip()]
    found=0
    for name in stores:
        got=0
        for page in range(1,3):
            q=urllib.parse.quote(name)
            u=ROOT+"/?s="+q if page==1 else ROOT+"/page/%d/?s=%s"%(page,q)
            try: body=fetch(u)
            except Exception as e:
                print("search fail",name,e,file=sys.stderr); break
            n=0
            for m in ANCHOR.finditer(body):
                n+=1; rid=m.group(1); title=H.unescape(m.group(2)).strip()
                tm=TITLE_DATE.match(title)
                if tm and rid not in seen and got<PER_STORE:
                    seen.add(rid); got+=1; found+=1
                    tasks.append((rid,tm.group(2).strip(),date_key(tm.group(1))))
            if n==0 or got>=PER_STORE: break
            time.sleep(INTERVAL)
        time.sleep(INTERVAL)
    print("店舗検索で追加: %d 件 / 検索店舗 %d"%(found,len(stores)))
    tasks.sort(key=lambda t:t[2],reverse=True)
    print("新着候補: %d / 取得上限 %d"%(len(tasks),MAX_NEW))
    added=0; nogroup=0; failed=0
    for rid,store,dk in tasks[:MAX_NEW]:
        url="%s/%s/?kishu=all"%(ROOT,rid)
        try: page=fetch(url)
        except Exception as e:
            failed+=1; print("report fail",rid,e,file=sys.stderr); continue
        g=(CG.findall(page) or [""])[0].strip()
        v[rid]="miyagi" if g=="宮城県" else ("outside" if g else "unknown")
        if v[rid]!="miyagi":
            if not g: nogroup+=1
            print("SKIP %s: %s"%(store,g or "group無し")); time.sleep(INTERVAL); continue
        rs=parse_report(page,url)
        if rs: rows.extend(dict(zip(HEADER,[str(x) if x is not None else '' for x in r])) for r in rs); added+=len(rs)
        time.sleep(INTERVAL)
        print("OK %s rows=%d"%(store,len(rs)))
    print("新規採用: %d 行 / group無し %d / 失敗 %d"%(added,nogroup,failed))
    ded=write_rows(rows)
    save_verdicts(v)
    days={}
    for r in ded:
        d=r['business_date']; days[d]=days.get(d,0)+1
    print("書き込み: %d 行 / %d 日 / %d 店舗"%(len(ded),len(days),len({r['hall'] for r in ded})))
    for d in sorted(days,reverse=True)[:6]: print("  %s : %d"%(d,days[d]))

main()

import re, csv, time, html as H, urllib.request, urllib.parse, datetime, collections
ROOT="https://min-repo.com"; UA="KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"; IV=1.2
A2=re.compile(r'href="https?://min-repo\.com/(\d+)/"[^>]*>(.*?)</a>', re.S)
TD=re.compile(r'^\s*([0-9]{1,2}/[0-9]{1,2}\([^)]*\))\s*(.+)$')
TAGS=re.compile(r'<[^>]+>')
def text(s): return H.unescape(TAGS.sub(" ",s)).strip()
def fetch(u):
    for a in range(3):
        try:
            rq=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja,en;q=0.5"})
            with urllib.request.urlopen(rq,timeout=45) as r: return r.read().decode("utf-8","replace")
        except Exception:
            if a==2: raise
            time.sleep(4)
targets=["ひまわり宮城岩沼店","ハードロック仙台一番町店","パチンコタイガー松森店","パラディソ1000泉店",
         "パラディソ沖野店","メルヘンワールド亘理店","メルヘンワールド涌谷店","多賀城ひまわり"]
for name in targets:
    body=fetch(ROOT+"/?s="+urllib.parse.quote(name))
    hits=[]
    for m in A2.finditer(body):
        t=text(m.group(2))
        mm=TD.match(t)
        if mm: hits.append((mm.group(1), mm.group(2).strip(), m.group(1)))
    hits.sort(reverse=True)
    print("%-22s アンカー%d件 上位: %s"%(name,len(hits),hits[:3]))
    time.sleep(IV)

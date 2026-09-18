import urllib.request, re, io
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36","Accept-Language":"ja"}
def get(u):
    r=urllib.request.Request(u,headers=UA)
    with urllib.request.urlopen(r,timeout=60) as f:
        return f.read().decode('utf-8','replace')
def text(h):
    return re.sub(r'\s+',' ',re.sub(r'(?s)<[^>]+>',' ',h)).strip()
ROW=re.compile(r'(?is)<tr[^>]*>(.*?)</tr>')
CELL=re.compile(r'(?is)<td[^>]*>(.*?)</td>')
out=[]
out.append("### 目的: min-repo のリポートで「差枚」がどの台に載るのかを実ページで確認する")
for u in ["https://min-repo.com/3357858/?kishu=all","https://min-repo.com/3355872/?kishu=all"]:
    try:
        p=get(u)
    except Exception as e:
        out.append("FETCH FAIL %s :: %s"%(u,e)); continue
    out.append("")
    out.append("URL %s len=%d 差枚出現=%d tr=%d td=%d"%(u,len(p),p.count("差枚"),p.count("<tr"),p.count("<td")))
    n=0; rows5=0; numdiff=0
    for m in ROW.finditer(p):
        cells=CELL.findall(m.group(1))
        if len(cells)<5: continue
        n+=1; rows5+=1
        vals=[text(c) for c in cells[:6]]
        d=vals[2] if len(vals)>2 else ""
        if re.match(r'^[-+]?[0-9,]+$', d or ''): numdiff+=1
        if n<=30:
            out.append("ROW%03d ncell=%d :: %s"%(n,len(cells)," | ".join(vals)[:180]))
    out.append("rows>=5cells=%d うち差枚が数値の行=%d"%(rows5,numdiff))
io.open("diag.txt","w",encoding="utf-8").write("\n".join(out))
print("\n".join(out))

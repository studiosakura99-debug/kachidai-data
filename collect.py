#!/usr/bin/env python3
# KachiDai データ収集 (宮城県限定・厳密ゲート) -> latest.csv / outside_ids.txt
import re, sys, time, html as H, urllib.request, urllib.error, datetime, os

ROOT = "https://min-repo.com"
UA = "KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"
INTERVAL = float(os.environ.get("KD_INTERVAL", "1.5"))
MAX_REPORTS = int(os.environ.get("KD_MAX", "250"))
OUT = os.environ.get("KD_OUT", "latest.csv")
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
# 実際の書式: 'content_group':'宮城県'
CG = re.compile(r"content_group['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]")
MASK = {"", "-", "－", "−", "―", "–", "--", "‒"}

def text(s):
    return H.unescape(TAGS.sub("", s)).strip()

def fetch(url):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read().decode("utf-8", "replace")
            if len(b) < 40000 and "<tr" not in b:      # シェル/チャレンジ判定
                last = RuntimeError("shell(%dB)" % len(b))
                time.sleep(3 * (attempt + 1)); continue
            return b
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429, 503):
                time.sleep(5 * (attempt + 1)); continue
            raise
        except Exception as e:
            last = e; time.sleep(5 * (attempt + 1))
    raise RuntimeError("fetch failed: %s" % last)

def to_int(s):
    s = (s or "").strip()
    if s in MASK: return None
    m = re.search(r'[-−－]?[0-9][0-9,]*', s)
    return None if not m else int(m.group(0).replace(",", "").replace("−", "-").replace("－", "-"))

def to_dec(s):
    s = (s or "").strip()
    if s in MASK: return None
    m = re.search(r'[-−－]?[0-9][0-9,]*(\.[0-9]+)?', s)
    return None if not m else float(m.group(0).replace(",", "").replace("−", "-").replace("－", "-"))

def date_key(t):
    m = re.match(r'^\s*([0-9]{1,2})/([0-9]{1,2})', t or "")
    return "%02d/%02d" % (int(m.group(1)), int(m.group(2))) if m else "00/00"

def pref_of(page):
    m = CG.findall(page)
    return m[0].strip() if m else ""

def parse_report(page, url):
    tm = TITLE.search(page)
    title = text(tm.group(1)) if tm else ""
    dm = DATE_R.search(title)
    if not dm: return []
    month, day = int(dm.group(1)), int(dm.group(2))
    year = datetime.date.today().year
    pm = PUBLISHED.search(page)
    if pm:
        year = int(pm.group(1))
        if month == 12 and int(pm.group(2)) == 1: year -= 1
    ds = "%04d-%02d-%02d" % (year, month, day)
    hall = title[dm.end():].strip()
    out = []
    for r in ROW.finditer(page):
        cells = [text(c) for c in CELL.findall(r.group(1))]
        if len(cells) < 5 or not re.search(r'[0-9]', cells[1] or ''): continue
        no = to_int(cells[1])
        if not no or no <= 0: continue
        out.append((ds, hall, cells[0], no, to_int(cells[2]), to_int(cells[3]), to_dec(cells[4]), url))
    return out

def main():
    tasks, seen = [], set()
    for ward in WARDS:
        for page in range(1, 13):
            u = ward if page == 1 else ward[:-1] + "/page/%d/" % page
            try:
                body = fetch(u)
            except Exception as e:
                print("cat fail", u, e, file=sys.stderr); break
            n = 0
            for m in ANCHOR.finditer(body):
                n += 1
                rid, title = m.group(1), H.unescape(m.group(2)).strip()
                tm = TITLE_DATE.match(title)
                if tm and rid not in seen:
                    seen.add(rid); tasks.append((rid, tm.group(2).strip(), date_key(tm.group(1))))
            if n == 0: break
            time.sleep(INTERVAL)
    tasks.sort(key=lambda t: t[2], reverse=True)
    print("tasks=%d newest=%s" % (len(tasks), tasks[0][2] if tasks else "-"))
    rows, outside, ok, failed, nogroup, dates = [], [], 0, 0, 0, {}
    for rid, store, dk in tasks[:MAX_REPORTS]:
        url = "%s/%s/?kishu=all" % (ROOT, rid)
        try:
            page = fetch(url)
        except Exception as e:
            failed += 1; print("report fail", rid, e, file=sys.stderr); continue
        pref = pref_of(page)
        if pref != "宮城県":                     # 厳密ゲート: content_group が宮城県以外/無しは不採用
            outside.append(rid)
            if not pref: nogroup += 1
            print("SKIP %s: %s (%s)" % (store, pref or "group無し", rid))
            time.sleep(INTERVAL); continue
        rs = parse_report(page, url)
        if not rs:
            failed += 1; continue
        ok += 1
        rows.extend(rs)
        dates[rs[0][0]] = dates.get(rs[0][0], 0) + len(rs)
        time.sleep(INTERVAL)
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3]), reverse=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("business_date,hall,machine,machine_number,difference,games,payout_rate,source_url\n")
        for r in rows:
            f.write("%s,%s,%s,%d,%s,%s,%s,%s\n" % (
                r[0], r[1].replace(",", " "), r[2].replace(",", " "), r[3],
                "" if r[4] is None else r[4], "" if r[5] is None else r[5],
                "" if r[6] is None else r[6], r[7]))
    with open("outside_ids.txt", "w", encoding="utf-8", newline="\n") as f:
        for i in sorted(set(outside)):
            f.write(i + "\n")
    print("採用=%d 除外(県外)=%d うちgroup無し=%d 失敗=%d 行=%d" % (ok, len(set(outside)), nogroup, failed, len(rows)))
    for d in sorted(dates, reverse=True)[:6]:
        print("  %s : %d rows" % (d, dates[d]))
    halls = sorted(set(r[1] for r in rows))
    print("店舗数=%d" % len(halls))
    print("wrote %s / outside_ids.txt" % OUT)

main()

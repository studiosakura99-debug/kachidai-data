#!/usr/bin/env python3
# KachiDai データ収集 (宮城県限定) -> latest.csv
# 出力: business_date,hall,machine,machine_number,difference,games,payout_rate,source_url
import re, sys, time, html as H, urllib.request, urllib.error, datetime, os

ROOT = "https://min-repo.com"
UA = "KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)"
INTERVAL = float(os.environ.get("KD_INTERVAL", "1.2"))
MAX_REPORTS = int(os.environ.get("KD_MAX", "130"))
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
NORTH = re.compile(r'[\u5317\u6d77\u9053]|岩手|福島|東京|埼玉|千葉|神奈川')
MASK = {"", "-", "－", "−", "―", "–", "--", "‒"}

def text(s):
    return H.unescape(TAGS.sub("", s)).strip()

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except Exception:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("fetch failed: " + url)

def to_int(s):
    s = (s or "").strip()
    if s in MASK:
        return None
    m = re.search(r'[-−－]?[0-9][0-9,]*', s)
    if not m:
        return None
    return int(m.group(0).replace(",", "").replace("−", "-").replace("－", "-"))

def to_dec(s):
    s = (s or "").strip()
    if s in MASK:
        return None
    m = re.search(r'[-−－]?[0-9][0-9,]*(\.[0-9]+)?', s)
    if not m:
        return None
    return float(m.group(0).replace(",", "").replace("−", "-").replace("－", "-"))

def date_key(t):
    m = re.match(r'^\s*([0-9]{1,2})/([0-9]{1,2})', t or "")
    return "%02d/%02d" % (int(m.group(1)), int(m.group(2))) if m else "00/00"

def is_miyagi(page):
    if NORTH.search(page):  # 他県の語が本文にあれば除外候補
        pass
    m = re.findall(r"content_group\s*[:=]\s*['\"]?([^'\"<>,\n]+)", page)
    if not m:
        return True  # 判定不能 -> 受理 (アプリと同一挙動)
    return any("宮城県" == s.strip() for s in m)

def parse_report(page, url):
    tm = TITLE.search(page)
    title = text(tm.group(1)) if tm else ""
    dm = DATE_R.search(title)
    if not dm:
        return []
    month, day = int(dm.group(1)), int(dm.group(2))
    year = datetime.date.today().year
    pm = PUBLISHED.search(page)
    if pm:
        year = int(pm.group(1))
        if month == 12 and int(pm.group(2)) == 1:
            year -= 1
    ds = "%04d-%02d-%02d" % (year, month, day)
    hall = title[dm.end():].strip()
    out = []
    for r in ROW.finditer(page):
        cells = [text(c) for c in CELL.findall(r.group(1))]
        if len(cells) < 5 or not re.search(r'[0-9]', cells[1]):
            continue
        no = to_int(cells[1])
        if not no or no <= 0:
            continue
        out.append((ds, hall, cells[0], no, to_int(cells[2]), to_int(cells[3]), to_dec(cells[4]), url))
    return out

def main():
    tasks, seen = [], set()
    for wi, ward in enumerate(WARDS):
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
                    seen.add(rid)
                    tasks.append((rid, tm.group(2).strip(), date_key(tm.group(1))))
            if n == 0:
                break
            time.sleep(INTERVAL)
    tasks.sort(key=lambda t: t[2], reverse=True)
    print("tasks=%d  newest=%s" % (len(tasks), tasks[0][2] if tasks else "-"))
    rows, ok, skipped, failed, dates = [], 0, 0, 0, {}
    for rid, store, dk in tasks[:MAX_REPORTS]:
        url = "%s/%s/?kishu=all" % (ROOT, rid)
        try:
            page = fetch(url)
        except Exception as e:
            failed += 1; print("report fail", rid, e, file=sys.stderr); continue
        if not is_miyagi(page):
            skipped += 1; print("SKIP 県外:", store, rid); time.sleep(INTERVAL); continue
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
    print("reports_ok=%d skipped_outside=%d failed=%d rows=%d" % (ok, skipped, failed, len(rows)))
    for d in sorted(dates, reverse=True):
        print("  %s : %d rows" % (d, dates[d]))
    print("wrote " + OUT)

main()

# min-repo のブロック（空応答）を検知して、無駄打ちせずに終了するラッパー。
import os, sys, urllib.request, datetime
UA = {"User-Agent": "KachiDaiResearch/2.2.9 (+data-quality-contact-not-configured)",
      "Accept-Language": "ja,en;q=0.5"}
PROBE = "https://min-repo.com/3357858/?kishu=all"
try:
    req = urllib.request.Request(PROBE, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as f:
        body = f.read().decode("utf-8", "replace")
    n = len(body)
except Exception as e:
    n = 0
    body = ""
    print("probe error:", e, file=sys.stderr)
print("probe len=%d" % n)
if n < 40000 and "<tr" not in body:
    print("BLOCKED: min-repo が空/短い応答を返している（len=%d）。今回は収集を中止して既存データを保持。" % n)
    open("collect_blocked.txt", "a", encoding="utf-8").write("%s len=%d\n" % (datetime.datetime.utcnow().isoformat(), n))
    sys.exit(0)
g = {"__name__": "__main__", "__file__": "collect.py"}
exec(compile(open("collect.py", encoding="utf-8").read(), "collect.py", "exec"), g)

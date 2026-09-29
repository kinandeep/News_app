#!/usr/bin/env python3
"""خادم غرفة الأخبار: يجلب RSS دورياً ويقدّم الواجهة و/api/feed.  التشغيل: python3 server.py"""
import json, os, re, threading, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", 8000))
INTERVAL = int(os.environ.get("INTERVAL", 300))  # ثوانٍ بين كل جلب

def gn(q):  # بحث Google News RSS لآخر 24 ساعة
    return "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:1d") + "&hl=ar&gl=LB&ceid=LB:ar"

# مفاتيح التبويبات تطابق معرّفات الواجهة. أضف أي RSS مباشر بنفس الطريقة:
FEEDS = {
    "pol": [gn("سياسة لبنان")],
    "spo": [gn("رياضة لبنان")],
    "mis": [gn("لبنان")],
    "qad": [gn("الأقضية لبنان بلدة")],
    "bhr": [gn("بعلبك الهرمل")],
}
# مثال: FEEDS["pol"].append("https://example.com/rss")

DATA, STATUS, LOCK = {k: [] for k in FEEDS}, {}, threading.Lock()

def words(t): return set(re.findall(r"\w+", t))
def jac(a, b):
    a, b = words(a), words(b)
    return len(a & b) / len(a | b) if a and b else 0

def parse(xml_bytes):
    out = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        src = it.findtext("source") or ""
        if src and title.endswith(" - " + src): title = title[: -len(src) - 3]
        pub = it.findtext("pubDate") or ""
        try: dt = parsedate_to_datetime(pub); iso = dt.astimezone().isoformat(); pub_ar = dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception: iso, pub_ar = "", pub
        out.append({"title": title, "source": src or "RSS", "url": (it.findtext("link") or "").strip(),
                    "published": pub_ar, "published_iso": iso, "echo": 0})
    return out

def refresh():
    for tab, urls in FEEDS.items():
        for u in urls:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 newsroom"})
                items = parse(urllib.request.urlopen(req, timeout=20).read())
                with LOCK:
                    cur = DATA.setdefault(tab, [])
                    for n in items:
                        if not n["title"]: continue
                        twin = next((c for c in cur if jac(c["title"], n["title"]) >= 0.8), None)
                        if twin:
                            if twin["source"] != n["source"]: twin["echo"] += 1  # تشابه عالٍ: ليست مصدراً مستقلاً
                        else: cur.append(n)
                    cur.sort(key=lambda x: x["published_iso"], reverse=True)
                    del cur[100:]
                STATUS[tab + "|" + u[:60]] = "ok " + time.strftime("%H:%M:%S")
            except Exception as e:
                STATUS[tab + "|" + u[:60]] = "خطأ: " + str(e)[:80]

def loop():
    while True:
        refresh(); time.sleep(INTERVAL)

class H(BaseHTTPRequestHandler):
    def send(self, body, ctype):
        self.send_response(200); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path.startswith("/api/feed"):
            with LOCK: self.send(json.dumps(DATA, ensure_ascii=False).encode(), "application/json")
        elif self.path.startswith("/api/status"):
            self.send(json.dumps(STATUS, ensure_ascii=False).encode(), "application/json")
        else:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            self.send(open(p, "rb").read(), "text/html")
    def log_message(self, *a): pass

if __name__ == "__main__":
    threading.Thread(target=loop, daemon=True).start()
    print("http://localhost:%d  (جلب كل %d ثانية)" % (PORT, INTERVAL))
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

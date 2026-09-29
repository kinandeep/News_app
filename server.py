import os
import json
import time
import threading
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8000))
INTERVAL = 3600  # تحديث دوري كل ساعة

# قائمة القنوات والمصادر الإخبارية
FEEDS = {
    "عاجل لبنان": "https://news.google.com/rss?hl=ar&gl=LB&ceid=LB:ar",
    "الوكالة الوطنية": f"https://news.google.com/rss/search?q={urllib.parse.quote('الوكالة الوطنية للإعلام')}&hl=ar&gl=LB&ceid=LB:ar",
    "LBCI": f"https://news.google.com/rss/search?q={urllib.parse.quote('LBCI Lebanon')}&hl=ar&gl=LB&ceid=LB:ar",
    "الميادين": f"https://news.google.com/rss/search?q={urllib.parse.quote('قناة الميادين')}&hl=ar&gl=LB&ceid=LB:ar",
    "الجزيرة": f"https://news.google.com/rss/search?q={urllib.parse.quote('الجزيرة')}&hl=ar&gl=LB&ceid=LB:ar",
    "العربية والحدث": f"https://news.google.com/rss/search?q={urllib.parse.quote('قناة العربية الحدث')}&hl=ar&gl=LB&ceid=LB:ar",
    "تكنولوجيا": f"https://news.google.com/rss/search?q={urllib.parse.quote('تكنولوجيا وذكاء اصطناعي')}&hl=ar&gl=LB&ceid=LB:ar",
    "اقتصاد": f"https://news.google.com/rss/search?q={urllib.parse.quote('اقتصاد أسواق مال')}&hl=ar&gl=LB&ceid=LB:ar",
    "رياضة": f"https://news.google.com/rss/search?q={urllib.parse.quote('أخبار الرياضة كرة قدم')}&hl=ar&gl=LB&ceid=LB:ar"
}

DATA = {}
STATUS = {}
LOCK = threading.Lock()

def fetch_rss(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as res:
        xml_data = res.read()
    root = ET.fromstring(xml_data)
    items = []
    for item in root.findall('.//item'):
        title = item.find('title').text if item.find('title') is not None else ""
        link = item.find('link').text if item.find('link') is not None else ""
        pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
        source = item.find('source').text if item.find('source') is not None else "مصدر إخباري"
        items.append({"title": title, "link": link, "pubDate": pubDate, "source": source})
    return items

def refresh():
    global DATA, STATUS
    new_data = {}
    new_status = {}
    for cat, url in FEEDS.items():
        try:
            items = fetch_rss(url)
            new_data[cat] = items
            new_status[cat] = f"ok {time.strftime('%H:%M:%S')}"
        except Exception as e:
            new_status[cat] = f"error: {str(e)}"
    with LOCK:
        DATA = new_data
        STATUS = new_status

def loop():
    while True:
        refresh()
        time.sleep(INTERVAL)

class H(BaseHTTPRequestHandler):
    def send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/feed"):
            with LOCK:
                self.send(json.dumps(DATA, ensure_ascii=False).encode(), "application/json")
        elif parsed.path.startswith("/api/search"):
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get('q', [''])[0]
            if query:
                encoded_q = urllib.parse.quote(query)
                search_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=ar&gl=LB&ceid=LB:ar"
                try:
                    results = fetch_rss(search_url)
                    self.send(json.dumps({"results": results}, ensure_ascii=False).encode(), "application/json")
                except Exception as e:
                    self.send(json.dumps({"error": str(e)}, ensure_ascii=False).encode(), "application/json")
            else:
                self.send(b'{"results": []}', "application/json")
        elif parsed.path.startswith("/api/status"):
            self.send(json.dumps(STATUS, ensure_ascii=False).encode(), "application/json")
        else:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            try:
                self.send(open(p, "rb").read(), "text/html")
            except:
                self.send(b"Index file not found", "text/plain")

if __name__ == "__main__":
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    server = HTTPServer(("0.0.0.0", PORT), H)
    server.serve_forever()

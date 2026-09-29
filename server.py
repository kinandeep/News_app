import os
import json
import time
import re
import threading
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8000))
INTERVAL = 3600  # جولة تحريرية آلية كل ساعة كاملة (3600 ثانية)

# بنك الكلمات المفتاحية لرصد وتدقيق أخبار البقاع
BEQAA_KEYWORDS = [
    "البقاع", "بعلبك", "الهرمل", "زحلة", "قوسايا", "رعية", "كفرزبد", "الفاعور", 
    "بدنايل", "الشراونة", "الكنيسة", "شمسطار", "بريتال", "عرسال", "دورس", 
    "تمنين", "أبلح", "رياق", "سعدنايل", "تعلبايا", "مجدل عنجر", "قب الياس", 
    "جوب جنين", "مشغرة", "راشيا", "البقاع الغربي", "البقاع الأوسط", "البقاع الشمالي"
]

RSS_FEEDS = {
    "لبنان_عام": "https://news.google.com/rss?hl=ar&gl=LB&ceid=LB:ar",
    "البقاع_مباشر": f"https://news.google.com/rss/search?q={urllib.parse.quote('البقاع OR بعلبك OR الهرمل OR زحلة')}&hl=ar&gl=LB&ceid=LB:ar",
    "LBCI": "https://www.lbcgroup.tv/rss/news/lebanon/ar",
    "الوكالة_الوطنية": f"https://news.google.com/rss/search?q={urllib.parse.quote('الوكالة الوطنية للإعلام')}&hl=ar&gl=LB&ceid=LB:ar",
    "الميادين": f"https://news.google.com/rss/search?q={urllib.parse.quote('الميادين لبنان')}&hl=ar&gl=LB&ceid=LB:ar"
}

STATE = {
    "articles": [],
    "last_run": "",
    "next_run_ts": 0,
    "status": {},
    "desk_summary": ""
}
LOCK = threading.Lock()

def fetch_feed(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
        }
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    items = []
    for item in root.findall(".//item"):
        title = item.find("title").text if item.find("title") is not None else ""
        link = item.find("link").text if item.find("link") is not None else ""
        pubDate = item.find("pubDate").text if item.find("pubDate") is not None else ""
        source = item.find("source").text if item.find("source") is not None else "مصدر صحفي"
        desc = item.find("description").text if item.find("description") is not None else ""
        clean_desc = re.sub(r'<[^>]+>', '', desc).strip()
        items.append({
            "raw_title": title.strip(),
            "link": link.strip(),
            "pubDate": pubDate.strip(),
            "source": source.strip(),
            "description": clean_desc
        })
    return items

def process_and_draft(item):
    """محرك التحرير وصياغة الأخبار الآلي"""
    raw_title = item["raw_title"]
    source = item["source"]
    link = item["link"]
    
    # فحص الارتباط بمنطقة البقاع
    text_corpus = f"{raw_title} {item.get('description', '')}"
    is_beqaa = any(k in text_corpus for k in BEQAA_KEYWORDS)
    
    # تحديد الموقع البقاعي الدقيق إن وجد
    found_towns = [k for k in BEQAA_KEYWORDS if k in text_corpus and k not in ["البقاع", "البقاع الغربي", "البقاع الأوسط", "البقاع الشمالي"]]
    location_tag = f"البقاع | {found_towns[0]}" if found_towns else ("البقاع" if is_beqaa else "لبنان")
    
    # تحرير العنوان التحريري
    clean_title = re.sub(r'\s*-\s*[^-]+$', '', raw_title) # حذف اسم المصدر الملحق في جوجل نيوز
    editorial_headline = f"{location_tag} | {clean_title}"
    
    # صياغة نص الخبر التحريري
    editorial_body = (
        f"أفادت مصادر ميدانية وإعلامية نقلاً عن {source} بأن {clean_title}. "
        f"وتشير المعطيات الأولية الواردة إلى متابعة الأجهزة والجهات المعنية للتطورات الميدانية في المنطقة، "
        f"في حين لم تصدر حتى اللحظة بيانات تفصيلية إضافية تؤكد حقيقة الإجراءات المتخذة على الأرض."
    )
    
    # صياغة شريط "عاجل"
    urgent_text = f"عاجل | بحسب {source}: {clean_title}."
    
    # صياغة منشور الشبكات الاجتماعية
    social_text = (
        f"تطورات {location_tag}:\n"
        f"{clean_title}\n\n"
        f"المصدر: {source}\n"
        f"التفاصيل: {link}\n"
        f"#لبنان #البقاع #أخبار_المحرر"
    )
    
    # قائمة ما يحتاج متابعة وتدقيق
    followups = [
        "التأكد من صدور بيان رسمي من المراجع المختصة أو الوزارات المعنية.",
        "التحقق من توقيت وسياق الحدث وعدم إعادة تدوير أخبار قديمة.",
        "فحص وتوثيق مكان وتاريخ أي صور أو وسائط مرافقة قبل اعتمادها."
    ]
    if is_beqaa:
        followups.insert(0, f"تأكيد المعطيات الميدانية مباشرة من مصادر وبلدات {location_tag}.")

    return {
        "id": hash(link),
        "headline": editorial_headline,
        "is_beqaa": is_beqaa,
        "status_label": "مسودة محررة / للمراجعة" if is_beqaa else "إشارة رصد",
        "editorial_body": editorial_body,
        "urgent_text": urgent_text,
        "social_text": social_text,
        "followups": followups,
        "source": source,
        "link": link,
        "pubDate": item.get("pubDate", "")
    }

def run_editorial_round():
    global STATE
    new_articles = []
    status_map = {}
    
    for feed_name, feed_url in RSS_FEEDS.items():
        try:
            fetched = fetch_feed(feed_url)
            status_map[feed_name] = f"نجاح ({len(fetched)} عنوان)"
            for f in fetched:
                new_articles.append(process_and_draft(f))
        except Exception as e:
            status_map[feed_name] = f"تعذر الوصول: {str(e)[:30]}"

    # إزالة التكرار بالاعتماد على تشابه الروابط والعناوين
    unique_items = {}
    for a in new_articles:
        if a["headline"] not in unique_items:
            unique_items[a["headline"]] = a
            
    sorted_articles = list(unique_items.values())
    # فرز البقاع أولاً في النشرات
    sorted_articles.sort(key=lambda x: (not x["is_beqaa"], x.get("pubDate", "")), reverse=False)

    with LOCK:
        STATE["articles"] = sorted_articles[:120]
        STATE["last_run"] = time.strftime("%I:%M %p - %Y/%m/%d")
        STATE["next_run_ts"] = time.time() + INTERVAL
        STATE["status"] = status_map
        STATE["desk_summary"] = (
            f"تم فحص أحداث البقاع ومحيطه أولاً، ثم أبرز التطورات اللبنانية. "
            f"إجمالي المواد المرصودة: {len(sorted_articles)}، منها {sum(1 for a in sorted_articles if a['is_beqaa'])} مادة تخص منطقة البقاع."
        )

def scheduler_thread():
    while True:
        run_editorial_round()
        time.sleep(INTERVAL)

class NewsHandler(BaseHTTPRequestHandler):
    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/api/feed":
            with LOCK:
                self.send_json({
                    "articles": STATE["articles"],
                    "last_run": STATE["last_run"],
                    "next_run_seconds": max(0, int(STATE["next_run_ts"] - time.time())),
                    "status": STATE["status"],
                    "desk_summary": STATE["desk_summary"]
                })
        elif parsed.path == "/api/search":
            qs = urllib.parse.parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            if not q:
                self.send_json({"results": []})
                return
            
            search_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ar&gl=LB&ceid=LB:ar"
            try:
                raw_items = fetch_feed(search_url)
                processed = [process_and_draft(item) for item in raw_items]
                processed.sort(key=lambda x: not x["is_beqaa"])
                self.send_json({"results": processed, "query": q})
            except Exception as e:
                self.send_json({"error": str(e), "results": []})
        else:
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            if os.path.exists(file_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

if __name__ == "__main__":
    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()
    server = HTTPServer(("0.0.0.0", PORT), NewsHandler)
    server.serve_forever()

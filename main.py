import os
import json
import asyncio
import logging
import hashlib
from datetime import datetime, date
from pathlib import Path
import feedparser
import requests
import google.generativeai as genai

# ─── إعدادات ───────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "ضع_مفتاحك_هنا")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "8830452082:AAEN2dkK18Vsk_l61igfwtmOKZv7KYNzlsA")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@wazeefat_alyoum")

SEEN_FILE = Path("data/seen_jobs.json")
LOG_FILE  = Path("logs/agent.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ─── مصادر RSS للخليج ──────────────────────────────────────────────────────
RSS_FEEDS = [
    # Indeed - دول الخليج
    {"source": "Indeed",     "country": "السعودية",  "url": "https://sa.indeed.com/rss?q=&l=&sort=date"},
    {"source": "Indeed",     "country": "الإمارات",  "url": "https://ae.indeed.com/rss?q=&l=&sort=date"},
    {"source": "Indeed",     "country": "الكويت",    "url": "https://www.indeed.com/rss?q=&l=Kuwait&sort=date"},
    {"source": "Indeed",     "country": "قطر",       "url": "https://www.indeed.com/rss?q=&l=Qatar&sort=date"},
    {"source": "Indeed",     "country": "البحرين",   "url": "https://www.indeed.com/rss?q=&l=Bahrain&sort=date"},
    {"source": "Indeed",     "country": "عُمان",     "url": "https://www.indeed.com/rss?q=&l=Oman&sort=date"},
    # Bayt.com
    {"source": "Bayt",       "country": "السعودية",  "url": "https://www.bayt.com/en/saudi-arabia/jobs/?jobId=0&filtered=1&format=rss"},
    {"source": "Bayt",       "country": "الإمارات",  "url": "https://www.bayt.com/en/uae/jobs/?jobId=0&filtered=1&format=rss"},
    {"source": "Bayt",       "country": "الكويت",    "url": "https://www.bayt.com/en/kuwait/jobs/?jobId=0&filtered=1&format=rss"},
    {"source": "Bayt",       "country": "قطر",       "url": "https://www.bayt.com/en/qatar/jobs/?jobId=0&filtered=1&format=rss"},
    {"source": "Bayt",       "country": "البحرين",   "url": "https://www.bayt.com/en/bahrain/jobs/?jobId=0&filtered=1&format=rss"},
    {"source": "Bayt",       "country": "عُمان",     "url": "https://www.bayt.com/en/oman/jobs/?jobId=0&filtered=1&format=rss"},
    # Naukrigulf
    {"source": "Naukrigulf", "country": "السعودية",  "url": "https://www.naukrigulf.com/saudi-arabia-jobs?format=rss"},
    {"source": "Naukrigulf", "country": "الإمارات",  "url": "https://www.naukrigulf.com/uae-jobs?format=rss"},
    {"source": "Naukrigulf", "country": "الكويت",    "url": "https://www.naukrigulf.com/kuwait-jobs?format=rss"},
    {"source": "Naukrigulf", "country": "قطر",       "url": "https://www.naukrigulf.com/qatar-jobs?format=rss"},
    {"source": "Naukrigulf", "country": "البحرين",   "url": "https://www.naukrigulf.com/bahrain-jobs?format=rss"},
    {"source": "Naukrigulf", "country": "عُمان",     "url": "https://www.naukrigulf.com/oman-jobs?format=rss"},
]

COUNTRY_FLAGS = {
    "السعودية": "🇸🇦",
    "الإمارات": "🇦🇪",
    "الكويت":   "🇰🇼",
    "قطر":      "🇶🇦",
    "البحرين":  "🇧🇭",
    "عُمان":    "🇴🇲",
}

# ─── تحميل/حفظ الوظائف المرئية سابقاً ─────────────────────────────────────
def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen)[-3000:]))  # نحتفظ بآخر 3000 فقط

def job_id(title: str, link: str) -> str:
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()

# ─── جمع الوظائف من RSS ────────────────────────────────────────────────────
def fetch_jobs(seen: set) -> dict:
    """يجمع الوظائف الجديدة من جميع المصادر ويصنّفها حسب الدولة"""
    by_country = {c: [] for c in COUNTRY_FLAGS}
    total_new  = 0

    for feed_info in RSS_FEEDS:
        source  = feed_info["source"]
        country = feed_info["country"]
        url     = feed_info["url"]
        try:
            log.info(f"جلب: {source} - {country}")
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "").strip()
                link  = entry.get("link", "").strip()
                if not title or not link:
                    continue
                jid = job_id(title, link)
                if jid in seen:
                    continue
                seen.add(jid)
                total_new += 1
                by_country[country].append({
                    "title":   title,
                    "link":    link,
                    "source":  source,
                    "country": country,
                })
        except Exception as e:
            log.warning(f"خطأ في {source} - {country}: {e}")

    log.info(f"وظائف جديدة: {total_new}")
    return by_country

# ─── Gemini: تصنيف وصياغة المنشور ─────────────────────────────────────────
def build_post_with_gemini(by_country: dict) -> str:
    """يستخدم Gemini لصياغة منشور احترافي بالعربية"""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # تحضير ملخص الوظائف للنموذج
    summary_lines = []
    for country, jobs in by_country.items():
        if jobs:
            sample = jobs[:5]  # أرسل عينة فقط لتوفير التوكنز
            titles = "\n".join(f"  - {j['title']} ({j['source']})" for j in sample)
            summary_lines.append(f"{country} ({len(jobs)} وظيفة):\n{titles}")

    if not summary_lines:
        return None

    jobs_text = "\n\n".join(summary_lines)
    now       = datetime.now()
    period    = "الصباحية" if now.hour < 12 else "المسائية"
    date_ar   = now.strftime("%Y/%m/%d")

    prompt = f"""
أنت محرر قناة وظائف خليجية على تليجرام. اكتب منشوراً احترافياً جذاباً بالعربية الفصحى المبسطة.

التاريخ: {date_ar}
الجلسة: {period}

الوظائف المتاحة اليوم:
{jobs_text}

القواعد:
1. ابدأ بعنوان جذاب مع إيموجي
2. اذكر عدد الوظائف لكل دولة مع علمها
3. اذكر أبرز 2-3 مسميات وظيفية لكل دولة
4. أضف تشجيعاً قصيراً في النهاية
5. أضف هاشتاقات خليجية مناسبة
6. لا تتجاوز 800 حرف
7. لا تكتب روابط، فقط المسميات والأعداد

اكتب المنشور مباشرة بدون مقدمة:
"""

    response = model.generate_content(prompt)
    return response.text.strip()

# ─── إرسال لتليجرام ────────────────────────────────────────────────────────
def post_to_telegram(text: str, jobs_by_country: dict) -> bool:
    """ينشر المنشور الرئيسي ثم روابط الوظائف"""
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    # المنشور الرئيسي
    r = requests.post(f"{base_url}/sendMessage", json={
        "chat_id":    TELEGRAM_CHANNEL,
        "text":       text,
        "parse_mode": "HTML",
    })
    if not r.ok:
        log.error(f"فشل إرسال تليجرام: {r.text}")
        return False
    log.info("تم نشر المنشور الرئيسي على تليجرام")

    # إرسال الروابط لكل دولة كرسائل منفصلة
    for country, jobs in jobs_by_country.items():
        if not jobs:
            continue
        flag = COUNTRY_FLAGS.get(country, "🌍")
        lines = [f"{flag} <b>وظائف {country}</b>\n"]
        for j in jobs[:10]:  # أفضل 10 روابط
            title = j["title"][:60]
            lines.append(f"• <a href='{j['link']}'>{title}</a>")
        msg = "\n".join(lines)
        requests.post(f"{base_url}/sendMessage", json={
            "chat_id":                  TELEGRAM_CHANNEL,
            "text":                     msg,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        })

    return True

# ─── الدالة الرئيسية ────────────────────────────────────────────────────────
def run():
    log.info("=" * 50)
    log.info(f"بدء الأجنت - {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    seen       = load_seen()
    by_country = fetch_jobs(seen)

    total = sum(len(v) for v in by_country.values())
    if total == 0:
        log.info("لا توجد وظائف جديدة هذه الجولة")
        save_seen(seen)
        return

    log.info(f"إجمالي الوظائف الجديدة: {total}")
    log.info("صياغة المنشور عبر Gemini...")

    post_text = build_post_with_gemini(by_country)
    if not post_text:
        log.warning("لم يتمكن Gemini من صياغة المنشور")
        return

    log.info("نشر على تليجرام...")
    success = post_to_telegram(post_text, by_country)

    save_seen(seen)
    log.info(f"اكتمل - نجاح: {success}")
    log.info("=" * 50)

if __name__ == "__main__":
    run()

import os
import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
import requests
import google.generativeai as genai

# ─── إعدادات ────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
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

COUNTRY_FLAGS = {
    "السعودية": "🇸🇦",
    "الإمارات": "🇦🇪",
    "الكويت":   "🇰🇼",
    "قطر":      "🇶🇦",
    "البحرين":  "🇧🇭",
    "عُمان":    "🇴🇲",
}

COUNTRIES = list(COUNTRY_FLAGS.keys())

# ─── تحميل/حفظ الوظائف المرئية سابقاً ──────────────────────────────────────
def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen)[-3000:]))

# ─── جمع الوظائف عبر Gemini + Google Search ─────────────────────────────────
def fetch_jobs_via_gemini() -> dict:
    """
    يستخدم Gemini مع Google Search grounding للبحث عن وظائف خليجية حقيقية
    ويعيد قاموساً مصنّفاً حسب الدولة
    """
    genai.configure(api_key=GEMINI_API_KEY)

    now     = datetime.now()
    period  = "الصباح" if now.hour < 12 else "المساء"
    date_ar = now.strftime("%Y/%m/%d")

    by_country = {c: [] for c in COUNTRIES}

    for country in COUNTRIES:
        flag = COUNTRY_FLAGS[country]
        log.info(f"جلب وظائف {flag} {country} عبر Gemini...")
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                tools=[{"google_search": {}}],          # Google Search grounding
            )

            prompt = f"""
ابحث الآن في الإنترنت عن أحدث الوظائف المتاحة في {country} اليوم {date_ar}.

المطلوب: قائمة بـ 8 إلى 12 وظيفة حقيقية منشورة حديثاً في {country}.

أعد الإجابة بهذا الشكل JSON فقط بدون أي نص إضافي أو backticks:
{{
  "jobs": [
    {{"title": "مسمى الوظيفة", "company": "اسم الشركة", "location": "المدينة في {country}", "source": "اسم موقع التوظيف"}},
    ...
  ]
}}
"""
            response = model.generate_content(prompt)
            text = response.text.strip()

            # تنظيف الرد
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            data = json.loads(text)
            jobs = data.get("jobs", [])

            for job in jobs:
                title   = job.get("title", "").strip()
                company = job.get("company", "").strip()
                if not title:
                    continue
                by_country[country].append({
                    "title":    title,
                    "company":  company,
                    "location": job.get("location", country),
                    "source":   job.get("source", "Gemini Search"),
                    "country":  country,
                })

            log.info(f"  ✅ {country}: {len(jobs)} وظيفة")

        except Exception as e:
            log.warning(f"  ⚠️ خطأ في {country}: {e}")

    return by_country

# ─── صياغة المنشور ───────────────────────────────────────────────────────────
def build_post(by_country: dict) -> str:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    now    = datetime.now()
    period = "الصباحية 🌅" if now.hour < 12 else "المسائية 🌙"
    date_ar = now.strftime("%Y/%m/%d")

    # ملخص الوظائف
    lines = []
    for country, jobs in by_country.items():
        if jobs:
            flag    = COUNTRY_FLAGS[country]
            samples = " | ".join(j["title"] for j in jobs[:3])
            lines.append(f"{flag} {country} ({len(jobs)} وظيفة): {samples}")

    if not lines:
        return None

    summary = "\n".join(lines)

    prompt = f"""
أنت محرر قناة وظائف خليجية على تليجرام. اكتب منشوراً احترافياً جذاباً.

التاريخ: {date_ar} | الجلسة: {period}

ملخص الوظائف المتاحة اليوم:
{summary}

القواعد:
- ابدأ بعنوان جذاب مع إيموجي 
- اذكر كل دولة مع علمها وعدد وظائفها
- اذكر 2-3 مسميات بارزة لكل دولة
- جملة تشجيعية قصيرة في النهاية
- أضف هاشتاقات: #وظائف_الخليج #وظائف #توظيف
- لا تتجاوز 900 حرف

اكتب المنشور مباشرة:
"""
    response = model.generate_content(prompt)
    return response.text.strip()

# ─── إرسال لتليجرام ──────────────────────────────────────────────────────────
def post_to_telegram(main_text: str, by_country: dict) -> bool:
    base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    # المنشور الرئيسي
    r = requests.post(f"{base}/sendMessage", json={
        "chat_id":    TELEGRAM_CHANNEL,
        "text":       main_text,
        "parse_mode": "HTML",
    })
    if not r.ok:
        log.error(f"فشل الإرسال: {r.text}")
        return False

    log.info("✅ تم نشر المنشور الرئيسي")

    # منشور تفصيلي لكل دولة
    for country, jobs in by_country.items():
        if not jobs:
            continue
        flag  = COUNTRY_FLAGS[country]
        lines = [f"{flag} <b>وظائف {country}</b>\n"]
        for j in jobs[:10]:
            company = f" — {j['company']}" if j.get("company") else ""
            lines.append(f"• {j['title']}{company}")
        lines.append(f"\n🔍 <i>للتقديم ابحث عن الوظيفة على {jobs[0].get('source','المواقع المتخصصة')}</i>")

        requests.post(f"{base}/sendMessage", json={
            "chat_id":                  TELEGRAM_CHANNEL,
            "text":                     "\n".join(lines),
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        })

    return True

# ─── الدالة الرئيسية ──────────────────────────────────────────────────────────
def run():
    log.info("=" * 55)
    log.info(f"بدء الأجنت — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    by_country = fetch_jobs_via_gemini()
    total      = sum(len(v) for v in by_country.values())

    if total == 0:
        log.warning("لم يتم جلب أي وظائف!")
        return

    log.info(f"إجمالي الوظائف: {total} — جاري الصياغة...")

    post_text = build_post(by_country)
    if not post_text:
        log.error("فشل بناء المنشور")
        return

    log.info("جاري النشر على تليجرام...")
    success = post_to_telegram(post_text, by_country)

    log.info(f"اكتمل — نجاح: {success}")
    log.info("=" * 55)

if __name__ == "__main__":
    run()

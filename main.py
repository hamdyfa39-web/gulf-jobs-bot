import os
import json
import logging
from datetime import datetime
from pathlib import Path
import requests
import google.generativeai as genai

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@wazeefat_alyoum")

LOG_FILE = Path("logs/agent.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

COUNTRY_FLAGS = {
    "السعودية": "🇸🇦", "الإمارات": "🇦🇪", "الكويت": "🇰🇼",
    "قطر": "🇶🇦", "البحرين": "🇧🇭", "عُمان": "🇴🇲",
}

def fetch_and_post():
    genai.configure(api_key=GEMINI_API_KEY)
    now     = datetime.now()
    period  = "الصباحية 🌅" if now.hour < 12 else "المسائية 🌙"
    date_ar = now.strftime("%Y/%m/%d")

    log.info("جاري البحث عن الوظائف عبر Gemini...")

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        tools=[{"google_search": {}}],
    )

    prompt = f"""
ابحث في الإنترنت الآن عن أحدث الوظائف المتاحة في دول الخليج العربي اليوم {date_ar}.
الدول: السعودية، الإمارات، الكويت، قطر، البحرين، عُمان.

اجمع 6 إلى 10 وظائف من كل دولة من مواقع مثل LinkedIn أو Bayt أو Indeed أو أي موقع توظيف.

أعد JSON فقط بهذا الشكل بدون أي نص خارجه:
{{
  "السعودية": [{{"title": "...", "company": "..."}}],
  "الإمارات": [{{"title": "...", "company": "..."}}],
  "الكويت":   [{{"title": "...", "company": "..."}}],
  "قطر":      [{{"title": "...", "company": "..."}}],
  "البحرين":  [{{"title": "...", "company": "..."}}],
  "عُمان":    [{{"title": "...", "company": "..."}}]
}}
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    by_country = json.loads(text)
    log.info(f"تم جلب الوظائف: {sum(len(v) for v in by_country.values())} وظيفة")

    # بناء المنشور
    lines = [f"📋 <b>وظائف الخليج — جلسة {period}</b>\n<i>{date_ar}</i>\n"]
    for country, jobs in by_country.items():
        if not jobs:
            continue
        flag = COUNTRY_FLAGS.get(country, "🌍")
        lines.append(f"\n{flag} <b>{country}</b> ({len(jobs)} وظيفة)")
        for j in jobs[:4]:
            company = f" | {j['company']}" if j.get("company") else ""
            lines.append(f"  • {j['title']}{company}")

    lines.append("\n\n#وظائف_الخليج #توظيف #وظائف #jobs")
    post_text = "\n".join(lines)

    base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    r = requests.post(f"{base}/sendMessage", json={
        "chat_id": TELEGRAM_CHANNEL,
        "text": post_text,
        "parse_mode": "HTML",
    })

    if r.ok:
        log.info("✅ تم النشر على تليجرام بنجاح!")
    else:
        log.error(f"❌ فشل النشر: {r.text}")

if __name__ == "__main__":
    log.info("=" * 50)
    log.info(f"بدء الأجنت — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    fetch_and_post()
    log.info("=" * 50)

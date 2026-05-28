# 🇸🇦 وظائف الخليج - نظام النشر التلقائي

نظام يجمع الوظائف من LinkedIn وIndeed وBayt وNaukrigulf ويصنفها حسب دول الخليج وينشرها تلقائياً على تليجرام مرتين يومياً.

---

## ⚙️ خطوات الإعداد

### 1. رفع الملفات على GitHub

1. اذهب إلى **github.com** وأنشئ repository جديد
2. اسمه مثلاً: `gulf-jobs-bot`
3. ارفع الملفات الثلاثة:
   - `main.py`
   - `requirements.txt`
   - `.github/workflows/jobs_agent.yml`

### 2. إضافة المفاتيح السرية

في GitHub repository اذهب إلى:
**Settings → Secrets and variables → Actions → New repository secret**

أضف هذه الثلاثة:

| الاسم | القيمة |
|-------|--------|
| `GEMINI_API_KEY` | مفتاحك من Google AI Studio |
| `TELEGRAM_TOKEN` | `8830452082:AAEN2dkK18Vsk_l61igfwtmOKZv7KYNzlsA` |
| `TELEGRAM_CHANNEL` | `@wazeefat_alyoum` |

### 3. تفعيل GitHub Actions

- اذهب إلى تبويب **Actions** في الـ repository
- اضغط **"I understand my workflows, go ahead and enable them"**

### 4. تجربة يدوية

- اذهب إلى **Actions → Gulf Jobs Agent**
- اضغط **"Run workflow"** ← **"Run workflow"**
- انتظر دقيقة وتحقق من قناتك!

---

## 📅 جدول النشر

| الوقت | التوقيت |
|-------|---------|
| 8:00 صباحاً | توقيت الرياض (UTC+3) |
| 6:00 مساءً | توقيت الرياض (UTC+3) |

---

## 📊 المصادر

- ✅ Indeed (6 دول خليجية)
- ✅ Bayt.com (6 دول خليجية)
- ✅ Naukrigulf (6 دول خليجية)

## 🌍 الدول المدعومة

🇸🇦 السعودية | 🇦🇪 الإمارات | 🇰🇼 الكويت | 🇶🇦 قطر | 🇧🇭 البحرين | 🇴🇲 عُمان

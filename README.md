# SoundCloud Quran Discord Bot

بوت ديسكورد لإدارة وتشغيل تلاوات القرآن من روابط SoundCloud داخل القنوات الصوتية.

## الميزات

- تشغيل مباشر من روابط SoundCloud
- طوابير تشغيل منفصلة لكل سيرفر (Guild)
- أزرار تفاعلية للتحكم
- طرد تلقائي بعد 60 ثانية من الخمول
- دعم Slash Commands فقط

## النشر على Railway

1. اضغط على "Deploy on Railway" أو ارفع المشروع يدويًا.
2. أضف متغير البيئة `DISCORD_TOKEN` في إعدادات Railway.
3. اضغط على Deploy وشغل البوت!

## الأوامر

- `/play <url>`: لتشغيل رابط SoundCloud
- `/queue`: عرض قائمة التشغيل

---

تم الإعداد باستخدام discord.js و play-dl.

# OpenAmer Agent

**סוכן ה-AI המשתפר באופן עצמי — לומד מניסיון, יוצר מיומנויות, זוכר את ההעדפות שלך ועובד עבורך בכל מקום.**

השתמשו בכל מודל שתרצו — OpenRouter, OpenAI, DeepSeek ועוד. החליפו באמצעות `openamer model` — ללא שינויים בקוד.

## תכונות

- **ממשק טרמינל אמיתי — TUI מלא עם השלמה אוטומטית, היסטוריה ופלט כלים בשידור חי (streaming)**
- **חי 어디 שאתם נמצאים — Telegram, Discord, Slack, WhatsApp ועוד, הכל משער (gateway) אחד**
- **לומד עם הזמן — זיכרון, מיומנויות המשתפרות מעצמן, היזכרות בין סשנים**
- **מקצה ומקביל — מפעיל סוכבי-משנה לעבודה במקביל**
- **אוטומציות מתוזמנות — cron מובנה לדוחות יומיים, גיבויים וביקורות**
- **רץ בכל מקום — מקומי, Docker, SSH, ענן, serverless**

## התקנה מהירה

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## מתחילים

```bash
openamer              # התחל בצ'אט
openamer setup        # הגדירו את מפתחות ה-API והספק שלכם
openamer model        # בחר את המודל שלך
openamer update       # עדכון לגרסה האחרונה
```

## עדכון

OpenAmer בודק עדכונים באופן אוטומטי ומציג אזהרה בבאנר הפתיחה. הרץ את הפקודה `openamer update` כדי לקבל את הגרסה העדכנית ביותר — הפעולה מגבה את הנתונים שלך תחילה.

## תרומה

תרומות מתקבלות בברכה — פתחו issues, שלחו pull requests, או הצטרפו לקהילה.

## רישיון

רישיון Apache 2.0. ראו {LICENSE}.

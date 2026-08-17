# OpenAmer Agent

**ራሱን የሚያሻሽለው የ AI ኤጀንት — ከልምድ ይማራል፣ ክህሎቶችን ይፈጥራል፣ ምርጫዎችዎን ያስታውሳል፣ እና በማንኛውም ቦታ ለእርስዎ ይሰራል።**

የፈለጉትን ሞዴል ይጠቀሙ — OpenRouter፣ OpenAI፣ DeepSeek እና ሌሎችንም። በ `openamer model` ይቀይሩ — ምንም ዓይነት የኮድ ለውጥ አያስፈልግም።

## ልዩነቶች

- **እውነተኛ የተርሚናል በይነገጽ — አውቶኮምፕሊት (autocomplete)፣ ታሪክ (history) እና የቱል ውጤቶችን በቀጥታ የሚያሳየው (streaming) ሙሉ TUI**
- **የሚገኙባቸው ቦታዎች ላይ ይገኛል — Telegram, Discord, Slack, WhatsApp እና ሌሎችም ከአንድ መግቢያ (gateway) ብቻ**
- **ከጊዜ ብዛት ይማራል — ትውስታ፣ ራስን የሚያሻሽሉ ክህሎቶች፣ በየክፍለ-ጊዜዎቹ (sessions) መካከል የሚደረግ ማስታወስ**
- **ያካፍላል & ያሰማራሉ — ለተጓዳኝ ስራዎች ንዑስ ወኪሎችን (subagents) ይፈጥራል**
- **የተቀጠሩ አውቶሜሽኖች — ለዕለታዊ ሪፖርቶች፣ ለባክአፕ (backups) እና ለኦዲቶች የሚያገለግል የውስጥ cron ስርአት**
- **በየትኛውም ቦታ ይሠራል — በሎካል (local)፣ በDocker፣ በSSH፣ በክላውድ (cloud) እና በሰርቨርለስ (serverless)**

## ፈጣን ተከላ

ዊንዶውስ (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

ሊኑክስ (Linux) / ማክ ኦኤስ (macOS):
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## መጀመር

```bash
openamer              # ውይይት ይጀምሩ
openamer setup        # የ API ቁልፎችዎን እና አቅራቢዎን ያዘጋጁ
openamer model        # ሞዴልዎን ይምረጡ
openamer update       # ወደ የቅርብ ጊዜው ስሪት ያዘምኑ
```

## በማዘመን ላይ ነው

OpenAmer በራስ-ሰር አዳዲስ ስሪቶችን (updates) ይፈትሻል እንዲሁም በእንኳን ደህና መጡ ባነሩ ላይ ማስጠንቀቂያ ያሳያል። የቅርብ ጊዜውን ስሪት ለማግኘት `openamer update` የሚለውን ትዕዛዝ ያስ çalışሉ — ይህ ትዕዛዝ በመጀመሪያ መረጃዎችዎን ያስጠባበቃል።

## ማበርከት

ተሳትፎዎች ተቀባይ ናቸው — ክፍት የሆኑ ችግሮችን (open issues) ያሳውቁ፣ የፑል ጥያቄዎችን (pull requests) ያቅርቡ ወይም ማህበረሰቡን ይቀላቀሉ።

## ፈቃድ

የአፓቼ ፈቃድ 2.0 (Apache License 2.0)። {LICENSE}ን ይመልከቱ።

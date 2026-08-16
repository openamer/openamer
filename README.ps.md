# OpenAmer Agent

**خپل ځان ښوونکی AI ایجنټ — له تجربو زده کړئ، مهارتونه جوړ کړئ، خپلې خوښې په یاد وساتئ، او هر ځای کې ستاسو لپاره کار وکړئ.**

هر هغه ماډل وکاروئ چې تاسو یې غواړئ — OpenRouter، OpenAI، DeepSeek او نور. د `openamer model` په واسطه یې بدل کړئ — پرته له کوم کوډ بدلون څخه.

## ډีټیلونه/برخې

- **رښتیني ټرمینل انټرفیس — بشپړ TUI چې د autocomplete، تاریخ (history) او د وسیلو د سټریمینګ output سره equipped دی**
- **هلته ژوند کوي چې تاسو یې کوئ — ټیلیګرام، ډیسکورډ، سلیک، واټس‌اپ او نور هم ټول له یوې دروازې (gateway) څخه**
- **د وخت په تېرېدو سره زده کړه — حافظه، د ځان سره ښه کولو مهارتونه، او د جلسو ترمنځ د یادښتونو ترلاسه کول**
- **تفویضوي او متوازي کوي — د متوازي کار لپاره فرعي ایجنټان رامینځته کوي**
- **پلان شوې اتوماتیک메이션 — د ورځنیو راپورونو، بیک‌اپونو او ऑडिटونو لپاره بلت-پلاټ (built-in) کرون (cron)**
- **هر ځای کې چلېږي — محلي (local)، ډاکر (Docker)، ایس ایس ایچ (SSH)، کلاوډ (cloud)، сърورلیس (serverless)**

## چټک instalação (چټک نصبول)

وینډوز (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

لینکس / مک او ایس (Linux / macOS):
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## پیل کول

```bash
openamer              # پېل کړئ خبرې کول
openamer setup        # خپل API کییز (keys) او چاپیریال/سپلایر (provider) ترتیب کړئ
openamer model        # خپل ماډل غوره کړئ
openamer update       # تر وروستۍ نسخې ته اپډیټ کړئ
```

## نآپډیټ کول

OpenAmer په اتوماتیک ډول د نويو 업데이트ونو لپاره ګروه کوي او په ښه راتلو بڼر (welcome banner) کې یو خبرداری ښیي. د وروستي ورژن ترلاسه کولو لپاره `openamer update` چل کړئ — دا لومړی ستاسو د ډیټا بیک اپ (back up) اخلي.

## مشارکت کول

د تعاون contributions ښه مرحبا دي — نوې مسئلې (open issues) وړاندې کړئ، د pull requests غوښتنې وکړئ، یا د ټولنې (community) سره یوځای شئ.

## لایسنس

د اپاچي لایسنس ۲.۰ (Apache License 2.0). {LICENSE} وګورئ.

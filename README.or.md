# OpenAmer Agent

**ସ୍ୱୟଂ-ସୁଧାରିତ AI ଏଜେଣ୍ଟ — ଅନୁଭବରୁ ଶିଖନ୍ତୁ, ନୂତନ କୌଶଳ ସୃଷ୍ଟି କରନ୍ତୁ, ଆପଣଙ୍କ ପସନ୍ଦକୁ ମନେ ରଖନ୍ତୁ ଏବଂ ଯେକୌଣସି ସ୍ଥାନରେ ଆପଣଙ୍କ ପାଇଁ କାମ କରନ୍ତୁ।**

ଆପଣ ଯେକୌଣସି ମଡେଲ୍ ବ୍ୟବହାର କରିପାରିବେ — OpenRouter, OpenAI, DeepSeek, ଏବଂ ଅନ୍ୟାନ୍ୟ। `openamer model` ସାହାଯ୍ୟରେ ପରିବର୍ତ୍ତନ କରନ୍ତୁ — କୌଣସି କୋଡ୍ ପରିବର୍ତ୍ତନର ଆବଶ୍ୟକତା ନାହିଁ।

## ବୈଶିଷ୍ଟ୍ୟଗୁଡ଼ିକ

- **ବାସ୍ତବ ଟର୍ମିନାଲ୍ ଇଣ୍ଟରଫେସ୍ — ଅଟୋକୋମ୍ପ୍ଲିଟ୍, ହିଷ୍ଟ୍ରି ଏବଂ ଷ୍ଟ୍ରିମିଂ ଟୁଲ୍ ଆଉଟପୁଟ୍ ସହିତ ସମ୍ପୂର୍ଣ୍ଣ TUI**
- **ଆପଣ ଯେଉଁଠି ରୁହନ୍ତି ସେଠାରେ ଉପଲବ୍ଧ — ଏକକ ଗେଟୱେ (gateway) ମାଧ୍ୟମରେ Telegram, Discord, Slack, WhatsApp ଏବଂ ଅନ୍ୟାନ୍ୟ ସେବା।**
- **ସମୟ ଅନୁସାରେ ଶିଖେ — ସ୍ମୃତି, ସ୍ୱୟଂ-ଉନ୍ନତି କାର୍ଯ୍ୟଦକ୍ଷତା, କ୍ରସ୍-ସେସନ୍ រିକଲ୍ (cross-session recall)**
- **ଡେଲିଗେଟ୍ ଏବଂ ପାରାଲେଲାଇଜ୍ କରେ — ସମାନ୍ତରାଳ କାର୍ଯ୍ୟ ପାଇଁ ସବ-ଏଜେଣ୍ଟମାନଙ୍କୁ ସୃଷ୍ଟି କରେ**
- **ନିର୍ଦ୍ଧାରିତ ଅଟୋମେସନ୍ (Scheduled automations) — ଦୈନିକ ରିପୋର୍ଟ, ବ୍ୟାକଅପ୍ ଏବଂ ଅଡିଟ୍ ପାଇଁ ଇନ-ବିଲ୍ଟ କ୍ରନ୍ (built-in cron)**
- **ଯେକୌଣସି ସ୍ଥାନରେ ଚାଲେ — local, Docker, SSH, cloud, serverless**

## ଶୀଘ୍ର ସ୍ଥାପନ (Quick Install)

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## ଆରମ୍ଭ କରିବା

```bash
openamer              # ଗପସପ ଆରମ୍ଭ କରନ୍ତୁ
openamer setup        # ଆପଣଙ୍କର API କୀ (keys) ଏବଂ ପ୍ରୋଭାଇଡର୍ (provider) ସେଟ୍ ଅପ୍ କରନ୍ତୁ
openamer model        # ଆପଣଙ୍କର ମଡେଲ୍ ବାଛନ୍ତୁ
openamer update       # ନୂତନତମ ସଂସ୍କରଣକୁ ଅପଡେଟ୍ କରନ୍ତୁ
```

## ଅପଡେଟ୍ କରାଯାଉଛି (Updating)

OpenAmer ସ୍ୱୟଂଚାଳିତ ଭାବରେ ଅପଡେଟ୍ ପାଇଁ ଯାଞ୍ଚ କରେ ଏବଂ ୱେଲକମ ବ୍ୟାନରରେ ଏକ ସତର୍କତା ଦେଖାଏ। ସର୍ବନୂତନ ଭର୍ସନ ପାଇଁ openamer update ଚଲାନ୍ତୁ — ଏହା ପ୍ରଥମେ ଆପଣଙ୍କ ଡାଟାକୁ ବ୍ୟାକଅପ୍ କରିବ।

## ଅବଦାନ କରିବା

ଅବଦାନକୁ ସ୍ୱାଗତ — open issues କରନ୍ତୁ, pull requests ପଠାନ୍ତୁ, କିମ୍ବା କମ୍ୟୁନିଟିରେ ଯୋଗ ଦିଅନ୍ତୁ।

## ଲାଇସେନ୍ସ

ଅପାଚେ ଲାଇସେନ୍ସ ୨.୦ (Apache License 2.0)। {LICENSE} ଦେଖନ୍ତୁ।

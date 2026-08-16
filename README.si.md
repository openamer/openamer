# OpenAmer Agent

**ස්වයං-වැඩිදියුණු වන AI නියෝජිතයා — අත්දැකීම් වලින් ඉගෙන ගන්න, කුසලතා නිර්මාණය කරන්න, ඔබේ රුචිකත්වයන් මතක තබා ගන්න, සහ ඕනෑම තැනක ඔබ වෙනුවෙන් වැඩ කරන්න.**

ඔබට කැමති ඕනෑම මොඩලයක් භාවිතා කරන්න — OpenRouter, OpenAI, DeepSeek සහ තවත් බොහෝ දේ. කේතයන්හි (code) කිසිදු වෙනසක් නොකර `openamer model` මගින් එය මාරු කරන්න.

## විශේෂාංග

- **සැබෑ ටර්මිනල් අතුරුමුහුණතක් — autocomplete, history සහ streaming tool output සහිත සම්පූර්ණ TUI එකක්**
- **ඔබ සිටින තැනම රැඳී සිටින්න — Telegram, Discord, Slack, WhatsApp සහ තවත් බොහෝ දේ එකම gateway එකකින්**
- **කාලයත් සමඟ ඉගෙන ගනී — මතකය, ස්වයං-වැඩිදියුණු වන කුසලතා, සැසි අතර මතකය (cross-session recall)**
- **ප්‍රතිනිධායි කරන අතර සමාන්තරගත කරයි — සමාන්තර වැඩ සඳහා උප-නියෝජිතයන් (subagents) නිර්මාණය කරයි**
- **සැලසුම් කරන ලද ස්වයංක්‍රීය කිරීම් (Scheduled automations) — දෛනික වාර්තා, උපස්ථ (backups) සහ විගණන (audits) සඳහා ඇතුළතින්ම ඇති cron පහසුකම**
- **ඕනෑම තැනක ක්‍රියාත්මක වේ — local, Docker, SSH, cloud, serverless**

## ඉක්මන් ස්ථාපනය (Quick Install)

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## ආරම්භ කිරීම

```bash
openamer              # චැට් කිරීම ආරම්භ කරන්න
openamer setup        # ඔබේ API යතුරු (keys) සහ සපයන්නා (provider) සැකසීම
openamer model        # ඔබේ මාදිලිය තෝරාගන්න
openamer update       # නවතම සංස්කරණයට යාවත්කාලීන කරන්න
```

## යාවත්කාලීන කිරීමයි

OpenAmer ස්වයංක්‍රීයව යාවත්කාලීන (updates) පරීක්ෂා කර පිළිගැනීමේ බැනරයේ (welcome banner) අනතුරු ඇඟවීමක් පෙන්වයි. නවතම සංස්කරණය ලබා ගැනීමට `openamer update` ක්‍රියාත්මක කරන්න — එය මුලින්ම ඔබේ දත්ත උපස්ථ (back up) කරයි.

## දායකත්වය ලබාදීම

දායකත්වයන් සාදරයෙන් පිළිගනිමු — open issues හරහා ගැටලු ඉදිරිපත් කරන්න, pull requests ඉදිරිපත් කරන්න, නැතහොත් ප්‍රජාව සමඟ සම්බන්ධ වන්න.

## බලපත්‍රය

Apache බලපත්‍රය 2.0. {LICENSE} බලන්න.

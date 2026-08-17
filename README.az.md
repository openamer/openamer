# OpenAmer Agent

**Özünü təkmilləşdirən Süni İntellekt agenti — təcrübədən öyrənir, bacarıqlar yaradır, üstünlüklərinizi xatırlayır və hər yerdə sizin üçün çalışır.**

İstədiyiniz modeli istifadə edin — OpenRouter, OpenAI, DeepSeek və s. `openamer model` ilə keçid edin — kod dəyişikliyi tələb olunmur.

## Xüsusiyyətlər

- **Həqiqi terminal interfeysi — avtomatik tamamlama, tarixçə və alət çıxışlarının axını ilə tam TUI**
- **Sizin olduğunuz yerdə yaşayır — Telegram, Discord, Slack, WhatsApp və daha çoxu tək bir şlüzdən (gateway)**
- **Zamanla öyrənir — yaddaş, özünü təkmilləşdirən bacarıqlar, sessiyalararası xatırlama**
- **Nümayəndə təyin edir və paralelləşdirir — paralel işlər üçün alt agentlər yaradır**
- **Planlaşdırılmış avtomatlaşdırmalar — gündəlik hesabatlar, ehtiyat nüsxələr və auditlər üçün daxili cron**
- **Hər yerdə işləyir — lokal, Docker, SSH, bulud, serverless**

## Sürətli Quraşdırma

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Başlanğıc

```bash
openamer              # Söhbətə başlayın
openamer setup        # API açarlarınızı və provayderinizi təyin edin
openamer model        # Modelinizi seçin
openamer update       # Ən son versiyaya yeniləyin
```

## Yenilənir

OpenAmer yenilənmələri avtomatik yoxlayır və xoş gəldiniz bannerində xəbərdarlıq göstərir. Ən son versiyanı əldə etmək üçün `openamer update` əmrini icra edin — o, əvvəlcə məlumatlarınızı ehtiyat nüsxəyə köçürür.

## Töhfə vermək

Töhfələr xoş qarşılanır — açıq məsələləri (issues) nəzərdən keçirin, pull request-lər göndərin və ya icmaya qoşulun.

## Lisenziya

Apache Lisenziyası 2.0. Baxın {LICENSE}.

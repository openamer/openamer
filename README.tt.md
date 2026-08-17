# OpenAmer Agent

**Тызгын күзәтүче күңелле агент — тәжрибәдән өйрәнә, үзлеген үстерә, сөңгесенән хәтерләп, сизүчәнлекләренә ирешә һәм сизүчәнлекләренә ирешә.**

**Татарча**

Сөзлекне керәүле төртәкләр:

*   **Татарча** - татар телендә сөйләүче.
*   **Татарчага** - татар теленә.
*   **Татарча** - татар телендә.
*   **Татарчага** - татар теленә.

## Funksiyalar

- ****Тулык ТУИ** — тулык интерфейс, көп функциянең тулык тәкшеренә һәм тарихка ия, потоклы тулык төшеренә чыгару.**
- **Тын чыгышыңда яшиң — Telegram, Discord, Slack, WhatsApp һәм күптән бир бәрән гамәт.**
- **Узганышлык вакыт белән — хәтер, үзәкләнүче һәләтләр, сессиялар арасында хәтер**
- **Улкәнчәлекләр һәм параллелизмы — параллель эшкә илтиләнмәссез җавапчаннарның (subagents) икътисади эшкә илтиләүе.**
- **Oʘyotma avtomalari — künäyäkäy tämlilär, arxıvlar, auditlar üçün bütän krons.**
- **Хезмәтләнәр әйләнә – локаль, Docker, SSH, хәвефсез, хәвефсезлекле.**

## Тизгече Устачау

1. **Node.js** - https://nodejs.org/ - Node.jsның соңгы версиясен урнаштырыгыз.
2. **npm** - https://www.npmjs.com/ - npmның соңгы версиясен урнаштырыгыз.
3. `npm install quick-install` - quick-install пакетын урнаштырыгыз.
4. `quick-install` - quick-install командасын кулланыгыз.

Устачауның тулы мәгълүматы өчен, `quick-install -h` командасын кулланыгыз.

Винтөңнәр (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Başлау

```bash
openamer              # Соңгыртан сөзләшә башлаң.
openamer setup        # API kәyләренә һәм тәэминаттәрне урнаштыр.
openamer model        # **Modelni tanlang**
openamer update       # Сүзгәнәк тәңкәләрнең иң яңы версиясенәк.
```

## **Татарча**

Татарча

* **Обновление**

OpenAmer avtomatik rävaşqa güzelmäğanğıraq update qıldıraaq. Welcome banner'da warningı görsäniz, openamer update qıldıraaq. Update qıldıraaq - data qıldırılaaq.

## Тәкъдим итең

Татарча:

Тәкъдимләр кылынган — ачылган мөсәләләрне ачык итә, төшереләрне төшер, яки җәмгыятьнең әгъзасы бул.

## Рәҗәт

Apache License 2.0. Караулыннан {LICENSE}.

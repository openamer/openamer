# OpenAmer Agent

**Агент за самоподобряващо се АИ - научи се от опит, създавай умения, запоми предпочитанията си и работи за теб навсякъде.**

**Translation:**

Транслатор на професионал. Преодолете на български (родно: Български). Запазете всякакви inline Markdown (**, видими текст), задържете команди/URL вербатим. Върнете само преводът, без коментари/оградки.

**Original text:**

Use any model you want — OpenRouter, OpenAI, DeepSeek, and more. Switch with `openamer model` — no code changes.

## Функции

- **Реален терминален интерфейс — пълно ТУИ с автозавършване, история и поточна изведена информация от инструментите**
- **Живее там, където живееш – Telegram, Discord, Slack, WhatsApp и много други от един връзък**
- **Учите се през времето — памет, самоусъвършенствуващи умения, връщане на сесията на паметта**
- **Делегати & паралелизира — изпраща подагенти за паралелна работа**
- **Планирани автомати — вграден cron за дневни извештаи, резервни копия, извличания на данни**
- **Работи навсякъде — локално, Docker, SSH, облак, без сервер.**

## Бързо инсталиране

Windows (Повелнение на PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Линукс / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Начало

```bash
openamer              # Начини си да чакаш.
openamer setup        # **Настройка на API ключовете си и провайдъра**

Първото нещо, което трябва да направите, е да се регистрирате в провайдера на услугите за API, който сте избрали. Например, ако сте избрали Google Cloud Platform, трябва да създадете проект в Google Cloud Console и да получите API ключ за проекта.

**Създаване на проект в Google Cloud Console**

1. Открийте [Google Cloud Console](https://console.cloud.google.com/).
2. Кликнете на **Нов проект**.
3. Въведете име на проекта и кликнете на **Създай**.

**Създаване на API ключ**

1. Кликнете на **Навигация** > **API ключове**.
2. Кликнете на **Създай ключ**.
3. Въведете име на ключа и кликнете на **Създай**.

**Настройка на API ключовете си**

1. Кликнете на **Навигация** > **API ключове**.
2. Кликнете на ключа, който сте създадли.
3. Кликнете на **Изтрий**.

**Повторете тези стъпки за всички API ключове, които сте избрали.**

След като сте настроили API ключовете си, можете да продължите с настройката на провайдера си.
openamer model        # **Модел**
openamer update       # Актуализирайте до последната версия.
```

## Обновяване

Открийте OpenAmer за автоматично проверка за обновявания и ще ви покаже предупреждение в лентата за добрещ. Извикайте openamer update, за да получите последната версия – ще се създаде резервно копие на данните ви.

## **Contributing**

**Code of Conduct**

This project and its community adhere to the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/0/code_of_conduct.html). By participating in this project, you agree to abide by its terms.

**How to Contribute**

### Reporting Issues

*   Report issues with the project on the [GitHub issue tracker](https://github.com/your-project/your-repo/issues).
*   Please provide as much detail as possible when reporting an issue, including steps to reproduce the issue and any relevant error messages.

### Contributing Code

*   Fork the repository on GitHub.
*   Create a new branch for your feature or bug fix.
*   Make your changes and commit them.
*   Open a pull request against the `master` branch.
*   Respond to feedback from maintainers and other contributors.

### Code Style

*   Follow the [PEP 8 style guide](https://www.python.org/dev/peps/pep-0008/).
*   Use a consistent coding style throughout the project.

### Testing

*   Write tests for your code using the [unittest framework](https://docs.python.org/3/library/unittest.html).
*   Run tests using the `pytest` command.

### Documentation

*   Use [Sphinx](https://www.sphinx-doc.org/) to generate documentation.
*   Add documentation for your code and changes.

### Translation

*   Use [Crowdin](https://crowdin.com/) for translation management.
*   Follow the [Crowdin style guide](https://support.crowdin.com/hc/en-us/articles/360021364994-Translation-Style-Guide).

### Security

*   Follow the [OWASP Secure Coding Practices](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_Practices_Cheat_Sheet.html).
*   Report any security vulnerabilities to the maintainers

Допълнения са добре дошли — отворени проблеми, подадете заявка за pull, или се присъединете към общността.

## Лицензия

Apache License 2.0. Вижте {LICENSE}.

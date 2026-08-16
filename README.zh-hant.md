# OpenAmer Agent

**自我改善的 AI 代理人 — 依據經驗學習，創造技能，記住你的偏好，無處不在為你工作。**

**翻譯工具**
================

我們可以使用多種翻譯工具來翻譯文本。以下是幾個選擇：

*   **Google翻譯**：[https://translate.google.com/](https://translate.google.com/)
*   **DeepL翻譯**：[https://www.deepl.com/translator](https://www.deepl.com/translator)
*   **OpenTranslator**：[https://www.opentranslator.com/](https://www.opentranslator.com/)
*   **Microsoft Translator**：[https://www.microsoft.com/en-us/translator](https://www.microsoft.com/en-us/translator)

您可以選擇任何一個工具來翻譯您的文本。

## **功能**

- **真實終端機介面 — 全功能 TUI（Text User Interface）支援自動完成、歷史紀錄和串流工具輸出**
- **生活在你身邊的社交平台 — Telegram、Discord、Slack、WhatsApp等都可以從一個入口處理**
- **學習過程中學習 — 記憶、自我改善技能、跨會議回憶**
- **代表與並行化 — 為並行工作分派子代理**
- **預設的自動化任務 — 每日報告、備份、審計的內建 cron**
- **可以在任何地方運行 — 本地、Docker、SSH、雲端、無伺服器**

## 快速安裝

Windows (PowerShell)
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## 開始使用

```bash
openamer              # 開始聊天
openamer setup        # **設定 API 金鑰 & 提供者**

1. 申請 API 金鑰
----------------

首先，需要申請 API 金鑰。這個步驟取決於你選擇的 API 提供者。以下是一些流行的 API 提供者：

*   [OpenWeatherMap](https://home.openweathermap.org/users/sign_up)
*   [Google Maps](https://cloud.google.com/maps-platform/pricing)
*   [Twitter Developer](https://developer.twitter.com/en/apply-for-access)
*   [Facebook Developer](https://developers.facebook.com/docs/apps/)

2. 申請完成後，會得到一個 API 金鑰。這個金鑰是用來驗證你的身份，讓你能夠使用 API 的功能。

3. 保存 API 金鑰
----------------

將 API 金鑰儲存到安全的地方，以免被他人取得。可以使用環境變數 (Environment Variable) 或是使用安全的密鑰管理工具。

4. 將 API 金鑰整合到程式碼
-------------------------

根據 API 提供者的文件，將 API 金鑰整合到程式碼中。這通常涉及到將金鑰代入 API 的 URL 或是 Header 中。

5. 測試 API
------------

使用 Postman 或是程式碼測試 API，確認金鑰正確無誤，並能夠正常發出 API 呼叫。

6. 部署 API 金鑰
----------------

將 API 金鑰部署到你的伺服器或是雲端平台，以便於後續的 API 呼叫。

**注意事項**

*   保持 API 金鑰安全，避免被他人取得。
*   限制 API 金鑰的存取權限，避免他人濫用。
*
openamer model        # 選擇你的模型
openamer update       # **更新至最新版本**
```

## 更新

OpenAmer 自動檢查更新並在歡迎標籤上顯示警告。執行 openamer update 可以取得最新版本 — 它會先備份您的資料。

## **貢獻**

歡迎贡献 — 開啟問題、提交 Pull Request 或加入社群。

## **許可證**

許可證是一種授予個體或組織對特定軟體、知識產權或其他資產的權利的文件。許可證通常由創造者或擁有者授予，規定使用、複製、修改或分發這些資產的條件。許可證可以是免費的，也可以收取費用。

許可證的目的在於保護創造者的權益，防止資產被濫用或非法使用。許可證也可以用來限制使用者對資產的使用權，例如限制使用者可以修改或分發資產的能力。

許可證有多種類型，包括：

* **自由軟體許可證**：允許使用者自由修改、複製和分發軟體。
* **專有軟體許可證**：限制使用者對軟體的使用權，通常需要購買或租借。
* **共享許可證**：允許使用者修改和分發軟體，但需要向創造者支付費用。
* **開放原始碼許可證**：允許使用者修改和分發軟體的原始碼，但需要公開原始碼。

許可證的範例包括：

* **MIT許可證**
* **Apache許可證**
* **GPL許可證**
* **BSD許可證**

許可證對於軟體開發和知識產權保護非常重要，它們確保創造者和使用者之間的權益得到保護。

Apache License 2.0。見 [LICENSE]。

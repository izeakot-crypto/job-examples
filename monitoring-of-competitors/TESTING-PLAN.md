# Testing Plan - Monitoring of Competitors v2

## 🎯 Мета тестування

Перевірити workflow на помилки перед production запуском.
**Ліміт: 15 тестових запусків**

---

## ⚠️ ВАЖЛИВА ПЕРЕВІРКА ПЕРЕД ЗАПУСКОМ

### Крок 0: Перевірка Loop Companies з'єднань

1. Відкрий workflow в n8n UI
2. Клікни на ноду **Loop Companies**
3. Подивись на з'єднання (лінії від ноди):

**ПРАВИЛЬНА конфігурація:**
```
Loop Companies:
├─ Output 0 (перша ітерація) → Read Previous Data
├─ Output 1 (не використовується) → нічого
└─ Output 2 (після всіх) → Prepare Telegram Message
```

**Якщо неправильно:**
- Видали всі з'єднання від Loop Companies
- З'єднай Output 0 → Read Previous Data
- З'єднай Output 2 → Prepare Telegram Message
- Save workflow

---

## 📋 План тестування (15 спроб)

### Спроба 1-2: Тест окремих нод

#### Тест 1: Companies List
1. Клікни на ноду **Companies List**
2. Натисни **Execute Node**
3. Перевір output: має бути масив з 19 компаній

**Очікуваний результат:**
```json
[
  {name: 'Ringover', url: 'https://www.ringover.com/'},
  {name: 'Netelip', url: 'https://www.netelip.com/en/'},
  ... (всього 19)
]
```

**Якщо помилка:** Перевір синтаксис масиву в SET ноді

---

#### Тест 2: Fetch Website (з першою компанією)
1. Execute Node на **Companies List**
2. Execute Node на **Loop Companies** (1 компанія)
3. Execute Node на **Fetch Website**
4. Перевір output: має бути HTML код

**Очікуваний результат:**
- Status: 200
- Body: HTML сторінки (починається з `<!DOCTYPE` або `<html>`)

**Якщо помилка:**
- Timeout → збільш timeout в параметрах (зараз 30000ms)
- SSL error → вже є `allowUnauthorizedCerts: true`
- Network error → перевір URL компанії

---

### Спроба 3-5: Тест паралельного збору даних

#### Тест 3: Fetch Website + Blog + Reviews
1. Execute Node на **Loop Companies**
2. Execute Node на **Read Previous Data** (може бути порожній при першому запуску)
3. Execute Node одночасно на:
   - **Fetch Website**
   - **Fetch Blog**
   - **Fetch Reviews**

**Очікуваний результат:**
- Всі 3 ноди виконались (зелені)
- Website: HTML код
- Blog: HTML або 404 (нормально якщо немає /blog)
- Reviews: HTML або 404 (нормально якщо немає /reviews)

**Якщо помилка:**
- 404 на Blog/Reviews → це нормально, Parse All Data це обробить
- Timeout → збільш timeout
- SSL → перевір allowUnauthorizedCerts

---

### Спроба 6-7: Тест парсингу даних

#### Тест 6: Parse All Data
1. Виконай попередні кроки (Fetch Website, Blog, Reviews)
2. Execute Node на **Parse All Data**

**Очікуваний результат:**
```json
{
  "company": "Ringover",
  "url": "https://www.ringover.com/",
  "currentData": {
    "website": {
      "title": "...",
      "description": "...",
      "h1Tags": [...],
      "hasNews": true/false,
      ...
    },
    "blog": {
      "articlesFound": 5,
      "recentArticles": [...]
    },
    "reviews": {
      "found": true/false,
      ...
    }
  },
  "previousData": null або {...}
}
```

**Якщо помилка:**
- Перевір що всі 3 fetch ноди виконались
- Перевір що код не має syntax errors
- Подивись error message в execution log

---

### Спроба 8-10: Тест AI Agent

#### Тест 8: AI Agent (КРИТИЧНИЙ ТЕСТ)
1. Виконай Parse All Data
2. Execute Node на **AI Agent**

**Очікуваний результат:**
Текстовий аналіз українською мовою з секціями:
```
✨ НОВІ ФІЧІ:
...

⚠️ ПРОБЛЕМИ:
...

📰 НОВИНИ/БЛОГ:
...

💬 ІНСАЙТИ З КОМЕНТАРІВ:
...

🎯 СТРАТЕГІЧНІ ВИСНОВКИ:
...
```

**Можливі помилки:**

1. **"OpenAI API error: unauthorized"**
   - Перевір OpenAI API key в credentials
   - Перевір баланс на https://platform.openai.com/usage
   - Перевір що credentials підключено до OpenAI Chat Model

2. **"Model not found"**
   - В OpenAI Chat Model змінити модель на `gpt-4o-mini` або `gpt-3.5-turbo`
   - Модель `gpt-4.1-nano` може не існувати

3. **"Prompt too long"**
   - Скоротити промпт в AI Agent
   - Або змінити модель на gpt-4o (більший контекст)

4. **Порожній вихід**
   - Перевір що Parse All Data передав дані
   - Перевір що промпт правильно налаштований

5. **Англійська мова в відповіді**
   - Додай в промпт: "ОБОВ'ЯЗКОВО українською мовою!"

---

### Спроба 11-12: Тест форматування та збереження

#### Тест 11: Format for Sheets
1. Виконай AI Agent
2. Execute Node на **Format for Sheets**

**Очікуваний результат:**
```json
{
  "Date": "2025-11-19",
  "Company": "Ringover",
  "AI Summary": "✨ НОВІ ФІЧІ: ...",
  "Link": "https://www.ringover.com/"
}
```

**Якщо помилка:**
- Перевір що AI Agent повернув текст
- Перевір код ноди на syntax errors

---

#### Тест 12: Save to Sheets
1. Виконай Format for Sheets
2. Execute Node на **Save to Sheets**
3. Перевір Google Sheets документ

**Очікуваний результат:**
- Новий рядок в таблиці
- Date, Company, AI Summary, Link заповнені

**Можливі помилки:**

1. **"Google Sheets API error: unauthorized"**
   - Перевір Google Sheets credentials
   - Re-authenticate якщо потрібно

2. **"Document not found"**
   - Перевір Sheet ID в параметрах ноди
   - Перевір що таблиця існує і доступна

3. **"Sheet not found"**
   - Перевір що Sheet Name = "Sheet1" (або твоя назва)

4. **"Invalid data format"**
   - Перевір що Format for Sheets повертає правильний формат
   - Перевір mapping в Save to Sheets ноді

---

### Спроба 13-14: Тест loop та Telegram

#### Тест 13: Повний цикл для 1 компанії
1. Налаштуй Loop Companies: batchSize = 1 (вже так)
2. Execute Workflow (весь workflow)
3. Спостерігай:
   - Loop виконує 1 ітерацію
   - Read Previous Data → Fetch → Parse → AI → Format → Save
   - Loop НЕ повертається назад (тільки 1 компанія)
   - Переходить до Prepare Telegram Message

**Очікуваний результат:**
- Всі ноди зелені
- 1 рядок в Google Sheets
- Prepare Telegram Message виконався

**Якщо помилка:**
- Loop зациклився → перевір з'єднання (Крок 0)
- Parse All Data error → подивись execution log
- AI Agent error → перевір OpenAI credentials

---

#### Тест 14: Send Telegram
1. Після успішного Prepare Telegram Message
2. Execute Node на **Send Telegram**

**Очікуваний результат:**
- Повідомлення прийшло в Telegram
- Формат:
```
📊 Щоденний звіт моніторингу конкурентів
📅 Дата: 19.11.2025

1. Ringover
✨ НОВІ ФІЧІ: ...
...
```

**Можливі помилки:**

1. **"Telegram API error: unauthorized"**
   - Перевір токен бота в credentials
   - Перевір що бот активний через @BotFather

2. **"Chat not found"**
   - Перевір Chat ID в параметрах
   - Відправ /start боту

3. **"Message too long"**
   - Telegram ліміт: 4096 символів
   - Скороти повідомлення в Prepare Telegram Message

4. **YOUR_GOOGLE_SHEET_URL не замінено**
   - В Prepare Telegram Message замінити на реальний URL

---

### Спроба 15: Фінальний тест (2-3 компанії)

#### Тест 15: Повний workflow з 2-3 компаніями
1. В Companies List залиш тільки 2-3 компанії для тесту:
```javascript
[
  {name: 'Ringover', url: 'https://www.ringover.com/'},
  {name: 'CloudTalk', url: 'https://www.cloudtalk.io/es/'},
  {name: 'Binotel', url: 'https://www.binotel.ua/ua'}
]
```

2. Execute Workflow
3. Спостерігай:
   - Loop обробляє кожну компанію по черзі
   - Після кожної → Save to Sheets → Loop повертається
   - Після всіх 3 → Prepare Telegram → Send Telegram

**Очікуваний результат:**
- 3 рядки в Google Sheets (по одному на компанію)
- 1 Telegram повідомлення з усіма 3 компаніями
- Loop НЕ зациклився

**Можливі помилки:**

1. **Loop зациклився**
   - Перевір з'єднання (має бути як в Кроці 0)
   - Перевір що Save to Sheets з'єднано з Loop input 0

2. **Деякі компанії пропущені**
   - Перевір timeout в Fetch нодах
   - Деякі сайти можуть бути недоступні → це нормально

3. **AI Agent падає на деяких компаніях**
   - Перевір чи Parse All Data обробляє null значення
   - Додай `|| ''` для захисту

4. **Telegram не приходить**
   - Перевір що Prepare Telegram Message отримав ВСІ компанії
   - Перевір що Loop вийшов через Output 2

---

## 📊 Checklist після тестування

Після 15 спроб заповни:

- [ ] Companies List працює
- [ ] Fetch Website працює
- [ ] Fetch Blog працює (або 404 - нормально)
- [ ] Fetch Reviews працює (або 404 - нормально)
- [ ] Parse All Data працює
- [ ] AI Agent працює (повертає текст українською)
- [ ] Format for Sheets працює
- [ ] Save to Sheets працює (з'являються рядки)
- [ ] Loop Companies НЕ зациклюється
- [ ] Prepare Telegram Message працює
- [ ] Send Telegram працює (приходить повідомлення)
- [ ] Повний workflow працює для 2-3 компаній

---

## 🐛 Типові помилки та рішення

### 1. Loop зациклюється
**Симптоми:** Workflow не завершується, обробляє компанії нескінченно

**Рішення:**
- Перевір з'єднання Loop Companies (Крок 0)
- Output 0 → Read Previous Data
- Output 2 → Prepare Telegram Message

### 2. Parse All Data падає з помилкою
**Симптоми:** "Cannot read property '...' of undefined"

**Рішення:**
- Додай `|| ''` для всіх HTML змінних
- Приклад: `const websiteHtml = $('Fetch Website').item.json.body || '';`

### 3. AI Agent повертає англійську
**Симптоми:** Аналіз англійською замість української

**Рішення:**
- В промпті додай: "КРИТИЧНО ВАЖЛИВО: Пиши виключно українською мовою!"
- В System Message додай: "You must respond in Ukrainian language only"

### 4. Google Sheets дублює рядки
**Симптоми:** Декілька рядків для однієї компанії

**Рішення:**
- Перевір що Loop правильно налаштований
- Перевір що Save to Sheets викликається 1 раз на компанію

### 5. Telegram не приходить
**Симптоми:** Всі ноди зелені, але повідомлення немає

**Рішення:**
- Перевір Chat ID
- Відправ /start боту
- Перевір токен в credentials
- Подивись execution log Send Telegram ноди

---

## 📝 Звіт після тестування

Після використання 15 спроб заповни:

**Використано спроб:** ___ / 15

**Статус workflow:**
- ✅ Повністю працює
- ⚠️ Працює з помилками (описати)
- ❌ Не працює (описати)

**Знайдені проблеми:**
1.
2.
3.

**Що потрібно доробити:**
1.
2.
3.

---

## 🎯 Production запуск

Коли всі тести пройдені:

1. В Companies List поверни всі 19 компаній
2. Перевір Google Sheets (має бути правильний ID)
3. Перевір Telegram (Chat ID та токен бота)
4. В Prepare Telegram Message замінити YOUR_GOOGLE_SHEET_URL
5. Активуй Schedule Trigger (toggle Active → ON)
6. Встанови розклад (за замовчуванням щодня о 9:00)

**Готово! 🚀**

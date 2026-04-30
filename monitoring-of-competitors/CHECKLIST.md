# Чек-лист запуску системи моніторингу конкурентів

## Підготовка

- [ ] Переглянути файл `README.md` для розуміння структури проєкту
- [ ] Перевірити список компаній у `config/companies.json`
- [ ] Додати/видалити компанії за потребою
- [ ] Перевірити коректність URL всіх компаній

## Налаштування n8n

### Імпорт та базова конфігурація
- [ ] Відкрити n8n
- [ ] Імпортувати workflow з `workflows/monitoring-workflow.json`
- [ ] Перевірити, що всі ноди успішно імпортувались
- [ ] Перейменувати workflow на "Monitoring of Competitors" (якщо потрібно)

### Налаштування Read Binary File node
- [ ] Відкрити ноду "Read Companies JSON"
- [ ] Вказати повний шлях до файлу `config/companies.json`:
  ```
  [USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\config\companies.json
  ```
- [ ] Тестувати ноду, переконатись що файл читається

### Налаштування розкладу
- [ ] Відкрити ноду "Schedule Trigger"
- [ ] Вибрати частоту запусків:
  - [ ] Щоденно о 9:00
  - [ ] Щодня о 18:00 (другий запуск)
  - [ ] Інший розклад: _____________
- [ ] Зберегти налаштування

## Інтеграція Google Sheets

### Створення таблиці
- [ ] Створити новий Google Sheets документ
- [ ] Назвати документ "Competitor Monitoring Data"
- [ ] Створити аркуші:
  - [ ] Sheet1: "Monitoring Data"
  - [ ] Sheet2: "Blog Posts"
  - [ ] Sheet3: "Social Media"
  - [ ] Sheet4: "Changes Log"

### Налаштування колонок

**Monitoring Data:**
- [ ] Додати заголовки: Date | Company | URL | Title | Description | Blog Posts Count | Social Posts Count | Sentiment | AI Summary | Priority | Action Required

**Blog Posts:**
- [ ] Додати заголовки: Date Found | Company | Title | URL | Published Date | Summary | Keywords | Sentiment

**Social Media:**
- [ ] Додати заголовки: Date | Company | Platform | Content | Engagement | Sentiment | Link

**Changes Log:**
- [ ] Додати заголовки: Date Detected | Company | Change Type | Old Value | New Value | Priority | Status

### Підключення до n8n
- [ ] В n8n відкрити Credentials
- [ ] Додати "Google Sheets API" credentials
- [ ] Авторизуватись через OAuth2
- [ ] Скопіювати ID таблиці з URL
- [ ] Вставити ID в ноду "Save to Google Sheets"
- [ ] Налаштувати mapping полів
- [ ] Тестувати запис даних

## Налаштування OpenAI

### Отримання API ключа
- [ ] Зареєструватись на https://platform.openai.com/
- [ ] Створити новий API ключ
- [ ] Скопіювати ключ (він показується тільки один раз!)
- [ ] Перевірити баланс на акаунті

### Інтеграція з n8n
- [ ] В n8n відкрити Credentials
- [ ] Додати "OpenAI API" credentials
- [ ] Вставити API ключ
- [ ] Відкрити ноду "AI Summarize Content"
- [ ] Вибрати модель: `gpt-4o-mini` (економна) або `gpt-4o` (краща якість)
- [ ] Перевірити промпт, адаптувати під свої потреби
- [ ] Тестувати AI аналіз на тестових даних

## Налаштування Telegram

### Створення бота
- [ ] Відкрити Telegram
- [ ] Знайти @BotFather
- [ ] Відправити команду `/newbot`
- [ ] Вказати ім'я бота
- [ ] Вказати username бота
- [ ] Скопіювати токен бота

### Отримання Chat ID
- [ ] Знайти @userinfobot
- [ ] Відправити `/start`
- [ ] Скопіювати ваш Chat ID

### Підключення до n8n
- [ ] В n8n додати "Telegram API" credentials
- [ ] Вставити токен бота
- [ ] Відкрити ноду "Send Telegram Notification"
- [ ] Вставити Chat ID
- [ ] Налаштувати шаблон повідомлення
- [ ] Тестувати відправку нотифікації

## Налаштування соцмереж (Опційно)

### YouTube Data API
- [ ] Перейти на https://console.cloud.google.com/
- [ ] Створити новий проєкт або вибрати існуючий
- [ ] Увімкнути "YouTube Data API v3"
- [ ] Створити credentials → API Key
- [ ] Скопіювати API ключ
- [ ] Додати в n8n як HTTP Request з параметром `key`
- [ ] Тестувати запит до YouTube API

### Facebook Graph API
- [ ] Перейти на https://developers.facebook.com/
- [ ] Створити новий App
- [ ] Додати продукт "Facebook Login"
- [ ] Отримати Page Access Token
- [ ] Додати в n8n як HTTP Request з Authorization header
- [ ] Тестувати запит до Facebook API

### LinkedIn API
- [ ] Перейти на https://www.linkedin.com/developers/
- [ ] Створити новий App
- [ ] Налаштувати OAuth 2.0
- [ ] Отримати Access Token
- [ ] Додати в n8n
- [ ] Тестувати запит

## Тестування системи

### Тестовий запуск
- [ ] Відкрити workflow в n8n
- [ ] Натиснути "Execute Workflow"
- [ ] Спостерігати виконання кожної ноди
- [ ] Перевірити чи немає помилок

### Перевірка кожного блоку
- [ ] Schedule Trigger активується
- [ ] Read Companies JSON читає файл
- [ ] Parse Companies парсить JSON
- [ ] Loop Over Companies проходить по списку
- [ ] Fetch Company Website отримує HTML
- [ ] Parse Website Content парсить контент
- [ ] Check Blog Monitoring перевіряє умови
- [ ] Fetch Blog отримує блог (якщо є)
- [ ] Parse Blog Content парсить блог
- [ ] AI Summarize Content створює саммарі
- [ ] Save to Google Sheets зберігає дані
- [ ] Check for Changes виявляє зміни
- [ ] Send Telegram Notification відправляє повідомлення

### Перевірка результатів
- [ ] Відкрити Google Sheets
- [ ] Переконатись що дані записались
- [ ] Перевірити формат даних
- [ ] Перевірити AI саммарі на якість

- [ ] Перевірити Telegram
- [ ] Переконатись що нотифікація прийшла
- [ ] Перевірити формат повідомлення
- [ ] Перевірити всі посилання

## Оптимізація

### Швидкість виконання
- [ ] Додати затримки між запитами (Wait node)
- [ ] Рекомендовано: 2-5 секунд між запитами до одного домену
- [ ] Перевірити timeout налаштування (збільшити якщо потрібно)

### Якість даних
- [ ] Перевірити чи всі селектори працюють
- [ ] Адаптувати парсинг під конкретні сайти
- [ ] Перевірити чи AI промпти дають якісні результати
- [ ] Налаштувати фільтрацію дублікатів

### Error Handling
- [ ] Додати Error Trigger workflows
- [ ] Налаштувати нотифікації про помилки
- [ ] Додати retry логіку для failed запитів
- [ ] Налаштувати логування

## Моніторинг та підтримка

### Щоденні перевірки
- [ ] Переглядати Google Sheets на нові дані
- [ ] Читати Telegram нотифікації
- [ ] Перевіряти чи workflow виконується за розкладом

### Щотижневі задачі
- [ ] Аналізувати зібрані дані
- [ ] Оновлювати AI промпти за потребою
- [ ] Додавати нові компанії для моніторингу
- [ ] Видаляти неактивні компанії

### Щомісячні задачі
- [ ] Переглядати витрати на API (OpenAI, YouTube, etc.)
- [ ] Оптимізувати використання квот
- [ ] Архівувати старі дані
- [ ] Оновлювати документацію

## Розширення функціоналу

### Додаткові функції
- [ ] Додати моніторинг цін (якщо є на сайтах)
- [ ] Інтегрувати аналіз коментарів
- [ ] Додати порівняльні звіти
- [ ] Створити дашборд для візуалізації
- [ ] Налаштувати email звіти

### Автоматизація
- [ ] Створити weekly/monthly звіти
- [ ] Автоматичне виявлення нових конкурентів
- [ ] Автоматична категоризація контенту
- [ ] Predictive analytics (майбутні тренди)

## Troubleshooting

### Якщо workflow не запускається
- [ ] Перевірити Schedule Trigger налаштування
- [ ] Активувати workflow (toggle в правому верхньому куті)
- [ ] Перевірити чи немає помилок в нодах

### Якщо не парсяться дані
- [ ] Перевірити URL компанії
- [ ] Перевірити timeout налаштування
- [ ] Подивитись структуру HTML сайту
- [ ] Адаптувати селектори під конкретний сайт

### Якщо AI не працює
- [ ] Перевірити API ключ OpenAI
- [ ] Перевірити баланс на акаунті
- [ ] Зменшити довжину промпту
- [ ] Спробувати іншу модель

### Якщо не зберігаються дані
- [ ] Перевірити Google Sheets credentials
- [ ] Перевірити ID таблиці
- [ ] Перевірити mapping полів
- [ ] Перевірити права доступу до таблиці

## Контакти та ресурси

### Документація
- [n8n Docs](https://docs.n8n.io/)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [YouTube API Docs](https://developers.google.com/youtube/v3)
- [Facebook Graph API Docs](https://developers.facebook.com/docs/graph-api)

### Підтримка
- n8n Community: https://community.n8n.io/
- GitHub Issues: https://github.com/n8n-io/n8n/issues

---

## Статус виконання

**Дата початку:** _____________
**Дата завершення:** _____________
**Відповідальна особа:** _____________

**Нотатки:**


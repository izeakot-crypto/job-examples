# Інструкції по налаштуванню системи моніторингу

## 1. Підготовка n8n

### Імпорт workflow
1. Відкрийте n8n
2. Перейдіть в розділ Workflows
3. Натисніть "Import from File"
4. Виберіть файл `workflows/monitoring-workflow.json`

## 2. Налаштування інтеграцій

### Google Sheets
1. Створіть новий Google Sheets документ
2. Додайте заголовки колонок: Date, Company, URL, Title, Description, Blog Posts, AI Summary
3. В n8n додайте Google Sheets credentials
4. В ноді "Save to Google Sheets" вкажіть ID вашого документа

### OpenAI (для AI суммаризації)
1. Отримайте API ключ на https://platform.openai.com/
2. В n8n додайте OpenAI credentials
3. Вкажіть ключ в налаштуваннях ноди "AI Summarize Content"

### Telegram (для нотифікацій)
1. Створіть бота через @BotFather
2. Отримайте токен бота
3. Отримайте ваш Chat ID (можна через @userinfobot)
4. В n8n додайте Telegram credentials
5. Вкажіть Chat ID в ноді "Send Telegram Notification"

## 3. Налаштування Read Binary File

В ноді "Read Companies JSON" вкажіть повний шлях до файлу:
```
[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\config\companies.json
```

## 4. Налаштування розкладу

В ноді "Schedule Trigger" налаштуйте частоту запусків:
- Щоденно: 24 години
- Щотижня: 168 годин
- Кастомний розклад за потребою

## 5. Тестування

### Тестовий запуск
1. Відкрийте workflow в n8n
2. Натисніть "Execute Workflow"
3. Перевірте виконання кожної ноди
4. Переконайтесь, що дані збираються та зберігаються

### Налагодження помилок
- Якщо сайт не завантажується - збільште timeout в HTTP Request
- Якщо парсинг не працює - перевірте структуру HTML
- Якщо AI не відповідає - перевірте API ключ та баланс

## 6. Розширення функціоналу

### Додавання соцмереж

#### YouTube
1. Отримайте YouTube API key
2. Додайте HTTP Request ноду для YouTube Data API
3. Використайте endpoint: `https://www.googleapis.com/youtube/v3/search`

#### LinkedIn
1. Створіть LinkedIn App
2. Отримайте Access Token
3. Додайте LinkedIn OAuth в n8n

#### Facebook
1. Створіть Facebook App
2. Отримайте Page Access Token
3. Використайте Graph API для отримання постів

### Додавання аналізу коментарів

1. Додайте ноду для скрапінгу коментарів з сайтів
2. Використайте AI для аналізу сентименту
3. Виявляйте ключові теми та "болі" клієнтів

## 7. Оптимізація

### Швидкість роботи
- Додайте затримки між запитами (Wait node)
- Використовуйте caching для даних
- Розділіть workflow на декілька менших

### Якість даних
- Додайте валідацію отриманих даних
- Фільтруйте дублікати
- Зберігайте історію змін

## 8. Моніторинг системи

### Перевірка роботи
- Налаштуйте нотифікації про помилки
- Ведіть лог виконання workflow
- Перевіряйте регулярність збору даних

### Метрики
- Кількість успішних запитів
- Час виконання workflow
- Кількість знайдених змін
- Якість AI суммаризації

## Додаткові ресурси

- [Документація n8n](https://docs.n8n.io/)
- [OpenAI API](https://platform.openai.com/docs)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Telegram Bot API](https://core.telegram.org/bots/api)


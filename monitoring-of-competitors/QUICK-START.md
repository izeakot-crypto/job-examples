# Quick Start Guide - Система моніторингу конкурентів

## Швидкий старт за 15 хвилин

### Крок 1: Імпорт workflow (2 хв)

1. Відкрийте ваш n8n
2. Натисніть "+" → "Import from File"
3. Виберіть файл: `workflows/monitoring-workflow.json`
4. Натисніть "Import"

### Крок 2: Налаштування файлу компаній (3 хв)

1. Відкрийте файл `config/companies.json`
2. Перевірте список компаній
3. За потребою відредагуйте URL або пріоритети
4. Збережіть файл

### Крок 3: Підключення Google Sheets (5 хв)

1. Створіть новий [Google Sheets](https://sheets.google.com) документ
2. Додайте заголовки в перший рядок:
   ```
   Date | Company | URL | Title | Description | Blog Posts | AI Summary
   ```
3. Скопіюйте ID документа з URL:
   ```
   https://docs.google.com/spreadsheets/d/[THIS_IS_THE_ID]/edit
   ```
4. В n8n:
   - Перейдіть до Credentials → Add Credential → Google Sheets
   - Авторизуйтесь через Google
   - Відкрийте ноду "Save to Google Sheets"
   - Вставте ID документа
   - Збережіть

### Крок 4: Налаштування OpenAI (3 хв)

1. Отримайте API ключ на [OpenAI Platform](https://platform.openai.com/api-keys)
2. В n8n:
   - Credentials → Add Credential → OpenAI
   - Вставте API ключ
   - Збережіть
3. Відкрийте ноду "AI Summarize Content"
4. Виберіть credentials
5. Модель: `gpt-4o-mini` (економна)

### Крок 5: Налаштування Telegram (2 хв)

1. В Telegram знайдіть `@BotFather`
2. Відправте `/newbot` і створіть бота
3. Скопіюйте токен
4. Знайдіть `@userinfobot` і отримайте ваш Chat ID
5. В n8n:
   - Credentials → Add Credential → Telegram
   - Вставте токен
   - Відкрийте ноду "Send Telegram Notification"
   - Вставте Chat ID

### Крок 6: Тестовий запуск

1. Натисніть "Execute Workflow"
2. Спостерігайте виконання
3. Перевірте Google Sheets - там має з'явитись дані
4. Перевірте Telegram - має прийти нотифікація

**Готово! 🎉** Ваша система моніторингу працює!

---

## Базова конфігурація

### Що моніторується за замовчуванням

- ✅ Головні сторінки сайтів
- ✅ Meta tags (title, description)
- ✅ Структура заголовків (H1, H2)
- ✅ Блоги компаній
- ✅ AI аналіз контенту
- ⬜ Соцмережі (потребує додаткового налаштування)
- ⬜ Ціни (потребує додаткового налаштування)

### Частота моніторингу

За замовчуванням: **1 раз на добу**

Для зміни:
1. Відкрийте ноду "Schedule Trigger"
2. Змініть інтервал
3. Збережіть workflow

---

## Перші результати

### Що ви побачите в Google Sheets

| Date | Company | URL | Title | Description | Blog Posts | AI Summary |
|------|---------|-----|-------|-------------|------------|------------|
| 2025-01-19 | Ringover | ringover.com | VoIP Solution | Cloud phone system... | 3 | Company focuses on... |

### Що ви отримаєте в Telegram

```
🔔 Зміни у конкурента: Ringover

🔴 Високий пріоритет:
• 2 нових статей у блозі
  - New Feature: AI Call Analytics
  - Pricing Update for 2025

🔗 Переглянути сайт
📊 Всього змін: 2
⏰ 19.01.2025, 10:30
```

---

## Налаштування розкладу

### Варіанти частоти моніторингу

#### Один раз на день (рекомендовано для старту)
```json
{
  "interval": [{ "field": "hours", "hoursInterval": 24 }]
}
```

#### Двічі на день
```json
{
  "interval": [{ "field": "hours", "hoursInterval": 12 }]
}
```

#### Кожної години (тільки для high-priority компаній)
```json
{
  "interval": [{ "field": "hours", "hoursInterval": 1 }]
}
```

#### Конкретний час (наприклад, 9:00 щодня)
```json
{
  "cronExpression": "0 9 * * *"
}
```

---

## Додавання нових компаній

### Швидкий спосіб

1. Відкрийте `config/companies.json`
2. Додайте новий об'єкт:

```json
{
  "name": "Нова Компанія",
  "url": "https://company.com/",
  "region": "Ukraine",
  "priority": "high",
  "monitoring": {
    "website": true,
    "blog": true,
    "socialMedia": {
      "youtube": true,
      "facebook": true,
      "linkedin": true
    }
  }
}
```

3. Збережіть файл
4. Workflow автоматично використає оновлений список

---

## Читання результатів

### Інтерпретація AI Summary

AI аналіз включає:
1. **Основні теми** - про що пише компанія
2. **Нові функції** - що анонсують
3. **Маркетингова стратегія** - як позиціонуються
4. **Цільова аудиторія** - на кого орієнтуються
5. **Insights** - що корисного для вас

### Приклад AI Summary:

```
Основні теми: Company focuses on AI-powered call analytics
and omnichannel customer support for SMBs.

Нові функції: Announced integration with Salesforce and
new mobile app with video calling.

Маркетингова стратегія: Emphasizing ease of use and
affordable pricing for small businesses.

Цільова аудиторія: Small to medium businesses in retail
and e-commerce sectors.

Insights: They're targeting the same SMB segment as us.
Their Salesforce integration could be a competitive advantage.
Consider prioritizing our CRM integrations.
```

---

## Звичайні питання (FAQ)

### Q: Скільки це коштує?

**A:** Залежить від використання:
- n8n: безкоштовно (self-hosted)
- OpenAI API: ~$0.10-0.50 на компанію на день (gpt-4o-mini)
- Google Sheets: безкоштовно
- Telegram: безкоштовно

**Приблизно $3-10 на місяць** для моніторингу 20 компаній

### Q: Як часто запускати моніторинг?

**A:** Рекомендації:
- **Для старту**: 1 раз на день
- **Для активного моніторингу**: 2-3 рази на день
- **Для критичних конкурентів**: 4-6 разів на день

### Q: Скільки компаній можна моніторити?

**A:** Технічно - необмежено, але:
- **Оптимально**: 10-20 компаній
- **Максимум в одному workflow**: 50 компаній
- **Для більше**: розділіть на декілька workflow

### Q: Що робити якщо workflow падає з помилкою?

**A:** Перевірте:
1. Чи існує URL компанії
2. Чи правильні credentials (Google Sheets, OpenAI)
3. Чи є баланс на OpenAI акаунті
4. Подивіться error log в n8n

### Q: Як покращити якість AI аналізу?

**A:**
1. Використовуйте модель `gpt-4o` замість `gpt-4o-mini`
2. Додайте більше контексту в промпт
3. Вкажіть конкретні питання для аналізу
4. Додайте приклади бажаних відповідей

---

## Наступні кроки

Після успішного запуску базової системи:

### Тиждень 1: Збір даних
- [ ] Спостерігайте за результатами
- [ ] Оцініть якість AI аналізу
- [ ] Налаштуйте частоту запусків

### Тиждень 2: Оптимізація
- [ ] Додайте компанії, які пропустили
- [ ] Покращіть AI промпти
- [ ] Налаштуйте фільтри нотифікацій

### Тиждень 3: Розширення
- [ ] Додайте моніторинг соцмереж (див. `docs/social-media-integration.md`)
- [ ] Налаштуйте weekly звіти
- [ ] Створіть дашборд в Google Sheets

### Місяць 1: Автоматизація
- [ ] Налаштуйте автоматичні weekly звіти
- [ ] Додайте аналіз трендів
- [ ] Інтегруйте з вашими внутрішніми системами

---

## Корисні посилання

- 📖 [Повна документація](./docs/setup-instructions.md)
- 📋 [Детальний чек-лист](./CHECKLIST.md)
- 🔧 [Code snippets для n8n](./docs/n8n-code-snippets.md)
- 🤖 [AI промпти](./docs/ai-prompts.md)
- 📱 [Інтеграція соцмереж](./docs/social-media-integration.md)
- ⭐ [Best Practices](./docs/best-practices.md)

---

## Підтримка

Якщо виникли питання:

1. Перевірте [документацію](./docs/)
2. Перегляньте [best practices](./docs/best-practices.md)
3. Шукайте рішення в [n8n community](https://community.n8n.io/)

**Успішного моніторингу! 🚀**

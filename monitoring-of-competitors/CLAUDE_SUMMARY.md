# Claude Summary - Monitoring of Competitors

## Про проєкт
Система автоматичного моніторингу конкурентів для Oki-toki (контакт-центр/телефонія).
Моніторить 19 компаній-конкурентів з різних регіонів.

## Workflow
- **URL**: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7
- **ID**: `qk1bISszvNIH6Ww7`
- **Назва**: "Monitoring of Competitors v2"
- **Статус**: Активний
- **Вузлів**: 40

## Архітектура Workflow
```
Schedule Trigger → Google Sheets (список компаній) → Loop Companies
    ↓
Для кожної компанії:
├── Fetch Website → Auto-detect YouTube → YouTube API
├── Auto-detect Social Links → Fetch G2 Page
└── Website Checker → Extract URLs → Fetch Pages → Parse Content
    ↓
Merge6 (агрегація всіх даних)
    ↓
AI Agent (OpenAI gpt-4.1-mini) + 7 Tools
    ↓
Parse AI JSON → Format for Sheets → Google Sheets (збереження)
```

## AI Agent Tools
1. youtube_channel_info
2. youtube_search
3. vk_group_info
4. telegram_channel_info
5. website_parser
6. g2_search
7. Wikipedia

## ПОТОЧНА ПРОБЛЕМА (29.12.2024)
**AI Agent споживає 200k+ токенів** - це ліміт LLM!

### Причина
Tools викликаються багато разів (84+ викликів OpenAI на одну компанію).
AI Agent робить повторні виклики tools замість того, щоб обмежитись.

### Рішення (треба застосувати)

**1. Оновити System Prompt в AI Agent node:**
```
Ти аналітик конкурентів. Повертай ТІЛЬКИ valid JSON без markdown.

⚠️ КРИТИЧНІ ОБМЕЖЕННЯ (ДУЖЕ ВАЖЛИВО!):
- Максимум 1 виклик кожного tool на компанію
- Якщо tool повернув помилку або пусто - НЕ повторюй виклик
- Загалом НЕ більше 5 викликів tools на одну компанію
- Якщо дані вже є в INPUT - НЕ використовуй tool для тих самих даних
- ЗАБОРОНЕНО робити більше 1 youtube_search запиту

ДОСТУПНІ ІНСТРУМЕНТИ (використовуй економно!):
1. youtube_channel_info - ОДИН виклик максимум
2. youtube_search - ОДИН виклик максимум
3. vk_group_info - ОДИН виклик якщо є VK посилання
4. telegram_channel_info - ОДИН виклик якщо є TG посилання
5. website_parser - НЕ використовуй - дані вже в input
6. g2_search - ОДИН виклик максимум
7. Wikipedia - тільки якщо нічого не знайдено

ІНСТРУКЦІЇ:
- Спочатку проаналізуй INPUT дані
- Tools тільки для ДОПОВНЕННЯ
- НЕ повторюй виклики tools!
- Повертай ТІЛЬКИ valid JSON
```

**2. В AI Agent node встановити Max Iterations = 5-7**

## Ключові файли
- `config/companies.json` - 19 компаній для моніторингу
- `workflows/*.json` - версії workflow
- `docs/` - документація

## Корисні команди для n8n MCP
```
mcp__n8n-flexible__n8n_get_workflow - отримати workflow
mcp__n8n-flexible__n8n_get_node - отримати конкретний node
mcp__n8n-flexible__n8n_update_node_parameters - оновити параметри node
```

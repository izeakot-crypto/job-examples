# ІНСТРУКЦІЯ: Додавання nodes для парсингу всіх сторінок

## Структура workflow:

```
Call Website Checker
  ↓
[1] Fetch Sitemap
  ↓
[2] Parse Sitemap XML
  ↓
[3] Filter Pages (гнучко blog/blogs/BlogS)
  ↓
[4] Fetch Page Content
  ↓
[5] Parse Page Content
  ↓
[6] Aggregate by Category
  ↓
[Далі до AI Agent...]
```

---

## Додавання nodes:

### 1️⃣ NODE: Fetch Sitemap

**Type:** Code
**Name:** `Fetch Sitemap`
**Position:** Після "Call Website Checker"
**Code:** Скопіювати з `01_FETCH_SITEMAP.js`

**Connection:**
- Input: Call Website Checker → Fetch Sitemap

---

### 2️⃣ NODE: HTTP Request - Get Sitemap

**Type:** HTTP Request
**Name:** `Get Sitemap XML`
**Parameters:**
- **URL:** `={{ $json.url }}`
- **Method:** GET
- **Options → Response → Never Error:** true
- **Timeout:** 30000

**Connection:**
- Fetch Sitemap → Get Sitemap XML

---

### 3️⃣ NODE: Parse Sitemap

**Type:** Code
**Name:** `Parse Sitemap XML`
**Code:** Скопіювати з `02_PARSE_SITEMAP.js`

**Connection:**
- Get Sitemap XML → Parse Sitemap XML

---

### 4️⃣ NODE: Filter Pages

**Type:** Code
**Name:** `Filter Pages`
**Code:** Скопіювати з `03_FILTER_PAGES.js`

**ВАЖЛИВО:** Цей node повертає `null` для URLs які не підходять
→ Додай **Remove Nulls** node після нього

**Connection:**
- Parse Sitemap XML → Filter Pages → **[Remove Empty Items]** → Fetch Page Content

**Remove Empty Items:**
- Type: Function
- Function: Keep Only Set

---

### 5️⃣ NODE: Fetch Page Content

**Type:** HTTP Request
**Name:** `Fetch Page Content`
**Parameters:** Взяти з `04_FETCH_PAGE.json` або налаштувати:
- **URL:** `={{ $json.url }}`
- **Headers:**
  - `User-Agent`: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`
  - `Accept`: `text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8`
  - `Accept-Language`: `en-US,en;q=0.9`
- **Options:**
  - Follow Redirects: true (max 5)
  - Never Error: true
  - Timeout: 30000

**Connection:**
- Filter Pages (через Remove Empty Items) → Fetch Page Content

---

### 6️⃣ NODE: Parse Page Content

**Type:** Code
**Name:** `Parse Page Content`
**Code:** Скопіювати з `05_PARSE_PAGE_CONTENT.js`

**Connection:**
- Fetch Page Content → Parse Page Content

---

### 7️⃣ NODE: Aggregate by Category

**Type:** Code
**Name:** `Aggregate by Category`
**Code:** Скопіювати з `06_AGGREGATE_BY_CATEGORY.js`

**ВАЖЛИВО:** Цей node чекає на ВСІ items від Parse Page Content
→ Він виконається тільки після обробки всіх сторінок

**Connection:**
- Parse Page Content → Aggregate by Category

---

## Приклад фільтрації (гнучкість):

Код в **Filter Pages** розпізнає:
- Blog: `/blog`, `/blogs`, `/BLOG`, `/BlogS`, `/article`, `/articles`, `/post`, `/posts`, `/insights`
- News: `/news`, `/новини`, `/новости`, `/press`, `/announcements`
- Reviews: `/review`, `/reviews`, `/testimonial`, `/testimonials`, `/отзывы`
- Pricing: `/pricing`, `/price`, `/plans`, `/тарифи`, `/ціни`
- Features: `/features`, `/feature`, `/можливості`, `/функції`

**Case-insensitive** - працює з будь-яким регістром!

---

## Що отримаємо на виході Aggregate by Category:

```json
{
  "companyUrl": "https://www.ringover.com",
  "companyName": "Ringover",
  "totalPagesParsed": 45,
  "statistics": {
    "blog": 15,
    "news": 3,
    "reviews": 2,
    "pricing": 1,
    "features": 8,
    "products": 5,
    "about": 2,
    "contact": 1,
    "careers": 3,
    "solutions": 5
  },
  "categorizedData": {
    "blog": [
      {
        "url": "https://www.ringover.com/blog/ai-features",
        "metadata": { "title": "...", "description": "..." },
        "content": {
          "articles": [
            { "title": "New AI Features", "date": "2025-12-01", "preview": "..." }
          ],
          "totalArticles": 1
        }
      }
    ],
    "reviews": [...],
    "pricing": [...],
    ...
  }
}
```

Ці дані можна відправити в AI Agent для аналізу!

---

## Тестування:

1. Запусти workflow на 1 компанії
2. Перевір output кожного node:
   - **Fetch Sitemap:** має повернути sitemap URLs
   - **Parse Sitemap XML:** масив всіх URLs зі сайту
   - **Filter Pages:** тільки URLs з blog, news, reviews тощо
   - **Parse Page Content:** спарсені дані для кожної сторінки
   - **Aggregate by Category:** згруповані дані

3. Перевір console logs для debugging

---

## Час виконання:

- **Sitemap fetch:** ~2-5 сек
- **Parse sitemap:** ~1 сек
- **Filter:** ~1 сек
- **Fetch кожної сторінки:** ~2-3 сек × кількість сторінок
- **Parse:** ~1 сек × кількість сторінок
- **Aggregate:** ~1 сек

**Для 50 сторінок:** ~3-5 хвилин загалом

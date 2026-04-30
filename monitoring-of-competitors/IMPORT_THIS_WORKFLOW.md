# ІМПОРТ ОНОВЛЕНОГО WORKFLOW

## Швидкий спосіб - через n8n UI:

1. Відкрий https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7

2. Після node **"Call 'website checker..."** додай ці 8 nodes вручну:

---

### NODE 1: Fetch Sitemap
- **Type:** Code
- **Name:** `Fetch Sitemap`
- **Code:** Скопіюй з `01_FETCH_SITEMAP.js`
- **Connection:** Call Website Checker → Fetch Sitemap

---

### NODE 2: Get Sitemap XML
- **Type:** HTTP Request
- **Name:** `Get Sitemap XML`
- **URL:** `={{ $json.url }}`
- **Method:** GET
- **Options → Response → Never Error:** true
- **Timeout:** 30000
- **Connection:** Fetch Sitemap → Get Sitemap XML

---

### NODE 3: Parse Sitemap XML
- **Type:** Code
- **Name:** `Parse Sitemap XML`
- **Code:** Скопіюй з `02_PARSE_SITEMAP.js`
- **Connection:** Get Sitemap XML → Parse Sitemap XML

---

### NODE 4: Filter Pages
- **Type:** Code
- **Name:** `Filter Pages`
- **Code:** Скопіюй з `03_FILTER_PAGES.js`
- **Connection:** Parse Sitemap XML → Filter Pages

---

### NODE 5: Remove Empty Items
- **Type:** Filter
- **Name:** `Remove Empty Items`
- **Conditions:** Keep if `url` is not empty
- **Connection:** Filter Pages → Remove Empty Items

---

### NODE 6: Fetch Page Content
- **Type:** HTTP Request
- **Name:** `Fetch Page Content`
- **URL:** `={{ $json.url }}`
- **Headers:**
  - User-Agent: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36`
  - Accept: `text/html,application/xhtml+xml,application/xml;q=0.9`
  - Accept-Language: `en-US,en;q=0.9`
- **Follow Redirects:** true (max 5)
- **Never Error:** true
- **Connection:** Remove Empty Items → Fetch Page Content

---

### NODE 7: Parse Page Content
- **Type:** Code
- **Name:** `Parse Page Content`
- **Code:** Скопіюй з `05_PARSE_PAGE_CONTENT.js`
- **Connection:** Fetch Page Content → Parse Page Content

---

### NODE 8: Aggregate by Category
- **Type:** Code
- **Name:** `Aggregate by Category`
- **Code:** Скопіюй з `06_AGGREGATE_BY_CATEGORY.js`
- **Connection:** Parse Page Content → Aggregate by Category

---

## Потім підключи до AI Agent:

Aggregate by Category → Merge1 (замість Parse All Data1)

---

## Час додавання: 10 хвилин

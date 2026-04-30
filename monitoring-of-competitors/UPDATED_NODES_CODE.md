# Оновлений код для нод

## 1. Extract & Filter URLs

**Що змінено:** Додано російські/українські URL-паттерни для blog, news, reviews, pricing, features

```javascript
// Extract & Filter URLs - отримуємо companyName/companyUrl з Edit Fields
var scanResult = $input.item.json;
var allResults = scanResult.all_results || [];

// ВАЖЛИВО: Отримуємо companyName/companyUrl з Edit Fields напряму
var editFieldsData = $('Edit Fields').first().json;
var companyName = editFieldsData.companyName || 'Unknown';
var companyUrl = editFieldsData.companyUrl || '';

console.log('Extract URLs - Company:', companyName, 'URL:', companyUrl, 'Total URLs:', allResults.length);

// Розширені категорії з російськими/українськими варіантами
var categories = {
  blog: /\/(blog|blogs|article|articles|post|posts|insights|news-blog|novosti|stati|publikacii|statya|zapiski|blogi)/i,
  news: /\/(news|press|announcements|newsroom|novosti|press-centr|media|press-reliz|sobytiya|events)/i,
  reviews: /\/(review|reviews|testimonial|testimonials|customer-stories|success-stories|case-studies|otzyvy|klienty|istorii-uspeha|otzivi|vidguki|clients)/i,
  pricing: /\/(pricing|price|prices|plans|tarif|cost|tarify|ceny|stoimost|cena|prays|tseny|oplata)/i,
  features: /\/(features|feature|capabilities|product-features|funkcii|vozmozhnosti|resheniya|funktsii|mozhlivosti|solutions|products)/i
};

var categorizedUrls = [];

for (var i = 0; i < allResults.length; i++) {
  var result = allResults[i];
  var url = result.url || '';
  if (result.has_errors) continue;

  for (var cat in categories) {
    if (categories[cat].test(url)) {
      categorizedUrls.push({
        url: url,
        category: cat,
        status_code: result.status_code,
        companyName: companyName,
        companyUrl: companyUrl
      });
      break;
    }
  }
}

console.log('Filtered URLs by category:', categorizedUrls.length);

if (categorizedUrls.length === 0) {
  return [{ json: { url: '', category: 'none', status_code: 0, companyName: companyName, companyUrl: companyUrl } }];
}

return categorizedUrls.map(function(item) { return { json: item }; });
```

---

## 2. Parse Page Content

**Що змінено:** Додано більше паттернів для парсингу статей блогу, включаючи російські класи

```javascript
// Parse Page Content - V3 з розширеним парсингом
var inputItem = $input.item.json;
var html = inputItem.body || '';

var setFieldsData = $('Set Fields Before Fetch').item.json;
var companyName = setFieldsData.companyName || 'Unknown';
var companyUrl = setFieldsData.companyUrl || '';
var pageUrl = setFieldsData.pageUrl || '';
var category = setFieldsData.category || 'unknown';

// Список слів для фільтрації
var excludeWords = ['privacy', 'cookie', 'terms', 'conditions', 'legal', 'contact', 'about', 'login', 'policy', 'politic', 'privacidad', 'condiciones', 'aviso', 'calidad', 'seguridad', 'uso'];

function isValidArticleTitle(title) {
  if (!title) return false;
  title = title.trim().toLowerCase();
  if (title.length < 15 || title.length > 250) return false;
  for (var i = 0; i < excludeWords.length; i++) {
    if (title.indexOf(excludeWords[i]) === 0) return false;
  }
  return true;
}

function extractText(html, pattern) {
  var match = html.match(pattern);
  return match ? match[1].trim() : null;
}

function cleanText(text) {
  if (!text) return null;
  return text.replace(/&nbsp;/gi, ' ').replace(/&amp;/gi, '&').replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/&#\d+;/g, '').replace(/\s+/g, ' ').trim();
}

// Видалити header/nav/footer
var cleanHtml = html
  .replace(/<header[^>]*>[\s\S]*?<\/header>/gi, '')
  .replace(/<nav[^>]*>[\s\S]*?<\/nav>/gi, '')
  .replace(/<footer[^>]*>[\s\S]*?<\/footer>/gi, '')
  .replace(/<aside[^>]*>[\s\S]*?<\/aside>/gi, '')
  .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
  .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');

var title = extractText(html, /<title[^>]*>([^<]+)<\/title>/i);
var description = extractText(html, /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i);
var h1Matches = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/gi) || [];
var h1Tags = h1Matches.map(function(h) { return h.replace(/<[^>]+>/g, '').trim(); }).filter(function(t) { return t.length > 2 && t.length < 200; }).slice(0, 5);

var categoryData = {};

if (category === 'blog' || category === 'news') {
  var articles = [];
  var seen = new Set();

  // Розширені паттерни для статей (включаючи російські класи)
  var patterns = [
    /<article[^>]*>([\s\S]*?)<\/article>/gi,
    /<div[^>]*class=["'][^"']*(?:post|entry|blog-item|news-item|article-card|card|item|novost|statya|publikaciya)[^"']*["'][^>]*>([\s\S]*?)<\/div>/gi,
    /<li[^>]*class=["'][^"']*(?:post|article|news|blog)[^"']*["'][^>]*>([\s\S]*?)<\/li>/gi
  ];

  for (var p = 0; p < patterns.length && articles.length < 15; p++) {
    var match;
    patterns[p].lastIndex = 0;
    while ((match = patterns[p].exec(cleanHtml)) !== null && articles.length < 15) {
      var content = match[1] || match[0];

      // Шукаємо заголовок в h1-h4 або в посиланнях
      var titleMatch = content.match(/<h[1-4][^>]*>([\s\S]*?)<\/h[1-4]>/i) ||
                       content.match(/<a[^>]*>([^<]{15,200})<\/a>/i);
      var dateMatch = content.match(/<time[^>]*datetime=["']([^"']+)["']/i) ||
                      content.match(/(\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{2,4})/);
      var t = titleMatch ? cleanText(titleMatch[1].replace(/<[^>]+>/g, '')) : null;

      if (isValidArticleTitle(t) && !seen.has(t.toLowerCase())) {
        seen.add(t.toLowerCase());
        articles.push({
          title: t,
          date: dateMatch ? (dateMatch[1] || dateMatch[0]) : null,
          preview: cleanText(content.replace(/<[^>]+>/g, ' ')).substring(0, 300)
        });
      }
    }
  }

  // Fallback: всі h2/h3 заголовки як потенційні статті
  if (articles.length === 0) {
    var headerRegex = /<h[2-3][^>]*>([\s\S]*?)<\/h[2-3]>/gi;
    var hMatch;
    while ((hMatch = headerRegex.exec(cleanHtml)) !== null && articles.length < 15) {
      var t = cleanText(hMatch[1].replace(/<[^>]+>/g, ''));
      if (isValidArticleTitle(t) && !seen.has(t.toLowerCase())) {
        seen.add(t.toLowerCase());
        articles.push({ title: t, date: null, preview: '' });
      }
    }
  }

  // Fallback: посилання на статті
  if (articles.length === 0) {
    var linkRegex = /<a[^>]*href=["']([^"']*\/(?:blog|news|stati|novosti|article)[^"']*)["'][^>]*>([^<]{15,200})<\/a>/gi;
    var lMatch;
    while ((lMatch = linkRegex.exec(cleanHtml)) !== null && articles.length < 15) {
      var t = cleanText(lMatch[2]);
      if (isValidArticleTitle(t) && !seen.has(t.toLowerCase())) {
        seen.add(t.toLowerCase());
        articles.push({ title: t, date: null, preview: '', url: lMatch[1] });
      }
    }
  }

  categoryData.articles = articles;
  categoryData.totalArticles = articles.length;
} else if (category === 'reviews') {
  var reviewMatches = html.match(/<div[^>]*class=["'][^"']*(?:review|testimonial|otzyv|otziv)[^"']*["'][^>]*>[\s\S]{1,3000}?<\/div>/gi) || [];
  categoryData.reviews = reviewMatches.slice(0, 10).map(function(review) {
    return { text: review.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().substring(0, 500), rating: null, author: null };
  });
  categoryData.totalReviews = reviewMatches.length;
} else if (category === 'pricing') {
  var priceMatches = html.match(/[\$\u20AC\u00A3\u20BD]?\s*\d+(?:[.,]\d{2,3})?(?:\s*(?:USD|EUR|GBP|RUB|руб|грн|\$|€|₽|₴))?/gi) || [];
  categoryData.prices = priceMatches.slice(0, 20);
  categoryData.hasPricing = priceMatches.length > 0;

  // Шукаємо тарифні плани
  var planMatches = html.match(/<div[^>]*class=["'][^"']*(?:plan|tariff|price-card|pricing-card)[^"']*["'][^>]*>[\s\S]{1,5000}?<\/div>/gi) || [];
  categoryData.plans = planMatches.length;
} else if (category === 'features') {
  var featureLists = html.match(/<ul[^>]*>[\s\S]{1,5000}?<\/ul>/gi) || [];
  var features = [];
  for (var j = 0; j < featureLists.length; j++) {
    var items = featureLists[j].match(/<li[^>]*>([^<]+)<\/li>/gi) || [];
    for (var k = 0; k < items.length; k++) {
      var text = items[k].replace(/<[^>]+>/g, '').trim();
      if (text.length > 10 && text.length < 200) features.push(text);
    }
  }
  categoryData.features = features.slice(0, 50);
}

return {
  url: pageUrl,
  category: category,
  companyName: companyName,
  companyUrl: companyUrl,
  metadata: { title: title, description: description, h1Tags: h1Tags },
  content: categoryData,
  parsedAt: new Date().toISOString()
};
```

---

## Як оновити в n8n:

1. Відкрийте воркфлоу: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7

2. **Extract & Filter URLs:**
   - Клікніть на ноду
   - Замініть весь код на код вище

3. **Parse Page Content:**
   - Клікніть на ноду
   - Замініть весь код на код вище

4. Збережіть (Ctrl+S)

5. Запустіть тест

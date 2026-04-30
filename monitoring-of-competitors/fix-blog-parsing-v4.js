const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs';

async function fix() {
  console.log('Fetching workflow...');
  const res = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    headers: { 'X-N8N-API-KEY': apiKey }
  });
  const workflow = await res.json();
  console.log('Workflow:', workflow.name);

  // Новий код для Parse All Data - V4 з фільтрацією меню/footer
  const parseAllDataCode = `// Parse All Data - V4 з фільтрацією меню/footer
var loopData = $('Loop Companies').item.json;
var editFieldsData = $('Edit Fields1').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';
var url = editFieldsData.companyUrl || loopData.companyUrl || '';

var mergeItems = $input.all();
var websiteHtml = mergeItems[0] && mergeItems[0].json ? (mergeItems[0].json.body || mergeItems[0].json.data || '') : '';
var blogHtml = mergeItems[1] && mergeItems[1].json ? (mergeItems[1].json.body || mergeItems[1].json.data || '') : '';
var reviewsHtml = mergeItems[2] && mergeItems[2].json ? (mergeItems[2].json.body || mergeItems[2].json.data || '') : '';

function cleanText(text) {
  if (!text) return null;
  return text.replace(/&nbsp;/gi, ' ').replace(/&#\\d+;/g, ' ').replace(/\\s+/g, ' ').trim();
}

// Список слів для фільтрації (меню, footer, legal pages)
var excludeWords = ['privacy', 'cookie', 'terms', 'conditions', 'legal', 'contact', 'about', 'login', 'sign', 'register', 'policy', 'politic', 'privacidad', 'condiciones', 'aviso', 'imprint', 'impressum', 'datenschutz', 'copyright', 'home', 'inicio', 'accueil', 'главная', 'контакты', 'о нас', 'calidad', 'seguridad', 'uso'];

function isValidArticleTitle(title) {
  if (!title) return false;
  title = title.trim().toLowerCase();
  // Мінімум 25 символів (короткі - це меню)
  if (title.length < 25 || title.length > 200) return false;
  // Виключити типові сторінки
  for (var i = 0; i < excludeWords.length; i++) {
    if (title.indexOf(excludeWords[i]) === 0) return false;
  }
  return true;
}

function extractTitle(html) {
  if (!html || html.length < 100) return null;
  var patterns = [
    /<title[^>]*>([\\s\\S]*?)<\\/title>/i,
    /<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i
  ];
  for (var i = 0; i < patterns.length; i++) {
    var match = html.match(patterns[i]);
    if (match && match[1]) {
      var title = cleanText(match[1]);
      if (title && title.length > 2) return title.substring(0, 200);
    }
  }
  return null;
}

function extractDescription(html) {
  if (!html || html.length < 100) return null;
  var patterns = [
    /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i,
    /<meta[^>]*property=["']og:description["'][^>]*content=["']([^"']+)["']/i
  ];
  for (var i = 0; i < patterns.length; i++) {
    var match = html.match(patterns[i]);
    if (match && match[1]) {
      var desc = cleanText(match[1]);
      if (desc && desc.length > 10) return desc.substring(0, 500);
    }
  }
  return null;
}

function extractH1Tags(html) {
  if (!html || html.length < 100) return [];
  var matches = [];
  var h1Regex = /<h1[^>]*>([\\s\\S]*?)<\\/h1>/gi;
  var match;
  while ((match = h1Regex.exec(html)) !== null && matches.length < 5) {
    var text = cleanText(match[1].replace(/<[^>]+>/g, ''));
    if (text && text.length > 2 && text.length < 200) matches.push(text);
  }
  return matches;
}

function extractKeywords(html) {
  if (!html) return [];
  var match = html.match(/<meta[^>]*name=["']keywords["'][^>]*content=["']([^"']+)["']/i);
  return match ? match[1].split(',').map(function(k) { return k.trim(); }).filter(function(k) { return k; }).slice(0, 10) : [];
}

function findBlogLinks(html) {
  var links = [];
  var linkRegex = /href=["']([^"']*\\/blog\\/[^"']+)["']/gi;
  var match;
  while ((match = linkRegex.exec(html)) !== null && links.length < 10) {
    var href = match[1];
    // Тільки посилання на статті (з датою або довгим slug)
    if (href && href.length > 30 && /\\/\\d{4}\\/|[a-z0-9-]{15,}/.test(href)) {
      links.push(href);
    }
  }
  return [...new Set(links)];
}

var website = {
  title: extractTitle(websiteHtml),
  description: extractDescription(websiteHtml),
  h1Tags: extractH1Tags(websiteHtml),
  keywords: extractKeywords(websiteHtml),
  blogLinks: findBlogLinks(websiteHtml),
  hasNews: /news|новини|новости|press|пресс/i.test(websiteHtml),
  hasBlog: /blog|блог|journal|журнал|articles|статьи/i.test(websiteHtml),
  hasPricing: /pricing|price|ціни|цены|тарифи|тарифы|стоимость/i.test(websiteHtml),
  hasFeatures: /features|можливості|возможности|функції|функции|solutions|решения/i.test(websiteHtml),
  htmlLength: websiteHtml.length
};

// Парсинг статей з фільтрацією header/nav/footer
function extractArticles(html) {
  if (!html || html.length < 500) return [];
  var articles = [];
  var seen = new Set();

  // Видалити header, nav, footer, aside
  var cleanHtml = html
    .replace(/<header[^>]*>[\\s\\S]*?<\\/header>/gi, '')
    .replace(/<nav[^>]*>[\\s\\S]*?<\\/nav>/gi, '')
    .replace(/<footer[^>]*>[\\s\\S]*?<\\/footer>/gi, '')
    .replace(/<aside[^>]*>[\\s\\S]*?<\\/aside>/gi, '');

  // Патерни для статей
  var patterns = [
    /<article[^>]*>([\\s\\S]*?)<\\/article>/gi,
    /<div[^>]*class=["'][^"']*(?:post-item|blog-post|news-item|entry-content|article-card|blog-card)[^"']*["'][^>]*>([\\s\\S]*?)<\\/div>/gi
  ];

  for (var p = 0; p < patterns.length && articles.length < 5; p++) {
    var match;
    patterns[p].lastIndex = 0;
    while ((match = patterns[p].exec(cleanHtml)) !== null && articles.length < 5) {
      var content = match[1] || match[0];

      var titleMatch = content.match(/<h[2-4][^>]*>([\\s\\S]*?)<\\/h[2-4]>/i) ||
                       content.match(/<a[^>]*class=["'][^"']*title[^"']*["'][^>]*>([^<]+)<\\/a>/i) ||
                       content.match(/<a[^>]*href=["'][^"']*\\/blog\\/[^"']*["'][^>]*>([^<]{25,150})<\\/a>/i);

      var dateMatch = content.match(/<time[^>]*datetime=["']([^"']+)["']/i) ||
                      content.match(/<time[^>]*>([^<]+)<\\/time>/i) ||
                      content.match(/(\\d{1,2}[\\.\\/\\-]\\d{1,2}[\\.\\/\\-]\\d{2,4})/);

      var title = titleMatch ? cleanText(titleMatch[1].replace(/<[^>]+>/g, '')) : null;

      if (isValidArticleTitle(title) && !seen.has(title.toLowerCase())) {
        seen.add(title.toLowerCase());
        articles.push({
          title: title,
          date: dateMatch ? cleanText(dateMatch[1]) : null,
          preview: cleanText(content.replace(/<[^>]+>/g, ' ')).substring(0, 200)
        });
      }
    }
  }

  // Fallback: шукати посилання на статті
  if (articles.length === 0) {
    var linkRegex = /<a[^>]*href=["']([^"']*\\/(?:blog|news|article)\\/[^"']*)["'][^>]*>([^<]{25,150})<\\/a>/gi;
    var lMatch;
    while ((lMatch = linkRegex.exec(cleanHtml)) !== null && articles.length < 5) {
      var title = cleanText(lMatch[2]);
      if (isValidArticleTitle(title) && !seen.has(title.toLowerCase())) {
        seen.add(title.toLowerCase());
        articles.push({ title: title, date: null, preview: '', url: lMatch[1] });
      }
    }
  }

  return articles;
}

var blogArticles = extractArticles(blogHtml);
if (blogArticles.length === 0) {
  blogArticles = extractArticles(websiteHtml);
}

var blog = {
  articlesFound: blogArticles.length,
  recentArticles: blogArticles
};

// Парсинг відгуків
function extractReviews(html) {
  if (!html || html.length < 500) return [];
  var reviews = [];
  var patterns = [
    /<div[^>]*class=["'][^"']*(?:review|testimonial|отзыв|feedback|quote)[^"']*["'][^>]*>([\\s\\S]*?)<\\/div>/gi,
    /<blockquote[^>]*>([\\s\\S]*?)<\\/blockquote>/gi
  ];
  for (var rp = 0; rp < patterns.length && reviews.length < 3; rp++) {
    var rm;
    patterns[rp].lastIndex = 0;
    while ((rm = patterns[rp].exec(html)) !== null && reviews.length < 3) {
      var text = cleanText((rm[1] || rm[0]).replace(/<[^>]+>/g, ' '));
      if (text && text.length > 50 && text.length < 500) reviews.push(text.substring(0, 200));
    }
  }
  return reviews;
}

var reviewSamples = extractReviews(reviewsHtml);
if (reviewSamples.length === 0) reviewSamples = extractReviews(websiteHtml);

var reviews = {
  found: reviewSamples.length > 0,
  count: reviewSamples.length,
  samples: reviewSamples
};

return {
  company: company,
  url: url,
  currentData: {
    website: website,
    blog: blog,
    reviews: reviews,
    scrapedAt: new Date().toISOString()
  },
  previousData: null,
  _debug: {
    websiteHtmlLength: websiteHtml.length,
    blogHtmlLength: blogHtml.length,
    reviewsHtmlLength: reviewsHtml.length,
    blogLinksFound: website.blogLinks
  }
};`;

  // Оновити Parse All Data
  const parseAllDataIndex = workflow.nodes.findIndex(n => n.name === 'Parse All Data');
  if (parseAllDataIndex !== -1) {
    workflow.nodes[parseAllDataIndex].parameters.jsCode = parseAllDataCode;
    console.log('✓ Parse All Data updated to V4');
  }

  // Новий код для Parse Page Content1 - V2
  const parsePageCode = `// Parse Page Content1 - V2 з фільтрацією
var inputItem = $input.item.json;
var html = inputItem.body || '';

var setFieldsData = $('Set Fields Before Fetch1').item.json;
var companyName = setFieldsData.companyName || 'Unknown';
var companyUrl = setFieldsData.companyUrl || '';
var pageUrl = setFieldsData.pageUrl || '';
var category = setFieldsData.category || 'unknown';

// Список слів для фільтрації
var excludeWords = ['privacy', 'cookie', 'terms', 'conditions', 'legal', 'contact', 'about', 'login', 'policy', 'politic', 'privacidad', 'condiciones', 'aviso', 'calidad', 'seguridad', 'uso'];

function isValidArticleTitle(title) {
  if (!title) return false;
  title = title.trim().toLowerCase();
  if (title.length < 25 || title.length > 200) return false;
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
  return text.replace(/&nbsp;/gi, ' ').replace(/\\s+/g, ' ').trim();
}

// Видалити header/nav/footer
var cleanHtml = html
  .replace(/<header[^>]*>[\\s\\S]*?<\\/header>/gi, '')
  .replace(/<nav[^>]*>[\\s\\S]*?<\\/nav>/gi, '')
  .replace(/<footer[^>]*>[\\s\\S]*?<\\/footer>/gi, '')
  .replace(/<aside[^>]*>[\\s\\S]*?<\\/aside>/gi, '');

var title = extractText(html, /<title[^>]*>([^<]+)<\\/title>/i);
var description = extractText(html, /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i);
var h1Matches = html.match(/<h1[^>]*>([\\s\\S]*?)<\\/h1>/gi) || [];
var h1Tags = h1Matches.map(function(h) { return h.replace(/<[^>]+>/g, '').trim(); }).filter(function(t) { return t.length > 2 && t.length < 200; }).slice(0, 5);

var categoryData = {};

if (category === 'blog' || category === 'news') {
  var articles = [];
  var seen = new Set();

  var patterns = [
    /<article[^>]*>([\\s\\S]*?)<\\/article>/gi,
    /<div[^>]*class=["'][^"']*(?:post|entry|blog-item|news-item|article-card)[^"']*["'][^>]*>([\\s\\S]*?)<\\/div>/gi
  ];

  for (var p = 0; p < patterns.length && articles.length < 10; p++) {
    var match;
    patterns[p].lastIndex = 0;
    while ((match = patterns[p].exec(cleanHtml)) !== null && articles.length < 10) {
      var content = match[1] || match[0];
      var titleMatch = content.match(/<h[2-4][^>]*>([\\s\\S]*?)<\\/h[2-4]>/i) ||
                       content.match(/<a[^>]*href=["'][^"']*\\/blog\\/[^"']*["'][^>]*>([^<]{25,150})<\\/a>/i);
      var dateMatch = content.match(/<time[^>]*datetime=["']([^"']+)["']/i);
      var t = titleMatch ? cleanText(titleMatch[1].replace(/<[^>]+>/g, '')) : null;

      if (isValidArticleTitle(t) && !seen.has(t.toLowerCase())) {
        seen.add(t.toLowerCase());
        articles.push({
          title: t,
          date: dateMatch ? dateMatch[1] : null,
          preview: cleanText(content.replace(/<[^>]+>/g, ' ')).substring(0, 300)
        });
      }
    }
  }

  // Fallback: посилання на статті
  if (articles.length === 0) {
    var linkRegex = /<a[^>]*href=["']([^"']*\\/(?:blog|news)\\/[^"']*)["'][^>]*>([^<]{25,150})<\\/a>/gi;
    var lMatch;
    while ((lMatch = linkRegex.exec(cleanHtml)) !== null && articles.length < 10) {
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
  var reviewMatches = html.match(/<div[^>]*class=["'][^"']*review[^"']*["'][^>]*>[\\s\\S]{1,3000}?<\\/div>/gi) || [];
  categoryData.reviews = reviewMatches.slice(0, 10).map(function(review) {
    return { text: review.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim().substring(0, 500), rating: null, author: null };
  });
  categoryData.totalReviews = reviewMatches.length;
} else if (category === 'pricing') {
  var priceMatches = html.match(/[\\$\\u20AC\\u00A3]\\s*\\d+(?:[.,]\\d{2})?|\\d+(?:[.,]\\d{2})?\\s*(?:USD|EUR|GBP)/gi) || [];
  categoryData.prices = priceMatches.slice(0, 20);
  categoryData.hasPricing = priceMatches.length > 0;
} else if (category === 'features') {
  var featureLists = html.match(/<ul[^>]*>[\\s\\S]{1,5000}?<\\/ul>/gi) || [];
  var features = [];
  for (var j = 0; j < featureLists.length; j++) {
    var items = featureLists[j].match(/<li[^>]*>([^<]+)<\\/li>/gi) || [];
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
};`;

  // Оновити Parse Page Content1
  const parsePageIndex = workflow.nodes.findIndex(n => n.name === 'Parse Page Content1');
  if (parsePageIndex !== -1) {
    workflow.nodes[parsePageIndex].parameters.jsCode = parsePageCode;
    console.log('✓ Parse Page Content1 updated to V2');
  }

  // Зберегти
  const cleanWorkflow = {
    name: workflow.name,
    nodes: workflow.nodes,
    connections: workflow.connections,
    settings: { executionOrder: workflow.settings?.executionOrder }
  };

  const putRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    method: 'PUT',
    headers: { 'X-N8N-API-KEY': apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify(cleanWorkflow)
  });

  if (putRes.ok) {
    console.log('✓ Workflow saved successfully!');
  } else {
    console.log('ERROR:', await putRes.text());
  }
}

fix().catch(e => console.error('Error:', e.message));


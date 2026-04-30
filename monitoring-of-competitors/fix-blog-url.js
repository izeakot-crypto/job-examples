const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs';

async function fixBlogUrl() {
  console.log('=== FIXING BLOG URL DETECTION ===\n');

  const getRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    headers: { 'X-N8N-API-KEY': apiKey }
  });
  const workflow = await getRes.json();
  console.log('Workflow fetched:', workflow.name);

  // Створити нову ноду "Detect Blog URL" перед Fetch Blog
  // Або краще - змінити Fetch Blog щоб спробувати різні шляхи

  // FIX: Parse All Data - витягувати статті з головної сторінки якщо блог порожній
  // + шукати посилання на блог/журнал
  const parseAllDataIndex = workflow.nodes.findIndex(n => n.name === 'Parse All Data');
  if (parseAllDataIndex !== -1) {
    workflow.nodes[parseAllDataIndex].parameters.jsCode = `// Parse All Data - V3 with better blog detection
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
  if (matches.length === 0) {
    var h2Regex = /<h2[^>]*>([\\s\\S]*?)<\\/h2>/gi;
    while ((match = h2Regex.exec(html)) !== null && matches.length < 3) {
      var text = cleanText(match[1].replace(/<[^>]+>/g, ''));
      if (text && text.length > 5 && text.length < 150) matches.push(text);
    }
  }
  return matches;
}

function extractKeywords(html) {
  if (!html) return [];
  var match = html.match(/<meta[^>]*name=["']keywords["'][^>]*content=["']([^"']+)["']/i);
  return match ? match[1].split(',').map(k => k.trim()).filter(k => k).slice(0, 10) : [];
}

// ПОКРАЩЕНО: Знайти посилання на блог/журнал
function findBlogLinks(html) {
  var blogPatterns = [
    /href=["']([^"']*(?:\\/blog|\\/journal|\\/news|\\/articles|\\/press|\\/media)[^"']*)["']/gi,
    /href=["']([^"']*(?:blog|journal|news|articles|press|novosti|statyi)[^"']*)["']/gi
  ];
  var links = [];
  for (var p = 0; p < blogPatterns.length; p++) {
    var match;
    blogPatterns[p].lastIndex = 0;
    while ((match = blogPatterns[p].exec(html)) !== null && links.length < 5) {
      if (match[1] && match[1].length < 100) links.push(match[1]);
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

// ПОКРАЩЕНО: Парсинг статей - більше патернів
function extractArticles(html) {
  if (!html || html.length < 500) return [];
  var articles = [];
  var seen = new Set();

  // Патерни для різних CMS та структур
  var patterns = [
    // Standard article
    /<article[^>]*>([\\s\\S]*?)<\\/article>/gi,
    // Div з класами post/entry/news/article
    /<div[^>]*class="[^"]*(?:post|entry|article|news-item|blog-item|journal-item)[^"]*"[^>]*>([\\s\\S]*?)<\\/div>(?=\\s*<div[^>]*class="[^"]*(?:post|entry)|\\s*<\\/|\\s*$)/gi,
    // Card layouts
    /<div[^>]*class="[^"]*card[^"]*"[^>]*>([\\s\\S]*?)<\\/div>(?=\\s*<div[^>]*class="[^"]*card|\\s*<\\/)/gi,
    // List items
    /<li[^>]*class="[^"]*(?:post|news|article|item)[^"]*"[^>]*>([\\s\\S]*?)<\\/li>/gi,
    // Links with titles (fallback)
    /<a[^>]*href="[^"]*(?:blog|journal|news|article)[^"]*"[^>]*>([^<]{15,100})<\\/a>/gi
  ];

  for (var p = 0; p < patterns.length && articles.length < 5; p++) {
    var match;
    patterns[p].lastIndex = 0;
    while ((match = patterns[p].exec(html)) !== null && articles.length < 5) {
      var content = match[1] || match[0];

      // Знайти заголовок (різні варіанти)
      var titleMatch = content.match(/<h[1-4][^>]*>([\\s\\S]*?)<\\/h[1-4]>/i) ||
                       content.match(/<a[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)<\\/a>/i) ||
                       content.match(/<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)<\\/span>/i) ||
                       content.match(/<a[^>]*href="[^"]*"[^>]*>([^<]{15,100})<\\/a>/i);

      var dateMatch = content.match(/<time[^>]*datetime=["']([^"']+)["']/i) ||
                      content.match(/<time[^>]*>([^<]+)<\\/time>/i) ||
                      content.match(/<span[^>]*class="[^"]*date[^"]*"[^>]*>([^<]+)<\\/span>/i) ||
                      content.match(/(\\d{1,2}[\\.\\/\\-]\\d{1,2}[\\.\\/\\-]\\d{2,4})/);

      var title = titleMatch ? cleanText(titleMatch[1].replace(/<[^>]+>/g, '')) : null;

      if (title && title.length > 10 && title.length < 200 && !seen.has(title)) {
        seen.add(title);
        articles.push({
          title: title,
          date: dateMatch ? cleanText(dateMatch[1]) : null,
          preview: cleanText(content.replace(/<[^>]+>/g, ' ')).substring(0, 200)
        });
      }
    }
  }

  // Якщо нічого не знайдено - спробувати витягнути всі h3/h4 як заголовки статей
  if (articles.length === 0) {
    var hRegex = /<h[3-4][^>]*>\\s*<a[^>]*>([^<]+)<\\/a>\\s*<\\/h[3-4]>/gi;
    var hMatch;
    while ((hMatch = hRegex.exec(html)) !== null && articles.length < 5) {
      var title = cleanText(hMatch[1]);
      if (title && title.length > 10 && !seen.has(title)) {
        seen.add(title);
        articles.push({ title: title, date: null, preview: '' });
      }
    }
  }

  return articles;
}

// Спробувати парсити блог, якщо порожній - головну сторінку
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
    /<div[^>]*class="[^"]*(?:review|testimonial|отзыв|feedback|quote)[^"]*"[^>]*>([\\s\\S]*?)<\\/div>/gi,
    /<blockquote[^>]*>([\\s\\S]*?)<\\/blockquote>/gi
  ];
  for (var rp = 0; rp < patterns.length && reviews.length < 3; rp++) {
    var rm;
    patterns[rp].lastIndex = 0;
    while ((rm = patterns[rp].exec(html)) !== null && reviews.length < 3) {
      var text = cleanText((rm[1] || rm[0]).replace(/<[^>]+>/g, ' '));
      if (text && text.length > 20 && text.length < 500) reviews.push(text.substring(0, 200));
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
    console.log('✓ Parse All Data updated - V3 with better article detection');
  }

  // ВАЖЛИВО: Змінити Fetch Blog щоб пробувати різні шляхи
  // Створимо Code ноду перед Fetch Blog для визначення правильного URL
  // Або простіше - змінити URL в Fetch Blog на головну сторінку і парсити статті звідти

  // Save
  console.log('\nSaving workflow...');
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
    console.log('✓ SUCCESS! Workflow saved.');
  } else {
    console.log('✗ ERROR:', await putRes.text());
  }
}

fixBlogUrl().catch(e => console.error('Error:', e.message));


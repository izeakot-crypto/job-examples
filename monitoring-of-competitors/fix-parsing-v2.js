const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs';

async function fixParsing() {
  console.log('=== FIXING PARSING V2 ===\n');

  const getRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    headers: { 'X-N8N-API-KEY': apiKey }
  });
  const workflow = await getRes.json();
  console.log('Workflow fetched:', workflow.name);

  // FIX: Parse All Data - покращений парсинг
  const parseAllDataIndex = workflow.nodes.findIndex(n => n.name === 'Parse All Data');
  if (parseAllDataIndex !== -1) {
    workflow.nodes[parseAllDataIndex].parameters.jsCode = `// Parse All Data - V2 FIXED
var loopData = $('Loop Companies').item.json;
// ВАЖЛИВО: Беремо companyName з Edit Fields1, не з Loop Companies
var editFieldsData = $('Edit Fields1').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';
var url = editFieldsData.companyUrl || loopData.companyUrl || '';

var mergeItems = $input.all();
var websiteHtml = mergeItems[0] && mergeItems[0].json ? (mergeItems[0].json.body || mergeItems[0].json.data || '') : '';
var blogHtml = mergeItems[1] && mergeItems[1].json ? (mergeItems[1].json.body || mergeItems[1].json.data || '') : '';
var reviewsHtml = mergeItems[2] && mergeItems[2].json ? (mergeItems[2].json.body || mergeItems[2].json.data || '') : '';

// Очистка HTML від &nbsp; та зайвих пробілів
function cleanText(text) {
  if (!text) return null;
  return text.replace(/&nbsp;/gi, ' ').replace(/\\s+/g, ' ').trim();
}

// Покращені функції парсингу
function extractTitle(html) {
  if (!html || html.length < 100) return null;
  var patterns = [
    /<title[^>]*>([\\s\\S]*?)<\\/title>/i,
    /<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i,
    /<meta[^>]*content=["']([^"']+)["'][^>]*property=["']og:title["']/i
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
    /<meta[^>]*content=["']([^"']+)["'][^>]*name=["']description["']/i,
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
  // Покращений regex для h1 - включає вкладені теги
  var matches = [];
  var h1Regex = /<h1[^>]*>([\\s\\S]*?)<\\/h1>/gi;
  var match;
  while ((match = h1Regex.exec(html)) !== null && matches.length < 5) {
    // Видалити всі HTML теги з середини h1
    var text = match[1].replace(/<[^>]+>/g, '');
    text = cleanText(text);
    if (text && text.length > 2 && text.length < 200) {
      matches.push(text);
    }
  }

  // Якщо h1 не знайдено, спробувати h2
  if (matches.length === 0) {
    var h2Regex = /<h2[^>]*>([\\s\\S]*?)<\\/h2>/gi;
    while ((match = h2Regex.exec(html)) !== null && matches.length < 3) {
      var text = match[1].replace(/<[^>]+>/g, '');
      text = cleanText(text);
      if (text && text.length > 5 && text.length < 150) {
        matches.push(text);
      }
    }
  }
  return matches;
}

function extractKeywords(html) {
  if (!html) return [];
  var match = html.match(/<meta[^>]*name=["']keywords["'][^>]*content=["']([^"']+)["']/i);
  if (match && match[1]) {
    return match[1].split(',').map(function(k) { return k.trim(); }).filter(function(k) { return k.length > 0; }).slice(0, 10);
  }
  return [];
}

var website = {
  title: extractTitle(websiteHtml),
  description: extractDescription(websiteHtml),
  h1Tags: extractH1Tags(websiteHtml),
  keywords: extractKeywords(websiteHtml),
  hasNews: /news|новини|новости|press|пресс/i.test(websiteHtml),
  hasBlog: /blog|блог|articles|статьи|journal/i.test(websiteHtml),
  hasPricing: /pricing|price|ціни|цены|тарифи|тарифы|стоимость/i.test(websiteHtml),
  hasFeatures: /features|можливості|возможности|функції|функции|solutions|решения/i.test(websiteHtml),
  htmlLength: websiteHtml.length
};

// Парсинг блогу - покращені селектори
function extractArticles(html) {
  if (!html || html.length < 500) return [];
  var articles = [];

  // Різні патерни для статей
  var patterns = [
    /<article[^>]*>([\\s\\S]*?)<\\/article>/gi,
    /<div[^>]*class="[^"]*(?:post|entry|article|news-item|blog-item)[^"]*"[^>]*>([\\s\\S]*?)<\\/div>(?=\\s*<div|\\s*<\\/|\\s*$)/gi,
    /<a[^>]*class="[^"]*(?:post|article|news)[^"]*"[^>]*>([\\s\\S]*?)<\\/a>/gi,
    /<li[^>]*class="[^"]*(?:post|news|article)[^"]*"[^>]*>([\\s\\S]*?)<\\/li>/gi
  ];

  for (var p = 0; p < patterns.length && articles.length < 5; p++) {
    var match;
    patterns[p].lastIndex = 0;
    while ((match = patterns[p].exec(html)) !== null && articles.length < 5) {
      var content = match[1] || match[0];

      // Знайти заголовок
      var titleMatch = content.match(/<h[1-4][^>]*>([\\s\\S]*?)<\\/h[1-4]>/i) ||
                       content.match(/<a[^>]*>([^<]{10,100})<\\/a>/i) ||
                       content.match(/<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)<\\/span>/i);

      var dateMatch = content.match(/<time[^>]*datetime=["']([^"']+)["']/i) ||
                      content.match(/<time[^>]*>([^<]+)<\\/time>/i) ||
                      content.match(/(\\d{1,2}[\\.\\/\\-]\\d{1,2}[\\.\\/\\-]\\d{2,4})/);

      var title = titleMatch ? cleanText(titleMatch[1].replace(/<[^>]+>/g, '')) : null;

      if (title && title.length > 5 && title.length < 200) {
        // Перевірити чи не дублікат
        var isDuplicate = articles.some(function(a) { return a.title === title; });
        if (!isDuplicate) {
          articles.push({
            title: title,
            date: dateMatch ? dateMatch[1] : null,
            preview: cleanText(content.replace(/<[^>]+>/g, ' ')).substring(0, 200)
          });
        }
      }
    }
  }
  return articles;
}

var blogArticles = extractArticles(blogHtml);
if (blogArticles.length === 0 && websiteHtml.length > 1000) {
  // Спробувати знайти статті на головній
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
    /<div[^>]*class="[^"]*(?:review|testimonial|отзыв|feedback)[^"]*"[^>]*>([\\s\\S]*?)<\\/div>/gi,
    /<blockquote[^>]*>([\\s\\S]*?)<\\/blockquote>/gi,
    /<p[^>]*class="[^"]*(?:review|testimonial)[^"]*"[^>]*>([\\s\\S]*?)<\\/p>/gi
  ];

  for (var rp = 0; rp < patterns.length && reviews.length < 3; rp++) {
    var rm;
    patterns[rp].lastIndex = 0;
    while ((rm = patterns[rp].exec(html)) !== null && reviews.length < 3) {
      var text = cleanText((rm[1] || rm[0]).replace(/<[^>]+>/g, ' '));
      if (text && text.length > 20 && text.length < 500) {
        reviews.push(text.substring(0, 200));
      }
    }
  }
  return reviews;
}

var reviewSamples = extractReviews(reviewsHtml);
if (reviewSamples.length === 0) {
  reviewSamples = extractReviews(websiteHtml);
}

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
    reviewsHtmlLength: reviewsHtml.length
  }
};`;
    console.log('✓ Parse All Data updated - V2');
  }

  // FIX: Інші ноди які використовують company з Loop Companies
  const nodesToFix = ['Parse YouTube Data', 'Format Social Activity', 'Merge Aggregator Data1', 'Parse G2 Data1'];

  for (const nodeName of nodesToFix) {
    const nodeIndex = workflow.nodes.findIndex(n => n.name === nodeName);
    if (nodeIndex !== -1 && workflow.nodes[nodeIndex].parameters.jsCode) {
      // Замінити отримання company з Loop Companies на Edit Fields1
      let code = workflow.nodes[nodeIndex].parameters.jsCode;
      if (code.includes("$('Loop Companies')") && !code.includes("$('Edit Fields1')")) {
        code = code.replace(
          /var company = loopData\.companyName \|\| loopData\.name \|\| loopData\.company \|\| 'Unknown';/g,
          "var editFieldsData = $('Edit Fields1').item.json;\nvar company = editFieldsData.companyName || loopData.companyName || 'Unknown';"
        );
        workflow.nodes[nodeIndex].parameters.jsCode = code;
        console.log('✓ Fixed company reference in:', nodeName);
      }
    }
  }

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

fixParsing().catch(e => console.error('Error:', e.message));


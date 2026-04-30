const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs';

async function fixWorkflow() {
  console.log('=== FIXING WORKFLOW PARSING ===\n');

  // 1. Отримати workflow
  console.log('1. Fetching workflow...');
  const getRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    headers: { 'X-N8N-API-KEY': apiKey }
  });
  const workflow = await getRes.json();
  console.log('   Workflow:', workflow.name);
  console.log('   Nodes:', workflow.nodes.length);

  // === FIX 1: Edit Fields1 - витягнути назву з URL ===
  console.log('\n2. Fixing Edit Fields1...');
  const editFieldsIndex = workflow.nodes.findIndex(n => n.name === 'Edit Fields1');
  if (editFieldsIndex !== -1) {
    workflow.nodes[editFieldsIndex].parameters.assignments.assignments = [
      {
        id: "760d4b4d-ee9a-4787-a693-2c116b729075",
        name: "companyUrl",
        value: "={{ $json.company || $json.url || $json.URL || '' }}",
        type: "string"
      },
      {
        id: "company-name-001",
        name: "companyName",
        // Витягнути назву з URL: https://www.netelip.com → Netelip
        value: "={{ (() => { const url = $json.company || $json.url || $json.URL || ''; const match = url.match(/https?:\\/\\/(?:www\\.)?([^\\/\\.]+)/i); return match ? match[1].charAt(0).toUpperCase() + match[1].slice(1) : 'Unknown'; })() }}",
        type: "string"
      }
    ];
    console.log('   ✓ Edit Fields1 updated - will extract company name from URL');
  } else {
    console.log('   ✗ Edit Fields1 not found!');
  }

  // === FIX 2: Fetch Website - додати headers ===
  console.log('\n3. Fixing Fetch Website...');
  const fetchWebsiteIndex = workflow.nodes.findIndex(n => n.name === 'Fetch Website');
  if (fetchWebsiteIndex !== -1) {
    workflow.nodes[fetchWebsiteIndex].parameters.sendHeaders = true;
    workflow.nodes[fetchWebsiteIndex].parameters.headerParameters = {
      parameters: [
        { name: "User-Agent", value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" },
        { name: "Accept", value: "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8" },
        { name: "Accept-Language", value: "en-US,en;q=0.5" }
      ]
    };
    console.log('   ✓ Fetch Website updated - added User-Agent headers');
  }

  // === FIX 3: Fetch Blog - додати headers ===
  console.log('\n4. Fixing Fetch Blog...');
  const fetchBlogIndex = workflow.nodes.findIndex(n => n.name === 'Fetch Blog');
  if (fetchBlogIndex !== -1) {
    workflow.nodes[fetchBlogIndex].parameters.sendHeaders = true;
    workflow.nodes[fetchBlogIndex].parameters.headerParameters = {
      parameters: [
        { name: "User-Agent", value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" },
        { name: "Accept", value: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" }
      ]
    };
    console.log('   ✓ Fetch Blog updated - added headers');
  }

  // === FIX 4: Fetch Reviews - додати headers ===
  console.log('\n5. Fixing Fetch Reviews...');
  const fetchReviewsIndex = workflow.nodes.findIndex(n => n.name === 'Fetch Reviews');
  if (fetchReviewsIndex !== -1) {
    workflow.nodes[fetchReviewsIndex].parameters.sendHeaders = true;
    workflow.nodes[fetchReviewsIndex].parameters.headerParameters = {
      parameters: [
        { name: "User-Agent", value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" },
        { name: "Accept", value: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" }
      ]
    };
    console.log('   ✓ Fetch Reviews updated - added headers');
  }

  // === FIX 5: Parse All Data - покращений парсинг HTML ===
  console.log('\n6. Fixing Parse All Data...');
  const parseAllDataIndex = workflow.nodes.findIndex(n => n.name === 'Parse All Data');
  if (parseAllDataIndex !== -1) {
    workflow.nodes[parseAllDataIndex].parameters.jsCode = `var loopData = $('Loop Companies').item.json;
var company = loopData.companyName || loopData.name || loopData.company || 'Unknown';
var url = loopData.companyUrl || loopData.url || loopData.URL || '';

var mergeItems = $input.all();
var websiteHtml = mergeItems[0] && mergeItems[0].json ? (mergeItems[0].json.body || mergeItems[0].json.data || '') : '';
var blogHtml = mergeItems[1] && mergeItems[1].json ? (mergeItems[1].json.body || mergeItems[1].json.data || '') : '';
var reviewsHtml = mergeItems[2] && mergeItems[2].json ? (mergeItems[2].json.body || mergeItems[2].json.data || '') : '';

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
    if (match && match[1] && match[1].trim().length > 2) {
      return match[1].trim().replace(/\\s+/g, ' ').substring(0, 200);
    }
  }
  return null;
}

function extractDescription(html) {
  if (!html || html.length < 100) return null;
  var patterns = [
    /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i,
    /<meta[^>]*content=["']([^"']+)["'][^>]*name=["']description["']/i,
    /<meta[^>]*property=["']og:description["'][^>]*content=["']([^"']+)["']/i,
    /<meta[^>]*content=["']([^"']+)["'][^>]*property=["']og:description["']/i
  ];
  for (var i = 0; i < patterns.length; i++) {
    var match = html.match(patterns[i]);
    if (match && match[1] && match[1].trim().length > 10) {
      return match[1].trim().substring(0, 500);
    }
  }
  return null;
}

function extractH1Tags(html) {
  if (!html || html.length < 100) return [];
  var h1Regex = /<h1[^>]*>([\\s\\S]*?)<\\/h1>/gi;
  var matches = [];
  var match;
  while ((match = h1Regex.exec(html)) !== null && matches.length < 5) {
    var text = match[1].replace(/<[^>]+>/g, '').trim();
    if (text && text.length > 2 && text.length < 200) matches.push(text);
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
  hasNews: /news|новини|новости|press/i.test(websiteHtml),
  hasBlog: /blog|блог|articles|статьи/i.test(websiteHtml),
  hasPricing: /pricing|price|ціни|цены|тарифи|тарифы/i.test(websiteHtml),
  hasFeatures: /features|можливості|возможности|функції|функции|solutions/i.test(websiteHtml),
  htmlLength: websiteHtml.length
};

// Парсинг блогу
function extractArticles(html) {
  if (!html || html.length < 500) return [];
  var articles = [];
  var patterns = [
    /<article[^>]*>([\\s\\S]*?)<\\/article>/gi,
    /<div[^>]*class="[^"]*(?:post|entry|article)[^"]*"[^>]*>([\\s\\S]*?)<\\/div>/gi,
    /<li[^>]*class="[^"]*post[^"]*"[^>]*>([\\s\\S]*?)<\\/li>/gi
  ];

  for (var p = 0; p < patterns.length && articles.length < 5; p++) {
    var match;
    patterns[p].lastIndex = 0;
    while ((match = patterns[p].exec(html)) !== null && articles.length < 5) {
      var content = match[1] || match[0];
      var titleMatch = content.match(/<h[1-4][^>]*>([\\s\\S]*?)<\\/h[1-4]>/i);
      var dateMatch = content.match(/<time[^>]*datetime=["']([^"']+)["']/i) || content.match(/(\\d{4}-\\d{2}-\\d{2})/);
      var title = titleMatch ? titleMatch[1].replace(/<[^>]+>/g, '').trim() : null;
      if (title && title.length > 5 && title.length < 200) {
        articles.push({
          title: title,
          date: dateMatch ? dateMatch[1] : null,
          preview: content.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim().substring(0, 200)
        });
      }
    }
  }
  return articles;
}

var blogArticles = extractArticles(blogHtml);
if (blogArticles.length === 0 && websiteHtml.length > 1000) {
  blogArticles = extractArticles(websiteHtml);
}

var blog = {
  articlesFound: blogArticles.length,
  recentArticles: blogArticles
};

// Парсинг відгуків
var reviewPatterns = [
  /<div[^>]*class="[^"]*(?:review|testimonial)[^"]*"[^>]*>([\\s\\S]*?)<\\/div>/gi,
  /<blockquote[^>]*>([\\s\\S]*?)<\\/blockquote>/gi
];
var reviewSamples = [];
for (var rp = 0; rp < reviewPatterns.length && reviewSamples.length < 3; rp++) {
  var rm;
  reviewPatterns[rp].lastIndex = 0;
  while ((rm = reviewPatterns[rp].exec(reviewsHtml)) !== null && reviewSamples.length < 3) {
    var text = (rm[1] || rm[0]).replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();
    if (text.length > 20 && text.length < 500) reviewSamples.push(text.substring(0, 200));
  }
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
    console.log('   ✓ Parse All Data updated - improved HTML parsing');
  }

  // === FIX 6: Auto-detect Social Links ===
  console.log('\n7. Fixing Auto-detect Social Links...');
  const socialLinksIndex = workflow.nodes.findIndex(n => n.name === 'Auto-detect Social Links');
  if (socialLinksIndex !== -1) {
    workflow.nodes[socialLinksIndex].parameters.jsCode = `var websiteHtml = $('Fetch Website').item.json.body || $('Fetch Website').item.json.data || '';
var loopData = $('Loop Companies').item.json;
var company = loopData.companyName || loopData.name || loopData.company || 'Unknown';

function extractUrl(html, pattern) {
  var match = html.match(pattern);
  return match ? match[0] : null;
}

return {
  company: company,
  linkedin: extractUrl(websiteHtml, /linkedin\\.com\\/company\\/[a-zA-Z0-9_-]+/i),
  facebook: extractUrl(websiteHtml, /facebook\\.com\\/[a-zA-Z0-9._-]+/i),
  twitter: extractUrl(websiteHtml, /(?:twitter|x)\\.com\\/[a-zA-Z0-9_]+/i),
  instagram: extractUrl(websiteHtml, /instagram\\.com\\/[a-zA-Z0-9._]+/i),
  youtube: extractUrl(websiteHtml, /youtube\\.com\\/(?:channel|c|user|@)[\\/]?[a-zA-Z0-9_-]+/i)
};`;
    console.log('   ✓ Auto-detect Social Links updated - added x.com support');
  }

  // === SAVE WORKFLOW ===
  console.log('\n8. Saving workflow...');
  const cleanSettings = {
    executionOrder: workflow.settings?.executionOrder
  };

  const cleanWorkflow = {
    name: workflow.name,
    nodes: workflow.nodes,
    connections: workflow.connections,
    settings: cleanSettings
  };

  const putRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    method: 'PUT',
    headers: {
      'X-N8N-API-KEY': apiKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(cleanWorkflow)
  });

  if (putRes.ok) {
    const result = await putRes.json();
    console.log('   ✓ SUCCESS! Workflow saved.');
    console.log('   New versionId:', result.versionId);
  } else {
    const errorText = await putRes.text();
    console.log('   ✗ ERROR:', errorText);
  }

  console.log('\n=== DONE ===');
  console.log('Now run the workflow manually to test!');
}

fixWorkflow().catch(e => console.error('Error:', e.message));


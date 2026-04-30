// Parse all data sources - ULTIMATE VERSION
const loopData = $('Loop Companies1').item.json;

// ============================================
// КРОК 1: Витягуємо company та URL з Google Sheets
// ============================================

console.log('🔍 Loop data available fields:', Object.keys(loopData));
console.log('📋 Full loop data:', JSON.stringify(loopData));

// Спробуємо всі можливі варіанти назв колонок
let company = loopData.company || loopData.name || loopData.Company || loopData.Name ||
              loopData['Компанія'] || loopData['Назва'] || loopData['название'] ||
              loopData.title || loopData.Title || '';

let url = loopData.url || loopData.URL || loopData.link || loopData.Link ||
          loopData.website || loopData.Website || loopData.site || '';

// ВАЖЛИВО: Якщо company містить URL, а url пустий - поміняти їх місцями
if (company && company.toString().match(/^https?:\/\//i)) {
  if (!url) {
    url = company;
    company = '';
  }
}

// Якщо назви немає, але є URL - витягуємо domain
if (!company && url) {
  try {
    const urlObj = new URL(url);
    // ringover.com -> Ringover
    company = urlObj.hostname
      .replace(/^www\./i, '')
      .split('.')[0]
      .charAt(0).toUpperCase() + urlObj.hostname.replace(/^www\./i, '').split('.')[0].slice(1);
  } catch (e) {
    company = 'Unknown';
  }
}

// Якщо URL немає, але company схожий на URL - використовуємо його
if (!url && company && company.match(/^https?:\/\//i)) {
  url = company;
  try {
    const urlObj = new URL(url);
    company = urlObj.hostname
      .replace(/^www\./i, '')
      .split('.')[0]
      .charAt(0).toUpperCase() + urlObj.hostname.replace(/^www\./i, '').split('.')[0].slice(1);
  } catch (e) {
    company = 'Unknown';
  }
}

console.log('✅ Extracted company:', company);
console.log('✅ Extracted URL:', url);

// ============================================
// КРОК 2: Парсимо Website, Blog, Reviews
// ============================================

const mergeItems = $input.all();
let websiteHtml = '';
let blogHtml = '';
let reviewsHtml = '';

// Website HTML
try {
  if (mergeItems && mergeItems.length > 0) {
    websiteHtml = mergeItems[0].json.body || mergeItems[0].json.data || '';
    console.log('📄 Website HTML length:', websiteHtml.length);
  }
} catch (e) {
  console.error('❌ Cannot get website data:', e.message);
}

// Blog HTML
try {
  if (mergeItems && mergeItems.length > 1) {
    blogHtml = mergeItems[1].json.body || mergeItems[1].json.data || '';
    console.log('📝 Blog HTML length:', blogHtml.length);
  }
} catch (e) {
  console.error('❌ Cannot get blog data:', e.message);
}

// Reviews HTML
try {
  if (mergeItems && mergeItems.length > 2) {
    reviewsHtml = mergeItems[2].json.body || mergeItems[2].json.data || '';
    console.log('⭐ Reviews HTML length:', reviewsHtml.length);
  }
} catch (e) {
  console.error('❌ Cannot get reviews data:', e.message);
}

// ============================================
// КРОК 3: Парсимо Website metadata (покращений)
// ============================================

const extractText = (html, pattern) => {
  const match = html.match(pattern);
  return match ? match[1].trim() : null;
};

// Title - кілька варіантів
const title = extractText(websiteHtml, /<title[^>]*>([^<]+)<\/title>/i) ||
              extractText(websiteHtml, /<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i);

// Description - кілька варіантів
const description = extractText(websiteHtml, /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i) ||
                    extractText(websiteHtml, /<meta[^>]*content=["']([^"']+)["'][^>]*name=["']description["']/i) ||
                    extractText(websiteHtml, /<meta[^>]*property=["']og:description["'][^>]*content=["']([^"']+)["']/i);

// H1 tags
const h1Matches = websiteHtml.match(/<h1[^>]*>([^<]+)<\/h1>/gi) || [];
const h1Tags = h1Matches.map(h => h.replace(/<[^>]+>/g, '').trim()).slice(0, 5);

// Перевірка секцій (case-insensitive, більше варіантів)
const hasNews = /news|новини|новости|actualités|noticias/i.test(websiteHtml);
const hasBlog = /blog|блог|блог/i.test(websiteHtml);
const hasPricing = /pricing|ціни|тарифи|цены|prix|precios|price/i.test(websiteHtml);
const hasFeatures = /features|можливості|функції|возможности|fonctionnalités|características/i.test(websiteHtml);

// Витягуємо перші параграфи як додаткову інформацію
const paragraphs = websiteHtml.match(/<p[^>]*>([^<]{50,})<\/p>/gi) || [];
const firstParagraphs = paragraphs
  .slice(0, 3)
  .map(p => p.replace(/<[^>]+>/g, '').trim())
  .filter(p => p.length > 50);

const website = {
  title: title,
  description: description,
  h1Tags: h1Tags,
  firstParagraphs: firstParagraphs,
  hasNews: hasNews,
  hasBlog: hasBlog,
  hasPricing: hasPricing,
  hasFeatures: hasFeatures,
  htmlLength: websiteHtml.length
};

// ============================================
// КРОК 4: Парсимо Blog (покращений)
// ============================================

const blogArticles = blogHtml.match(/<article[^>]*>([\s\S]{1,5000}?)<\/article>/gi) || [];
const blogPosts = blogHtml.match(/<div[^>]*class="[^"]*post[^"]*"[^>]*>([\s\S]{1,5000}?)<\/div>/gi) || [];
const allArticles = [...blogArticles, ...blogPosts];

const blog = {
  articlesFound: allArticles.length,
  recentArticles: allArticles.slice(0, 5).map((article, i) => {
    const titleMatch = article.match(/<h[1-4][^>]*>([^<]{5,200})<\/h[1-4]>/i);
    const dateMatch = article.match(/<time[^>]*datetime=["']([^"']+)["']/i) ||
                     article.match(/(\d{4}-\d{2}-\d{2})/);
    const textContent = article.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
                              .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
                              .replace(/<[^>]+>/g, ' ')
                              .replace(/\s+/g, ' ')
                              .trim();

    return {
      title: titleMatch ? titleMatch[1].trim() : `Article ${i+1}`,
      date: dateMatch ? dateMatch[1] : null,
      preview: textContent.substring(0, 300).trim()
    };
  })
};

// ============================================
// КРОК 5: Парсимо Reviews (покращений)
// ============================================

const reviewPatterns = [
  /<div[^>]*class="[^"]*review[^"]*"[^>]*>([\s\S]{1,2000}?)<\/div>/gi,
  /<div[^>]*class="[^"]*testimonial[^"]*"[^>]*>([\s\S]{1,2000}?)<\/div>/gi,
  /<article[^>]*class="[^"]*review[^"]*"[^>]*>([\s\S]{1,2000}?)<\/article>/gi
];

let reviewMatches = [];
for (const pattern of reviewPatterns) {
  const matches = reviewsHtml.match(pattern) || [];
  reviewMatches = reviewMatches.concat(matches);
  if (reviewMatches.length >= 5) break;
}

const reviews = {
  found: reviewMatches.length > 0,
  count: reviewMatches.length,
  samples: reviewMatches.slice(0, 5).map(r => {
    const text = r.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
                  .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
                  .replace(/<[^>]+>/g, ' ')
                  .replace(/\s+/g, ' ')
                  .trim();
    return text.substring(0, 200).trim();
  })
};

// ============================================
// РЕЗУЛЬТАТ
// ============================================

console.log('📊 Results:', {
  company,
  url,
  titleFound: !!title,
  descriptionFound: !!description,
  h1Count: h1Tags.length,
  blogArticles: blog.articlesFound,
  reviews: reviews.count
});

return {
  company: company || 'Unknown',
  url: url || '',
  currentData: {
    website: website,
    blog: blog,
    reviews: reviews,
    scrapedAt: new Date().toISOString()
  },
  previousData: null
};

// Parse all data sources - FIXED VERSION v4
const loopData = $('Loop Companies1').item.json;

// КРИТИЧНО: Правильно витягуємо назву компанії та URL
// Спочатку дивимось що є в loopData
console.log('Loop data keys:', Object.keys(loopData));

// Витягуємо назву компанії - може бути в різних полях
let company = loopData.name || loopData.company || loopData['Компанія'] || loopData['Company'] || loopData['Назва'] || 'Unknown';

// Витягуємо URL - може бути в різних полях
let url = loopData.url || loopData.URL || loopData.link || loopData.website || loopData['Website'] || '';

// ВАЖЛИВО: Якщо company містить URL (починається з http), то це помилка
// Шукаємо назву в інших полях
if (company.startsWith('http')) {
  // company містить URL, треба знайти реальну назву
  url = company; // Зберігаємо URL
  company = loopData.name || loopData['Компанія'] || loopData['Company'] || loopData['Назва'] || 'Unknown';

  // Якщо все ще не знайшли назву, витягуємо domain з URL
  if (company === 'Unknown' || company.startsWith('http')) {
    try {
      const urlObj = new URL(url);
      company = urlObj.hostname.replace('www.', '').replace(/\..+$/, ''); // netelip.com -> netelip
    } catch (e) {
      company = 'Unknown';
    }
  }
}

console.log('Extracted company:', company);
console.log('Extracted URL:', url);

let previousData = null;

// Get merged items: [0]=Website, [1]=Blog, [2]=Reviews
const mergeItems = $input.all();

// Parse website - now available from Merge index 0
let websiteHtml = '';
try {
  if (mergeItems && mergeItems.length > 0) {
    websiteHtml = mergeItems[0].json.body || '';
  }
} catch (e) {
  console.log('Cannot get website data:', e.message);
  websiteHtml = '';
}

// Extract website metadata
const titleMatch = websiteHtml.match(/<title[^>]*>([^<]+)<\/title>/i);
const descMatch = websiteHtml.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i) ||
                  websiteHtml.match(/<meta[^>]*content=["']([^"']+)["'][^>]*name=["']description["']/i);
const h1Matches = websiteHtml.match(/<h1[^>]*>([^<]+)<\/h1>/gi) || [];

const website = {
  title: titleMatch ? titleMatch[1].trim() : null,
  description: descMatch ? descMatch[1].trim() : null,
  h1Tags: h1Matches.map(h => h.replace(/<[^>]+>/g, '').trim()).slice(0, 3),
  hasNews: /news|новини/i.test(websiteHtml),
  hasBlog: /blog|блог/i.test(websiteHtml),
  hasPricing: /pricing|ціни|тарифи/i.test(websiteHtml),
  hasFeatures: /features|можливості|функції/i.test(websiteHtml)
};

// Parse blog - from Merge index 1
let blogHtml = '';
try {
  if (mergeItems && mergeItems.length > 1) {
    blogHtml = mergeItems[1].json.body || '';
  }
} catch (e) {
  console.log('Cannot get blog data:', e.message);
  blogHtml = '';
}

const blogArticles = blogHtml.match(/<article[^>]*>([\s\S]*?)<\/article>/gi) || [];
const blog = {
  articlesFound: blogArticles.length,
  recentArticles: blogArticles.slice(0, 5).map((article, i) => {
    const titleMatch = article.match(/<h[1-3][^>]*>([^<]+)<\/h[1-3]>/i);
    const dateMatch = article.match(/<time[^>]*datetime=["']([^"']+)["']/i) || article.match(/(\d{4}-\d{2}-\d{2})/);
    return {
      title: titleMatch ? titleMatch[1].trim() : `Article ${i+1}`,
      date: dateMatch ? dateMatch[1] : null,
      preview: article.replace(/<[^>]+>/g, '').substring(0, 200).trim()
    };
  })
};

// Parse reviews - from Merge index 2
let reviewsHtml = '';
try {
  if (mergeItems && mergeItems.length > 2) {
    reviewsHtml = mergeItems[2].json.body || '';
  }
} catch (e) {
  console.log('Cannot get reviews data:', e.message);
  reviewsHtml = '';
}

const reviewMatches = reviewsHtml.match(/<div[^>]*class="[^"]*review[^"]*"[^>]*>([\s\S]*?)<\/div>/gi) || [];
const reviews = {
  found: reviewMatches.length > 0,
  count: reviewMatches.length,
  samples: reviewMatches.slice(0, 3).map(r => r.replace(/<[^>]+>/g, '').substring(0, 150).trim())
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
  previousData: previousData
};

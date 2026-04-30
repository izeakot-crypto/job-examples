// Parse all data sources - FIXED VERSION
const loopData = $('Loop Companies1').item.json;

// Safe access to company data from Google Sheets
const company = loopData.company || loopData.name || loopData['Компанія'] || loopData['Company'] || 'Unknown';
const url = loopData.url || loopData.URL || loopData.link || '';

// Skip previous data since Read Previous Data1 node doesn't exist
let previousData = null;

// Parse website - SAFE ACCESS
let websiteHtml = '';
try {
  const websiteData = $('Fetch Website1').item.json;
  websiteHtml = websiteData.body || '';
} catch (e) {
  console.log('Fetch Website1 not available:', e.message);
  websiteHtml = '';
}

const titleMatch = websiteHtml.match(/<title[^>]*>([^<]+)<\/title>/i);
const descMatch = websiteHtml.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i);
const h1Matches = websiteHtml.match(/<h1[^>]*>([^<]+)<\/h1>/gi) || [];

const website = {
  title: titleMatch ? titleMatch[1].trim() : null,
  description: descMatch ? descMatch[1].trim() : null,
  h1Tags: h1Matches.map(h => h.replace(/<[^>]+>/g, '').trim()),
  hasNews: websiteHtml.toLowerCase().includes('news'),
  hasBlog: websiteHtml.toLowerCase().includes('blog'),
  hasPricing: websiteHtml.toLowerCase().includes('pricing'),
  hasFeatures: websiteHtml.toLowerCase().includes('features')
};

// Parse blog
const blogHtml = $('Fetch Blog1').item.json.body || '';
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

// Parse reviews/testimonials
const reviewsHtml = $('Fetch Reviews1').item.json.body || '';
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

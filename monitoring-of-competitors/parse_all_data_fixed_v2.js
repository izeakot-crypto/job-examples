// Parse all data sources - FIXED VERSION v2
const loopData = $('Loop Companies1').item.json;

// Safe access to company data from Google Sheets
const company = loopData.company || loopData.name || loopData['Компанія'] || loopData['Company'] || 'Unknown';
const url = loopData.url || loopData.URL || loopData.link || '';

// Skip previous data since Read Previous Data1 node doesn't exist
let previousData = null;

// Parse website - get from Merge input items
let websiteHtml = '';
try {
  // $input.all() contains all merged items from Fetch Blog1 and Fetch Reviews1
  // We need to check if there's any website data
  // Since Fetch Website1 is NOT connected to Merge, we need different approach

  // Try to get from input items (this is Merge output)
  const mergeItems = $input.all();

  // The Merge node combines Fetch Blog1 (index 0) and Fetch Reviews1 (index 1)
  // But Fetch Website1 is NOT in Merge! It goes separately to Auto-detect nodes

  // We can't access Fetch Website1 from here because it's in parallel branch
  // So we'll parse only blog and reviews that we have

  websiteHtml = ''; // No website data available in this branch
} catch (e) {
  console.log('Cannot get website data:', e.message);
  websiteHtml = '';
}

const website = {
  title: null,
  description: null,
  h1Tags: [],
  hasNews: false,
  hasBlog: false,
  hasPricing: false,
  hasFeatures: false
};

// Parse blog - get from Merge
let blogHtml = '';
try {
  const mergeItems = $input.all();
  // First item in merge should be from Fetch Blog1
  if (mergeItems && mergeItems.length > 0) {
    blogHtml = mergeItems[0].json.body || '';
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

// Parse reviews/testimonials - get from Merge
let reviewsHtml = '';
try {
  const mergeItems = $input.all();
  // Second item in merge should be from Fetch Reviews1
  if (mergeItems && mergeItems.length > 1) {
    reviewsHtml = mergeItems[1].json.body || '';
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

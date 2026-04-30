const items = $input.all();
const company = items[0]?.json?.company || items[0]?.json?.companyName || 'Unknown';
const url = items[0]?.json?.url || items[0]?.json?.companyUrl || '-';

const ytItem = items.find(i => i.json.youtubeVideoCount !== undefined);
const youtubeActivity = ytItem?.json?.youtubeActivity || '-';

const socialItem = items.find(i => i.json.linkedinActivity !== undefined);
const linkedinActivity = socialItem?.json?.linkedinActivity || '-';
const facebookActivity = socialItem?.json?.facebookActivity || '-';
const vkActivity = socialItem?.json?.vkActivity || '-';
const telegramActivity = socialItem?.json?.telegramActivity || '-';
const socialLinksCount = socialItem?.json?.socialLinksCount || 0;

const g2Item = items.find(i => i.json.aggregatorMentions !== undefined);
const aggregatorMentions = g2Item?.json?.aggregatorMentions || '-';
const g2Rating = g2Item?.json?.g2Rating || '-';
const g2ReviewsCount = g2Item?.json?.g2ReviewsCount || 0;

// Collect page data and convert to readable text (not raw JSON)
const webItems = items.filter(i => i.json.categorizedData);
const categories = { blog: [], news: [], reviews: [], pricing: [], features: [] };

webItems.forEach(w => {
  const cd = w.json.categorizedData || {};
  Object.keys(cd).forEach(k => {
    if (cd[k] && cd[k].length > 0 && categories[k] !== undefined) {
      cd[k].forEach(p => {
        const title = (p.metadata && p.metadata.title) ? String(p.metadata.title) : '';
        // Parse content if it's JSON string, extract readable parts
        let text = '';
        try {
          const raw = typeof p.content === 'string' ? p.content : JSON.stringify(p.content || '');
          const parsed = JSON.parse(raw);
          // Extract meaningful text from parsed content
          const parts = [];
          if (parsed.features) parts.push('Features: ' + parsed.features.slice(0, 10).join(', '));
          if (parsed.prices && parsed.prices.length) parts.push('Prices: ' + parsed.prices.join(', '));
          if (parsed.plans && parsed.plans.length) parts.push('Plans: ' + parsed.plans.join(', '));
          if (parsed.articles && parsed.articles.length) {
            parts.push('Articles: ' + parsed.articles.map(a => a.title || '').filter(Boolean).join(', '));
          }
          if (parsed.topics && parsed.topics.length) parts.push('Topics: ' + parsed.topics.slice(0, 8).join(', '));
          if (parsed.mainContent) parts.push(parsed.mainContent.substring(0, 300));
          text = parts.join('. ') || raw.substring(0, 300);
        } catch(e) {
          text = String(typeof p.content === 'string' ? p.content : JSON.stringify(p.content || '')).substring(0, 300);
        }
        categories[k].push(title + ': ' + text);
      });
    }
  });
});

// Build readable summary for each category
const pageSummary = {};
Object.keys(categories).forEach(k => {
  if (categories[k].length > 0) {
    pageSummary[k] = categories[k].map((item, i) => (i + 1) + '. ' + item).join('\n');
  } else {
    pageSummary[k] = '-';
  }
});

return {
  company, url,
  youtubeActivity, linkedinActivity, facebookActivity,
  vkActivity, telegramActivity, socialLinksCount,
  aggregatorMentions, g2Rating, g2ReviewsCount,
  totalPagesParsed: webItems.reduce((s, w) => s + (w.json.totalPagesParsed || 0), 0),
  blogSummary: pageSummary.blog,
  newsSummary: pageSummary.news,
  reviewsSummary: pageSummary.reviews,
  pricingSummary: pageSummary.pricing,
  featuresSummary: pageSummary.features
};
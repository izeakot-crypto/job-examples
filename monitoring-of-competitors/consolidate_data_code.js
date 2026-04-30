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

const webItems = items.filter(i => i.json.categorizedData);
const allPages = { blog: [], news: [], reviews: [], pricing: [], features: [] };
webItems.forEach(w => {
  const cd = w.json.categorizedData || {};
  Object.keys(cd).forEach(k => {
    if (cd[k] && cd[k].length > 0 && allPages[k] !== undefined) {
      allPages[k] = allPages[k].concat(cd[k].map(p => ({
        url: p.url || '',
        title: (p.metadata && p.metadata.title) ? String(p.metadata.title) : '',
        content: typeof p.content === 'string' ? p.content.substring(0, 500) : JSON.stringify(p.content || '').substring(0, 500)
      })));
    }
  });
});

return {
  company, url,
  youtubeActivity, linkedinActivity, facebookActivity,
  vkActivity, telegramActivity, socialLinksCount,
  aggregatorMentions, g2Rating, g2ReviewsCount,
  totalPagesParsed: webItems.reduce((s, w) => s + (w.json.totalPagesParsed || 0), 0),
  pages: allPages
};
// Parse Page Content - V4 (fixed: data instead of body)
var inputItem = $input.item.json;
var html = inputItem.data || inputItem.body || '';
var setFieldsData = $('Set Fields Before Fetch').item.json;
var companyName = setFieldsData.companyName || 'Unknown';
var companyUrl = setFieldsData.companyUrl || '';
var pageUrl = setFieldsData.pageUrl || '';
var category = setFieldsData.category || 'unknown';
function cleanText(text) {
if (!text) return '';
return text.replace(/&nbsp;/gi, ' ').replace(/&amp;/gi, '&').replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/&#\d+;/g, '').replace(/\s+/g, ' ').trim();
}
var cleanHtml = html.replace(/<header[^>]*>[\s\S]*?<\/header>/gi, '').replace(/<nav[^>]*>[\s\S]*?<\/nav>/gi, '').replace(/<footer[^>]*>[\s\S]*?<\/footer>/gi, '').replace(/<aside[^>]*>[\s\S]*?<\/aside>/gi, '').replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
var titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
var title = titleMatch ? cleanText(titleMatch[1]) : null;
var descMatch = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i);
var description = descMatch ? cleanText(descMatch[1]) : null;
var h1Matches = cleanHtml.match(/<h1[^>]*>([\s\S]*?)<\/h1>/gi) || [];
var h2Matches = cleanHtml.match(/<h2[^>]*>([\s\S]*?)<\/h2>/gi) || [];
var h3Matches = cleanHtml.match(/<h3[^>]*>([\s\S]*?)<\/h3>/gi) || [];
var h1Tags = h1Matches.map(function(h) { return cleanText(h.replace(/<[^>]+>/g, '')); }).filter(function(t) { return t.length > 2 && t.length < 200; });
var h2Tags = h2Matches.map(function(h) { return cleanText(h.replace(/<[^>]+>/g, '')); }).filter(function(t) { return t.length > 5 && t.length < 200; }).slice(0, 10);
var h3Tags = h3Matches.map(function(h) { return cleanText(h.replace(/<[^>]+>/g, '')); }).filter(function(t) { return t.length > 5 && t.length < 200; }).slice(0, 15);
var categoryData = {};
if (category === 'blog' || category === 'news') {
var articles = [];
var seen = new Set();
var articlePatterns = [/<article[^>]*>([\s\S]*?)<\/article>/gi, /<div[^>]*class=["'][^"']*(?:post|entry|blog-item|news-item|article)[^"']*["'][^>]*>([\s\S]*?)<\/div>/gi];
for (var p = 0; p < articlePatterns.length && articles.length < 15; p++) {
var match;
articlePatterns[p].lastIndex = 0;
while ((match = articlePatterns[p].exec(cleanHtml)) !== null && articles.length < 15) {
var content = match[1] || match[0];
var tMatch = content.match(/<h[1-4][^>]*>([\s\S]*?)<\/h[1-4]>/i);
var t = tMatch ? cleanText(tMatch[1].replace(/<[^>]+>/g, '')) : null;
if (t && t.length > 10 && !seen.has(t.toLowerCase())) {
seen.add(t.toLowerCase());
articles.push({ title: t, preview: cleanText(content.replace(/<[^>]+>/g, ' ')).substring(0, 200) });
}
}
}
if (articles.length === 0) {
h2Tags.concat(h3Tags).forEach(function(t) {
if (!seen.has(t.toLowerCase()) && articles.length < 15) {
seen.add(t.toLowerCase());
articles.push({ title: t, preview: '' });
}
});
}
categoryData.articles = articles;
categoryData.topics = h2Tags.slice(0, 10);
} else if (category === 'reviews') {
categoryData.topics = h2Tags.concat(h3Tags).slice(0, 15);
categoryData.mainContent = cleanText(cleanHtml.replace(/<[^>]+>/g, ' ')).substring(0, 1000);
} else if (category === 'pricing') {
var priceMatches = html.match(/\d+[\s\u00a0]*(?:руб|₽|рублей|RUB)|[\$€£]\s*\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s*(?:USD|EUR|GBP|руб)/gi) || [];
categoryData.prices = [...new Set(priceMatches)].slice(0, 20);
categoryData.hasPricing = priceMatches.length > 0;
categoryData.plans = h2Tags.concat(h3Tags).filter(function(t) { return t.match(/пакет|тариф|план|price|plan|базов|стандарт|премиум|pro|enterprise/i); }).slice(0, 10);
categoryData.topics = h2Tags.slice(0, 10);
} else if (category === 'features') {
var features = [];
var featureLists = cleanHtml.match(/<ul[^>]*>[\s\S]{1,10000}?<\/ul>/gi) || [];
for (var j = 0; j < featureLists.length && features.length < 30; j++) {
var items = featureLists[j].match(/<li[^>]*>([\s\S]*?)<\/li>/gi) || [];
for (var k = 0; k < items.length && features.length < 30; k++) {
var text = cleanText(items[k].replace(/<[^>]+>/g, ''));
if (text.length > 10 && text.length < 300) features.push(text);
}
}
categoryData.features = features;
categoryData.topics = h2Tags.concat(h3Tags).slice(0, 15);
}
var mainText = cleanText(cleanHtml.replace(/<[^>]+>/g, ' ')).substring(0, 1500);
return {
url: pageUrl,
category: category,
companyName: companyName,
companyUrl: companyUrl,
metadata: { title: title, description: description, h1: h1Tags, h2: h2Tags, h3: h3Tags },
content: categoryData,
summary: mainText,
parsedAt: new Date().toISOString()
};
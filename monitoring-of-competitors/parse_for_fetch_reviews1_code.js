// Parse for Fetch Reviews1 - парсинг ТІЛЬКИ відгуків
var html = $input.item.json.data || $input.item.json.body || '';
var editFieldsData = $('Edit Fields').item.json;
var companyName = editFieldsData.companyName || 'Unknown';
var companyUrl = editFieldsData.companyUrl || '';

function cleanText(text) {
  if (!text) return '';
  return text.replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&#\d+;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Видалити header/nav/footer
var cleanHtml = html
  .replace(/<header[\s\S]*?<\/header>/gi, '')
  .replace(/<nav[\s\S]*?<\/nav>/gi, '')
  .replace(/<footer[\s\S]*?<\/footer>/gi, '')
  .replace(/<script[\s\S]*?<\/script>/gi, '')
  .replace(/<style[\s\S]*?<\/style>/gi, '');

// Витягнути title
var titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
var pageTitle = titleMatch ? cleanText(titleMatch[1]) : '';

// Витягнути h1
var h1Match = cleanHtml.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
var h1Text = h1Match ? cleanText(h1Match[1].replace(/<[^>]+>/g, '')) : '';

// Парсинг відгуків - різні паттерни
var reviews = [];
var seen = new Set();

// Паттерн 1: section блоки з відгуками
var sectionPattern = /<section[^>]*class[^>]*>[\s\S]*?<\/section>/gi;
var sections = cleanHtml.match(sectionPattern) || [];

for (var i = 0; i < sections.length && reviews.length < 20; i++) {
  var section = sections[i];
  var nameMatch = section.match(/<strong[^>]*>([^<]+)<\/strong>/i);
  var name = nameMatch ? cleanText(nameMatch[1]) : null;
  var roleMatch = section.match(/<span[^>]*>([^<]+)<\/span>/i);
  var role = roleMatch ? cleanText(roleMatch[1]) : null;
  var paragraphs = section.match(/<p[^>]*>([\s\S]*?)<\/p>/gi) || [];
  var reviewText = '';
  for (var j = 0; j < paragraphs.length; j++) {
    var pText = cleanText(paragraphs[j].replace(/<[^>]+>/g, ''));
    if (pText.length > 30) reviewText += pText + ' ';
  }
  reviewText = reviewText.trim();
  if (name && reviewText.length > 50 && !seen.has(reviewText.substring(0, 100))) {
    seen.add(reviewText.substring(0, 100));
    reviews.push({ author: name, role: role, company: role ? role.split(',').pop().trim() : null, text: reviewText.substring(0, 500), preview: reviewText.substring(0, 150) });
  }
}

// Паттерн 2: div з класами review/testimonial
if (reviews.length === 0) {
  var divPattern = /<div[^>]*class=['"][^'"]*(?:review|testimonial|feedback|client|case)[^'"]*['"][^>]*>([\s\S]*?)<\/div>/gi;
  var match;
  while ((match = divPattern.exec(cleanHtml)) !== null && reviews.length < 20) {
    var content = match[1];
    var text = cleanText(content.replace(/<[^>]+>/g, ' '));
    if (text.length > 50 && !seen.has(text.substring(0, 100))) {
      seen.add(text.substring(0, 100));
      reviews.push({ author: null, role: null, company: null, text: text.substring(0, 500), preview: text.substring(0, 150) });
    }
  }
}

// Паттерн 3: blockquote
if (reviews.length === 0) {
  var quotePattern = /<blockquote[^>]*>([\s\S]*?)<\/blockquote>/gi;
  var qMatch;
  while ((qMatch = quotePattern.exec(cleanHtml)) !== null && reviews.length < 20) {
    var text = cleanText(qMatch[1].replace(/<[^>]+>/g, ' '));
    if (text.length > 50) reviews.push({ author: null, role: null, company: null, text: text.substring(0, 500), preview: text.substring(0, 150) });
  }
}

var is404 = /404|not found|error/i.test(pageTitle);

return {
  company: companyName,
  url: companyUrl,
  reviewsUrl: companyUrl + '/reviews',
  pageTitle: pageTitle,
  h1: h1Text,
  is404: is404,
  reviewsFound: reviews.length,
  reviews: reviews,
  hasReviews: reviews.length > 0,
  parsedAt: new Date().toISOString(),
  _debug: { htmlLength: html.length, sectionsFound: sections.length }
};

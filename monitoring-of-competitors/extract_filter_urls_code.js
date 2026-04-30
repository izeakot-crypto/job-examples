// Extract & Filter URLs - V2 з розширеними паттернами
var scanResult = $input.item.json;
var allResults = scanResult.all_results || [];
var editFieldsData = $('Edit Fields').first().json;
var companyName = editFieldsData.companyName || 'Unknown';
var companyUrl = editFieldsData.companyUrl || '';
console.log('Extract URLs - Company:', companyName, 'Total URLs:', allResults.length);
var categories = {
blog: /\/(blog|blogs|article|articles|post|posts|insights|journal|novosti|stati|publikacii)/i,
news: /\/(news|press|announcements|newsroom|events|meropriyatiya|sobytiya)/i,
reviews: /\/(review|reviews|testimonial|testimonials|customer-stories|success-stories|case-studies|otzyvy|klienty|use_mango|clients)/i,
pricing: /\/(pricing|price|prices|plans|tarif|cost|tariffs|ceny|stoimost)/i,
features: /\/(features|feature|capabilities|vozmozhnosti|resheniya|funktsii|marketplace|integraciya)/i
};
var categorizedUrls = [];
var seenUrls = new Set();
for (var i = 0; i < allResults.length; i++) {
var result = allResults[i];
var url = result.url || '';
if (result.has_errors || seenUrls.has(url)) continue;
seenUrls.add(url);
if (url.match(/\/$/)) {
var path = url.replace(/https?:\/\/[^\/]+/, '');
if (path === '/' || path === '/about/' || path === '/promo/' || path === '/products/') continue;
}
for (var cat in categories) {
if (categories[cat].test(url)) {
categorizedUrls.push({
url: url,
category: cat,
status_code: result.status_code,
companyName: companyName,
companyUrl: companyUrl
});
break;
}
}
}
console.log('Filtered URLs:', categorizedUrls.length, 'Categories:', categorizedUrls.map(function(u) { return u.category; }).join(', '));
if (categorizedUrls.length === 0) {
return [{ json: { url: '', category: 'none', status_code: 0, companyName: companyName, companyUrl: companyUrl } }];
}
return categorizedUrls.map(function(item) { return { json: item }; });
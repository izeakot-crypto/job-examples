// КРОК 2: Парсимо Sitemap XML і витягуємо всі URLs
// Цей код йде після HTTP Request що завантажив sitemap

const sitemapXml = $input.item.json.body || $input.item.json.data || '';

console.log('📄 Sitemap XML length:', sitemapXml.length);

// Витягуємо всі <loc> URLs з XML
const urlMatches = sitemapXml.match(/<loc>(.*?)<\/loc>/gi) || [];
const allUrls = urlMatches.map(match => {
    return match.replace(/<\/?loc>/gi, '').trim();
});

console.log('🔍 Total URLs found in sitemap:', allUrls.length);

// Повертаємо кожен URL як окремий item для фільтрації
return allUrls.map(url => ({ url: url }));

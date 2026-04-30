// КРОК 1: Витягуємо Sitemap URLs
// Цей код йде в Code node після "Call Website Checker"

const scanResult = $input.item.json;

console.log('📊 Processing scan result...');

// Витягуємо robots.txt
const robotsTxt = scanResult.robots_txt || {};
const sitemaps = [];

// Шукаємо Sitemap URLs в robots.txt
if (robotsTxt.raw_content) {
    const sitemapMatches = robotsTxt.raw_content.match(/Sitemap:\s*(https?:\/\/[^\s]+)/gi);
    if (sitemapMatches) {
        sitemapMatches.forEach(match => {
            const url = match.replace(/Sitemap:\s*/i, '').trim();
            sitemaps.push(url);
        });
    }
}

console.log('🗺️ Found sitemaps:', sitemaps);

// Витягуємо base URL
const baseUrl = scanResult.all_results && scanResult.all_results[0]
    ? scanResult.all_results[0].url
    : '';

// Якщо sitemap не знайдено в robots.txt, спробуємо стандартні URLs
if (sitemaps.length === 0 && baseUrl) {
    const standardSitemaps = [
        baseUrl + '/sitemap.xml',
        baseUrl + '/sitemap_index.xml',
        baseUrl + '/sitemap-index.xml'
    ];
    sitemaps.push(...standardSitemaps);
    console.log('⚠️ No sitemap in robots.txt, trying standard URLs');
}

// Повертаємо масив URLs для fetch
return sitemaps.map(url => ({ url: url }));

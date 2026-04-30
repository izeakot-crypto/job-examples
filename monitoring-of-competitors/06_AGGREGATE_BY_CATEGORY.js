// КРОК 6: Агрегуємо всі спарсені сторінки по категоріям

const allPages = $input.all();

console.log('📊 Total pages parsed:', allPages.length);

// Групуємо по категоріям
const byCategory = {
    blog: [],
    news: [],
    reviews: [],
    pricing: [],
    features: [],
    products: [],
    about: [],
    contact: [],
    careers: [],
    solutions: []
};

allPages.forEach(page => {
    const pageData = page.json;
    const category = pageData.category;

    if (byCategory[category]) {
        byCategory[category].push(pageData);
    }
});

// Статистика
const stats = {};
Object.keys(byCategory).forEach(cat => {
    stats[cat] = byCategory[cat].length;
});

console.log('📈 Pages by category:', stats);

// Витягуємо company URL з першої сторінки
let companyUrl = 'Unknown';
if (allPages.length > 0 && allPages[0].json.url) {
    try {
        const firstUrl = allPages[0].json.url;
        const urlObj = new URL(firstUrl);
        companyUrl = urlObj.origin; // https://example.com
    } catch (e) {
        companyUrl = 'Unknown';
    }
}

// Повертаємо агреговані дані
return {
    companyUrl: companyUrl,
    companyName: companyUrl.replace('https://', '').replace('http://', '').split('.')[0],
    totalPagesParsed: allPages.length,
    statistics: stats,
    categorizedData: byCategory,
    aggregatedAt: new Date().toISOString()
};

// КРОК 5: Парсимо контент сторінки в залежності від категорії

const pageUrl = $input.item.json.url || '';
const category = $('Filter Pages').item.json.category;
const html = $input.item.json.body || '';

console.log(`📄 Parsing ${category} page: ${pageUrl}`);
console.log(`HTML length: ${html.length}`);

// Helper функція для витягування тексту
const extractText = (html, pattern) => {
    const match = html.match(pattern);
    return match ? match[1].trim() : null;
};

// Базова метаінформація (для всіх сторінок)
const title = extractText(html, /<title[^>]*>([^<]+)<\/title>/i) ||
              extractText(html, /<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i);

const description = extractText(html, /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i) ||
                    extractText(html, /<meta[^>]*property=["']og:description["'][^>]*content=["']([^"']+)["']/i);

const h1Tags = (html.match(/<h1[^>]*>([^<]+)<\/h1>/gi) || [])
    .map(h => h.replace(/<[^>]+>/g, '').trim())
    .slice(0, 5);

// Специфічний парсинг в залежності від категорії
let categoryData = {};

if (category === 'blog' || category === 'news') {
    // Парсимо статті
    const articleMatches = html.match(/<article[^>]*>([\s\S]{1,10000}?)<\/article>/gi) || [];
    const postMatches = html.match(/<div[^>]*class="[^"]*post[^"]*"[^>]*>([\s\S]{1,10000}?)<\/div>/gi) || [];
    const allArticles = [...articleMatches, ...postMatches];

    categoryData.articles = allArticles.slice(0, 10).map((article, i) => {
        const articleTitle = extractText(article, /<h[1-4][^>]*>([^<]{5,300})<\/h[1-4]>/i);
        const dateMatch = article.match(/<time[^>]*datetime=["']([^"']+)["']/i) ||
                         article.match(/(\d{4}-\d{2}-\d{2})/);
        const textContent = article
            .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
            .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();

        return {
            title: articleTitle || `Article ${i+1}`,
            date: dateMatch ? dateMatch[1] : null,
            preview: textContent.substring(0, 500).trim(),
            url: pageUrl
        };
    });

    categoryData.totalArticles = allArticles.length;

} else if (category === 'reviews') {
    // Парсимо відгуки
    const reviewPatterns = [
        /<div[^>]*class="[^"]*review[^"]*"[^>]*>([\s\S]{1,3000}?)<\/div>/gi,
        /<div[^>]*class="[^"]*testimonial[^"]*"[^>]*>([\s\S]{1,3000}?)<\/div>/gi,
        /<article[^>]*class="[^"]*review[^"]*"[^>]*>([\s\S]{1,3000}?)<\/article>/gi
    ];

    let reviewMatches = [];
    for (const pattern of reviewPatterns) {
        const matches = html.match(pattern) || [];
        reviewMatches = reviewMatches.concat(matches);
        if (reviewMatches.length >= 10) break;
    }

    categoryData.reviews = reviewMatches.slice(0, 10).map((review, i) => {
        // Шукаємо рейтинг
        const ratingMatch = review.match(/(\d+(?:\.\d+)?)\s*(?:out of|\/)\s*5|rating[^\d]*(\d+(?:\.\d+)?)/i);
        const rating = ratingMatch ? (ratingMatch[1] || ratingMatch[2]) : null;

        // Витягуємо текст
        const text = review
            .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
            .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();

        // Шукаємо автора
        const authorMatch = review.match(/by\s+([A-Za-z\s]+)|author[^>]*>([^<]+)/i);
        const author = authorMatch ? (authorMatch[1] || authorMatch[2]).trim() : null;

        return {
            text: text.substring(0, 500).trim(),
            rating: rating ? parseFloat(rating) : null,
            author: author,
            url: pageUrl
        };
    });

    categoryData.totalReviews = reviewMatches.length;

} else if (category === 'pricing') {
    // Парсимо тарифи
    const priceMatches = html.match(/[\$€£]\s*\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s*(?:USD|EUR|GBP)/gi) || [];
    const planMatches = html.match(/<div[^>]*class="[^"]*plan[^"]*"[^>]*>([\s\S]{1,2000}?)<\/div>/gi) || [];

    categoryData.prices = priceMatches.slice(0, 20);
    categoryData.plansFound = planMatches.length;
    categoryData.hasPricing = priceMatches.length > 0;

} else if (category === 'features' || category === 'products') {
    // Витягуємо списки features
    const featureLists = html.match(/<ul[^>]*>([\s\S]{1,5000}?)<\/ul>/gi) || [];
    const features = [];

    featureLists.forEach(list => {
        const items = list.match(/<li[^>]*>([^<]+)<\/li>/gi) || [];
        items.forEach(item => {
            const text = item.replace(/<[^>]+>/g, '').trim();
            if (text.length > 5 && text.length < 200) {
                features.push(text);
            }
        });
    });

    categoryData.features = features.slice(0, 50);
    categoryData.totalFeatures = features.length;
}

// Повертаємо результат
return {
    url: pageUrl,
    category: category,
    metadata: {
        title: title,
        description: description,
        h1Tags: h1Tags
    },
    content: categoryData,
    parsedAt: new Date().toISOString()
};

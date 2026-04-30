// Фільтрація сторінок після парсингу всього домену
// Input: результат від workflow що парсить всі піддомени

const parsedData = $input.all();
const companyName = $('Loop Companies1').item.json.name || 'Unknown';
const mainUrl = $('Loop Companies1').item.json.url || '';

console.log('📊 Total pages parsed:', parsedData.length);

// Категорії сторінок які нас цікавлять
const pageCategories = {
  blog: [],
  news: [],
  reviews: [],
  testimonials: [],
  about: [],
  pricing: [],
  features: [],
  products: [],
  solutions: [],
  contact: [],
  careers: [],
  caseStudies: [],
  other: []
};

// Ключові слова для кожної категорії (багатомовні)
const keywords = {
  blog: /\/(blog|блог|article|post|insights|resources|learn)/i,
  news: /\/(news|новини|новости|actualités|press|announcement)/i,
  reviews: /\/(review|отзыв|testimonial|customer-stories|success)/i,
  testimonials: /\/(testimonial|customer|client|success-stories)/i,
  about: /\/(about|про-нас|о-нас|company|who-we-are|team)/i,
  pricing: /\/(pricing|price|plans|тарифи|ціни|цены|cost)/i,
  features: /\/(features|можливості|функції|capabilities|product)/i,
  products: /\/(product|solution|service|послуги|продукт)/i,
  solutions: /\/(solution|use-case|industry)/i,
  contact: /\/(contact|support|help|підтримка|контакт)/i,
  careers: /\/(career|job|vacancy|hiring|join|робота)/i,
  caseStudies: /\/(case-study|use-case|customer-story|приклад)/i
};

// Обробляємо кожну сторінку
parsedData.forEach((item, index) => {
  const pageData = item.json;

  // Отримуємо URL сторінки (можливі різні поля)
  const pageUrl = pageData.url || pageData.link || pageData.page || pageData.href || '';

  if (!pageUrl) {
    console.log(`⚠ Skipping item ${index}: no URL`);
    return;
  }

  // Визначаємо категорію
  let categorized = false;

  for (const [category, pattern] of Object.entries(keywords)) {
    if (pattern.test(pageUrl)) {
      pageCategories[category].push({
        url: pageUrl,
        title: pageData.title || '',
        description: pageData.description || '',
        content: pageData.content || pageData.body || pageData.html || '',
        metaData: {
          keywords: pageData.keywords || [],
          author: pageData.author || '',
          date: pageData.date || pageData.publishedDate || '',
          lang: pageData.lang || 'en'
        }
      });
      categorized = true;
      break; // Одна сторінка = одна категорія
    }
  }

  // Якщо не підійшла під жодну категорію - в other
  if (!categorized) {
    pageCategories.other.push({
      url: pageUrl,
      title: pageData.title || '',
      description: pageData.description || ''
    });
  }
});

// Статистика
console.log('📈 Categorization results:');
console.log('  Blog articles:', pageCategories.blog.length);
console.log('  News:', pageCategories.news.length);
console.log('  Reviews/Testimonials:', pageCategories.reviews.length + pageCategories.testimonials.length);
console.log('  About pages:', pageCategories.about.length);
console.log('  Pricing pages:', pageCategories.pricing.length);
console.log('  Features:', pageCategories.features.length);
console.log('  Products/Solutions:', pageCategories.products.length + pageCategories.solutions.length);
console.log('  Case Studies:', pageCategories.caseStudies.length);
console.log('  Other:', pageCategories.other.length);

// Повертаємо відфільтровані та категоризовані дані
return {
  company: companyName,
  mainUrl: mainUrl,
  totalParsed: parsedData.length,
  categories: pageCategories,
  stats: {
    blog: pageCategories.blog.length,
    news: pageCategories.news.length,
    reviews: pageCategories.reviews.length + pageCategories.testimonials.length,
    about: pageCategories.about.length,
    pricing: pageCategories.pricing.length,
    features: pageCategories.features.length,
    products: pageCategories.products.length + pageCategories.solutions.length,
    caseStudies: pageCategories.caseStudies.length
  },
  parsedAt: new Date().toISOString()
};

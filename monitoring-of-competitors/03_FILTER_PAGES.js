// КРОК 3: Фільтруємо потрібні сторінки (ГНУЧКО)
// Цей код фільтрує URLs по категоріям

const url = $input.item.json.url || '';

console.log('🔎 Checking URL:', url);

// Категорії та гнучкі patterns (case-insensitive, різні варіанти)
const categories = {
    blog: /\/(blog|blogs|article|articles|post|posts|insights|news-blog|блог|блоги)/i,
    news: /\/(news|новини|новости|actualit[eé]s|press|noticias|announcements|newsroom)/i,
    reviews: /\/(review|reviews|отзыв|отзывы|testimonial|testimonials|customer-stories|success-stories|case-studies)/i,
    pricing: /\/(pricing|price|prices|plans|тариф|ціни|цены|tarif|cost)/i,
    features: /\/(features|feature|можливост|функц|capabilities|product-features|fonctionnalit)/i,
    about: /\/(about|про-нас|о-нас|company|who-we-are|team|our-team|sobre|à-propos)/i,
    contact: /\/(contact|support|help|підтримк|контакт|soporte)/i,
    careers: /\/(career|careers|job|jobs|vacancy|vacancies|hiring|join|робота|emploi)/i,
    solutions: /\/(solution|solutions|use-case|use-cases|industry|industries)/i,
    products: /\/(product|products|service|services|послуг|produit)/i
};

// Перевіряємо URL на відповідність категоріям
let matchedCategory = null;
for (const [category, pattern] of Object.entries(categories)) {
    if (pattern.test(url)) {
        matchedCategory = category;
        console.log(`✅ Matched category: ${category}`);
        break;
    }
}

// Якщо не підходить під жодну категорію - пропускаємо
if (!matchedCategory) {
    console.log('⏭️ URL не відповідає жодній категорії');
    return null; // Це видалить item з потоку
}

// Повертаємо URL з категорією
return {
    url: url,
    category: matchedCategory,
    timestamp: new Date().toISOString()
};

// Parse AI JSON - SIMPLIFIED VERSION
const response = $input.item.json;

// Змінні на верхньому рівні
let rawContent = '';
let parsedData = null;

try {
  // Витягуємо content з різних можливих структур
  if (response.output) {
    rawContent = response.output;
  } else if (response.text) {
    rawContent = response.text;
  } else if (response.choices && response.choices[0] && response.choices[0].message) {
    rawContent = response.choices[0].message.content;
  } else {
    rawContent = JSON.stringify(response);
  }

  // Видаляємо markdown блоки
  rawContent = rawContent.replace(/```json\n?/g, '');
  rawContent = rawContent.replace(/```\n?/g, '');
  rawContent = rawContent.trim();

  // Парсимо JSON
  if (typeof rawContent === 'string') {
    parsedData = JSON.parse(rawContent);
  } else {
    parsedData = rawContent;
  }

  // Перевіряємо обов'язкові поля
  const requiredFields = [
    'company', 'url', 'youtubeActivity', 'linkedinActivity',
    'facebookActivity', 'aggregatorMentions', 'newFeatures',
    'problems', 'reviewInsights', 'news', 'blogArticles',
    'customerPains', 'customerWants', 'summary'
  ];

  for (let i = 0; i < requiredFields.length; i++) {
    const field = requiredFields[i];
    if (!parsedData.hasOwnProperty(field)) {
      throw new Error('Missing field: ' + field);
    }
  }

} catch (err) {
  // Логуємо помилку
  console.error('Parsing error:', err.message);
  console.error('Raw content:', rawContent);

  // Повертаємо fallback дані
  parsedData = {
    company: 'Unknown',
    url: '',
    youtubeActivity: '-',
    linkedinActivity: '-',
    facebookActivity: '-',
    aggregatorMentions: '-',
    newFeatures: [],
    problems: ['Помилка парсингу AI: ' + err.message],
    reviewInsights: 'Дані недоступні',
    news: [],
    blogArticles: [],
    customerPains: [],
    customerWants: [],
    summary: 'Аналіз не вдався - потрібна ручна перевірка'
  };
}

// Повертаємо результат
return {
  company: parsedData.company,
  url: parsedData.url,
  youtubeActivity: parsedData.youtubeActivity,
  linkedinActivity: parsedData.linkedinActivity,
  facebookActivity: parsedData.facebookActivity,
  aggregatorMentions: parsedData.aggregatorMentions,
  aiAnalysis: {
    newFeatures: parsedData.newFeatures,
    problems: parsedData.problems,
    reviewInsights: parsedData.reviewInsights,
    news: parsedData.news,
    blogArticles: parsedData.blogArticles,
    customerPains: parsedData.customerPains,
    customerWants: parsedData.customerWants,
    summary: parsedData.summary
  },
  parsedAt: new Date().toISOString()
};

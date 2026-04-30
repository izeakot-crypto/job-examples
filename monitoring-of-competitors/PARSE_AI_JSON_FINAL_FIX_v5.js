// Parse AI JSON - FINAL FIX v5
// AI Agent тепер повертає ВСЕ в одному JSON (company, url, youtube, social, g2, aiAnalysis)
const response = $input.item.json;
let parsedData;
let content = ''; // Оголошуємо ТУТ, щоб була доступна в catch блоці

try {
  if (response.output) {
    content = response.output;
  } else if (response.text) {
    content = response.text;
  } else if (response.choices?.[0]?.message?.content) {
    content = response.choices[0].message.content;
  } else {
    content = JSON.stringify(response);
  }

  // Remove markdown code blocks if AI added them
  content = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

  parsedData = typeof content === 'string' ? JSON.parse(content) : content;

  // Validate required fields
  const required = ['company', 'url', 'youtubeActivity', 'linkedinActivity', 'facebookActivity',
                   'aggregatorMentions', 'newFeatures', 'problems', 'reviewInsights', 'news',
                   'blogArticles', 'customerPains', 'customerWants', 'summary'];

  for (const field of required) {
    if (!(field in parsedData)) {
      throw new Error(`Missing required field: ${field}`);
    }
  }

} catch (error) {
  console.error('AI JSON parsing error:', error.message);
  console.error('Raw content:', content); // Тепер content доступна тут
  parsedData = {
    company: 'Unknown',
    url: '',
    youtubeActivity: '-',
    linkedinActivity: '-',
    facebookActivity: '-',
    aggregatorMentions: '-',
    newFeatures: [],
    problems: [`Помилка парсингу AI: ${error.message}`],
    reviewInsights: 'Дані недоступні',
    news: [],
    blogArticles: [],
    customerPains: [],
    customerWants: [],
    summary: 'Аналіз не вдався - потрібна ручна перевірка'
  };
}

// Return ALL data - NO paired items access needed!
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

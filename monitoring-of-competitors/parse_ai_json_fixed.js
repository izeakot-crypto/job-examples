// Parse AI JSON response and handle errors - NO PAIRED ITEMS
const response = $input.item.json;
let aiData;

try {
  // AI Agent returns output in different format
  // Try to extract from output field or text field
  let content = '';

  if (response.output) {
    content = response.output;
  } else if (response.text) {
    content = response.text;
  } else if (response.choices?.[0]?.message?.content) {
    // Fallback for HTTP Request format
    content = response.choices[0].message.content;
  } else {
    // Try to use response directly if it's already JSON
    content = JSON.stringify(response);
  }

  // Parse JSON
  aiData = typeof content === 'string' ? JSON.parse(content) : content;

  // Validate required fields
  const required = ['newFeatures', 'problems', 'reviewInsights', 'news',
                   'blogArticles', 'customerPains', 'customerWants', 'summary'];

  for (const field of required) {
    if (!(field in aiData)) {
      throw new Error(`Missing required field: ${field}`);
    }
  }

} catch (error) {
  // Fallback structure on error
  console.error('AI JSON parsing error:', error.message);
  aiData = {
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

// Return only AI analysis without company/url to avoid paired item issues
return {
  aiAnalysis: aiData,
  parsedAt: new Date().toISOString()
};

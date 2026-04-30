// Collect all data - NO PAIRED ITEMS VERSION
const aiData = $input.item.json;

// Get AI analysis data
const aiAnalysis = aiData.aiAnalysis || {};

// Helper: convert array to comma-separated string
const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return '-';
  if (arr.length === 0) return '-';
  return arr.join(', ');
};

// Helper: convert blog articles to readable string
const blogToString = (articles) => {
  if (!Array.isArray(articles)) return '-';
  if (articles.length === 0) return '-';
  return articles.map(a =>
    `${a.title || 'Без назви'} (${a.date || 'дата невідома'}): ${(a.summary || '').substring(0, 100)}...`
  ).join(' | ');
};

// Create 16-column row
// Note: Company, URL and other branch data will be added by next node or manually
return {
  'Дата': new Date().toISOString().split('T')[0],
  'Компанія': 'TODO', // Will be filled from Loop or manually
  'URL': 'TODO', // Will be filled from Loop or manually
  'Нові фічі': arrayToString(aiAnalysis.newFeatures),
  'Проблеми': arrayToString(aiAnalysis.problems),
  'Інсайти з коментарів': aiAnalysis.reviewInsights || '-',
  'Новини (з останньої перевірки)': arrayToString(aiAnalysis.news),
  'Статті в блозі (з останньої перевірки)': blogToString(aiAnalysis.blogArticles),
  'YouTube активність': 'TODO', // Will be filled from parallel branch
  'Facebook активність': 'TODO', // Will be filled from parallel branch
  'LinkedIn активність': 'TODO', // Will be filled from parallel branch
  'Згадки на агрегаторах': 'TODO', // Will be filled from parallel branch
  'Кількість згадок в соцмережах': '0',
  'Болі клієнтів з коментарів': arrayToString(aiAnalysis.customerPains),
  'Хотілки клієнтів з коментарів': arrayToString(aiAnalysis.customerWants),
  'AI Summary': aiAnalysis.summary || '-'
};

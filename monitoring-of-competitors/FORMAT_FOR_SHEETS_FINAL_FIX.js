// Format for Sheets - FINAL FIX v4
// Тепер ВСІ дані приходять від Parse AI JSON Response1 (no paired items needed!)
const data = $input.item.json;

const aiAnalysis = data.aiAnalysis || {};
const company = data.company || 'Unknown';
const url = data.url || '';
const youtubeActivity = data.youtubeActivity || '-';
const linkedinActivity = data.linkedinActivity || '-';
const facebookActivity = data.facebookActivity || '-';
const aggregatorMentions = data.aggregatorMentions || '-';

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
return {
  'Дата': new Date().toISOString().split('T')[0],
  'Компанія': company,
  'URL': url,
  'Нові фічі': arrayToString(aiAnalysis.newFeatures),
  'Проблеми': arrayToString(aiAnalysis.problems),
  'Інсайти з коментарів': aiAnalysis.reviewInsights || '-',
  'Новини (з останньої перевірки)': arrayToString(aiAnalysis.news),
  'Статті в блозі (з останньої перевірки)': blogToString(aiAnalysis.blogArticles),
  'YouTube активність': youtubeActivity,
  'Facebook активність': facebookActivity,
  'LinkedIn активність': linkedinActivity,
  'Згадки на агрегаторах': aggregatorMentions,
  'Кількість згадок в соцмережах': '0',
  'Болі клієнтів з коментарів': arrayToString(aiAnalysis.customerPains),
  'Хотілки клієнтів з коментарів': arrayToString(aiAnalysis.customerWants),
  'AI Summary': aiAnalysis.summary || '-'
};

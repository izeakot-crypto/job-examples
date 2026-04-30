// Format for Sheets - PASS THROUGH VERSION
// Ця версія зберігає ВСІ дані і передає їх далі для Check/Update логіки

const data = $input.item.json;
const ai = data.aiAnalysis || {};

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
    `${a.title || '?'} (${a.date || 'дата невідома'}): ${(a.summary || '').substring(0, 100)}...`
  ).join(' | ');
};

// Create 16-column row + PASS THROUGH всіх оригінальних даних
const result = {
  // ===== FORMAT FOR GOOGLE SHEETS (16 колонок) =====
  'Дата': new Date().toISOString().split('T')[0],
  'Компанія': data.company || 'Unknown',
  'URL': data.url || '',
  'Нові фічі': arrayToString(ai.newFeatures),
  'Проблеми': arrayToString(ai.problems),
  'Інсайти з коментарів': ai.reviewInsights || '-',
  'Новини (з останньої перевірки)': arrayToString(ai.news),
  'Статті в блозі (з останньої перевірки)': blogToString(ai.blogArticles),
  'YouTube активність': data.youtubeActivity || '-',
  'Facebook активність': data.facebookActivity || '-',
  'LinkedIn активність': data.linkedinActivity || '-',
  'Згадки на агрегаторах': data.aggregatorMentions || '-',
  'Кількість згадок в соцмережах': String(data.socialMentionsCount || 0),
  'Болі клієнтів з коментарів': arrayToString(ai.customerPains),
  'Хотілки клієнтів з коментарів': arrayToString(ai.customerWants),
  'AI Summary': ai.summary || '-',

  // ===== PASS THROUGH - для подальшої обробки =====
  // Ці дані потрібні для наступних нод
  _originalData: {
    company: data.company,
    url: data.url,
    aiAnalysis: ai,
    parsedAt: data.parsedAt
  },

  // Маркер для Check If Company Exists - що це нові дані
  _isNewData: true,

  // Для зручності - ключові поля для пошуку
  _searchKey: {
    company: (data.company || '').toLowerCase().trim(),
    url: (data.url || '').toLowerCase().trim()
  }
};

console.log('Format for Sheets - Output keys:', Object.keys(result));
console.log('Format for Sheets - Company:', result['Компанія']);

return result;

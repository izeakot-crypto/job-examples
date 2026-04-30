// Format for Sheets - reads from Merge2 output
// Merge2 combines: [0]=Parse AI JSON Response1, [1]=Parse YouTube Data1, [2]=Format Social Activity1, [3]=Merge Aggregator Data

const allData = $input.all();

// Get AI analysis from index 0
const aiAnalysis = allData[0]?.json?.aiAnalysis || {};

// Get YouTube from index 1
const youtubeActivity = allData[1]?.json?.youtubeActivity || '-';

// Get Social from index 2
const linkedinActivity = allData[2]?.json?.linkedinActivity || '-';
const facebookActivity = allData[2]?.json?.facebookActivity || '-';

// Get G2 from index 3
const aggregatorMentions = allData[3]?.json?.aggregatorMentions || '-';

// Get company and URL from Loop (still accessible from execution context)
const loopData = $('Loop Companies1').item.json;
const company = loopData.company || loopData.name || loopData['Компанія'] || loopData['Company'] || 'Unknown';
const url = loopData.url || loopData.URL || loopData.link || '';

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

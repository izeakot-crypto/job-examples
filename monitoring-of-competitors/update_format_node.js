// Format for Sheets - PASS THROUGH VERSION
const data = $input.item.json;
const ai = data.aiAnalysis || {};

const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return "-";
  if (arr.length === 0) return "-";
  return arr.join(", ");
};

const blogToString = (articles) => {
  if (!Array.isArray(articles)) return "-";
  if (articles.length === 0) return "-";
  return articles.map(a => a.title + " (" + (a.date || "?") + "): " + (a.summary || "").substring(0, 100) + "...").join(" | ");
};

const result = {
  "Дата": new Date().toISOString().split("T")[0],
  "Компанія": data.company || "Unknown",
  "URL": data.url || "",
  "Нові фічі": arrayToString(ai.newFeatures),
  "Проблеми": arrayToString(ai.problems),
  "Інсайти з коментарів": ai.reviewInsights || "-",
  "Новини (з останньої перевірки)": arrayToString(ai.news),
  "Статті в блозі (з останньої перевірки)": blogToString(ai.blogArticles),
  "YouTube активність": data.youtubeActivity || "-",
  "Facebook активність": data.facebookActivity || "-",
  "LinkedIn активність": data.linkedinActivity || "-",
  "Згадки на агрегаторах": data.aggregatorMentions || "-",
  "Кількість згадок в соцмережах": String(data.socialMentionsCount || 0),
  "Болі клієнтів з коментарів": arrayToString(ai.customerPains),
  "Хотілки клієнтів з коментарів": arrayToString(ai.customerWants),
  "AI Summary": ai.summary || "-",
  _originalData: { company: data.company, url: data.url, parsedAt: data.parsedAt },
  _isNewData: true
};

console.log("Format for Sheets - Company:", result["Компанія"]);
return result;

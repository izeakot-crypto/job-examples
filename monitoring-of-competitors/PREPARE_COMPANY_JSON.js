// Формуємо JSON для відправки у workflow парсингу домену
const loopData = $('Loop Companies1').item.json;

// Витягуємо URL
let url = loopData.url || loopData.URL || loopData.link || loopData.website ||
          loopData.company || loopData.name || '';

// Якщо URL не починається з http, додаємо https://
if (url && !url.match(/^https?:\/\//i)) {
  url = 'https://' + url;
}

// Повертаємо JSON у форматі для execution
return {
  row_number: loopData.row_number || $itemIndex + 2,
  company: url
};

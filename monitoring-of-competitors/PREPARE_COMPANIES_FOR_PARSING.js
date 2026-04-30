// Підготовка компаній для відправки у workflow парсингу доменів
// Input: дані з Google Sheets (Loop Companies1)
const loopData = $('Loop Companies1').item.json;

// Витягуємо URL компанії
let url = loopData.url || loopData.URL || loopData.link || loopData.website ||
          loopData.company || loopData.name || '';

// Якщо це не URL, пропускаємо
if (!url || !url.match(/^https?:\/\//i)) {
  return {
    skip: true,
    reason: 'No valid URL found',
    originalData: loopData
  };
}

// Витягуємо domain з URL
let domain = '';
try {
  const urlObj = new URL(url);
  domain = urlObj.hostname.replace(/^www\./i, ''); // ringover.com
} catch (e) {
  return {
    skip: true,
    reason: 'Invalid URL format',
    url: url
  };
}

// Витягуємо назву компанії
let companyName = loopData.name || loopData.company || loopData['Компанія'] ||
                  loopData['Company'] || loopData['Назва'] || '';

// Якщо назва містить URL, витягуємо з domain
if (!companyName || companyName.match(/^https?:\/\//i)) {
  // ringover.com -> Ringover
  companyName = domain.split('.')[0];
  companyName = companyName.charAt(0).toUpperCase() + companyName.slice(1);
}

// Формуємо JSON для відправки у workflow парсингу доменів
return {
  company: url,  // Повний URL для парсингу
  companyName: companyName,  // Назва для ідентифікації
  domain: domain,  // Чистий domain
  row_number: loopData.row_number || $itemIndex + 2,  // Номер рядка
  originalUrl: url
};

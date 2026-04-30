const fs = require('fs');
const https = require('https');

// Читаємо поточний воркфлоу
const data = JSON.parse(fs.readFileSync('C:/Users/izeak/.claude/projects/C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors/c07261c1-a225-44cb-a2ce-90406882e3d3/tool-results/mcp-n8n-flexible-n8n_get_workflow-1766660497995.txt'));
const workflow = JSON.parse(data[0].text);

// Новий код для Extract & Filter URLs - розширені паттерни
const newExtractCode = `// Extract & Filter URLs - розширені паттерни для RU/UA сайтів
var scanResult = $input.item.json;
var allResults = scanResult.all_results || [];

var editFieldsData = $('Edit Fields').first().json;
var companyName = editFieldsData.companyName || 'Unknown';
var companyUrl = editFieldsData.companyUrl || '';

console.log('Extract URLs - Company:', companyName, 'Total URLs:', allResults.length);

// Розширені категорії - включають URL паттерни mango-office
var categories = {
  blog: /\\/(blog|blogs|article|articles|post|posts|insights|journal|novosti|stati|publikacii|news-blog)/i,
  news: /\\/(news|press|announcements|newsroom|press-centr|events|meropriyatiya|sobytiya)/i,
  reviews: /\\/(review|reviews|testimonial|testimonials|customer-stories|success-stories|case-studies|otzyvy|klienty|use_mango|clients)/i,
  pricing: /\\/(pricing|price|prices|plans|tarif|cost|tariffs|ceny|stoimost)/i,
  features: /\\/(features|feature|capabilities|product-features|vozmozhnosti|resheniya|funktsii|products\\/[^\\/]+\\/vozmozhnosti|products\\/[^\\/]+\\/resheniya)/i
};

var categorizedUrls = [];
var seenUrls = new Set();

for (var i = 0; i < allResults.length; i++) {
  var result = allResults[i];
  var url = result.url || '';

  // Пропускаємо якщо є помилки або вже бачили
  if (result.has_errors || seenUrls.has(url)) continue;
  seenUrls.add(url);

  // Пропускаємо головну сторінку та about
  if (url.match(/\\/$/) && !url.match(/\\/[a-z]+\\/$/i)) continue;
  if (url.match(/\\/about\\/?$/i)) continue;
  if (url.match(/\\/promo\\/?$/i)) continue;

  for (var cat in categories) {
    if (categories[cat].test(url)) {
      categorizedUrls.push({
        url: url,
        category: cat,
        status_code: result.status_code,
        companyName: companyName,
        companyUrl: companyUrl
      });
      break;
    }
  }
}

console.log('Filtered URLs by category:', categorizedUrls.length);
console.log('Categories:', JSON.stringify(categorizedUrls.map(u => u.category + ': ' + u.url)));

if (categorizedUrls.length === 0) {
  return [{ json: { url: '', category: 'none', status_code: 0, companyName: companyName, companyUrl: companyUrl, message: 'No URLs matched categories' } }];
}

return categorizedUrls.map(function(item) { return { json: item }; });`;

// Знаходимо та оновлюємо ноду
const extractNode = workflow.nodes.find(n => n.name === 'Extract & Filter URLs');
if (extractNode) {
  extractNode.parameters.jsCode = newExtractCode;
  console.log('Updated Extract & Filter URLs');
} else {
  console.log('ERROR: Node not found!');
}

// Готуємо дані для API
const updateData = {
  name: workflow.name,
  nodes: workflow.nodes,
  connections: workflow.connections,
  settings: workflow.settings
};

// Зберігаємо для перевірки
fs.writeFileSync('C:/Users/izeak/OneDrive/Work.Oki-toki/Monitoring of competitors/workflow_with_new_extract.json', JSON.stringify(updateData, null, 2));
console.log('Saved workflow to workflow_with_new_extract.json');

// Відправляємо в n8n API
const postData = JSON.stringify(updateData);

const options = {
  hostname: 'n8nletsdo.online',
  port: 443,
  path: '/api/v1/workflows/qk1bISszvNIH6Ww7',
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(postData),
    'X-N8N-API-KEY': process.env.N8N_API_KEY || ''
  }
};

if (!process.env.N8N_API_KEY) {
  console.log('No API key - workflow saved to file, import manually');
  process.exit(0);
}

const req = https.request(options, (res) => {
  let data = '';
  res.on('data', (chunk) => data += chunk);
  res.on('end', () => {
    if (res.statusCode === 200) {
      console.log('Workflow updated successfully via API!');
    } else {
      console.log('API Error:', res.statusCode, data);
    }
  });
});

req.on('error', (e) => console.error('Request error:', e));
req.write(postData);
req.end();

const fs = require('fs');
const https = require('https');

const updateData = JSON.parse(fs.readFileSync('C:/Users/izeak/OneDrive/Work.Oki-toki/Monitoring of competitors/workflow_with_parse_reviews.json'));
const postData = JSON.stringify(updateData);

const apiKey = process.env.N8N_API_KEY;
if (!apiKey) {
  console.log('ERROR: N8N_API_KEY not set. Please set it first.');
  console.log('Workflow saved to workflow_with_parse_reviews.json - import manually.');
  process.exit(0);
}

const options = {
  hostname: 'n8nletsdo.online',
  port: 443,
  path: '/api/v1/workflows/qk1bISszvNIH6Ww7',
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(postData),
    'X-N8N-API-KEY': apiKey
  }
};

const req = https.request(options, (res) => {
  let data = '';
  res.on('data', (chunk) => data += chunk);
  res.on('end', () => {
    if (res.statusCode === 200) {
      console.log('SUCCESS: Workflow updated!');
    } else {
      console.log('ERROR:', res.statusCode, data.substring(0, 500));
    }
  });
});

req.on('error', (e) => console.error('Request error:', e));
req.write(postData);
req.end();

import json
import urllib.request
import sys
sys.stdout.reconfigure(encoding='utf-8')

N8N_URL = 'https://n8nletsdo.online'
WORKFLOW_ID = 'qk1bISszvNIH6Ww7'
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs'

url = f'{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}'
req = urllib.request.Request(url)
req.add_header('X-N8N-API-KEY', API_KEY)

with urllib.request.urlopen(req) as response:
    wf = json.loads(response.read().decode('utf-8'))

# Update Fetch G2 Page - add proper headers
for node in wf['nodes']:
    if node['name'] == 'Fetch G2 Page':
        node['parameters'] = {
            'url': "=https://www.g2.com/search?query={{ encodeURIComponent($('Edit Fields').item.json.companyName) }}",
            'sendHeaders': True,
            'headerParameters': {
                'parameters': [
                    {'name': 'User-Agent', 'value': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
                    {'name': 'Accept', 'value': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'},
                    {'name': 'Accept-Language', 'value': 'en-US,en;q=0.9'},
                    {'name': 'Accept-Encoding', 'value': 'gzip, deflate, br'},
                    {'name': 'Cache-Control', 'value': 'no-cache'},
                    {'name': 'Referer', 'value': 'https://www.google.com/'}
                ]
            },
            'options': {
                'response': {
                    'response': {
                        'neverError': True
                    }
                },
                'timeout': 30000
            }
        }
        print('Updated Fetch G2 Page with proper headers')
        break

# New improved Parse G2 Data code
parse_g2_code = """var html = $input.item.json.body || $input.item.json.data || '';
var statusCode = $input.item.json.statusCode || 200;
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';

// Check if blocked or error
if (statusCode === 403 || statusCode === 429) {
  return {
    company: company,
    g2Data: 'G2: Blocked (anti-bot protection)',
    g2Found: false,
    g2Rating: null,
    g2ReviewsCount: 0,
    g2Error: 'Access blocked by G2',
    g2StatusCode: statusCode
  };
}

if (!html || html.length < 1000) {
  return {
    company: company,
    g2Data: 'G2: No data received',
    g2Found: false,
    g2Rating: null,
    g2ReviewsCount: 0,
    g2Error: 'Empty response',
    g2StatusCode: statusCode
  };
}

// Multiple patterns to find rating
var ratingPatterns = [
  /(\\d+\\.\\d+)\\s*out of 5/i,
  /(\\d+\\.\\d+)\\s*\\/\\s*5/i,
  /\"rating\"\\s*:\\s*(\\d+\\.?\\d*)/i,
  /\"ratingValue\"\\s*:\\s*\"?(\\d+\\.?\\d*)/i,
  /data-rating=\"(\\d+\\.?\\d*)\"/i,
  /class=\"[^\"]*star[^\"]*\"[^>]*>(\\d+\\.?\\d*)/i,
  /average[\\s\\-_]?rating[\"\\s:>]*(\\d+\\.?\\d*)/i
];

var reviewPatterns = [
  /(\\d+[,\\d]*)\\s*reviews?/i,
  /(\\d+[,\\d]*)\\s*ratings?/i,
  /\"reviewCount\"\\s*:\\s*\"?(\\d+)/i,
  /\"ratingCount\"\\s*:\\s*\"?(\\d+)/i,
  /(\\d+[,\\d]*)\\s*verified/i
];

var rating = null;
var reviewsCount = null;
var productName = null;
var productUrl = null;

// Try to find rating
for (var i = 0; i < ratingPatterns.length; i++) {
  var match = html.match(ratingPatterns[i]);
  if (match && match[1]) {
    var num = parseFloat(match[1]);
    if (num > 0 && num <= 5) {
      rating = num;
      break;
    }
  }
}

// Try to find reviews count
for (var j = 0; j < reviewPatterns.length; j++) {
  var match = html.match(reviewPatterns[j]);
  if (match && match[1]) {
    reviewsCount = parseInt(match[1].replace(/,/g, ''));
    if (reviewsCount > 0) break;
  }
}

// Try to find product name
var nameMatch = html.match(/<h1[^>]*>([^<]+)<\\/h1>/i) ||
                html.match(/\"name\"\\s*:\\s*\"([^\"]+)\"/i) ||
                html.match(/class=\"product-name[^\"]*\"[^>]*>([^<]+)/i);
if (nameMatch) {
  productName = nameMatch[1].trim();
}

// Try to find product URL on G2
var urlMatch = html.match(/href=\"(\\/products\\/[^\"]+)\"/i) ||
               html.match(/href=\"(https:\\/\\/www\\.g2\\.com\\/products\\/[^\"]+)\"/i);
if (urlMatch) {
  productUrl = urlMatch[1].startsWith('http') ? urlMatch[1] : 'https://www.g2.com' + urlMatch[1];
}

// Check if we found the company in search results
var companyLower = company.toLowerCase().replace(/[-_\\s]/g, '');
var foundInResults = html.toLowerCase().includes(companyLower) ||
                     html.toLowerCase().includes(company.toLowerCase());

if (!rating && !foundInResults) {
  return {
    company: company,
    g2Data: 'G2: Not found in search results',
    g2Found: false,
    g2Rating: null,
    g2ReviewsCount: 0,
    g2ProductName: null,
    g2ProductUrl: null,
    g2SearchPerformed: true
  };
}

var g2Summary = '';
if (rating) {
  g2Summary = 'G2: ' + rating.toFixed(1) + '/5';
  if (reviewsCount) {
    g2Summary += ' (' + reviewsCount + ' reviews)';
  }
  if (productName) {
    g2Summary += ' - ' + productName;
  }
} else if (foundInResults) {
  g2Summary = 'G2: Found but no rating available';
} else {
  g2Summary = 'G2: Not found';
}

return {
  company: company,
  g2Data: g2Summary,
  g2Found: !!rating || foundInResults,
  g2Rating: rating,
  g2ReviewsCount: reviewsCount || 0,
  g2ProductName: productName,
  g2ProductUrl: productUrl,
  g2SearchPerformed: true
};"""

# New improved Merge Aggregator Data code
merge_aggregator_code = """var g2 = $input.item.json;
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';

// Build comprehensive aggregator summary
var aggregatorData = [];

// G2 data
if (g2.g2Found) {
  aggregatorData.push({
    platform: 'G2',
    rating: g2.g2Rating,
    reviewsCount: g2.g2ReviewsCount,
    productName: g2.g2ProductName,
    productUrl: g2.g2ProductUrl,
    summary: g2.g2Data
  });
}

// Create summary string
var aggregatorMentions = g2.g2Data || 'No aggregator data found';

return {
  company: company,
  aggregatorMentions: aggregatorMentions,
  g2Rating: g2.g2Rating || null,
  g2ReviewsCount: g2.g2ReviewsCount || 0,
  g2ProductUrl: g2.g2ProductUrl || null,
  g2Found: g2.g2Found || false,
  aggregatorData: aggregatorData
};"""

# Update nodes
for node in wf['nodes']:
    if node['name'] == 'Parse G2 Data':
        node['parameters']['jsCode'] = parse_g2_code
        print('Updated Parse G2 Data')
    elif node['name'] == 'Merge Aggregator Data':
        node['parameters']['jsCode'] = merge_aggregator_code
        print('Updated Merge Aggregator Data')

# Prepare update
valid_settings_keys = ['executionOrder', 'saveDataErrorExecution', 'saveDataSuccessExecution',
                       'saveManualExecutions', 'callerPolicy', 'errorWorkflow', 'timezone']
settings = {k: v for k, v in wf.get('settings', {}).items() if k in valid_settings_keys}

workflow_update = {
    'name': wf['name'],
    'nodes': wf['nodes'],
    'connections': wf['connections'],
    'settings': settings
}

# Send update
url = f'{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}'
data = json.dumps(workflow_update).encode('utf-8')

req = urllib.request.Request(url, data=data, method='PUT')
req.add_header('Content-Type', 'application/json')
req.add_header('X-N8N-API-KEY', API_KEY)

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print('SUCCESS! G2 aggregator nodes updated.')
        print('Updated at:', result.get('updatedAt', 'unknown'))
except urllib.error.HTTPError as e:
    print(f'Error {e.code}: {e.reason}')
    error_body = e.read().decode('utf-8')
    print('Response:', error_body[:1000])


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

# New code for Auto-detect Social Links1 - includes VK, Telegram, etc.
auto_detect_social_code = """var websiteHtml = $('Fetch Website1').item.json.body || $('Fetch Website1').item.json.data || '';
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';

// Helper function to extract URL
function extractUrl(html, pattern) {
  var match = html.match(pattern);
  return match ? match[0] : null;
}

// Helper to extract all matches
function extractAllUrls(html, pattern) {
  var matches = html.match(new RegExp(pattern.source, 'gi')) || [];
  return [...new Set(matches)]; // unique values
}

// Social media patterns - including Russian/CIS platforms
var patterns = {
  // International
  linkedin: /linkedin\\.com\\/(?:company|in)\\/[a-zA-Z0-9_-]+/i,
  facebook: /facebook\\.com\\/[a-zA-Z0-9._-]+/i,
  twitter: /(?:twitter|x)\\.com\\/[a-zA-Z0-9_]+/i,
  instagram: /instagram\\.com\\/[a-zA-Z0-9._]+/i,
  youtube: /youtube\\.com\\/(?:channel\\/|c\\/|user\\/|@)?[a-zA-Z0-9_-]+/i,

  // Russian/CIS platforms
  vk: /vk\\.com\\/[a-zA-Z0-9._-]+/i,
  telegram: /t\\.me\\/[a-zA-Z0-9_]+/i,
  ok: /ok\\.ru\\/[a-zA-Z0-9._-]+/i,
  dzen: /(?:dzen|zen)\\.yandex\\.ru\\/[a-zA-Z0-9._-]+/i,
  rutube: /rutube\\.ru\\/(?:channel|video)\\/[a-zA-Z0-9_-]+/i,

  // Other
  tiktok: /tiktok\\.com\\/@[a-zA-Z0-9._-]+/i,
  whatsapp: /(?:wa\\.me|whatsapp\\.com)\\/[a-zA-Z0-9_+-]+/i,
  viber: /viber\\.com\\/[a-zA-Z0-9_-]+/i
};

// Exclude patterns (not real social profiles)
var excludePatterns = {
  youtube: /youtube\\.com\\/(watch|embed|playlist|results|feed|channel\\/|c\\/|user\\/|@)?$/i,
  facebook: /facebook\\.com\\/(sharer|share|dialog|plugins)/i,
  twitter: /twitter\\.com\\/(intent|share)/i
};

var results = {
  company: company
};

// Extract all social links
for (var platform in patterns) {
  var url = extractUrl(websiteHtml, patterns[platform]);

  // Check if it's not an exclude pattern
  if (url && excludePatterns[platform] && excludePatterns[platform].test(url)) {
    url = null;
  }

  results[platform] = url;
}

// Count found links
var foundLinks = Object.keys(results).filter(function(key) {
  return key !== 'company' && results[key] !== null;
});

results.socialLinksCount = foundLinks.length;
results.foundPlatforms = foundLinks;

return results;"""

# New code for Format Social Activity1
format_social_code = """var data = $input.item.json;
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';

var activities = [];

// International platforms
if (data.linkedin) activities.push('LinkedIn: ' + data.linkedin);
if (data.facebook) activities.push('Facebook: ' + data.facebook);
if (data.twitter) activities.push('Twitter/X: ' + data.twitter);
if (data.instagram) activities.push('Instagram: ' + data.instagram);
if (data.youtube) activities.push('YouTube: ' + data.youtube);
if (data.tiktok) activities.push('TikTok: ' + data.tiktok);

// Russian/CIS platforms
if (data.vk) activities.push('VK: ' + data.vk);
if (data.telegram) activities.push('Telegram: ' + data.telegram);
if (data.ok) activities.push('OK.ru: ' + data.ok);
if (data.dzen) activities.push('Dzen: ' + data.dzen);
if (data.rutube) activities.push('RuTube: ' + data.rutube);

// Messengers
if (data.whatsapp) activities.push('WhatsApp: ' + data.whatsapp);
if (data.viber) activities.push('Viber: ' + data.viber);

return {
  company: company,
  linkedinActivity: data.linkedin ? 'LinkedIn: ' + data.linkedin : '-',
  facebookActivity: data.facebook ? 'Facebook: ' + data.facebook : '-',
  vkActivity: data.vk ? 'VK: ' + data.vk : '-',
  telegramActivity: data.telegram ? 'Telegram: ' + data.telegram : '-',
  youtubeActivity: data.youtube ? 'YouTube: ' + data.youtube : '-',
  allSocialLinks: activities.length > 0 ? activities.join('; ') : '-',
  socialLinksCount: data.socialLinksCount || 0,
  foundPlatforms: data.foundPlatforms || []
};"""

# Update nodes
for node in wf['nodes']:
    if node['name'] == 'Auto-detect Social Links1':
        node['parameters']['jsCode'] = auto_detect_social_code
        print('Updated Auto-detect Social Links1')
    elif node['name'] == 'Format Social Activity1':
        node['parameters']['jsCode'] = format_social_code
        print('Updated Format Social Activity1')

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
        print('SUCCESS! Social links detection updated.')
        print('Updated at:', result.get('updatedAt', 'unknown'))
except urllib.error.HTTPError as e:
    print(f'Error {e.code}: {e.reason}')
    error_body = e.read().decode('utf-8')
    print('Response:', error_body[:1000])


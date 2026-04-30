import json
import urllib.request
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Get fresh workflow
N8N_URL = 'https://n8nletsdo.online'
WORKFLOW_ID = 'qk1bISszvNIH6Ww7'
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs'

url = f'{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}'
req = urllib.request.Request(url)
req.add_header('X-N8N-API-KEY', API_KEY)

with urllib.request.urlopen(req) as response:
    wf = json.loads(response.read().decode('utf-8'))

# Fix Auto-detect YouTube Channel1 code
auto_detect_code = """var websiteHtml = $('Fetch Website1').item.json.body || $('Fetch Website1').item.json.data || '';
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var companyName = editFieldsData.companyName || loopData.companyName || 'Unknown';

var youtubePatterns = [
  { pattern: /youtube\\.com\\/channel\\/([a-zA-Z0-9_-]+)/i, type: 'channelId' },
  { pattern: /youtube\\.com\\/c\\/([a-zA-Z0-9_-]+)/i, type: 'customUrl' },
  { pattern: /youtube\\.com\\/user\\/([a-zA-Z0-9_-]+)/i, type: 'username' },
  { pattern: /youtube\\.com\\/@([a-zA-Z0-9_-]+)/i, type: 'handle' },
  { pattern: /youtube\\.com\\/([a-zA-Z][a-zA-Z0-9_-]{2,})(?:[\\/\"'\\s\\?]|$)/i, type: 'legacyUsername' }
];

var excludeWords = ['watch', 'embed', 'playlist', 'results', 'feed', 'gaming',
  'premium', 'music', 'kids', 'tv', 'shorts', 'live', 'about', 'redirect',
  'howyoutubeworks', 'yt', 'creators', 'ads', 'upload', 'attribution_link',
  'channel', 'user', 'c', 'hashtag', 'trending', 'subscription', 'account'];

var channelId = null;
var channelHandle = null;
var youtubeUrl = null;
var matchType = null;

for (var i = 0; i < youtubePatterns.length; i++) {
  var match = websiteHtml.match(youtubePatterns[i].pattern);
  if (match && match[1] && excludeWords.indexOf(match[1].toLowerCase()) === -1) {
    channelHandle = match[1];
    matchType = youtubePatterns[i].type;

    if (matchType === 'channelId') {
      youtubeUrl = 'https://www.youtube.com/channel/' + channelHandle;
      channelId = channelHandle;
    } else if (matchType === 'handle') {
      youtubeUrl = 'https://www.youtube.com/@' + channelHandle;
    } else {
      youtubeUrl = 'https://www.youtube.com/' + channelHandle;
    }
    break;
  }
}

return {
  company: companyName,
  youtubeChannelId: channelId,
  youtubeHandle: channelHandle,
  youtubeUrl: youtubeUrl,
  autoDetected: !!channelHandle,
  matchType: matchType
};"""

# Fix Parse YouTube Data1 code
parse_youtube_code = """var response = $input.item.json;
var resolveData = $('Resolve YouTube ChannelId').item.json;
var autoDetectData = $('Auto-detect YouTube Channel1').item.json;
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';

// If channel not found on site
if (!autoDetectData.autoDetected) {
  return {
    company: company,
    youtubeActivity: 'YouTube channel not found on site',
    youtubeVideoCount: 0,
    youtubeUrl: null
  };
}

// If channel resolve failed
if (!resolveData.items || resolveData.items.length === 0) {
  return {
    company: company,
    youtubeActivity: 'YouTube channel could not be resolved: ' + autoDetectData.youtubeHandle,
    youtubeVideoCount: 0,
    youtubeUrl: autoDetectData.youtubeUrl
  };
}

// If no videos in response
if (!response.items || response.items.length === 0) {
  return {
    company: company,
    youtubeActivity: 'No new videos this week',
    youtubeVideoCount: 0,
    youtubeUrl: autoDetectData.youtubeUrl,
    youtubeChannelName: resolveData.items[0].snippet.title
  };
}

var videos = response.items;
var videoCount = videos.length;
var latestVideo = videos[0];
var channelInfo = resolveData.items[0];

return {
  company: company,
  youtubeActivity: videoCount + ' new videos. Latest: "' + latestVideo.snippet.title + '" (' + latestVideo.snippet.publishedAt.split('T')[0] + ')',
  youtubeVideoCount: videoCount,
  youtubeUrl: autoDetectData.youtubeUrl,
  youtubeChannelName: channelInfo.snippet.title,
  youtubeVideos: videos.slice(0, 3).map(function(v) {
    return {
      title: v.snippet.title,
      publishedAt: v.snippet.publishedAt,
      url: 'https://www.youtube.com/watch?v=' + v.id.videoId
    };
  })
};"""

# Update nodes
for node in wf['nodes']:
    if node['name'] == 'Auto-detect YouTube Channel1':
        node['parameters']['jsCode'] = auto_detect_code
        print('Fixed Auto-detect YouTube Channel1')
    elif node['name'] == 'Parse YouTube Data1':
        node['parameters']['jsCode'] = parse_youtube_code
        print('Fixed Parse YouTube Data1')
    elif node['name'] == 'YouTube API Search1':
        # Fix channelId parameter
        for param in node['parameters']['queryParameters']['parameters']:
            if param['name'] == 'channelId':
                param['value'] = "={{ $json.items && $json.items[0] ? $json.items[0].id : $('Auto-detect YouTube Channel1').item.json.youtubeChannelId }}"
                print('Fixed YouTube API Search1 channelId')
                break

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
        print('SUCCESS! Workflow fixed.')
        print('Updated at:', result.get('updatedAt', 'unknown'))
except urllib.error.HTTPError as e:
    print(f'Error {e.code}: {e.reason}')
    error_body = e.read().decode('utf-8')
    print('Response:', error_body[:1000])


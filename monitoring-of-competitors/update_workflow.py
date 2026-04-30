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

# Find position of Auto-detect YouTube Channel1 node
auto_detect_pos = None
youtube_api_pos = None
for node in wf['nodes']:
    if node['name'] == 'Auto-detect YouTube Channel1':
        auto_detect_pos = node['position']
    if node['name'] == 'YouTube API Search1':
        youtube_api_pos = node['position']

print('Auto-detect position:', auto_detect_pos)
print('YouTube API position:', youtube_api_pos)

# New node position - between Auto-detect and YouTube API
new_node_pos = [auto_detect_pos[0] + 110, auto_detect_pos[1]]

# Create new Resolve YouTube ChannelId node
resolve_node = {
    'parameters': {
        'url': 'https://www.googleapis.com/youtube/v3/channels',
        'authentication': 'predefinedCredentialType',
        'nodeCredentialType': 'googleApi',
        'sendQuery': True,
        'queryParameters': {
            'parameters': [
                {'name': 'part', 'value': 'id,snippet'},
                {'name': 'forUsername', 'value': '={{ $json.youtubeHandle }}'},
                {'name': 'key', 'value': '={{ $credentials.youtubeApiKey }}'}
            ]
        },
        'options': {
            'response': {
                'response': {
                    'neverError': True
                }
            }
        }
    },
    'id': 'resolve-youtube-channelid-001',
    'name': 'Resolve YouTube ChannelId',
    'type': 'n8n-nodes-base.httpRequest',
    'typeVersion': 4.2,
    'position': new_node_pos,
    'credentials': {
        'googleApi': {
            'id': 'BusW9DlkA4x5GyCq',
            'name': 'Google Service Account account'
        }
    }
}

wf['nodes'].append(resolve_node)
print('Added Resolve YouTube ChannelId node')

# Update connections
# Before: Auto-detect YouTube Channel1 -> YouTube API Search1
# After: Auto-detect YouTube Channel1 -> Resolve YouTube ChannelId -> YouTube API Search1

# Remove old connection from Auto-detect to YouTube API
if 'Auto-detect YouTube Channel1' in wf['connections']:
    old_conns = wf['connections']['Auto-detect YouTube Channel1']
    # Keep other connections, remove YouTube API Search1
    new_main = []
    for conn_list in old_conns.get('main', []):
        filtered = [c for c in conn_list if c.get('node') != 'YouTube API Search1']
        new_main.append(filtered)
    # Add connection to Resolve node
    if new_main:
        new_main[0].append({'node': 'Resolve YouTube ChannelId', 'type': 'main', 'index': 0})
    else:
        new_main = [[{'node': 'Resolve YouTube ChannelId', 'type': 'main', 'index': 0}]]
    wf['connections']['Auto-detect YouTube Channel1']['main'] = new_main

# Add connection from Resolve to YouTube API
wf['connections']['Resolve YouTube ChannelId'] = {
    'main': [[{'node': 'YouTube API Search1', 'type': 'main', 'index': 0}]]
}

print('Updated connections')

# Also update Parse YouTube Data1 code to handle resolved channelId
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

for node in wf['nodes']:
    if node['name'] == 'Parse YouTube Data1':
        node['parameters']['jsCode'] = parse_youtube_code
        print('Updated Parse YouTube Data1')
        break

# Update YouTube API Search1 to use resolved channelId
for node in wf['nodes']:
    if node['name'] == 'YouTube API Search1':
        # Update channelId parameter to use resolved data
        for param in node['parameters']['queryParameters']['parameters']:
            if param['name'] == 'channelId':
                param['value'] = "={{ $json.items && $json.items[0] ? $json.items[0].id : $('Auto-detect YouTube Channel1').item.json.youtubeChannelId }}"
                print('Updated YouTube API Search1 channelId parameter')
                break
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
        print('SUCCESS! Workflow updated with new node and connections.')
        print('Updated at:', result.get('updatedAt', 'unknown'))
except urllib.error.HTTPError as e:
    print(f'Error {e.code}: {e.reason}')
    error_body = e.read().decode('utf-8')
    print('Response:', error_body[:1000])


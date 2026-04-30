import json
import urllib.request
import sys
sys.stdout.reconfigure(encoding='utf-8')

N8N_URL = 'https://n8nletsdo.online'
WORKFLOW_ID = 'qk1bISszvNIH6Ww7'
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs'

# Get current workflow
url = f'{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}'
req = urllib.request.Request(url)
req.add_header('X-N8N-API-KEY', API_KEY)

with urllib.request.urlopen(req) as response:
    wf = json.loads(response.read().decode('utf-8'))

print('Current nodes:')
for node in wf['nodes']:
    print(f"  - {node['name']} ({node['type']})")

# Find AI Agent node
ai_agent = None
for node in wf['nodes']:
    if node['name'] == 'AI Agent':
        ai_agent = node
        break

if not ai_agent:
    print('ERROR: AI Agent node not found!')
    sys.exit(1)

print(f"\nAI Agent position: {ai_agent['position']}")

# Find existing tool nodes
tool_nodes = [n for n in wf['nodes'] if 'Tool' in n.get('type', '')]
print(f"Existing Tool nodes: {[t['name'] for t in tool_nodes]}")

# Check connections to AI Agent
ai_connections = wf.get('connections', {}).get('AI Agent', {})
print(f"AI Agent connections: {ai_connections}")

# Find what's connected TO AI Agent (as tools)
connected_to_ai = []
for node_name, outputs in wf.get('connections', {}).items():
    for output_type, connections in outputs.items():
        for conn_list in connections:
            for conn in conn_list:
                if conn.get('node') == 'AI Agent':
                    connected_to_ai.append({'from': node_name, 'type': output_type, 'index': conn.get('index', 0)})

print(f"\nNodes connected TO AI Agent: {connected_to_ai}")

# VK Group Info Tool code
vk_tool_code = '''const input = $input.item.json.query || $input.item.json.input || '';

let groupId = input
  .replace('https://vk.com/', '')
  .replace('http://vk.com/', '')
  .replace('vk.com/', '')
  .replace('/', '')
  .trim();

try {
  const publicUrl = `https://vk.com/${groupId}`;
  const response = await fetch(publicUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    }
  });

  const html = await response.text();

  let groupName = null;
  let membersCount = null;
  let description = null;

  const nameMatch = html.match(/<title>([^<]+)<\\/title>/i);
  if (nameMatch) groupName = nameMatch[1].replace(' | VK', '').trim();

  const membersMatch = html.match(/(\\d+[\\s,.]?\\d*)\\s*(?:подписчик|участник|member|follower)/i);
  if (membersMatch) membersCount = parseInt(membersMatch[1].replace(/[\\s,.]/g, ''));

  const descMatch = html.match(/<meta[^>]*name="description"[^>]*content="([^"]+)"/i);
  if (descMatch) description = descMatch[1];

  return {
    groupId: groupId,
    groupName: groupName,
    groupUrl: publicUrl,
    membersCount: membersCount,
    description: description,
    dataSource: 'public page parsing'
  };
} catch (error) {
  return {
    error: error.message,
    groupId: groupId,
    groupUrl: `https://vk.com/${groupId}`
  };
}'''

# Telegram Channel Info Tool code
telegram_tool_code = '''const input = $input.item.json.query || $input.item.json.input || '';

let channelUsername = input
  .replace('https://t.me/', '')
  .replace('http://t.me/', '')
  .replace('t.me/', '')
  .replace('@', '')
  .replace('/', '')
  .trim();

try {
  const url = `https://t.me/s/${channelUsername}`;
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9'
    }
  });

  const html = await response.text();

  if (!html || html.length < 500) {
    return {
      channelUsername: channelUsername,
      channelUrl: `https://t.me/${channelUsername}`,
      error: 'Channel not found or private',
      isPrivate: true
    };
  }

  let channelName = null;
  let channelDescription = null;
  let subscribersCount = null;

  const nameMatch = html.match(/<meta property="og:title" content="([^"]+)"/i);
  if (nameMatch) channelName = nameMatch[1].trim();

  const descMatch = html.match(/<meta property="og:description" content="([^"]+)"/i);
  if (descMatch) channelDescription = descMatch[1].trim();

  const subsMatch = html.match(/([\\d\\s,\\.]+)\\s*(?:subscribers?|members?)/i);
  if (subsMatch) subscribersCount = parseInt(subsMatch[1].replace(/[\\s,\\.]/g, ''));

  const messageTexts = html.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\\s\\S]*?)<\\/div>/gi) || [];
  const posts = [];

  for (let i = 0; i < Math.min(messageTexts.length, 5); i++) {
    let text = messageTexts[i]
      .replace(/<[^>]+>/g, ' ')
      .replace(/\\s+/g, ' ')
      .trim()
      .substring(0, 200);
    if (text.length > 10) {
      posts.push({ text: text });
    }
  }

  return {
    channelUsername: channelUsername,
    channelName: channelName,
    channelUrl: `https://t.me/${channelUsername}`,
    description: channelDescription,
    subscribersCount: subscribersCount,
    recentPosts: posts,
    postsCount: posts.length,
    isPrivate: false
  };
} catch (error) {
  return {
    error: error.message,
    channelUsername: channelUsername,
    channelUrl: `https://t.me/${channelUsername}`
  };
}'''

# Website Parser Tool code
website_tool_code = '''const input = $input.item.json.query || $input.item.json.input || '';

let url = input.trim();
if (!url.startsWith('http://') && !url.startsWith('https://')) {
  url = 'https://' + url;
}

try {
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8'
    },
    redirect: 'follow'
  });

  const html = await response.text();

  if (!html || html.length < 100) {
    return { error: 'Empty response', url: url };
  }

  const titleMatch = html.match(/<title[^>]*>([^<]+)<\\/title>/i);
  const title = titleMatch ? titleMatch[1].trim() : null;

  const descMatch = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)/i);
  const description = descMatch ? descMatch[1].trim() : null;

  const h1Matches = html.match(/<h1[^>]*>([^<]+)<\\/h1>/gi) || [];
  const h1Tags = h1Matches.map(h => h.replace(/<[^>]+>/g, '').trim()).filter(h => h.length > 0);

  const phoneMatches = html.match(/(?:\\+7|8)[\\s\\-\\(]*\\d{3}[\\s\\-\\)]*\\d{3}[\\s\\-]*\\d{2}[\\s\\-]*\\d{2}/g) || [];
  const phones = [...new Set(phoneMatches)].slice(0, 5);

  const emailMatches = html.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g) || [];
  const emails = [...new Set(emailMatches)].filter(e => !e.includes('example')).slice(0, 5);

  return {
    url: url,
    title: title,
    description: description,
    h1: h1Tags,
    phones: phones,
    emails: emails,
    pageSize: html.length
  };
} catch (error) {
  return {
    error: error.message,
    url: url
  };
}'''

# G2 Search Tool code
g2_tool_code = '''const input = $input.item.json.query || $input.item.json.input || '';
const searchQuery = input.trim();

try {
  const searchUrl = `https://www.g2.com/search?query=${encodeURIComponent(searchQuery)}`;

  const response = await fetch(searchUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Referer': 'https://www.google.com/',
      'Cache-Control': 'no-cache'
    }
  });

  if (response.status === 403 || response.status === 429) {
    return {
      query: searchQuery,
      error: 'G2 blocked the request (anti-bot protection)',
      statusCode: response.status,
      suggestion: 'Try using Google search with "site:g2.com ' + searchQuery + '"',
      searchUrl: searchUrl
    };
  }

  const html = await response.text();

  if (!html || html.length < 1000) {
    return {
      query: searchQuery,
      error: 'No data received from G2',
      searchUrl: searchUrl
    };
  }

  const products = [];
  const jsonLdMatch = html.match(/<script type="application\\/ld\\+json">([\\s\\S]*?)<\\/script>/gi);
  if (jsonLdMatch) {
    for (const match of jsonLdMatch) {
      try {
        const jsonStr = match.replace(/<script[^>]*>/, '').replace(/<\\/script>/, '');
        const data = JSON.parse(jsonStr);
        if (data['@type'] === 'Product' || data['@type'] === 'SoftwareApplication') {
          products.push({
            name: data.name,
            rating: data.aggregateRating?.ratingValue || null,
            reviewCount: data.aggregateRating?.reviewCount || null,
            description: (data.description || '').substring(0, 200),
            url: data.url || null
          });
        }
      } catch (e) {}
    }
  }

  let pageRating = null;
  let pageReviews = null;

  const ratingMatch = html.match(/(\\d+\\.?\\d*)\\s*out of 5/i) ||
                      html.match(/\\"ratingValue\\"\\s*:\\s*\\"?(\\d+\\.?\\d*)/i);
  if (ratingMatch) pageRating = parseFloat(ratingMatch[1]);

  const reviewMatch = html.match(/(\\d+[,\\d]*)\\s*reviews?/i) ||
                      html.match(/\\"reviewCount\\"\\s*:\\s*\\"?(\\d+)/i);
  if (reviewMatch) pageReviews = parseInt(reviewMatch[1].replace(/,/g, ''));

  return {
    query: searchQuery,
    searchUrl: searchUrl,
    found: products.length > 0,
    productsCount: products.length,
    products: products.slice(0, 5),
    pageRating: pageRating,
    pageReviews: pageReviews
  };
} catch (error) {
  return {
    query: searchQuery,
    error: error.message,
    searchUrl: `https://www.g2.com/search?query=${encodeURIComponent(searchQuery)}`
  };
}'''

# Define new tool nodes
ai_pos = ai_agent['position']
new_tools = [
    {
        'name': 'VK Group Info Tool',
        'type': '@n8n/n8n-nodes-langchain.toolCode',
        'typeVersion': 1.2,
        'position': [ai_pos[0] - 200, ai_pos[1] + 400],
        'parameters': {
            'name': 'vk_group_info',
            'description': 'Get information about a VKontakte (VK) group or page including members count and description. Input should be VK URL or group ID (e.g., vk.com/mangotelecom or mangotelecom).',
            'jsCode': vk_tool_code
        }
    },
    {
        'name': 'Telegram Channel Tool',
        'type': '@n8n/n8n-nodes-langchain.toolCode',
        'typeVersion': 1.2,
        'position': [ai_pos[0], ai_pos[1] + 400],
        'parameters': {
            'name': 'telegram_channel_info',
            'description': 'Get information about a Telegram channel including subscribers count and recent posts. Input should be Telegram URL or username (e.g., t.me/mango_office or mango_office).',
            'jsCode': telegram_tool_code
        }
    },
    {
        'name': 'Website Parser Tool',
        'type': '@n8n/n8n-nodes-langchain.toolCode',
        'typeVersion': 1.2,
        'position': [ai_pos[0] + 200, ai_pos[1] + 400],
        'parameters': {
            'name': 'website_parser',
            'description': 'Fetch and parse any website to extract title, description, headings, phones, and emails. Input should be a full URL.',
            'jsCode': website_tool_code
        }
    },
    {
        'name': 'G2 Search Tool',
        'type': '@n8n/n8n-nodes-langchain.toolCode',
        'typeVersion': 1.2,
        'position': [ai_pos[0] + 400, ai_pos[1] + 400],
        'parameters': {
            'name': 'g2_search',
            'description': 'Search for a company/product on G2.com to get ratings and reviews. Input should be the company or product name.',
            'jsCode': g2_tool_code
        }
    }
]

# Check if tools already exist
existing_names = [n['name'] for n in wf['nodes']]
tools_to_add = []
for tool in new_tools:
    if tool['name'] not in existing_names:
        tools_to_add.append(tool)
        print(f"Will add: {tool['name']}")
    else:
        print(f"Already exists: {tool['name']}")

if not tools_to_add:
    print("\nAll tools already exist!")
else:
    # Add new tool nodes
    for tool in tools_to_add:
        wf['nodes'].append(tool)

    # Add connections from tools to AI Agent
    if 'connections' not in wf:
        wf['connections'] = {}

    for tool in tools_to_add:
        wf['connections'][tool['name']] = {
            'ai_tool': [[{'node': 'AI Agent', 'type': 'ai_tool', 'index': 0}]]
        }

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
    data = json.dumps(workflow_update).encode('utf-8')

    req = urllib.request.Request(url, data=data, method='PUT')
    req.add_header('Content-Type', 'application/json')
    req.add_header('X-N8N-API-KEY', API_KEY)

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f'\nSUCCESS! Added {len(tools_to_add)} tools to workflow.')
            print('Tools added:', [t['name'] for t in tools_to_add])
            print('Updated at:', result.get('updatedAt', 'unknown'))
    except urllib.error.HTTPError as e:
        print(f'Error {e.code}: {e.reason}')
        error_body = e.read().decode('utf-8')
        print('Response:', error_body[:1000])


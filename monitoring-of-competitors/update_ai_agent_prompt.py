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

# Find AI Agent and update system message
for node in wf['nodes']:
    if node['name'] == 'AI Agent':
        new_system_message = """Ти аналітик конкурентів. Повертай ТІЛЬКИ valid JSON без markdown.

ДОСТУПНІ ІНСТРУМЕНТИ:
1. youtube_channel_info - отримати інформацію про YouTube канал (підписники, відео, опис). Input: URL або назва каналу.
2. youtube_search - пошук відео на YouTube. Input: пошуковий запит.
3. vk_group_info - інформація про VK групу (учасники, опис). Input: vk.com/group або group_id.
4. telegram_channel_info - інформація про Telegram канал (підписники, пости). Input: t.me/channel або username.
5. website_parser - парсинг веб-сайту (title, description, phones, emails). Input: URL.
6. g2_search - пошук на G2.com (рейтинги, відгуки). Input: назва компанії.
7. Wikipedia - загальна інформація про компанії.

ІНСТРУКЦІЇ:
- Якщо є URL соцмереж (VK, Telegram, YouTube) - ОБОВ'ЯЗКОВО використай відповідні tools для отримання деталей
- Аналізуй активність: скільки підписників, як часто публікують
- Шукай додаткову інформацію про компанію якщо даних недостатньо
- Повертай ТІЛЬКИ valid JSON без ```markdown```"""

        node['parameters']['options']['systemMessage'] = new_system_message
        print('Updated AI Agent system message')
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
data = json.dumps(workflow_update).encode('utf-8')

req = urllib.request.Request(url, data=data, method='PUT')
req.add_header('Content-Type', 'application/json')
req.add_header('X-N8N-API-KEY', API_KEY)

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print('SUCCESS! AI Agent system prompt updated.')
        print('Updated at:', result.get('updatedAt', 'unknown'))
except urllib.error.HTTPError as e:
    print(f'Error {e.code}: {e.reason}')
    error_body = e.read().decode('utf-8')
    print('Response:', error_body[:1000])


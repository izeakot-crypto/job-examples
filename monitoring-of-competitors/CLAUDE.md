# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Competitor monitoring system for Oki-toki (contact center/telephony SaaS). Automatically collects and analyzes data from 19 competitor companies using n8n workflows, stores results in Google Sheets.

## n8n Workflows

### Production Workflow (n8n.oki-toki.net)
- **URL**: https://n8n.oki-toki.net/workflow/i8tUO6CtinXxJFu2
- **ID**: `i8tUO6CtinXxJFu2`
- **Name**: "Monitoring of Competitors"

### Development Workflow (n8nletsdo.online)
- **URL**: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7
- **ID**: `qk1bISszvNIH6Ww7`
- **Name**: "Monitoring of Competitors v2"

### Architecture
```
Schedule Trigger → Google Sheets (company list) → Loop Companies
    ↓
Edit Fields
    ↓
┌───────────────────────────────────┬──────────────────────────┐
↓                                   ↓                          ↓
Fetch Website                       Call 'website checker_backup'
↓                                   ↓
├─ Auto-detect YouTube → API        Extract & Filter URLs
├─ Auto-detect Social Links         ↓
└─ Fetch G2 Page                    Loop Over Items → Parse Pages
    ↓                               ↓
Merge6 (4 inputs) ←─────────────────┘
    ↓
AI Agent (OpenAI gpt-4.1-mini)
    ↓
Parse AI JSON → Format for Sheets
    ↓
Check If Exists → Update/Append Row → Loop
```

### AI Agent Tools (7 available)
1. `youtube_channel_info` - YouTube channel details
2. `youtube_search` - search videos
3. `vk_group_info` - VK group info
4. `telegram_channel_info` - Telegram channel info
5. `website_parser` - parse websites (avoid - data already in input)
6. `g2_search` - G2 ratings/reviews
7. `Wikipedia` - general info

## n8n MCP Commands

```bash
# Set API key for n8n.oki-toki.net
mcp__n8n-flexible__n8n_set_api_key apiKey="..." url="https://n8n.oki-toki.net"

# Workflow operations
mcp__n8n-flexible__n8n_get_workflow workflowId="i8tUO6CtinXxJFu2"
mcp__n8n-flexible__n8n_get_node workflowId="..." nodeName="AI Agent"
mcp__n8n-flexible__n8n_update_node_parameters workflowId="..." nodeName="..." parameters={...}
mcp__n8n-flexible__n8n_update_node_code workflowId="..." nodeName="..." code="..."
mcp__n8n-flexible__n8n_get_executions workflowId="..." limit=5
```

## Google Sheets Integration

**Results Spreadsheet**: https://docs.google.com/spreadsheets/d/1Ac0NTkXXJoF3E5PFUNH7al2Bk7BrVaQwmaNfdRHAJds/

**Service Account**: `monitoring-of-competitors@noted-creek-481412-k7.iam.gserviceaccount.com`
**Credentials file**: `[USER_HOME]\Downloads\noted-creek-481412-k7-57f228a0aece.json`

**Python access example**:
```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = r'[USER_HOME]\Downloads\noted-creek-481412-k7-57f228a0aece.json'
SPREADSHEET_ID = 'YOUR_SECRET_TOKEN'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)
```

## Key Files

- `config/companies.json` - 19 companies with monitoring settings (priority, regions, social media flags)
- `workflows/*.json` - workflow export files
- `docs/ai-prompts.md` - AI prompt templates for different analysis types
- `docs/n8n-code-snippets.md` - JavaScript snippets for Code nodes
- `format_sheets.py` - Python script for Google Sheets formatting

## Known Issues & Solutions

### Token Consumption Problem
AI Agent consumes 200k+ tokens due to excessive tool calls.

**Root cause**: System prompt says "ОБОВ'ЯЗКОВО використай tools" which forces tool usage even when data already exists in input.

**Solution**:
1. Set `Max Iterations: 3` in AI Agent options
2. Update system prompt to FORBID tool usage:
```
Ти аналітик конкурентів.

ПРАВИЛА:
1. НЕ використовуй tools - ВСІ дані вже в INPUT
2. Аналізуй ТІЛЬКИ надані дані
3. Поверни ТІЛЬКИ valid JSON (без ```)
4. Відповідай УКРАЇНСЬКОЮ
5. Якщо даних немає - пиши "-"
```

3. In OpenAI Chat Model: `Maximum Number of Tokens: 4000`

## n8n Code Patterns

All Code nodes use JavaScript. Common patterns:
```javascript
// Access input
$input.item.json
$input.all()

// Access other nodes
$('NodeName').item.json
$('NodeName').all()

// Return single item
return { key: value }

// Return multiple items
return [{ json: {...} }, { json: {...} }]

// Safe access with fallback
$input.item.json.field || 'default'
```

## Output Schema (Google Sheets columns)

| Column | Description |
|--------|-------------|
| Дата | Analysis date |
| Компанія | Company name |
| URL | Website URL |
| Нові фічі | New features detected |
| Проблеми | Problems/issues |
| Інсайти з коментарів | Comment insights |
| Новини | Recent news |
| Статті в блозі | Blog articles |
| YouTube/Facebook/LinkedIn активність | Social media activity |
| Згадки на агрегаторах | G2/Capterra mentions |
| Болі/Хотілки клієнтів | Customer pains/wants |
| AI Summary | AI-generated summary |
| isNewEntry | TRUE if new company |



# N8n Flexible MCP Server

Гнучкий MCP сервер для N8n, який дозволяє оновлювати **тільки частину** workflow (наприклад, код однієї ноди) без передачі всього JSON.

## Функціонал

| Функція | Опис |
|---------|------|
| `n8n_set_session` | Встановити session cookie для N8n |
| `n8n_get_workflow` | Отримати повний workflow |
| `n8n_list_workflows` | Список всіх workflow |
| `n8n_get_node` | Отримати одну ноду з workflow |
| `n8n_update_node_code` | **Оновити ТІЛЬКИ код в Code node** ⭐ |
| `n8n_update_node_parameters` | **Оновити параметри ноди (partial)** ⭐ |
| `n8n_add_node` | Додати нову ноду |
| `n8n_execute_workflow` | Виконати workflow |
| `n8n_get_executions` | Отримати історію виконань |

## Встановлення

### Крок 1: Перевірити компіляцію

```bash
cd "[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\n8n-mcp-server"
npm run build
```

Має створитися папка `dist/` з `index.js`

### Крок 2: Додати MCP сервер до Claude Code

Відкрийте файл:
```
[USER_HOME]\.claude\settings.local.json
```

Додайте в розділ `enabledMcpjsonServers`:

```json
{
  "enabledMcpjsonServers": [
    "n8n-custom",
    "supabase",
    "n8n-flexible"
  ],
  "mcpServers": {
    "n8n-flexible": {
      "command": "node",
      "args": [
        "C:\\Users\\izeak\\OneDrive\\Work.Oki-toki\\Monitoring of competitors\\n8n-mcp-server\\dist\\index.js"
      ],
      "env": {
        "N8N_URL": "https://n8nletsdo.online"
      }
    }
  }
}
```

### Крок 3: Перезавантажити Claude Code

Закрийте і відкрийте Claude Code знову.

## Використання

### Приклад 1: Оновити код в ноді

```
Спочатку встанови сесію з cookie: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Потім онови код в ноді "Format for Sheets" у workflow w5Pn8RXfEteblgbC на цей код:
[код JavaScript]
```

### Приклад 2: Отримати ноду

```
Отримай ноду "Format for Sheets" з workflow w5Pn8RXfEteblgbC
```

## Порівняння з існуючим n8n-custom MCP

| Функція | n8n-custom (існуючий) | n8n-flexible (новий) |
|---------|----------------------|----------------------|
| Отримати workflow | ✅ | ✅ |
| Оновити workflow | ✅ (повний JSON) | ✅ (partial update) |
| Оновити код ноди | ❌ | ✅ **(тільки код!)** |
| Оновити параметри ноди | ❌ | ✅ **(partial merge)** |
| Отримати одну ноду | ❌ | ✅ |

## Архітектура

Сервер працює так:
1. Отримує повний workflow через API
2. Знаходить потрібну ноду за назвою
3. Змінює **тільки потрібне поле**
4. Відправляє назад повний workflow

Це дозволяє оновлювати частини workflow без необхідності формувати повний JSON вручну.



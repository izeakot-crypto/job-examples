# N8n Flexible MCP Server - ГОТОВО! ✅

## Що створено

Гнучкий MCP сервер для N8n з можливістю **часткового оновлення workflow** - тепер ви можете оновити тільки код однієї ноди без передачі всього JSON!

## Файли створено:

```
[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\n8n-mcp-server\
├── src/
│   └── index.ts          # вихідний код TypeScript
├── dist/
│   └── index.js          # скомпільований JavaScript
├── package.json          # залежності npm
├── tsconfig.json         # конфіг TypeScript
└── README.md             # документація

[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\
└── .mcp.json            # конфіг MCP сервера для Claude Code
```

## Доступні функції MCP

| Функція | Опис |
|---------|------|
| `n8n_set_session` | Встановити session cookie |
| `n8n_get_workflow` | Отримати workflow |
| `n8n_list_workflows` | Список всіх workflow |
| `n8n_get_node` | Отримати одну ноду |
| `n8n_update_node_code` | **Оновити ТІЛЬКИ код в Code node** ⭐ |
| `n8n_update_node_parameters` | **Оновити параметри ноди (merge)** ⭐ |
| `n8n_add_node` | Додати нову ноду |
| `n8n_execute_workflow` | Виконати workflow |
| `n8n_get_executions` | Історія виконань |

## Як користуватися

### Перезавантажте Claude Code

Закрийте і відкрийте Claude Code, щоб завантажити новий MCP сервер.

### Приклад використання

Тепер ви можете сказати:

```
Онови код в ноді "Format for Sheets" у workflow w5Pn8RXfEteblgbC на цей код:

const data = $input.item.json;
const ai = data.aiAnalysis || {};

const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return "-";
  if (arr.length === 0) return "-";
  return arr.join(", ");
};

const result = {
  'Компанія': data.company || 'Unknown',
  'URL': data.url || '',
  _originalData: { company: data.company, url: data.url },
  _isNewData: true
};

return result;
```

MCP сервер **сам** отримає повний workflow, знайде ноду "Format for Sheets", оновить тільки код `jsCode` і збереже назад!

## Переваги над існуючим n8n-custom MCP

| n8n-custom (існуючий) | n8n-flexible (новий) |
|----------------------|----------------------|
| Потрібен повний JSON | Тільки код або параметри |
| Складно вручну формувати | Просто вкажи назву ноди |
| Ризик помилки в connections | Автоматично зберігає connections |

## Наступні кроки

1. **Перезавантажте Claude Code**
2. **Протестуйте**: спробуйте оновити код в ноді
3. **Насолодуйтесь**: більше не потрібні ручні копіювання в UI!


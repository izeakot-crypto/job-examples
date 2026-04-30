# 📘 N8n Flexible MCP Server - Документація

## ✅ Статус перевірки: КОРЕКТНИЙ

- ✅ TypeScript компіляція: **успішна**
- ✅ JavaScript синтаксис: **коректний**
- ✅ Всі методи: **реалізовані**
- ✅ Логіка authentication: **виправлена**

---

## 🎯 Що робить цей MCP сервер?

**N8n Flexible MCP** - це Model Context Protocol (MCP) сервер який дозволяє Claude Code взаємодіяти з n8n workflow automation платформою через API.

### Основна функція:
**Редагування окремих нод в n8n workflows БЕЗ необхідності змінювати весь workflow**

---

## 🔧 Доступні методи (Tools):

### 1️⃣ **n8n_set_api_key** 🆕 (РЕКОМЕНДОВАНО)
**Що робить:** Встановлює API key для authentication з n8n
**Коли використовувати:** На початку роботи, щоб MCP міг робити API запити
**Параметри:**
- `apiKey` (обов'язковий) - JWT токен з n8n
- `url` (опціональний) - URL n8n інстансу

**Приклад:**
```javascript
mcp__n8n-flexible__n8n_set_api_key({
  apiKey: "eyJhbGc...",
  url: "https://n8nletsdo.online"
})
```

**Що відбувається:**
1. Встановлює глобальну змінну `N8N_API_KEY`
2. Опціонально оновлює `N8N_URL`
3. Всі наступні API запити використовуватимуть цей API key

---

### 2️⃣ **n8n_set_session**
**Що робить:** Встановлює session cookie для authentication (альтернатива API key)
**Параметри:**
- `cookie` (обов'язковий) - значення cookie `n8n-auth`
- `url` (опціональний) - URL n8n інстансу

**Примітка:** API key має вищий пріоритет ніж session cookie!

---

### 3️⃣ **n8n_get_workflow**
**Що робить:** Отримує повну структуру workflow по ID
**Параметри:**
- `workflowId` (обов'язковий) - ID workflow

**Повертає:** Повний JSON з нодами, connections, settings

---

### 4️⃣ **n8n_list_workflows**
**Що робить:** Отримує список всіх workflows
**Параметри:** немає

**Повертає:** Масив workflows з їх ID, назвами, статусами

---

### 5️⃣ **n8n_update_node_code** ⭐ (КЛЮЧОВИЙ МЕТОД)
**Що робить:** Оновлює КОД в Code ноді БЕЗ зміни всього workflow
**Параметри:**
- `workflowId` (обов'язковий) - ID workflow
- `nodeName` (обов'язковий) - Назва ноди
- `code` (обов'язковий) - Новий JavaScript код

**Як працює:**
1. Отримує поточний workflow через API
2. Знаходить ноду по імені
3. Перевіряє що це Code нода (type: `n8n-nodes-base.code`)
4. Змінює ТІЛЬКИ параметр `jsCode`
5. Відправляє оновлений workflow назад через PATCH запит

**Приклад:**
```javascript
mcp__n8n-flexible__n8n_update_node_code({
  workflowId: "qk1bISszvNIH6Ww7",
  nodeName: "Format for Sheets3",
  code: "const data = $input.item.json; return {result: data};"
})
```

---

### 6️⃣ **n8n_update_node_parameters** ⭐⭐⭐ (НАЙВАЖЛИВІШИЙ)
**Що робить:** Оновлює ПАРАМЕТРИ будь-якої ноди (частковий merge)
**Параметри:**
- `workflowId` (обов'язковий) - ID workflow
- `nodeName` (обов'язковий) - Назва ноди
- `parameters` (обов'язковий) - Об'єкт з новими параметрами

**Як працює:**
1. Отримує поточний workflow
2. Знаходить ноду по імені
3. **MERGE** нових параметрів з існуючими (не заміна!)
4. Оновлює workflow

**Приклад використання для Append New Row:**
```javascript
mcp__n8n-flexible__n8n_update_node_parameters({
  workflowId: "qk1bISszvNIH6Ww7",
  nodeName: "Append New Row1",
  parameters: {
    columns: {
      mappingMode: "defineBelow",
      value: {
        "Дата": "={{ $json['Дата'] || new Date().toISOString().split('T')[0] }}",
        "Компанія": "={{ $json['Компанія'] || 'Unknown' }}",
        "URL": "={{ $json['URL'] || '-' }}"
        // ... і так далі
      }
    }
  }
})
```

**Це САМЕ ТЕ що нам потрібно для виправлення Append New Row1!**

---

### 7️⃣ **n8n_get_node**
**Що робить:** Отримує конкретну ноду з workflow
**Параметри:**
- `workflowId` (обов'язковий)
- `nodeName` (обов'язковий)

**Повертає:** JSON з конфігурацією ноди (parameters, position, type, тощо)

---

### 8️⃣ **n8n_add_node**
**Що робить:** Додає НОВУ ноду в workflow
**Параметри:**
- `workflowId` (обов'язковий)
- `node` (обов'язковий) - конфігурація ноди
- `connectFrom` (опціональний) - з'єднання з іншою нодою

**Приклад:**
```javascript
mcp__n8n-flexible__n8n_add_node({
  workflowId: "xxx",
  node: {
    name: "My New Node",
    type: "n8n-nodes-base.set",
    parameters: {},
    position: [100, 200]
  },
  connectFrom: "Previous Node"
})
```

---

### 9️⃣ **n8n_execute_workflow**
**Що робить:** Запускає workflow вручну
**Параметри:**
- `workflowId` (обов'язковий)
- `data` (опціональний) - input дані

**Повертає:** Execution ID та статус

---

### 🔟 **n8n_get_executions**
**Що робить:** Отримує історію виконань workflow
**Параметри:**
- `workflowId` (обов'язковий)
- `limit` (опціональний, default: 10)

**Повертає:** Список executions з статусами, датами, помилками

---

## 🔐 Логіка Authentication (ВИПРАВЛЕНА!)

### Пріоритет:
1. **API Key** (якщо встановлений через `n8n_set_api_key`)
   - Заголовок: `X-N8N-API-KEY: <token>`
2. **Session Cookie** (fallback, якщо немає API key)
   - Заголовок: `Cookie: n8n-auth=<cookie>`

### Що було виправлено:
**ДО:**
```javascript
// Спочатку cookie, потім API key
if (cookie) use cookie
else if (apiKey) use apiKey  // ❌ Ніколи не виконується якщо є cookie!
```

**ПІСЛЯ:**
```javascript
// Спочатку API key, потім cookie
if (apiKey) use apiKey       // ✅ Пріоритет
else if (cookie) use cookie  // ✅ Fallback
```

---

## 🛠️ Внутрішня логіка:

### `n8nRequest(endpoint, options)`
Базова функція для всіх API запитів:
1. Формує URL: `${N8N_URL}${endpoint}`
2. Додає headers:
   - `Content-Type: application/json`
   - `X-N8N-API-KEY` (якщо є API key)
   - `Cookie` (якщо немає API key але є session)
3. Робить fetch запит
4. Перевіряє response.ok
5. Повертає JSON або викидає помилку

### `findNodeByName(workflow, nodeName)`
Знаходить ноду в workflow по імені або ID:
```javascript
workflow.nodes.find(n => n.name === nodeName || n.id === nodeName)
```

### `findNodeById(workflow, nodeId)`
Знаходить ноду тільки по ID:
```javascript
workflow.nodes.find(n => n.id === nodeId)
```

---

## 📊 Структура workflow:

```javascript
{
  "id": "workflowId",
  "name": "Workflow Name",
  "nodes": [
    {
      "id": "node-uuid",
      "name": "Node Name",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "...",
        "columns": {...},
        // інші параметри
      },
      "position": [x, y]
    }
  ],
  "connections": {
    "Node1": {
      "main": [[{"node": "Node2", "type": "main", "index": 0}]]
    }
  },
  "settings": {...}
}
```

---

## 🎯 Використання для нашої задачі:

### Задача: Виправити Append New Row1
**Проблема:** Mapping без fallback → "Could not get parameter"

**Рішення:**
```javascript
// 1. Встановити API key
mcp__n8n-flexible__n8n_set_api_key({apiKey: "..."})

// 2. Оновити параметри ноди
mcp__n8n-flexible__n8n_update_node_parameters({
  workflowId: "qk1bISszvNIH6Ww7",
  nodeName: "Append New Row1",
  parameters: {
    columns: {
      value: {
        "Дата": "={{ $json['Дата'] || new Date().toISOString().split('T')[0] }}",
        "Компанія": "={{ $json['Компанія'] || 'Unknown' }}",
        // ... всі інші поля з fallback
      }
    }
  }
})

// 3. Оновити AI промпт
mcp__n8n-flexible__n8n_update_node_parameters({
  workflowId: "qk1bISszvNIH6Ww7",
  nodeName: "AI Agent1",
  parameters: {
    text: "Новий оптимізований промпт..."
  }
})
```

---

## ⚠️ Важливі примітки:

1. **MCP сервер працює через STDIO** - Claude Code запускає його як subprocess
2. **Всі зміни workflow відбуваються через PATCH** `/api/v1/workflows/{id}`
3. **Merge параметрів** - існуючі параметри НЕ видаляються, тільки оновлюються
4. **Node lookup** - можна шукати по `name` або `id`
5. **Error handling** - всі помилки API повертаються як text з `isError: true`

---

## 🚀 Готовність до використання:

- ✅ Build успішний
- ✅ Синтаксис коректний
- ✅ Всі методи реалізовані
- ✅ Authentication виправлено
- ⏳ **ПОТРІБНО:** Перезапустити Claude Code для завантаження

---

## 🔄 Наступні кроки:

1. Перезапустити Claude Code
2. Використати `n8n_set_api_key` з вашим API key
3. Виправити всі проблемні ноди автоматично
4. Протестувати workflow


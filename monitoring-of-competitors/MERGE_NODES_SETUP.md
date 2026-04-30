# ВИПРАВЛЕННЯ LOGIC AFTER FORMAT FOR SHEETS

## Проблема
Після ноди "Format for Sheets" дані губляться при передачі до "Check If Company Exists".
Причина: неправильна налаштована Merge нода або відсутній pass-through даних.

## РІШЕННЯ

### Схема workflow після Format for Sheets:

```
Format for Sheets
    │
    ├─────────────────┐
    │                 │
    ▼                 ▼
Get Existing Data   (прямий потік даних)
    │                 │
    └──────── Merge ──┘
                │
                ▼
    Check If Company Exists
                │
                ▼
         IF Company Exists
           /          \
     (true)         (false)
       │               │
       ▼               ▼
  Update Row    Append New Row
       │               │
       └───────┬───────┘
               ▼
        Loop Companies (next)
```

---

## КРОК 1: Оновити Format for Sheets

1. Відкрити ноду **Format for Sheets**
2. Замінити код на вміст файлу `FORMAT_FOR_SHEETS_PASSTHROUGH.js`
3. Зберегти

**Що змінено:** Додано `_originalData`, `_searchKey` та інші службові поля для pass-through.

---

## КРОК 2: Налаштувати Get Existing Data

1. Створити нову ноду **Google Sheets** після Format for Sheets
2. **Operation:** `Get Many` (отримати всі рядки)
3. **Document:** вибрати Google Sheet "Competitor_Analysis_Template"
4. **Sheet:** вибрати аркуш
5. **Options → Return All:** `true` (отримати всі рядки, не обмежувати)
6. Зберегти

---

## КРОК 3: Налаштувати Merge ноду

Це **КРИТИЧНА** нода - вона об'єднує нові дані з існуючими.

1. Створити ноду **Merge** між Format for Sheets та Check If Company Exists
2. **Mode:** `Merge by Index`
3. **Inputs:** 2 (можна більше, якщо є додаткові джерела)

### Підключення:
- **Input 1:** Format for Sheets (нові дані)
- **Input 2:** Get Existing Data (існуючі рядки з Google Sheets)

4. Зберегти

---

## КРОК 4: Оновити Check If Company Exists

1. Відкрити ноду **Check If Company Exists**
2. Замінити код на вміст файлу `CHECK_IF_COMPANY_EXISTS_FIXED.js`
3. Зберегти

**Що робить код:**
- Читає `$input.all()` - всі вхідні дані
- Перший item (index 0) - нові дані компанії
- Інші items (index 1+) - існуючі рядки з Google Sheets
- Порівнює назву компанії та URL
- Повертає `_action: 'update'` або `_action: 'append'`

---

## КРОК 5: Налаштувати IF Company Exists

1. Створити ноду **IF** після Check If Company Exists
2. **Condition:**
   - Value 1: `{{ $json._action }}`
   - Operation: `String Equals`
   - Value 2: `update`

3. **Connections:**
   - **Output 1 (true)** → Update Existing Row
   - **Output 2 (false)** → Append New Row

---

## КРОК 6: Налаштувати Update Existing Row

1. Створити ноду **Google Sheets**
2. **Operation:** `Update`
3. **Document:** той самий Google Sheet
4. **Sheet:** той самий аркуш
5. **Row ID:** `{{ $json._rowId }}`
6. **Columns → Mapping Mode:** `Define Below`
7. Додати всі колонки:
   ```
   Дата: {{ $json['Дата'] }}
   Компанія: {{ $json['Компанія'] }}
   URL: {{ $json['URL'] }}
   Нові фічі: {{ $json['Нові фічі'] }}
   Проблеми: {{ $json['Проблеми'] }}
   ... (всі 16 колонок)
   ```
8. **Matching Columns:** `Компанія`
9. Зберегти

---

## КРОК 7: Налаштувати Append New Row

1. Створити ноду **Google Sheets**
2. **Operation:** `Append`
3. **Document:** той самий Google Sheet
4. **Sheet:** той самий аркуш
5. **Columns → Mapping Mode:** `Define Below`
6. Додати всі колонки (такі самі як в Update)
7. Зберегти

---

## КРОК 8: Підключити назад до Loop

Обидві ноди (Update та Append) мають підключатися назад до **Loop Companies**:

- **Update Existing Row** → **Loop Companies** (input 0)
- **Append New Row** → **Loop Companies** (input 0)

---

## ТЕСТУВАННЯ

### Тест 1: Нова компанія (append)
1. Запустити workflow на компанії, якої немає в Google Sheets
2. Очікуваний результат:
   - `Check If Company Exists` → `_action: "append"`
   - `IF Company Exists` → output 2 (false)
   - Створюється новий рядок

### Тест 2: Існуюча компанія (update)
1. Запустити workflow на компанії, яка вже є в Google Sheets
2. Очікуваний результат:
   - `Check If Company Exists` → `_action: "update"`
   - `IF Company Exists` → output 1 (true)
   - Рядок оновлюється, не створюється дублікат

---

## DEBUGGING

### Якщо дані все одно губляться:

Перевірте в **Check If Company Exists**:
```javascript
console.log('Total inputs:', $input.all().length);
console.log('Input 0 (new data):', JSON.stringify($input.first().json));
console.log('Input 1+ (existing):', $input.all().slice(1).map(i => JSON.stringify(i.json)));
```

### Якщо Merge не працює:

Спробуйте інший режим Merge:
- **Merge by Index** - об'єднує за порядковим номером
- **Combine All** - об'єднує все в один масив
- **Wait** - чекає обидва输入, потім пропускає далі

### Альтернатива: використовуйте Code node замість Merge

Якщо Merge нода не працює, створіть Code node "Merge Manually":

```javascript
// Get new data from Format for Sheets (stored in item)
const newData = $input.item.json;

// Get existing data from Google Sheets (через $('Get Existing Data').all())
const existingData = $('Get Existing Data').all();

// Combine for Check If Company Exists
return [
  { json: newData },
  ...existingData
];
```

---

## ФАЙЛИ

1. `FORMAT_FOR_SHEETS_PASSTHROUGH.js` - виправлений Format for Sheets
2. `CHECK_IF_COMPANY_EXISTS_FIXED.js` - виправлений Check If Company Exists
3. Цей файл - інструкція з налаштування


# ІНСТРУКЦІЯ ІМПОРТУ ВОРКФЛОУ

1. Відкрийте n8n: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7

2. Натисніть кнопку меню (3 точки) у верхньому правому куті

3. Виберіть 'Import from File...'

4. Виберіть файл: updated_workflow_v2.json
   Шлях: C:/Users/izeak/OneDrive/Work.Oki-toki/Monitoring of competitors/updated_workflow_v2.json

5. Підтвердіть заміну (Replace)

## Що змінилось:

1. НОВА НОДА: 'Prepare AI Prompt' (між Merge4 та AI Agent1)
   - Готує промпт з РЕАЛЬНИМИ даними
   - Позиція: [3320, -784]

2. ОНОВЛЕНО: 'AI Agent1'
   - User prompt: {{ $json.preparedPrompt }}
   - System prompt: Professional BI Analyst з VoIP/Contact Center досвідом

3. НОВІ CONNECTIONS:
   - Merge4 → Prepare AI Prompt
   - Prepare AI Prompt → AI Agent1

## Очікуваний результат:
Замість n8n expressions у відповіді AI видаватиме реальний аналіз.

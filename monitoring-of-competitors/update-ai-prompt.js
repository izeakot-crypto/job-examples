const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs';

// Новий оптимізований промпт - коротший і швидший
const newPrompt = `Аналізуй компанію та поверни JSON.

ДАНІ:
Компанія: {{ $input.all()[0].json.company }}
URL: {{ $input.all()[0].json.url || '-' }}
Title: {{ $input.all()[0].json.currentData.website.title || '-' }}
Description: {{ $input.all()[0].json.currentData.website.description || '-' }}
YouTube: {{ $input.all()[1].json.youtubeActivity || '-' }}
LinkedIn: {{ $input.all()[2].json.linkedinActivity || '-' }}
Facebook: {{ $input.all()[2].json.facebookActivity || '-' }}
G2: {{ $input.all()[3].json.aggregatorMentions || '-' }}
Блог статей: {{ $input.all()[0].json.currentData.blog.articlesFound || 0 }}
Відгуків: {{ $input.all()[0].json.currentData.reviews.count || 0 }}

ПОВЕРНИ JSON (без \`\`\`):
{
  "company": "{{ $input.all()[0].json.company }}",
  "url": "{{ $input.all()[0].json.url || '-' }}",
  "youtubeActivity": "{{ $input.all()[1].json.youtubeActivity || '-' }}",
  "linkedinActivity": "{{ $input.all()[2].json.linkedinActivity || '-' }}",
  "facebookActivity": "{{ $input.all()[2].json.facebookActivity || '-' }}",
  "aggregatorMentions": "{{ $input.all()[3].json.aggregatorMentions || '-' }}",
  "socialMentionsCount": {{ ($input.all()[2].json.socialLinksCount || 0) + ($input.all()[3].json.g2ReviewsCount || 0) }},
  "newFeatures": ["виділи 2-3 ключові фічі з title/description"],
  "problems": ["якщо є скарги - вкажи, інакше '-'"],
  "reviewInsights": "короткий висновок про відгуки або '-'",
  "news": ["останні новини або '-'"],
  "blogArticles": [{"title": "назва", "date": "дата", "summary": "опис"}],
  "customerPains": ["болі клієнтів або '-'"],
  "customerWants": ["потреби клієнтів або '-'"],
  "summary": "1-2 речення про компанію: позиціонування, сильні сторони"
}`;

const newSystemMessage = "Ти аналітик. Повертай ТІЛЬКИ valid JSON без markdown.";

async function updateAIPrompt() {
  console.log('Fetching workflow...');

  const getRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    headers: { 'X-N8N-API-KEY': apiKey }
  });
  const workflow = await getRes.json();

  console.log('Workflow fetched:', workflow.name);

  // Знайти AI Agent1
  const aiNodeIndex = workflow.nodes.findIndex(n => n.name === 'AI Agent1');
  if (aiNodeIndex === -1) {
    console.log('AI Agent1 NOT FOUND!');
    return;
  }

  console.log('Found AI Agent1 at index:', aiNodeIndex);
  console.log('Old prompt length:', workflow.nodes[aiNodeIndex].parameters.text.length);

  // Оновити промпт
  workflow.nodes[aiNodeIndex].parameters.text = newPrompt;
  workflow.nodes[aiNodeIndex].parameters.options.systemMessage = newSystemMessage;

  console.log('New prompt length:', newPrompt.length);

  // Очистити workflow
  const cleanSettings = {
    executionOrder: workflow.settings?.executionOrder
  };

  const cleanWorkflow = {
    name: workflow.name,
    nodes: workflow.nodes,
    connections: workflow.connections,
    settings: cleanSettings
  };

  console.log('Updating workflow...');

  const putRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    method: 'PUT',
    headers: {
      'X-N8N-API-KEY': apiKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(cleanWorkflow)
  });

  console.log('Response status:', putRes.status);

  if (putRes.ok) {
    console.log('SUCCESS! AI prompt updated.');
    const result = await putRes.json();
    console.log('New versionId:', result.versionId);
  } else {
    const errorText = await putRes.text();
    console.log('ERROR:', errorText);
  }
}

updateAIPrompt().catch(e => console.error('Error:', e.message));


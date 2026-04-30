const apiKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzhkYmVhYy0wNDJjLTRmNDEtYWQzYy0yN2NkYTcwMTYwNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY2NTcyNDQxLCJleHAiOjE3NjkxMTkyMDB9.8wbIK7T6ve610S_TqB8nPMh8IdTlQtEXjk44Rv6QhEs';

async function updateNodes() {
  console.log('Fetching workflow...');

  // 1. Отримати workflow
  const getRes = await fetch('https://n8nletsdo.online/api/v1/workflows/qk1bISszvNIH6Ww7', {
    headers: { 'X-N8N-API-KEY': apiKey }
  });
  const workflow = await getRes.json();

  console.log('Workflow fetched:', workflow.name);
  console.log('Nodes count:', workflow.nodes.length);

  // Новий mapping з fallback
  const newMapping = {
    'Дата': "={{ $json['Дата'] || new Date().toISOString().split('T')[0] }}",
    'Компанія': "={{ $json['Компанія'] || 'Unknown' }}",
    'URL': "={{ $json['URL'] || '-' }}",
    'Нові фічі': "={{ $json['Нові фічі'] || '-' }}",
    'Проблеми': "={{ $json['Проблеми'] || '-' }}",
    'Інсайти з коментарів': "={{ $json['Інсайти з коментарів'] || '-' }}",
    'Новини (з останньої перевірки)': "={{ $json['Новини (з останньої перевірки)'] || '-' }}",
    'Статті в блозі (з останньої перевірки)': "={{ $json['Статті в блозі (з останньої перевірки)'] || '-' }}",
    'YouTube активність': "={{ $json['YouTube активність'] || '-' }}",
    'Facebook активність': "={{ $json['Facebook активність'] || '-' }}",
    'LinkedIn активність': "={{ $json['LinkedIn активність'] || '-' }}",
    'Згадки на агрегаторах': "={{ $json['Згадки на агрегаторах'] || '-' }}",
    'Кількість згадок в соцмережах': "={{ $json['Кількість згадок в соцмережах'] || '0' }}",
    'Болі клієнтів з коментарів': "={{ $json['Болі клієнтів з коментарів'] || '-' }}",
    'Хотілки клієнтів з коментарів': "={{ $json['Хотілки клієнтів з коментарів'] || '-' }}",
    'AI Summary': "={{ $json['AI Summary'] || '-' }}",
    'isNewEntry': "={{ $json.isNewEntry || 'false' }}"
  };

  // 2. Знайти і оновити Append New Row1
  const appendNodeIndex = workflow.nodes.findIndex(n => n.name === 'Append New Row1');
  if (appendNodeIndex !== -1) {
    console.log('Found Append New Row1 at index:', appendNodeIndex);
    workflow.nodes[appendNodeIndex].parameters.columns.value = newMapping;
  } else {
    console.log('Append New Row1 NOT FOUND!');
  }

  // 3. Знайти і оновити Update Existing Row1
  const updateNodeIndex = workflow.nodes.findIndex(n => n.name === 'Update Existing Row1');
  if (updateNodeIndex !== -1) {
    console.log('Found Update Existing Row1 at index:', updateNodeIndex);
    workflow.nodes[updateNodeIndex].parameters.columns.value = newMapping;
  } else {
    console.log('Update Existing Row1 NOT FOUND!');
  }

  // 4. Очистити workflow від read-only полів - МІНІМАЛЬНИЙ набір
  // Також очистити settings від зайвих полів
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

  // 5. PUT оновлений workflow
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
    console.log('SUCCESS! Workflow updated.');
    const result = await putRes.json();
    console.log('New versionId:', result.versionId);
  } else {
    const errorText = await putRes.text();
    console.log('ERROR:', errorText);
  }
}

updateNodes().catch(e => console.error('Error:', e.message));


// === PATCH for /var/www/seo-articles/api/controllers/ideasController.js ===
// Replace the n8n webhook call in approveIdea() with Python pipeline call.
//
// FIND this block (around line 130-155):
//
//     // Call N8n webhook
//     const n8nUrl = `${process.env.N8N_BASE_URL}${process.env.N8N_APPROVE_IDEA_WEBHOOK}`;
//     try {
//         const n8nResponse = await axios.post(n8nUrl, {
//             idea_id: id,
//             timestamp: new Date().toISOString()
//         });
//         res.json({
//             status: 'approved',
//             translation_started: true,
//             idea_id: id,
//             n8n_response: n8nResponse.data
//         });
//     } catch (n8nError) {
//         console.error('N8n webhook error:', n8nError.message);
//         res.json({
//             status: 'approved',
//             translation_started: false,
//             idea_id: id,
//             warning: 'N8n webhook failed'
//         });
//     }
//
// REPLACE WITH:
//
//     // Call Python pipeline (replaces N8n WF1/WF2/WF3)
//     const pipelineUrl = process.env.PYTHON_PIPELINE_URL || 'http://127.0.0.1:8000';
//     try {
//         const pipelineResponse = await axios.post(`${pipelineUrl}/approve-idea`, {
//             idea_id: id,
//             timestamp: new Date().toISOString()
//         });
//         res.json({
//             status: 'approved',
//             translation_started: true,
//             idea_id: id,
//             pipeline_response: pipelineResponse.data
//         });
//     } catch (pipelineError) {
//         console.error('Python pipeline error:', pipelineError.message);
//         res.json({
//             status: 'approved',
//             translation_started: false,
//             idea_id: id,
//             warning: 'Python pipeline not available'
//         });
//     }
//
// Also add to /var/www/seo-articles/api/.env:
//     PYTHON_PIPELINE_URL=http://127.0.0.1:8000

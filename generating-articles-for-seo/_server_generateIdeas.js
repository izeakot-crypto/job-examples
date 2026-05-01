// NEW ENDPOINTS:
// POST /api/ideas/generate - Generates mock ideas
// POST /api/ideas/bulk-save - Receives ideas from N8n and saves to DB

const supabase = require('../config/supabase');
const { v4: uuidv4 } = require('uuid');

// Generate ideas via Python pipeline (Claude with outline). Falls back to
// local mock generator only if pipeline is unreachable.
exports.generateIdeas = async (req, res) => {
    try {
        const { limit = 5, count } = req.body || {};
        const requested = Number(count ?? limit) || 5;

        console.log(`[Generate Ideas] Requesting ${requested} ideas from Python pipeline...`);

        const pythonUrl = process.env.PYTHON_PIPELINE_URL || 'http://127.0.0.1:8000';
        const axios = require('axios');

        try {
            const pipelineResponse = await axios.post(`${pythonUrl}/generate-ideas`, {
                count: requested,
                timestamp: new Date().toISOString(),
            }, { timeout: 300000 });

            const newIdeas = pipelineResponse.data.ideas || [];
            console.log(`[Generate Ideas] Pipeline returned ${newIdeas.length} ideas`);
            return res.json({
                success: true,
                count: newIdeas.length,
                ideas: newIdeas,
                source: 'pipeline',
            });
        } catch (pipelineErr) {
            console.warn('[Generate Ideas] Pipeline failed, falling back to mock:', pipelineErr.message);
            // fall through to legacy mock generator below
        }

        // ───── Legacy fallback (no outline) ─────
        const limit_ = requested;

        // Template topics for Oki-Toki blog
        const topics = [
            'Як налаштувати інтеграцію CRM з телефонією',
            'Автоматизація call-центру: покроковий гайд',
            'Топ-10 функцій Oki-Toki для підвищення продажів',
            'Як аналізувати метрики call-центру',
            'Інтеграція IP-телефонії з CRM системою',
            'Налаштування черги дзвінків у Oki-Toki',
            'Як збільшити конверсію через холодні дзвінки',
            'Автоматичний розподіл дзвінків між операторами',
            'Reporting та аналітика в CRM для колл-центру',
            'Як налаштувати IVR меню для вхідних дзвінків',
            'Інтеграція Oki-Toki з популярними CRM',
            'Скрипти продажів для колл-центру',
            'Як мотивувати операторів call-центру',
            'KPI для колл-центру: що вимірювати',
            'Налаштування SIP trunk для бізнесу',
            'Як організувати віддалену роботу call-центру',
            'Автоматизація обробки вхідних заявок',
            'Якість обслуговування клієнтів у call-центрі',
            'Налаштування webhooks для CRM інтеграцій',
            'Як знизити середній час обробки дзвінка'
        ];

        // Shuffle and take random topics
        const shuffled = topics.sort(() => 0.5 - Math.random());
        const selected = shuffled.slice(0, limit_);

        // Generate ideas with realistic data
        const ideas = selected.map((title, index) => {
            const priorityScore = Math.floor(Math.random() * 40) + 60; // 60-100

            // Extract keywords from title
            const stopWords = ['як', 'що', 'для', 'при', 'про', 'від', 'до', 'в', 'на', 'з', 'і', 'та', 'або', 'а', 'але', 'не', 'по'];
            const keywords = title.toLowerCase()
                .split(/\s+/)
                .filter(w => w.length > 3 && !stopWords.includes(w))
                .slice(0, 5);

            return {
                id: uuidv4(),
                title: title,
                description: `Експертна стаття про ${title.toLowerCase()}. Аналіз для Oki-Toki блогу.`,
                type: 'article',
                status: 'pending',
                keywords: keywords.length > 0 ? keywords : ['колл-центр', 'crm'],
                outline: '',
                priority_score: priorityScore,
                created_at: new Date().toISOString()
            };
        });

        console.log('[Generate Ideas] Generated ideas:', ideas.map(i => i.title));

        // Save to Supabase
        if (supabase) {
            console.log('[Generate Ideas] Saving to Supabase...');

            const { data, error } = await supabase
                .from('ideas')
                .insert(ideas)
                .select();

            if (error) {
                console.error('[Generate Ideas] Supabase error:', error);
                throw error;
            }

            console.log(`[Generate Ideas] Successfully saved ${data.length} ideas to DB`);

            res.json({
                success: true,
                count: data.length,
                ideas: data,
                message: `Згенеровано ${data.length} ідей статей`
            });
        } else {
            console.log('[Generate Ideas] No Supabase - returning mock data');

            // No Supabase - return mock data
            res.json({
                success: true,
                count: ideas.length,
                ideas: ideas,
                message: `Згенеровано ${ideas.length} ідей статей (mock)`
            });
        }

    } catch (error) {
        console.error('[Generate Ideas] Error:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

// POST /api/ideas/bulk-save - Receives ideas from N8n workflow
exports.bulkSaveIdeas = async (req, res) => {
    try {
        const payload = req.body;

        console.log('[Bulk Save] Received data from N8n:', JSON.stringify(payload).substring(0, 200));

        // Extract ideas array from N8n response format
        let ideas = [];

        if (payload.ideas && Array.isArray(payload.ideas)) {
            ideas = payload.ideas;
        } else if (payload.success && payload.ideas) {
            ideas = payload.ideas;
        } else if (Array.isArray(payload)) {
            ideas = payload;
        } else {
            console.error('[Bulk Save] Unknown payload format:', payload);
            return res.status(400).json({
                success: false,
                error: 'Invalid payload format'
            });
        }

        console.log(`[Bulk Save] Extracted ${ideas.length} ideas`);

        if (ideas.length === 0) {
            return res.json({
                success: true,
                count: 0,
                message: 'No ideas to save'
            });
        }

        // Ensure all ideas have required fields and add ID if missing
        const ideasToSave = ideas.map(idea => ({
            id: idea.id || uuidv4(),
            title: idea.title,
            description: idea.description || '',
            type: idea.type || 'article',
            status: idea.status || 'pending',
            keywords: idea.keywords || [],
            outline: idea.outline || '',
            priority_score: idea.priority_score || 50,
            created_at: idea.created_at || new Date().toISOString()
        }));

        // Save to Supabase
        if (supabase) {
            console.log('[Bulk Save] Saving to Supabase...');

            const { data, error } = await supabase
                .from('ideas')
                .insert(ideasToSave)
                .select();

            if (error) {
                console.error('[Bulk Save] Supabase error:', error);
                throw error;
            }

            console.log(`[Bulk Save] Successfully saved ${data.length} ideas to DB`);

            res.json({
                success: true,
                count: data.length,
                ideas: data,
                message: `Збережено ${data.length} ідей в базу даних`
            });
        } else {
            console.log('[Bulk Save] No Supabase - returning mock success');

            res.json({
                success: true,
                count: ideasToSave.length,
                ideas: ideasToSave,
                message: `Отримано ${ideasToSave.length} ідей (Supabase не підключено)`
            });
        }

    } catch (error) {
        console.error('[Bulk Save] Error:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

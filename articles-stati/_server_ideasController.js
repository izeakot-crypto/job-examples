const supabase = require('../config/supabase');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

// Mock data for development (when Supabase not configured)
let mockIdeas = [
    {
        id: uuidv4(),
        title: 'Топ 10 трендів веб-дизайну в 2025 році',
        description: 'Огляд найактуальніших трендів веб-дизайну 2025 року',
        type: 'review',
        status: 'pending',
        priority_score: 85,
        keywords: ['веб-дизайн', 'тренди 2025', 'UI/UX'],
        created_at: new Date().toISOString()
    },
    {
        id: uuidv4(),
        title: 'SEO оптимізація для e-commerce: повний гайд',
        description: 'Детальне керівництво по SEO для інтернет-магазинів',
        type: 'guide',
        status: 'pending',
        priority_score: 92,
        keywords: ['SEO', 'e-commerce', 'оптимізація'],
        created_at: new Date().toISOString()
    }
];

// GET /api/ideas?status=pending
exports.getIdeas = async (req, res) => {
    try {
        const { status } = req.query;

        if (supabase) {
            let query = supabase.from('ideas').select('*');

            if (status) {
                query = query.eq('status', status);
            }

            const { data, error } = await query.order('created_at', { ascending: false });

            if (error) throw error;

            res.json(data);
        } else {
            // Mock response
            const filteredIdeas = status
                ? mockIdeas.filter(idea => idea.status === status)
                : mockIdeas;

            res.json(filteredIdeas);
        }
    } catch (error) {
        console.error('Error fetching ideas:', error);
        res.status(500).json({ error: error.message });
    }
};

// GET /api/ideas/:id
exports.getIdeaById = async (req, res) => {
    try {
        const { id } = req.params;

        if (supabase) {
            const { data, error } = await supabase
                .from('ideas')
                .select('*')
                .eq('id', id)
                .single();

            if (error) throw error;
            if (!data) {
                return res.status(404).json({ error: 'Idea not found' });
            }

            res.json(data);
        } else {
            // Mock response
            const idea = mockIdeas.find(i => i.id === id);
            if (!idea) {
                return res.status(404).json({ error: 'Idea not found' });
            }
            res.json(idea);
        }
    } catch (error) {
        console.error('Error fetching idea:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/ideas/:id/approve
exports.approveIdea = async (req, res) => {
    try {
        const { id } = req.params;

        console.log(`[Approve Idea] Approving idea: ${id}`);

        let ideaData = null;

        // Update idea status in database
        if (supabase) {
            const { data, error } = await supabase
                .from('ideas')
                .update({
                    status: 'approved',
                    updated_at: new Date().toISOString()
                })
                .eq('id', id)
                .select()
                .single();

            if (error) {
                console.error('[Approve Idea] Error:', error);
                throw error;
            }

            ideaData = data;
            console.log(`[Approve Idea] Successfully approved idea: ${id}`);

            // Create article entry immediately with progress tracking
            const articleId = id; // Use same ID as idea
            const theme = ideaData.title || 'Нова стаття';

            // Check if article already exists
            const { data: existingArticle } = await supabase
                .from('articles_audit')
                .select('id')
                .eq('id', articleId)
                .single();

            if (!existingArticle) {
                // Create new article with initial progress state
                const { error: articleError } = await supabase
                    .from('articles_audit')
                    .insert([{
                        id: articleId,
                        theme_ua: theme,
                        status: 'not_checked',
                        progress_stage: 'idea_approved',
                        progress_percent: 14,
                        progress_message: 'Ідея схвалена, починаємо генерацію...',
                        progress_updated_at: new Date().toISOString(),
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString()
                    }]);

                if (articleError) {
                    console.error('[Approve Idea] Error creating article:', articleError);
                    // Don't throw - continue with workflow
                } else {
                    console.log(`[Approve Idea] Created article entry: ${articleId}`);

                    // Broadcast new article via SSE
                    const { broadcastNewArticle } = require('../routes/sse');
                    if (broadcastNewArticle) {
                        broadcastNewArticle({
                            id: articleId,
                            idea_id: articleId,
                            title: theme,
                            theme: theme,
                            status: 'not_checked',
                            date: new Date().toLocaleString('uk-UA'),
                            progress_stage: 'idea_approved',
                            progress_percent: 14,
                            progress_message: 'Ідея схвалена, починаємо генерацію...'
                        });
                    }
                }
            }
        } else {
            // Mock update
            const idea = mockIdeas.find(i => i.id === id);
            if (idea) {
                idea.status = 'approved';
            }
        }

        // Call Python pipeline (replaces N8n WF1/WF2/WF3)
        const pipelineUrl = process.env.PYTHON_PIPELINE_URL || 'http://127.0.0.1:8000';

        try {
            const pipelineResponse = await axios.post(`${pipelineUrl}/approve-idea`, {
                idea_id: id,
                timestamp: new Date().toISOString()
            });

            res.json({
                status: 'approved',
                translation_started: true,
                idea_id: id,
                pipeline_response: pipelineResponse.data
            });
        } catch (pipelineError) {
            console.error('Python pipeline error:', pipelineError.message);
            // Still return success even if pipeline fails
            res.json({
                status: 'approved',
                translation_started: false,
                idea_id: id,
                warning: 'Python pipeline not available'
            });
        }
    } catch (error) {
        console.error('Error approving idea:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/ideas/:id/reject
exports.rejectIdea = async (req, res) => {
    try {
        const { id } = req.params;
        const { reason } = req.body;

        console.log(`[Reject Idea] Rejecting idea: ${id}`);

        if (supabase) {
            const { data, error } = await supabase
                .from('ideas')
                .update({
                    status: 'rejected',
                    updated_at: new Date().toISOString()
                })
                .eq('id', id)
                .select()
                .single();

            if (error) {
                console.error('[Reject Idea] Error:', error);
                throw error;
            }

            console.log(`[Reject Idea] Successfully rejected idea: ${id}`);
        } else {
            const idea = mockIdeas.find(i => i.id === id);
            if (idea) {
                idea.status = 'rejected';
            }
        }

        res.json({
            status: 'rejected',
            idea_id: id
        });
    } catch (error) {
        console.error('Error rejecting idea:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/ideas - Create new idea
exports.createIdea = async (req, res) => {
    try {
        const { title, description, type, keywords } = req.body;

        const newIdea = {
            id: uuidv4(),
            title,
            description,
            type: type || 'article',
            status: 'pending',
            priority_score: Math.floor(Math.random() * 100),
            keywords: keywords || [],
            created_at: new Date().toISOString()
        };

        if (supabase) {
            const { data, error } = await supabase
                .from('ideas')
                .insert([newIdea])
                .select()
                .single();

            if (error) throw error;

            res.status(201).json(data);
        } else {
            mockIdeas.push(newIdea);
            res.status(201).json(newIdea);
        }
    } catch (error) {
        console.error('Error creating idea:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/ideas/load-more - Load more ideas from N8n
exports.loadMoreIdeas = async (req, res) => {
    try {
        const { limit = 10, offset = 0 } = req.body;

        // Call Python pipeline to generate more ideas
        const pythonUrl = process.env.PYTHON_PIPELINE_URL || 'http://127.0.0.1:8000';

        try {
            const pipelineResponse = await axios.post(`${pythonUrl}/generate-ideas`, {
                count: limit,
                timestamp: new Date().toISOString()
            }, {
                timeout: 300000 // 5 minutes timeout
            });

            const newIdeas = pipelineResponse.data.ideas || [];
            console.log(`[LoadMoreIdeas] Generated ${newIdeas.length} ideas via Python pipeline`);

            res.json({
                success: true,
                count: newIdeas.length,
                ideas: newIdeas
            });
        } catch (pipelineError) {
            console.error('Python pipeline error:', pipelineError.message);
            return res.status(503).json({
                success: false,
                error: 'Pipeline not available: ' + pipelineError.message
            });
        }
    } catch (error) {
        console.error('Error loading more ideas:', error);
        res.status(500).json({ error: error.message });
    }
};

// DELETE /api/ideas/:id
exports.deleteIdea = async (req, res) => {
    try {
        const { id } = req.params;
        console.log(`[Delete Idea] Deleting idea: ${id}`);

        if (supabase) {
            const { error } = await supabase
                .from('ideas')
                .delete()
                .eq('id', id);

            if (error) throw error;

            console.log(`[Delete Idea] Successfully deleted idea: ${id}`);
            res.json({ success: true, message: 'Idea deleted', idea_id: id });
        } else {
            // Mock delete
            const index = mockIdeas.findIndex(idea => idea.id === id);
            if (index > -1) {
                mockIdeas.splice(index, 1);
            }
            res.json({ success: true, message: 'Idea deleted (mock)', idea_id: id });
        }
    } catch (error) {
        console.error('[Delete Idea] Error:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/ideas/:id/rewrite — re-generate idea via Claude based on user edits
exports.rewriteIdea = async (req, res) => {
    try {
        const { id } = req.params;
        const { title = '', description = '', outline = '', keywords = [], comments = '' } = req.body || {};

        console.log(`[Rewrite Idea] id=${id}, comments length=${comments.length}`);

        const pipelineUrl = process.env.PYTHON_PIPELINE_URL || 'http://127.0.0.1:8000';
        const axios = require('axios');

        let response;
        try {
            response = await axios.post(`${pipelineUrl}/rewrite-idea`, {
                idea_id: id,
                title, description, outline,
                keywords: Array.isArray(keywords) ? keywords : String(keywords).split(',').map(s => s.trim()).filter(Boolean),
                comments,
            }, { timeout: 120000 });
        } catch (pipelineErr) {
            const details = pipelineErr.response?.data?.detail || pipelineErr.message;
            console.error('[Rewrite Idea] Pipeline error:', details);
            return res.status(502).json({ success: false, error: 'AI rewrite failed: ' + details });
        }

        return res.json(response.data);
    } catch (error) {
        console.error('[Rewrite Idea] Error:', error);
        res.status(500).json({ error: error.message });
    }
};

module.exports = exports;

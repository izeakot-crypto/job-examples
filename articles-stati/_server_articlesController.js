const supabase = require('../config/supabase');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');
const { broadcastNewArticle, broadcastImageReady } = require('../routes/sse');

const PYTHON_API_URL = process.env.PYTHON_PIPELINE_URL || process.env.PYTHON_API_URL || 'http://localhost:8000';

// Strip HTML tags and truncate text for image generation description
function stripHtmlAndTruncate(html, maxLength = 500) {
    if (!html) return '';
    const text = html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// Trigger image generation via N8n webhook (fire-and-forget)
async function triggerImageGeneration(articleId, theme, translationText) {
    try {
        const description = stripHtmlAndTruncate(translationText);
        const n8nUrl = process.env.N8N_BASE_URL || 'https://n8n.oki-toki.net';

        console.log(`[Image Gen] Triggering image generation for article ${articleId}`);
        console.log(`[Image Gen] Topic: ${theme}`);
        console.log(`[Image Gen] Description length: ${description.length} chars`);

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 120000);

        const pythonUrl = process.env.PYTHON_PIPELINE_URL || 'http://127.0.0.1:8000';
        const response = await fetch(`${pythonUrl}/generate-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic: theme, description }),
            signal: controller.signal
        });

        clearTimeout(timeout);

        if (!response.ok) {
            throw new Error(`N8n webhook returned ${response.status}`);
        }

        const result = await response.json();
        console.log(`[Image Gen] N8n response received for article ${articleId}`);

        // Extract base64 image from response
        const base64Image = result.imageBase64 || result.image || result.base64 || result.data;

        if (base64Image) {
            // Build full data URI if needed
            const mimeType = result.mimeType || 'image/png';
            const imageData = base64Image.startsWith('data:') ? base64Image : `data:${mimeType};base64,${base64Image}`;

            // Save to DB immediately so it persists
            if (supabase) {
                await supabase.from('articles_audit').update({ article_image: imageData }).eq('id', articleId);
                console.log(`[Image Gen] Image saved to DB for article ${articleId}`);
            }
            // Broadcast via SSE so frontend can show preview
            broadcastImageReady({ article_id: articleId, article_image: imageData });
        } else {
            console.warn(`[Image Gen] No image data in N8n response for article ${articleId}`);
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error(`[Image Gen] Timeout for article ${articleId}`);
        } else {
            console.error(`[Image Gen] Error for article ${articleId}:`, error.message);
        }
    }
}

// GET /api/articles?status=not_checked
exports.getArticles = async (req, res) => {
    try {
        const { status } = req.query;
        console.log(`[getArticles] Starting request with status filter: ${status || 'none'}`);

        if (supabase) {
            console.log('[getArticles] Supabase client available, querying articles_audit...');
            let query = supabase
                .from('articles_audit')
                .select('*');

            if (status) {
                query = query.eq('status', status);
            }

            const { data, error } = await query.order('created_at', { ascending: false });

            if (error) {
                console.error('[getArticles] Supabase error:', JSON.stringify(error, null, 2));
                throw error;
            }

            console.log(`[getArticles] Successfully fetched ${data?.length || 0} articles from database`);

            // Transform data for frontend - convert from separate columns to translations object
            // Use language-specific themes (theme_ua, theme_en, etc.) or fallback to theme_ua
            const articles = data.map(article => {
                const translations = {};

                // Use language-specific themes, fallback to theme_ua (main theme)
                const mainTheme = article.theme_ua || article.theme || 'Без назви';

                if (article.translation_ua) translations.uk = {
                    title: article.theme_ua || mainTheme,
                    content: article.translation_ua
                };
                if (article.translation_en) translations.en = {
                    title: article.theme_en || mainTheme,
                    content: article.translation_en
                };
                if (article.translation_ru) translations.ru = {
                    title: article.theme_ru || mainTheme,
                    content: article.translation_ru
                };
                if (article.translation_pl) translations.pl = {
                    title: article.theme_pl || mainTheme,
                    content: article.translation_pl
                };
                if (article.translation_es) translations.es = {
                    title: article.theme_es || mainTheme,
                    content: article.translation_es
                };
                if (article.translation_tr) translations.tr = {
                    title: article.theme_tr || mainTheme,
                    content: article.translation_tr
                };

                return {
                    id: article.id,
                    idea_id: article.id, // Using id as idea_id for compatibility
                    title: mainTheme,
                    theme: mainTheme,
                    description: '',
                    status: article.status || 'not_checked',
                    translations: translations,
                    date: new Date(article.created_at).toLocaleString('uk-UA'),
                    created_at: article.created_at,
                    updated_at: article.updated_at,
                    // Progress tracking
                    progress_stage: article.progress_stage || 'review_ready',
                    progress_percent: article.progress_percent || 100,
                    progress_message: article.progress_message || null,
                    // Image flag (don't send full base64 in list view)
                    has_image: !!article.article_image
                };
            });

            res.json(articles);
        } else {
            // Mock response when database is not configured
            res.json([
                {
                    id: uuidv4(),
                    title: 'Як налаштувати CRM для колл-центру',
                    theme: 'Як налаштувати CRM для колл-центру',
                    description: 'Детальна інструкція налаштування CRM',
                    status: 'not_checked',
                    date: new Date().toLocaleString('uk-UA'),
                    translations: {}
                }
            ]);
        }
    } catch (error) {
        console.error('Error fetching articles:', error);
        res.status(500).json({ error: error.message });
    }
};

// GET /api/articles/:id
exports.getArticleById = async (req, res) => {
    try {
        const { id } = req.params;

        if (supabase) {
            const { data, error } = await supabase
                .from('articles_audit')
                .select('*')
                .eq('id', id)
                .single();

            if (error) throw error;
            if (!data) {
                return res.status(404).json({ error: 'Article not found' });
            }

            // Fetch linked idea to get keywords (articles_audit.id === ideas.id)
            let ideaKeywords = null;
            try {
                const { data: ideaRow } = await supabase
                    .from('ideas')
                    .select('keywords')
                    .eq('id', id)
                    .maybeSingle();
                if (ideaRow) ideaKeywords = ideaRow.keywords;
            } catch (e) { /* ignore */ }

            // Transform to frontend format
            // Use language-specific themes, fallback to theme_ua
            const mainTheme = data.theme_ua || data.theme || 'Без назви';
            const translations = {};

            if (data.translation_ua) translations.uk = {
                title: data.theme_ua || mainTheme,
                content: data.translation_ua
            };
            if (data.translation_en) translations.en = {
                title: data.theme_en || mainTheme,
                content: data.translation_en
            };
            if (data.translation_ru) translations.ru = {
                title: data.theme_ru || mainTheme,
                content: data.translation_ru
            };
            if (data.translation_pl) translations.pl = {
                title: data.theme_pl || mainTheme,
                content: data.translation_pl
            };
            if (data.translation_es) translations.es = {
                title: data.theme_es || mainTheme,
                content: data.translation_es
            };
            if (data.translation_tr) translations.tr = {
                title: data.theme_tr || mainTheme,
                content: data.translation_tr
            };

            const article = {
                id: data.id,
                theme: mainTheme,
                status: data.status,
                translations: translations,
                created_at: data.created_at,
                updated_at: data.updated_at,
                article_image: data.article_image || null,
                // Verification fields per language
                ai_ua: data.ai_ua, ai_en: data.ai_en, ai_ru: data.ai_ru,
                ai_pl: data.ai_pl, ai_es: data.ai_es, ai_tr: data.ai_tr,
                uniqueness_ua: data.uniqueness_ua, uniqueness_en: data.uniqueness_en,
                uniqueness_ru: data.uniqueness_ru, uniqueness_pl: data.uniqueness_pl,
                uniqueness_es: data.uniqueness_es, uniqueness_tr: data.uniqueness_tr,
                zerogpt_ua: data.zerogpt_ua, zerogpt_en: data.zerogpt_en,
                zerogpt_ru: data.zerogpt_ru, zerogpt_pl: data.zerogpt_pl,
                zerogpt_es: data.zerogpt_es, zerogpt_tr: data.zerogpt_tr,
                status_ua: data.status_ua, status_en: data.status_en,
                status_ru: data.status_ru, status_pl: data.status_pl,
                status_es: data.status_es, status_tr: data.status_tr,
                overall_status: data.overall_status,
                verification_report: data.verification_report || null,
                keywords: ideaKeywords || data.keywords || null,
                meta_description: data.meta_description || {},
                wordpress_post_id: data.wordpress_post_id || null,
                wordpress_url: data.wordpress_url || null,
            };

            res.json(article);
        } else {
            // Mock response
            res.status(404).json({ error: 'Article not found' });
        }
    } catch (error) {
        console.error('Error fetching article:', error);
        res.status(500).json({ error: error.message });
    }
};

// PUT /api/articles/:id
exports.updateArticle = async (req, res) => {
    try {
        const { id } = req.params;
        const { status, theme, translations, article_image, meta_description } = req.body;

        console.log(`[Update Article] Updating article ${id}`);
        console.log(`[Update Article] Status: ${status}`);
        console.log(`[Update Article] Theme: ${theme}`);
        console.log(`[Update Article] Translations languages: ${translations ? Object.keys(translations).join(', ') : 'none'}`);
        console.log(`[Update Article] article_image: ${article_image === null ? 'DELETE' : article_image === undefined ? 'not provided' : 'provided'}`);

        if (supabase) {
            const updateData = {
                updated_at: new Date().toISOString()
            };

            if (status) updateData.status = status;

            // Handle article_image: null = delete, string = save
            if (article_image === null) {
                updateData.article_image = null;
            } else if (typeof article_image === 'string' && article_image.length > 0) {
                updateData.article_image = article_image;
            }

            // Save the main theme to theme_ua (primary theme column)
            if (theme) {
                updateData.theme_ua = theme;
            }

            // Convert translations object to separate columns
            if (translations) {
                // Ukrainian
                if (translations.uk) {
                    updateData.translation_ua = translations.uk.content;
                    // Use translations title OR main theme
                    if (translations.uk.title) updateData.theme_ua = translations.uk.title;
                }
                // English
                if (translations.en) {
                    updateData.translation_en = translations.en.content;
                    if (translations.en.title) updateData.theme_en = translations.en.title;
                }
                // Russian
                if (translations.ru) {
                    updateData.translation_ru = translations.ru.content;
                    if (translations.ru.title) updateData.theme_ru = translations.ru.title;
                }
                // Polish
                if (translations.pl) {
                    updateData.translation_pl = translations.pl.content;
                    if (translations.pl.title) updateData.theme_pl = translations.pl.title;
                }
                // Spanish
                if (translations.es) {
                    updateData.translation_es = translations.es.content;
                    if (translations.es.title) updateData.theme_es = translations.es.title;
                }
                // Turkish
                if (translations.tr) {
                    updateData.translation_tr = translations.tr.content;
                    if (translations.tr.title) updateData.theme_tr = translations.tr.title;
                }
            }

            // Meta description (qTranslate-style object: {ua, en, ru, pl, es, tr})
            if (meta_description && typeof meta_description === 'object') {
                updateData.meta_description = meta_description;
            }

            console.log(`[Update Article] Updating columns:`, Object.keys(updateData));
            console.log(`[Update Article] theme_ua will be: ${updateData.theme_ua}`);

            const { data, error } = await supabase
                .from('articles_audit')
                .update(updateData)
                .eq('id', id)
                .select()
                .single();

            if (error) {
                console.error('[Update Article] Supabase error:', error);
                throw error;
            }

            console.log(`[Update Article] Successfully updated article ${id}`);
            console.log(`[Update Article] Saved theme_ua: ${data.theme_ua}`);

            res.json({
                success: true,
                article: data,
                message: 'Article updated successfully'
            });
        } else {
            // Mock response
            res.json({
                success: true,
                message: 'Article updated (database not configured)'
            });
        }
    } catch (error) {
        console.error('[Update Article] Error:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/articles/:id/publish
exports.publishArticle = async (req, res) => {
    try {
        const { id } = req.params;
        const { article_image } = req.body;

        console.log(`[Publish Article] Publishing article ${id} to WordPress`);

        // Save image to DB before publishing (if provided)
        if (article_image && supabase) {
            await supabase
                .from('articles_audit')
                .update({ article_image })
                .eq('id', id);
            console.log(`[Publish Article] Image saved to DB for ${id}`);
        }

        // Call Python backend to publish to WordPress
        const response = await axios.post(`${PYTHON_API_URL}/publish-article`, {
            idea_id: id,
            timestamp: new Date().toISOString()
        }, { timeout: 360000 });

        console.log(`[Publish Article] WordPress result:`, response.data);

        res.json({
            success: true,
            wordpress_post_id: response.data.wordpress_post_id,
            wordpress_url: response.data.wordpress_url,
            status: response.data.status,
            message: 'Article published to WordPress as draft'
        });
    } catch (error) {
        console.error('Error publishing article:', error.response?.data || error.message);
        res.status(500).json({
            error: error.response?.data?.detail || error.message,
            success: false
        });
    }
};

// DELETE /api/articles/:id
exports.deleteArticle = async (req, res) => {
    try {
        const { id } = req.params;

        console.log(`[Delete Article] Deleting article ${id}`);

        if (supabase) {
            const { error } = await supabase
                .from('articles_audit')
                .delete()
                .eq('id', id);

            if (error) {
                console.error('Supabase error:', error);
                throw error;
            }

            console.log(`Successfully deleted article ${id}`);

            res.json({
                success: true,
                message: 'Article deleted successfully'
            });
        } else {
            // Mock response
            res.json({
                success: true,
                message: 'Article deleted (database not configured)'
            });
        }
    } catch (error) {
        console.error('Error deleting article:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/articles/save-for-review - Saves to articles_audit AND broadcasts via SSE
exports.saveForReview = async (req, res) => {
    try {
        console.log('[Save for Review] Full request body:', JSON.stringify(req.body, null, 2));

        const { id: article_id, theme, translation_ua, translation_en, translation_ru, translation_pl, translation_es, translation_tr } = req.body;

        if (!theme) {
            return res.status(400).json({
                success: false,
                error: 'theme is required'
            });
        }

        console.log(`[Save for Review] Processing article: ${article_id || 'new'}, theme: ${theme}`);
        console.log(`[Save for Review] translation_ua length: ${translation_ua ? translation_ua.length : 0} chars`);

        // Build translations object for broadcasting
        const translations = {};
        if (translation_ua) translations.uk = { title: theme, content: translation_ua };
        if (translation_en) translations.en = { title: theme, content: translation_en };
        if (translation_ru) translations.ru = { title: theme, content: translation_ru };
        if (translation_pl) translations.pl = { title: theme, content: translation_pl };
        if (translation_es) translations.es = { title: theme, content: translation_es };
        if (translation_tr) translations.tr = { title: theme, content: translation_tr };

        let savedId = article_id;

        // Save to articles_audit table
        if (supabase) {
            if (article_id) {
                // Check if article already exists
                const { data: existingArticle } = await supabase
                    .from('articles_audit')
                    .select('id')
                    .eq('id', article_id)
                    .single();

                if (existingArticle) {
                    // Update existing article
                    const { error } = await supabase
                        .from('articles_audit')
                        .update({
                            theme_ua: theme,
                            translation_ua: translation_ua || null,
                            translation_en: translation_en || null,
                            translation_ru: translation_ru || null,
                            translation_pl: translation_pl || null,
                            translation_es: translation_es || null,
                            translation_tr: translation_tr || null,
                            status: 'not_checked',
                            progress_stage: 'review_ready',
                            progress_percent: 100,
                            progress_message: 'Готово до перевірки',
                            progress_updated_at: new Date().toISOString(),
                            updated_at: new Date().toISOString()
                        })
                        .eq('id', article_id);

                    if (error) {
                        console.error('[Save for Review] Supabase update error:', error);
                        throw error;
                    }
                    console.log(`[Save for Review] Updated article in DB: ${article_id}`);
                } else {
                    // Create new article with provided ID
                    const articleData = {
                        id: article_id,
                        theme_ua: theme,
                        translation_ua: translation_ua || null,
                        translation_en: translation_en || null,
                        translation_ru: translation_ru || null,
                        translation_pl: translation_pl || null,
                        translation_es: translation_es || null,
                        translation_tr: translation_tr || null,
                        status: 'not_checked',
                        progress_stage: 'review_ready',
                        progress_percent: 100,
                        progress_message: 'Готово до перевірки',
                        progress_updated_at: new Date().toISOString(),
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString()
                    };

                    const { error } = await supabase
                        .from('articles_audit')
                        .insert([articleData]);

                    if (error) {
                        console.error('[Save for Review] Supabase insert error:', error);
                        throw error;
                    }
                    console.log(`[Save for Review] Saved new article to DB: ${article_id}`);
                }
            } else {
                // Create new article with generated ID
                savedId = uuidv4();
                const articleData = {
                    id: savedId,
                    theme_ua: theme,
                    translation_ua: translation_ua || null,
                    translation_en: translation_en || null,
                    translation_ru: translation_ru || null,
                    translation_pl: translation_pl || null,
                    translation_es: translation_es || null,
                    translation_tr: translation_tr || null,
                    status: 'not_checked',
                    progress_stage: 'review_ready',
                    progress_percent: 100,
                    progress_message: 'Готово до перевірки',
                    progress_updated_at: new Date().toISOString(),
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString()
                };

                const { error } = await supabase
                    .from('articles_audit')
                    .insert([articleData]);

                if (error) {
                    console.error('[Save for Review] Supabase insert error:', error);
                    throw error;
                }
                console.log(`[Save for Review] Saved new article to DB: ${savedId}`);
            }
        }

        // Create article object for broadcasting
        const article = {
            id: savedId,
            idea_id: savedId,
            title: theme,
            theme: theme,
            description: '',
            status: 'not_checked',
            translations: translations,
            date: new Date().toLocaleString('uk-UA'),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            // Progress tracking
            progress_stage: 'review_ready',
            progress_percent: 100,
            progress_message: 'Готово до перевірки'
        };

        // Broadcast to all connected SSE clients
        console.log(`[Save for Review] Broadcasting to SSE clients...`);
        broadcastNewArticle(article);

        // Return success response
        res.json({
            success: true,
            article_id: savedId,
            theme: theme,
            message: 'Стаття збережена в БД та відправлена на перевірку',
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error('[Save for Review] Error:', error);
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
};

// POST /api/articles/audit - Saves article to database for archival (called by separate N8n node)
exports.saveToAudit = async (req, res) => {
    try {
        const { id: article_id, theme, translation_ua, translation_en, translation_ru, translation_pl, translation_es, translation_tr } = req.body;

        if (!article_id || !theme) {
            return res.status(400).json({
                success: false,
                error: 'id and theme are required'
            });
        }

        console.log(`[Audit] Saving article to database: ${article_id}, theme: ${theme}`);

        // Build translations object
        const translations = {};
        if (translation_ua) translations.uk = { title: theme, content: translation_ua };
        if (translation_en) translations.en = { title: theme, content: translation_en };
        if (translation_ru) translations.ru = { title: theme, content: translation_ru };
        if (translation_pl) translations.pl = { title: theme, content: translation_pl };
        if (translation_es) translations.es = { title: theme, content: translation_es };
        if (translation_tr) translations.tr = { title: theme, content: translation_tr };

        if (supabase) {
            // Check if article already exists
            const { data: existingArticle } = await supabase
                .from('articles')
                .select('id')
                .eq('idea_id', article_id)
                .single();

            if (existingArticle) {
                // Update existing article
                const { data, error } = await supabase
                    .from('articles')
                    .update({
                        translations: translations,
                        updated_at: new Date().toISOString()
                    })
                    .eq('idea_id', article_id)
                    .select()
                    .single();

                if (error) {
                    console.error('[Audit] Supabase error:', error);
                    throw error;
                }

                console.log(`[Audit] Updated article in database: ${article_id}`);

                return res.json({
                    success: true,
                    article_id: data.id,
                    theme: theme,
                    message: 'Стаття оновлена в базі даних',
                    timestamp: new Date().toISOString()
                });
            } else {
                // Create new article
                const articleData = {
                    id: uuidv4(),
                    idea_id: article_id,
                    status: 'not_checked',
                    translations: translations,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString()
                };

                const { data, error } = await supabase
                    .from('articles')
                    .insert([articleData])
                    .select()
                    .single();

                if (error) {
                    console.error('[Audit] Supabase error:', error);
                    throw error;
                }

                console.log(`[Audit] Saved new article to database: ${article_id}`);

                res.json({
                    success: true,
                    article_id: data.id,
                    theme: theme,
                    message: 'Стаття збережена в базі даних',
                    timestamp: new Date().toISOString()
                });
            }
        } else {
            // No database
            res.json({
                success: false,
                error: 'Database not configured',
                timestamp: new Date().toISOString()
            });
        }
    } catch (error) {
        console.error('[Audit] Error:', error);
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
};

// POST /api/articles/:id/generate-image - Manual image generation/regeneration
exports.generateImage = async (req, res) => {
    try {
        const { id } = req.params;

        console.log(`[Generate Image] Manual trigger for article ${id}`);

        if (!supabase) {
            return res.status(500).json({ error: 'Database not configured' });
        }

        // Fetch article data
        const { data: article, error } = await supabase
            .from('articles_audit')
            .select('theme_ua, translation_ua, translation_en, translation_ru')
            .eq('id', id)
            .single();

        if (error || !article) {
            return res.status(404).json({ error: 'Article not found' });
        }

        const theme = article.theme_ua || 'Untitled';
        const text = article.translation_ua || article.translation_en || article.translation_ru || '';

        if (!text) {
            return res.status(400).json({ error: 'No article text available for image generation' });
        }

        // Return immediately, run generation in background
        res.json({ success: true, message: 'Image generation started' });

        // Fire-and-forget
        triggerImageGeneration(id, theme, text).catch(err => {
            console.error(`[Generate Image] Failed for article ${id}:`, err.message);
        });

    } catch (error) {
        console.error('[Generate Image] Error:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/articles/:id/regenerate - Re-trigger article generation via N8n
exports.regenerateArticle = async (req, res) => {
    try {
        const { id } = req.params;

        console.log(`[Regenerate] Regenerating article ${id}`);

        if (!supabase) {
            return res.status(500).json({ error: 'Database not configured' });
        }

        // Fetch article data to get idea_id and theme
        const { data: article, error: fetchError } = await supabase
            .from('articles_audit')
            .select('id, theme_ua, idea_id')
            .eq('id', id)
            .single();

        if (fetchError || !article) {
            return res.status(404).json({ error: 'Article not found' });
        }

        // Reset article to generating state
        const { error: updateError } = await supabase
            .from('articles_audit')
            .update({
                progress_stage: 'generating',
                progress_percent: 10,
                progress_message: 'Регенерация статьи...',
                progress_updated_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            })
            .eq('id', id);

        if (updateError) {
            console.error('[Regenerate] Supabase update error:', updateError);
            throw updateError;
        }

        // Broadcast progress reset via SSE
        const { broadcastProgressUpdate } = require('../routes/sse');
        if (broadcastProgressUpdate) {
            broadcastProgressUpdate({
                article_id: id,
                progress_stage: 'generating',
                progress_percent: 10,
                progress_message: 'Регенерация статьи...'
            });
        }

        // Trigger Python pipeline to regenerate
        const pythonUrl = process.env.PYTHON_PIPELINE_URL || 'http://127.0.0.1:8000';
        const webhookUrl = `${pythonUrl}/approve-idea`;

        console.log(`[Regenerate] Triggering Python pipeline: ${webhookUrl}`);

        // Fire-and-forget: trigger Python pipeline
        fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                idea_id: article.idea_id || id,
                regenerate: true
            })
        }).catch(err => {
            console.error(`[Regenerate] Pipeline error: ${err.message}`);
        });

        res.json({
            success: true,
            article_id: id,
            message: 'Regeneration started'
        });

    } catch (error) {
        console.error('[Regenerate] Error:', error);
        res.status(500).json({ error: error.message });
    }
};

// GET /api/dashboard/stats - Real dashboard statistics from database
exports.getDashboardStats = async (req, res) => {
    try {
        if (!supabase) {
            return res.json({
                articles_on_review: 0,
                articles_published: 0,
                ideas_pending: 0,
                ideas_rejected: 0,
                period_stats: { today: 0, week: 0, month: 0, total: 0 },
                articles_by_day: []
            });
        }

        // Run all queries in parallel
        const [
            reviewResult,
            publishedResult,
            pendingIdeasResult,
            rejectedIdeasResult,
            allArticlesResult
        ] = await Promise.all([
            supabase.from('articles_audit').select('id', { count: 'exact', head: true }).eq('status', 'not_checked'),
            supabase.from('articles_audit').select('id', { count: 'exact', head: true }).eq('status', 'published'),
            supabase.from('ideas').select('id', { count: 'exact', head: true }).eq('status', 'pending'),
            supabase.from('ideas').select('id', { count: 'exact', head: true }).eq('status', 'rejected'),
            supabase.from('articles_audit').select('updated_at, status').eq('status', 'published').order('updated_at', { ascending: false })
        ]);

        const articlesOnReview = reviewResult.count || 0;
        const articlesPublished = publishedResult.count || 0;
        const ideasPending = pendingIdeasResult.count || 0;
        const ideasRejected = rejectedIdeasResult.count || 0;

        // Calculate period stats
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const weekStart = new Date(todayStart);
        weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1); // Monday
        if (weekStart > todayStart) weekStart.setDate(weekStart.getDate() - 7);
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

        const allArticles = allArticlesResult.data || [];
        const totalArticles = allArticles.length;

        let todayCount = 0, weekCount = 0, monthCount = 0;
        // Articles by day for chart (last 30 days)
        const dayMap = {};
        const thirtyDaysAgo = new Date(todayStart);
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 29);

        // Initialize all 30 days with 0
        for (let d = new Date(thirtyDaysAgo); d <= todayStart; d.setDate(d.getDate() + 1)) {
            const key = d.toISOString().split('T')[0];
            dayMap[key] = 0;
        }

        for (const article of allArticles) {
            const created = new Date(article.updated_at || article.created_at);
            if (created >= todayStart) todayCount++;
            if (created >= weekStart) weekCount++;
            if (created >= monthStart) monthCount++;

            const dayKey = created.toISOString().split('T')[0];
            if (dayMap.hasOwnProperty(dayKey)) {
                dayMap[dayKey]++;
            }
        }

        // Convert dayMap to sorted array
        const articlesByDay = Object.entries(dayMap)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([date, count]) => ({ date, count }));

        res.json({
            articles_on_review: articlesOnReview,
            articles_published: articlesPublished,
            ideas_pending: ideasPending,
            ideas_rejected: ideasRejected,
            period_stats: {
                today: todayCount,
                week: weekCount,
                month: monthCount,
                total: totalArticles
            },
            articles_by_day: articlesByDay
        });

    } catch (error) {
        console.error('[Dashboard Stats] Error:', error);
        res.status(500).json({ error: error.message });
    }
};

module.exports = exports;


// Stub: uploadImage (Supabase Storage patch not applied)
const multer = require('multer');
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });
exports.uploadImage = [upload.single('image'), async (req, res) => {
    res.status(501).json({ error: 'Image upload not configured' });
}];

// Stub: deleteImage
exports.deleteImage = async (req, res) => {
    res.status(501).json({ error: 'Image delete not configured' });
};

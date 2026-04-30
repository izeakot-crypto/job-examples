"""Patch articlesController.js to save images as files instead of base64 in DB.

Changes:
1. Add fs/path requires
2. Add saveImageToFile() and deleteImageFile() helpers
3. Modify triggerImageGeneration() to save file + store URL in DB
4. Modify generateImage() to delete old file before regenerating
"""

path_file = "/var/www/seo-articles/api/controllers/articlesController.js"

with open(path_file, "r") as f:
    content = f.read()

# 1. Add fs and path requires after existing requires
old_requires = "const { broadcastNewArticle, broadcastImageReady } = require('../routes/sse');"
new_requires = """const { broadcastNewArticle, broadcastImageReady } = require('../routes/sse');
const fs = require('fs');
const path = require('path');

// Directory for article images
const IMAGES_DIR = path.join(__dirname, '../public/images');
if (!fs.existsSync(IMAGES_DIR)) {
    fs.mkdirSync(IMAGES_DIR, { recursive: true });
    console.log('[Image] Created images directory:', IMAGES_DIR);
}

// Save base64 image to file, return relative URL path
function saveImageToFile(articleId, base64Data) {
    try {
        // Parse data URI: data:image/png;base64,AAAA...
        const match = base64Data.match(/^data:image\\/(\\w+);base64,(.+)$/);
        if (!match) {
            console.error('[Image] Invalid base64 data URI format');
            return null;
        }
        const ext = match[1] === 'jpeg' ? 'jpg' : match[1];
        const buffer = Buffer.from(match[2], 'base64');
        const filename = `article-${articleId}.${ext}`;
        const filepath = path.join(IMAGES_DIR, filename);

        // Delete any old files for this article (different extensions)
        deleteImageFile(articleId);

        fs.writeFileSync(filepath, buffer);
        console.log(`[Image] Saved file: ${filename} (${(buffer.length / 1024).toFixed(1)} KB)`);
        return `/images/${filename}`;
    } catch (err) {
        console.error(`[Image] Failed to save file for article ${articleId}:`, err.message);
        return null;
    }
}

// Delete image file(s) for an article
function deleteImageFile(articleId) {
    try {
        const extensions = ['png', 'jpg', 'jpeg', 'webp'];
        for (const ext of extensions) {
            const filepath = path.join(IMAGES_DIR, `article-${articleId}.${ext}`);
            if (fs.existsSync(filepath)) {
                fs.unlinkSync(filepath);
                console.log(`[Image] Deleted old file: article-${articleId}.${ext}`);
            }
        }
    } catch (err) {
        console.error(`[Image] Failed to delete file for article ${articleId}:`, err.message);
    }
}"""

if old_requires in content:
    content = content.replace(old_requires, new_requires, 1)
    print("OK: Added fs/path requires and helper functions")
else:
    print("WARN: Could not find requires block")

# 2. Modify triggerImageGeneration to save file instead of base64 in DB
old_save = """            // Save image to DB immediately so it persists across page reloads
            console.log(`[Image Gen] Image generated for article ${articleId}, saving to DB and broadcasting`);
            try {
                if (supabase) {
                    await supabase
                        .from('articles_audit')
                        .update({ article_image: imageData })
                        .eq('id', articleId);
                    console.log(`[Image Gen] Image saved to DB for article ${articleId}`);
                }
            } catch (dbErr) {
                console.error(`[Image Gen] Failed to save image to DB: ${dbErr.message}`);
            }
            // Also broadcast via SSE so frontend updates immediately
            broadcastImageReady({ article_id: articleId, article_image: imageData });"""

new_save = """            // Save image as file (not base64 in DB) to keep DB clean
            const imageUrl = saveImageToFile(articleId, imageData);
            if (imageUrl) {
                // Store only the URL path in DB (not huge base64)
                try {
                    if (supabase) {
                        await supabase
                            .from('articles_audit')
                            .update({ article_image: imageUrl })
                            .eq('id', articleId);
                        console.log(`[Image Gen] Image URL saved to DB for article ${articleId}: ${imageUrl}`);
                    }
                } catch (dbErr) {
                    console.error(`[Image Gen] Failed to save image URL to DB: ${dbErr.message}`);
                }
                // Broadcast URL via SSE so frontend updates immediately
                broadcastImageReady({ article_id: articleId, article_image: imageUrl });
            } else {
                console.error(`[Image Gen] Failed to save image file for article ${articleId}`);
            }"""

if old_save in content:
    content = content.replace(old_save, new_save, 1)
    print("OK: Modified triggerImageGeneration to save as file")
else:
    print("WARN: Could not find old save block in triggerImageGeneration")

# 3. Modify generateImage endpoint to delete old image before regenerating
old_generate = """        // Return immediately, run generation in background
        res.json({ success: true, message: 'Image generation started' });

        // Fire-and-forget
        triggerImageGeneration(id, theme, text).catch(err => {
            console.error(`[Generate Image] Failed for article ${id}:`, err.message);
        });"""

new_generate = """        // Delete old image from DB and disk before generating new one
        console.log(`[Generate Image] Deleting old image for article ${id}`);
        deleteImageFile(id);
        try {
            await supabase
                .from('articles_audit')
                .update({ article_image: null })
                .eq('id', id);
            console.log(`[Generate Image] Old image cleared from DB for article ${id}`);
        } catch (clearErr) {
            console.error(`[Generate Image] Failed to clear old image: ${clearErr.message}`);
        }

        // Return immediately, run generation in background
        res.json({ success: true, message: 'Image generation started' });

        // Fire-and-forget
        triggerImageGeneration(id, theme, text).catch(err => {
            console.error(`[Generate Image] Failed for article ${id}:`, err.message);
        });"""

if old_generate in content:
    content = content.replace(old_generate, new_generate, 1)
    print("OK: Modified generateImage to delete old image first")
else:
    print("WARN: Could not find generateImage fire-and-forget block")

with open(path_file, "w") as f:
    f.write(content)

print("Patch complete: articlesController.js")

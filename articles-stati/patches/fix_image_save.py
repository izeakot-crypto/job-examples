"""Patch articlesController.js to save image to DB immediately"""
import re

path = "/var/www/seo-articles/api/controllers/articlesController.js"

with open(path, "r") as f:
    content = f.read()

# 1. Replace "Don't save to DB" with "Save to DB immediately"
old_block = """            // Don't save to DB yet - only on publish
            // Broadcast via SSE so frontend can show preview
            console.log(`[Image Gen] Image generated for article ${articleId}, broadcasting to frontend (not saving to DB)`);
            broadcastImageReady({ article_id: articleId, article_image: imageData });"""

new_block = """            // Save image to DB immediately so it persists across page reloads
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

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    print("OK: Replaced image save logic")
else:
    print("WARN: Old block not found, trying alternative match")
    # Try without the exact whitespace
    content = content.replace(
        "// Don't save to DB yet - only on publish",
        "// Save image to DB immediately so it persists across page reloads",
        1
    )
    content = content.replace(
        'broadcasting to frontend (not saving to DB)',
        'saving to DB and broadcasting',
        1
    )

# 2. Add supabase require at top of triggerImageGeneration if not already there
# The supabase is already required at top of file, so just need to make sure
# the function references it correctly

with open(path, "w") as f:
    f.write(content)

print("Patch complete")

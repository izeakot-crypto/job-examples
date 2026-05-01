"""Add upload-image and delete-image endpoints to articlesController.js and routes."""

import re

# 1. Add endpoints to controller
ctrl_path = "/var/www/seo-articles/api/controllers/articlesController.js"

with open(ctrl_path, "r") as f:
    content = f.read()

# Add multer require at top (after fs require)
old_fs = "const fs = require('fs');\nconst path = require('path');"
new_fs = """const fs = require('fs');
const path = require('path');
const multer = require('multer');
const upload = multer({ dest: '/tmp/uploads/', limits: { fileSize: 10 * 1024 * 1024 } });"""

if old_fs in content:
    content = content.replace(old_fs, new_fs, 1)
    print("OK: Added multer require")
else:
    print("WARN: fs/path requires not found (maybe patch not applied yet?)")

# Add upload-image and delete-image endpoints after generateImage
# Find the end of generateImage export
old_after_generate = """// POST /api/articles/:id/regenerate - Re-trigger article generation via N8n"""

new_endpoints = """// POST /api/articles/:id/upload-image - Upload image file from user
exports.uploadImage = [upload.single('image'), async (req, res) => {
    try {
        const { id } = req.params;
        console.log(`[Upload Image] Upload for article ${id}`);

        if (!req.file) {
            return res.status(400).json({ error: 'No image file provided' });
        }

        if (!supabase) {
            return res.status(500).json({ error: 'Database not configured' });
        }

        // Delete old image file
        deleteImageFile(id);

        // Move uploaded file to images directory with article ID
        const ext = path.extname(req.file.originalname).toLowerCase().replace('.', '') || 'png';
        const filename = `article-${id}.${ext}`;
        const destPath = path.join(IMAGES_DIR, filename);

        fs.renameSync(req.file.path, destPath);
        const imageUrl = `/images/${filename}`;

        console.log(`[Upload Image] Saved: ${filename} (${(req.file.size / 1024).toFixed(1)} KB)`);

        // Save URL to DB
        await supabase
            .from('articles_audit')
            .update({ article_image: imageUrl })
            .eq('id', id);

        console.log(`[Upload Image] URL saved to DB for article ${id}: ${imageUrl}`);
        res.json({ success: true, imageUrl });

    } catch (error) {
        console.error('[Upload Image] Error:', error);
        // Clean up temp file
        if (req.file && fs.existsSync(req.file.path)) {
            fs.unlinkSync(req.file.path);
        }
        res.status(500).json({ error: error.message });
    }
}];

// DELETE /api/articles/:id/delete-image - Delete image from DB and disk
exports.deleteImage = async (req, res) => {
    try {
        const { id } = req.params;
        console.log(`[Delete Image] Deleting image for article ${id}`);

        // Delete file from disk
        deleteImageFile(id);

        // Clear from DB
        if (supabase) {
            await supabase
                .from('articles_audit')
                .update({ article_image: null })
                .eq('id', id);
            console.log(`[Delete Image] Cleared from DB for article ${id}`);
        }

        res.json({ success: true, message: 'Image deleted' });

    } catch (error) {
        console.error('[Delete Image] Error:', error);
        res.status(500).json({ error: error.message });
    }
};

// POST /api/articles/:id/regenerate - Re-trigger article generation via N8n"""

if old_after_generate in content:
    content = content.replace(old_after_generate, new_endpoints, 1)
    print("OK: Added upload-image and delete-image endpoints")
else:
    print("WARN: Could not find regenerate comment marker")

with open(ctrl_path, "w") as f:
    f.write(content)

print("Patch complete: articlesController.js endpoints")

# 2. Add routes
routes_path = "/var/www/seo-articles/api/routes/articles.js"

with open(routes_path, "r") as f:
    routes = f.read()

old_route = "// POST /api/articles/:id/generate-image\nrouter.post('/:id/generate-image', articlesController.generateImage);"
new_route = """// POST /api/articles/:id/generate-image
router.post('/:id/generate-image', articlesController.generateImage);

// POST /api/articles/:id/upload-image
router.post('/:id/upload-image', ...articlesController.uploadImage);

// DELETE /api/articles/:id/delete-image
router.delete('/:id/delete-image', articlesController.deleteImage);"""

if old_route in routes:
    routes = routes.replace(old_route, new_route, 1)
    print("OK: Added upload-image and delete-image routes")
else:
    print("WARN: Could not find generate-image route")

with open(routes_path, "w") as f:
    f.write(routes)

print("Patch complete: routes/articles.js")

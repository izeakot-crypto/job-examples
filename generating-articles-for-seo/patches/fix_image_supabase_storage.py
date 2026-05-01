"""Patch articlesController.js to use Supabase Storage instead of local filesystem.

Replaces local file saving with Supabase Storage bucket 'article-images'.
"""

path_file = "/var/www/seo-articles/api/controllers/articlesController.js"

with open(path_file, "r") as f:
    content = f.read()

# 1. Remove local fs/multer/IMAGES_DIR block, replace with Supabase Storage helpers
old_fs_block = """const fs = require('fs');
const path = require('path');
const multer = require('multer');
const upload = multer({ dest: '/tmp/uploads/', limits: { fileSize: 10 * 1024 * 1024 } });

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

new_storage_block = """const path = require('path');
const multer = require('multer');
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

const SUPABASE_BUCKET = 'article-images';

// Initialize Supabase Storage bucket (runs once on startup)
async function initStorageBucket() {
    if (!supabase) return;
    try {
        const { data: buckets } = await supabase.storage.listBuckets();
        const exists = buckets?.some(b => b.name === SUPABASE_BUCKET);
        if (!exists) {
            await supabase.storage.createBucket(SUPABASE_BUCKET, { public: true });
            console.log(`[Storage] Created bucket: ${SUPABASE_BUCKET}`);
        } else {
            console.log(`[Storage] Bucket exists: ${SUPABASE_BUCKET}`);
        }
    } catch (err) {
        console.error('[Storage] Failed to init bucket:', err.message);
    }
}
initStorageBucket();

// Upload base64 image to Supabase Storage, return public URL
async function saveImageToStorage(articleId, base64Data) {
    try {
        const match = base64Data.match(/^data:image\\/(\\w+);base64,(.+)$/);
        if (!match) {
            console.error('[Storage] Invalid base64 data URI format');
            return null;
        }
        const ext = match[1] === 'jpeg' ? 'jpg' : match[1];
        const buffer = Buffer.from(match[2], 'base64');
        const filename = `article-${articleId}.${ext}`;
        const contentType = `image/${match[1]}`;

        // Delete old files first
        await deleteImageFromStorage(articleId);

        // Upload to Supabase Storage
        const { data, error } = await supabase.storage
            .from(SUPABASE_BUCKET)
            .upload(filename, buffer, {
                contentType,
                upsert: true
            });

        if (error) {
            console.error(`[Storage] Upload error: ${error.message}`);
            return null;
        }

        // Get public URL
        const { data: urlData } = supabase.storage
            .from(SUPABASE_BUCKET)
            .getPublicUrl(filename);

        const publicUrl = urlData.publicUrl;
        console.log(`[Storage] Uploaded: ${filename} (${(buffer.length / 1024).toFixed(1)} KB) -> ${publicUrl}`);
        return publicUrl;
    } catch (err) {
        console.error(`[Storage] Failed to upload for article ${articleId}:`, err.message);
        return null;
    }
}

// Upload file buffer to Supabase Storage
async function saveFileToStorage(articleId, fileBuffer, originalName) {
    try {
        const ext = path.extname(originalName).toLowerCase().replace('.', '') || 'png';
        const filename = `article-${articleId}.${ext}`;
        const contentType = `image/${ext === 'jpg' ? 'jpeg' : ext}`;

        await deleteImageFromStorage(articleId);

        const { data, error } = await supabase.storage
            .from(SUPABASE_BUCKET)
            .upload(filename, fileBuffer, {
                contentType,
                upsert: true
            });

        if (error) {
            console.error(`[Storage] Upload error: ${error.message}`);
            return null;
        }

        const { data: urlData } = supabase.storage
            .from(SUPABASE_BUCKET)
            .getPublicUrl(filename);

        const publicUrl = urlData.publicUrl;
        console.log(`[Storage] Uploaded file: ${filename} (${(fileBuffer.length / 1024).toFixed(1)} KB) -> ${publicUrl}`);
        return publicUrl;
    } catch (err) {
        console.error(`[Storage] Failed to upload file for article ${articleId}:`, err.message);
        return null;
    }
}

// Delete image from Supabase Storage
async function deleteImageFromStorage(articleId) {
    try {
        const extensions = ['png', 'jpg', 'jpeg', 'webp'];
        const filesToDelete = extensions.map(ext => `article-${articleId}.${ext}`);

        const { data, error } = await supabase.storage
            .from(SUPABASE_BUCKET)
            .remove(filesToDelete);

        if (error) {
            console.error(`[Storage] Delete error: ${error.message}`);
        } else if (data && data.length > 0) {
            console.log(`[Storage] Deleted old files for article ${articleId}`);
        }
    } catch (err) {
        console.error(`[Storage] Failed to delete for article ${articleId}:`, err.message);
    }
}"""

if old_fs_block in content:
    content = content.replace(old_fs_block, new_storage_block, 1)
    print("OK: Replaced local fs with Supabase Storage helpers")
else:
    print("WARN: Local fs block not found")

# 2. Fix triggerImageGeneration to use saveImageToStorage
old_save_image = """            // Save image as file (not base64 in DB) to keep DB clean
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

new_save_image = """            // Upload to Supabase Storage (not base64 in DB)
            const imageUrl = await saveImageToStorage(articleId, imageData);
            if (imageUrl) {
                // Store only the public URL in DB
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
                console.error(`[Image Gen] Failed to upload image for article ${articleId}`);
            }"""

if old_save_image in content:
    content = content.replace(old_save_image, new_save_image, 1)
    print("OK: Fixed triggerImageGeneration for Supabase Storage")
else:
    print("WARN: triggerImageGeneration save block not found")

# 3. Fix generateImage endpoint — use deleteImageFromStorage
old_delete_gen = """        // Delete old image from DB and disk before generating new one
        console.log(`[Generate Image] Deleting old image for article ${id}`);
        deleteImageFile(id);"""

new_delete_gen = """        // Delete old image from Supabase Storage and DB before generating new one
        console.log(`[Generate Image] Deleting old image for article ${id}`);
        await deleteImageFromStorage(id);"""

if old_delete_gen in content:
    content = content.replace(old_delete_gen, new_delete_gen, 1)
    print("OK: Fixed generateImage delete for Supabase Storage")
else:
    print("WARN: generateImage delete block not found")

# 4. Fix uploadImage endpoint — use saveFileToStorage
old_upload = """// POST /api/articles/:id/upload-image - Upload image file from user
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
}];"""

new_upload = """// POST /api/articles/:id/upload-image - Upload image file to Supabase Storage
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

        // Upload to Supabase Storage
        const imageUrl = await saveFileToStorage(id, req.file.buffer, req.file.originalname);

        if (!imageUrl) {
            return res.status(500).json({ error: 'Failed to upload to storage' });
        }

        // Save URL to DB
        await supabase
            .from('articles_audit')
            .update({ article_image: imageUrl })
            .eq('id', id);

        console.log(`[Upload Image] URL saved to DB for article ${id}: ${imageUrl}`);
        res.json({ success: true, imageUrl });

    } catch (error) {
        console.error('[Upload Image] Error:', error);
        res.status(500).json({ error: error.message });
    }
}];"""

if old_upload in content:
    content = content.replace(old_upload, new_upload, 1)
    print("OK: Fixed uploadImage for Supabase Storage")
else:
    print("WARN: uploadImage block not found")

# 5. Fix deleteImage endpoint — use deleteImageFromStorage
old_delete_ep = """// DELETE /api/articles/:id/delete-image - Delete image from DB and disk
exports.deleteImage = async (req, res) => {
    try {
        const { id } = req.params;
        console.log(`[Delete Image] Deleting image for article ${id}`);

        // Delete file from disk
        deleteImageFile(id);"""

new_delete_ep = """// DELETE /api/articles/:id/delete-image - Delete image from Supabase Storage and DB
exports.deleteImage = async (req, res) => {
    try {
        const { id } = req.params;
        console.log(`[Delete Image] Deleting image for article ${id}`);

        // Delete from Supabase Storage
        await deleteImageFromStorage(id);"""

if old_delete_ep in content:
    content = content.replace(old_delete_ep, new_delete_ep, 1)
    print("OK: Fixed deleteImage for Supabase Storage")
else:
    print("WARN: deleteImage block not found")

with open(path_file, "w") as f:
    f.write(content)

print("Patch complete: Supabase Storage")

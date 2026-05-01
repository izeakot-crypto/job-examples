"""Patch script.js to handle image URLs (file paths) instead of only base64.

Changes:
1. updateEditorImage() - handle both /images/... URLs and data: base64
2. uploadFeaturedImage handler - upload file to server, get URL back
3. deleteFeaturedImage - also delete file on server
4. Add upload endpoint call for file uploads
"""

path_file = "/var/www/seo-articles/api/public/script.js"

with open(path_file, "r") as f:
    content = f.read()

# 1. Fix updateEditorImage to handle both URL paths and base64
old_update = """// Update editor image preview with base64 data
function updateEditorImage(base64Data) {
    const img = document.getElementById('featured-image-img');
    const placeholder = document.getElementById('image-placeholder');

    if (img && placeholder) {
        // Add data URI prefix if not present
        if (base64Data && !base64Data.startsWith('data:')) {
            base64Data = 'data:image/png;base64,' + base64Data;
        }
        img.src = base64Data;
        img.style.display = 'block';
        placeholder.style.display = 'none';
    }
}"""

new_update = """// Update editor image preview (handles both URL paths and base64)
function updateEditorImage(imageData) {
    const img = document.getElementById('featured-image-img');
    const placeholder = document.getElementById('image-placeholder');

    if (img && placeholder) {
        if (imageData && imageData.startsWith('/images/')) {
            // File URL path - prepend API base
            img.src = API_BASE_URL + imageData + '?t=' + Date.now();
        } else if (imageData && imageData.startsWith('data:')) {
            // Base64 data URI
            img.src = imageData;
        } else if (imageData) {
            // Raw base64 without prefix
            img.src = 'data:image/png;base64,' + imageData;
        }
        img.style.display = 'block';
        placeholder.style.display = 'none';
    }
}"""

if old_update in content:
    content = content.replace(old_update, new_update, 1)
    print("OK: Fixed updateEditorImage for URL paths")
else:
    print("WARN: updateEditorImage block not found")

# 2. Fix upload handler to upload file to server instead of sending base64 to DB
old_upload = """function handleFeaturedImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        showNotification('Пожалуйста, выберите изображение', 'error');
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        const base64Full = e.target.result;
        currentArticleImage = base64Full;
        updateEditorImage(base64Full);
        // Save uploaded image to DB immediately
        if (currentArticleId) {
            fetch(`${API_BASE_URL}/api/articles/${currentArticleId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ article_image: base64Full })
            }).then(() => {
                console.log('[Image] Uploaded image saved to DB');
            }).catch(err => {
                console.error('[Image] Failed to save uploaded image to DB:', err);
            });
        }
        showNotification('Изображение загружено и сохранено', 'success');
    };
    reader.readAsDataURL(file);
    event.target.value = '';
}"""

new_upload = """function handleFeaturedImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        showNotification('Пожалуйста, выберите изображение', 'error');
        return;
    }

    if (!currentArticleId) {
        showNotification('Сначала откройте статью', 'error');
        return;
    }

    // Upload file to server via FormData
    const formData = new FormData();
    formData.append('image', file);

    showNotification('Загрузка изображения...', 'info');

    fetch(`${API_BASE_URL}/api/articles/${currentArticleId}/upload-image`, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.imageUrl) {
            currentArticleImage = data.imageUrl;
            updateEditorImage(data.imageUrl);
            showNotification('Изображение загружено и сохранено', 'success');
            console.log('[Image] Uploaded and saved:', data.imageUrl);
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    })
    .catch(err => {
        console.error('[Image] Upload failed:', err);
        showNotification('Ошибка загрузки: ' + err.message, 'error');
    });

    event.target.value = '';
}"""

if old_upload in content:
    content = content.replace(old_upload, new_upload, 1)
    print("OK: Fixed upload handler to use file upload")
else:
    print("WARN: Upload handler block not found")

# 3. Fix deleteFeaturedImage to use delete endpoint
old_delete = """// Delete featured image (from memory AND DB)
function deleteFeaturedImage() {
    if (!confirm('Удалить изображение?')) return;

    currentArticleImage = null;
    showImagePlaceholder();

    // Also delete from DB
    if (currentArticleId) {
        fetch(`${API_BASE_URL}/api/articles/${currentArticleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article_image: null })
        }).then(() => {
            console.log('[Image] Deleted from DB');
        }).catch(err => {
            console.error('[Image] Failed to delete from DB:', err);
        });
    }

    showNotification('Изображение удалено', 'success');
}"""

new_delete = """// Delete featured image (from DB and disk)
function deleteFeaturedImage() {
    if (!confirm('Удалить изображение?')) return;

    currentArticleImage = null;
    showImagePlaceholder();

    // Delete from DB and file system
    if (currentArticleId) {
        fetch(`${API_BASE_URL}/api/articles/${currentArticleId}/delete-image`, {
            method: 'DELETE'
        }).then(res => res.json())
        .then(data => {
            console.log('[Image] Deleted from DB and disk:', data);
        }).catch(err => {
            console.error('[Image] Failed to delete:', err);
        });
    }

    showNotification('Изображение удалено', 'success');
}"""

if old_delete in content:
    content = content.replace(old_delete, new_delete, 1)
    print("OK: Fixed deleteFeaturedImage to use delete endpoint")
else:
    print("WARN: deleteFeaturedImage block not found")

# 4. Fix SSE handler to handle URL paths
old_sse = """                    currentArticleImage = data.article_image;
                    updateEditorImage(data.article_image);"""

new_sse = """                    currentArticleImage = data.article_image;
                    updateEditorImage(data.article_image);
                    console.log('[SSE] Image received:', data.article_image?.substring(0, 60));"""

if old_sse in content:
    content = content.replace(old_sse, new_sse, 1)
    print("OK: Added SSE image logging")
else:
    print("WARN: SSE handler block not found")

with open(path_file, "w") as f:
    f.write(content)

print("Patch complete: script.js")

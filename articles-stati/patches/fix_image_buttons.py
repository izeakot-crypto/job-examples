"""Patch script.js to fix image delete (save to DB) and ensure persistence"""

path = "/var/www/seo-articles/api/public/script.js"

with open(path, "r") as f:
    content = f.read()

# 1. Fix deleteFeaturedImage to also delete from DB
old_delete = """// Delete featured image (from memory only, not DB)
function deleteFeaturedImage() {
    if (!confirm('Удалить изображение?')) return;

    currentArticleImage = null;
    showImagePlaceholder();
    showNotification('Изображение удалено', 'success');
}"""

new_delete = """// Delete featured image (from memory AND DB)
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

if old_delete in content:
    content = content.replace(old_delete, new_delete, 1)
    print("OK: Fixed deleteFeaturedImage to delete from DB")
else:
    print("WARN: deleteFeaturedImage block not found")

# 2. Fix uploadFeaturedImage to also save to DB
old_upload_notify = "        showNotification('Изображение загружено (сохранится при публикации)', 'success');"
new_upload_notify = """        // Save uploaded image to DB immediately
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
        showNotification('Изображение загружено и сохранено', 'success');"""

if old_upload_notify in content:
    content = content.replace(old_upload_notify, new_upload_notify, 1)
    print("OK: Fixed upload to save to DB immediately")
else:
    print("WARN: Upload notification not found")

with open(path, "w") as f:
    f.write(content)

print("Patch complete")

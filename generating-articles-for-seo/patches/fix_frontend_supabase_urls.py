"""Fix frontend updateEditorImage to handle Supabase Storage URLs."""

path_file = "/var/www/seo-articles/api/public/script.js"

with open(path_file, "r") as f:
    content = f.read()

old_update = """// Update editor image preview (handles both URL paths and base64)
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

new_update = """// Update editor image preview (handles Supabase URLs, local paths, and base64)
function updateEditorImage(imageData) {
    const img = document.getElementById('featured-image-img');
    const placeholder = document.getElementById('image-placeholder');

    if (img && placeholder && imageData) {
        if (imageData.startsWith('http')) {
            // Full URL (Supabase Storage)
            img.src = imageData;
        } else if (imageData.startsWith('/images/')) {
            // Local file path (legacy)
            img.src = API_BASE_URL + imageData;
        } else if (imageData.startsWith('data:')) {
            // Base64 data URI (legacy)
            img.src = imageData;
        } else {
            // Raw base64 without prefix (legacy)
            img.src = 'data:image/png;base64,' + imageData;
        }
        img.style.display = 'block';
        placeholder.style.display = 'none';
    }
}"""

if old_update in content:
    content = content.replace(old_update, new_update, 1)
    print("OK: Fixed updateEditorImage for Supabase URLs")
else:
    print("WARN: updateEditorImage block not found")

with open(path_file, "w") as f:
    f.write(content)

print("Patch complete: frontend Supabase URLs")

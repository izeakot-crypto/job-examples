# Інтеграція з соцмережами

## YouTube API

### Налаштування
1. Створіть проєкт в Google Cloud Console
2. Увімкніть YouTube Data API v3
3. Створіть API ключ

### Пошук каналу компанії
```
GET https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q=COMPANY_NAME&key=YOUR_API_KEY
```

### Отримання останніх відео
```
GET https://www.googleapis.com/youtube/v3/search?part=snippet&channelId=CHANNEL_ID&order=date&maxResults=10&key=YOUR_API_KEY
```

### Отримання коментарів до відео
```
GET https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId=VIDEO_ID&maxResults=100&key=YOUR_API_KEY
```

### Приклад n8n конфігурації

**HTTP Request node для YouTube:**
```json
{
  "method": "GET",
  "url": "https://www.googleapis.com/youtube/v3/search",
  "qs": {
    "part": "snippet",
    "channelId": "={{ $json.youtubeChannelId }}",
    "order": "date",
    "maxResults": 10,
    "key": "={{ $credentials.youtubeApiKey }}"
  }
}
```

**Code node для обробки відповіді:**
```javascript
const videos = $input.item.json.items || [];

return videos.map(video => ({
  title: video.snippet.title,
  description: video.snippet.description,
  publishedAt: video.snippet.publishedAt,
  videoId: video.id.videoId,
  thumbnail: video.snippet.thumbnails.default.url,
  channelTitle: video.snippet.channelTitle
}));
```

---

## Facebook Graph API

### Налаштування
1. Створіть Facebook App на developers.facebook.com
2. Додайте доступ до Pages
3. Отримайте Page Access Token

### Отримання постів сторінки
```
GET https://graph.facebook.com/v18.0/PAGE_ID/posts?fields=id,message,created_time,likes.summary(true),comments.summary(true),shares&access_token=YOUR_TOKEN
```

### Отримання коментарів до поста
```
GET https://graph.facebook.com/v18.0/POST_ID/comments?fields=message,created_time,from&access_token=YOUR_TOKEN
```

### Приклад n8n конфігурації

**HTTP Request node для Facebook:**
```json
{
  "method": "GET",
  "url": "https://graph.facebook.com/v18.0/{{ $json.facebookPageId }}/posts",
  "qs": {
    "fields": "id,message,created_time,likes.summary(true),comments.summary(true),shares",
    "access_token": "={{ $credentials.facebookAccessToken }}",
    "limit": 10
  }
}
```

**Code node для обробки:**
```javascript
const posts = $input.item.json.data || [];

return posts.map(post => ({
  id: post.id,
  message: post.message || '',
  createdAt: post.created_time,
  likes: post.likes?.summary?.total_count || 0,
  comments: post.comments?.summary?.total_count || 0,
  shares: post.shares?.count || 0
}));
```

---

## LinkedIn API

### Налаштування
1. Створіть LinkedIn App
2. Налаштуйте OAuth 2.0
3. Отримайте Access Token з правами r_organization_social

### Отримання постів організації
```
GET https://api.linkedin.com/v2/shares?q=owners&owners=urn:li:organization:ORGANIZATION_ID&count=10
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Приклад n8n конфігурації

**HTTP Request node для LinkedIn:**
```json
{
  "method": "GET",
  "url": "https://api.linkedin.com/v2/shares",
  "qs": {
    "q": "owners",
    "owners": "={{ $json.linkedinOrgId }}",
    "count": 10
  },
  "headers": {
    "Authorization": "Bearer {{ $credentials.linkedinAccessToken }}",
    "X-Restli-Protocol-Version": "2.0.0"
  }
}
```

---

## Twitter/X API

### Налаштування
1. Створіть Developer Account на developer.twitter.com
2. Створіть App
3. Отримайте Bearer Token

### Пошук твітів компанії
```
GET https://api.twitter.com/2/tweets/search/recent?query=from:USERNAME&max_results=10
Authorization: Bearer YOUR_BEARER_TOKEN
```

### Приклад n8n конфігурації

**HTTP Request node для Twitter:**
```json
{
  "method": "GET",
  "url": "https://api.twitter.com/2/tweets/search/recent",
  "qs": {
    "query": "from:{{ $json.twitterUsername }}",
    "max_results": 10,
    "tweet.fields": "created_at,public_metrics,author_id"
  },
  "headers": {
    "Authorization": "Bearer {{ $credentials.twitterBearerToken }}"
  }
}
```

---

## Загальна структура workflow для соцмереж

```
1. Loop Over Companies
   ↓
2. IF company.monitoring.socialMedia.youtube == true
   ↓
3. Fetch YouTube Videos
   ↓
4. Parse YouTube Data
   ↓
5. Fetch Video Comments (optional)
   ↓
6. IF company.monitoring.socialMedia.facebook == true
   ↓
7. Fetch Facebook Posts
   ↓
8. Parse Facebook Data
   ↓
9. IF company.monitoring.socialMedia.linkedin == true
   ↓
10. Fetch LinkedIn Posts
    ↓
11. Parse LinkedIn Data
    ↓
12. Merge All Social Data
    ↓
13. AI Analysis of Social Content
    ↓
14. Save Results
```

---

## AI Промпти для аналізу соцмереж

### Аналіз контенту
```
Проаналізуй наступні пости конкурента {{ company }} з соцмереж:

YouTube відео:
{{ youtubeVideos }}

Facebook пости:
{{ facebookPosts }}

LinkedIn публікації:
{{ linkedinPosts }}

Видай аналіз:
1. Які теми найчастіше обговорюються
2. Які нові продукти/фічі анонсуються
3. Який тон комунікації (професійний, casual, агресивний маркетинг)
4. Яка engagement rate (лайки, коментарі, shares)
5. Які ключові повідомлення для аудиторії
```

### Аналіз коментарів
```
Проаналізуй коментарі клієнтів під постами {{ company }}:

Коментарі:
{{ comments }}

Визнач:
1. Основні "болі" клієнтів
2. Найчастіші питання
3. Позитивні відгуки (що подобається)
4. Негативні відгуки (що не подобається)
5. Запити на нові функції
6. Загальний сентимент (позитивний/негативний/нейтральний)
```

---

## Rate Limits та Best Practices

### YouTube Data API
- Квота: 10,000 units/день (базова)
- Search cost: 100 units
- Videos list: 1 unit
- Comments list: 1 unit

**Порада:** Кешуйте дані, робіть запити не частіше 1 разу на день

### Facebook Graph API
- Rate limit: 200 calls/hour/user
- Page rate limit: залежить від кількості підписників

**Порада:** Використовуйте batch requests для оптимізації

### LinkedIn API
- Rate limit: варіюється, зазвичай 100 requests/день для базового плану

**Порада:** Запитуйте тільки необхідні поля

### Twitter API
- Free tier: 1,500 tweets/month
- Basic tier ($100/month): 10,000 tweets/month

**Порада:** Фільтруйте запити, використовуйте правильні query parameters

---

## Обробка помилок

### Приклад Error Handler в n8n

**Code node для обробки помилок API:**
```javascript
try {
  const response = $input.item.json;

  if (response.error) {
    return {
      success: false,
      error: response.error.message || 'Unknown error',
      platform: $json.platform,
      company: $json.company
    };
  }

  return {
    success: true,
    data: response
  };
} catch (error) {
  return {
    success: false,
    error: error.message,
    platform: $json.platform,
    company: $json.company
  };
}
```

### Retry логіка

Додайте Wait node з затримкою 5-10 секунд між запитами для уникнення rate limits.

---

## Планування збору даних

### Рекомендована частота

- **YouTube:** 1 раз на день (нові відео публікуються не так часто)
- **Facebook:** 2-3 рази на день (вища активність)
- **LinkedIn:** 1 раз на день (B2B контент оновлюється рідше)
- **Twitter:** 3-4 рази на день (найвища частота постів)

### Оптимізація

1. Збирайте спочатку дані з high-priority компаній
2. Використовуйте conditional logic для пропуску неактивних акаунтів
3. Зберігайте дані локально для порівняння
4. Нотифікуйте тільки про значні зміни

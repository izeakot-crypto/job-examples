# n8n Code Snippets для моніторингу

## Парсинг HTML контенту

### 1. Парсинг мета-тегів

```javascript
// Code node: Parse SEO Meta Tags
const html = $input.item.json.body || '';
const company = $input.item.json.company || 'Unknown';
const url = $input.item.json.url || '';

// Helper function to extract meta content
function getMetaContent(html, pattern) {
  const match = html.match(pattern);
  return match ? match[1].trim() : null;
}

// Extract meta tags
const title = getMetaContent(html, /<title[^>]*>([^<]+)<\/title>/i);
const description = getMetaContent(html, /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i);
const ogTitle = getMetaContent(html, /<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i);
const ogDescription = getMetaContent(html, /<meta[^>]*property=["']og:description["'][^>]*content=["']([^"']+)["']/i);
const keywords = getMetaContent(html, /<meta[^>]*name=["']keywords["'][^>]*content=["']([^"']+)["']/i);

// Extract headers
const h1Tags = (html.match(/<h1[^>]*>([^<]+)<\/h1>/gi) || [])
  .map(h => h.replace(/<[^>]+>/g, '').trim());

const h2Tags = (html.match(/<h2[^>]*>([^<]+)<\/h2>/gi) || [])
  .map(h => h.replace(/<[^>]+>/g, '').trim())
  .slice(0, 10); // First 10 H2s

return {
  company: company,
  url: url,
  timestamp: new Date().toISOString(),
  seo: {
    title: title,
    description: description,
    ogTitle: ogTitle,
    ogDescription: ogDescription,
    keywords: keywords ? keywords.split(',').map(k => k.trim()) : [],
    h1Tags: h1Tags,
    h2Tags: h2Tags,
    titleLength: title ? title.length : 0,
    descriptionLength: description ? description.length : 0
  }
};
```

### 2. Парсинг блогу

```javascript
// Code node: Parse Blog Posts
const html = $input.item.json.body || '';
const company = $input.item.json.company || 'Unknown';
const baseUrl = $input.item.json.url || '';

// Multiple patterns to try for different blog platforms
const articlePatterns = [
  /<article[^>]*>([\s\S]*?)<\/article>/gi,
  /<div[^>]*class="[^"]*post[^"]*"[^>]*>([\s\S]*?)<\/div>/gi,
  /<div[^>]*class="[^"]*entry[^"]*"[^>]*>([\s\S]*?)<\/div>/gi
];

let articles = [];

// Try each pattern
for (const pattern of articlePatterns) {
  const matches = html.matchAll(pattern);
  articles = Array.from(matches);
  if (articles.length > 0) break;
}

// Parse each article
const posts = articles.slice(0, 20).map((article, index) => {
  const articleHtml = article[0];

  // Extract title
  const titleMatch = articleHtml.match(/<h[1-3][^>]*>([^<]+)<\/h[1-3]>/i);
  const title = titleMatch ? titleMatch[1].trim() : null;

  // Extract link
  const linkMatch = articleHtml.match(/href=["']([^"']+)["']/i);
  let link = linkMatch ? linkMatch[1] : null;

  // Make absolute URL
  if (link && !link.startsWith('http')) {
    link = new URL(link, baseUrl).href;
  }

  // Extract date
  const datePatterns = [
    /<time[^>]*datetime=["']([^"']+)["']/i,
    /<span[^>]*class="[^"]*date[^"]*"[^>]*>([^<]+)<\/span>/i,
    /(\d{4}-\d{2}-\d{2})/
  ];

  let publishedDate = null;
  for (const datePattern of datePatterns) {
    const dateMatch = articleHtml.match(datePattern);
    if (dateMatch) {
      publishedDate = dateMatch[1];
      break;
    }
  }

  // Extract excerpt (first paragraph or first 200 chars)
  const textContent = articleHtml.replace(/<[^>]+>/g, ' ').trim();
  const excerpt = textContent.substring(0, 300).trim() + '...';

  return {
    title: title || `Post ${index + 1}`,
    link: link,
    publishedDate: publishedDate,
    excerpt: excerpt
  };
}).filter(post => post.title && post.link); // Only valid posts

return {
  company: company,
  url: baseUrl,
  timestamp: new Date().toISOString(),
  blogPosts: posts,
  totalFound: posts.length
};
```

### 3. Детектування змін

```javascript
// Code node: Detect Changes
const currentData = $input.item.json.current;
const previousData = $input.item.json.previous;
const company = currentData.company;

const changes = [];

// Check title change
if (currentData.seo.title !== previousData.seo.title) {
  changes.push({
    type: 'title_change',
    field: 'Title',
    oldValue: previousData.seo.title,
    newValue: currentData.seo.title,
    priority: 'medium'
  });
}

// Check description change
if (currentData.seo.description !== previousData.seo.description) {
  changes.push({
    type: 'description_change',
    field: 'Description',
    oldValue: previousData.seo.description,
    newValue: currentData.seo.description,
    priority: 'medium'
  });
}

// Check for new blog posts
const previousPostTitles = (previousData.blogPosts || []).map(p => p.title);
const newPosts = (currentData.blogPosts || []).filter(
  post => !previousPostTitles.includes(post.title)
);

if (newPosts.length > 0) {
  changes.push({
    type: 'new_blog_posts',
    field: 'Blog',
    count: newPosts.length,
    newPosts: newPosts,
    priority: 'high'
  });
}

// Check H1 changes
const h1Changed = JSON.stringify(currentData.seo.h1Tags) !== JSON.stringify(previousData.seo.h1Tags);
if (h1Changed) {
  changes.push({
    type: 'h1_change',
    field: 'H1 Headers',
    oldValue: previousData.seo.h1Tags,
    newValue: currentData.seo.h1Tags,
    priority: 'low'
  });
}

return {
  company: company,
  timestamp: new Date().toISOString(),
  hasChanges: changes.length > 0,
  changesCount: changes.length,
  changes: changes,
  currentData: currentData,
  previousData: previousData
};
```

### 4. Аналіз сентименту коментарів

```javascript
// Code node: Sentiment Analysis Helper
const comments = $input.item.json.comments || [];
const company = $input.item.json.company;

// Simple keyword-based sentiment analysis
const positiveKeywords = [
  'excellent', 'great', 'amazing', 'wonderful', 'fantastic', 'love',
  'best', 'perfect', 'awesome', 'brilliant', 'outstanding', 'helpful',
  'easy', 'simple', 'reliable', 'recommend'
];

const negativeKeywords = [
  'terrible', 'awful', 'bad', 'worst', 'hate', 'horrible', 'useless',
  'poor', 'disappointing', 'frustrated', 'angry', 'broken', 'bug',
  'issue', 'problem', 'difficult', 'complicated', 'expensive'
];

function analyzeSentiment(text) {
  const lowerText = text.toLowerCase();

  let positiveCount = 0;
  let negativeCount = 0;

  positiveKeywords.forEach(keyword => {
    if (lowerText.includes(keyword)) positiveCount++;
  });

  negativeKeywords.forEach(keyword => {
    if (lowerText.includes(keyword)) negativeCount++;
  });

  if (positiveCount > negativeCount) return 'positive';
  if (negativeCount > positiveCount) return 'negative';
  return 'neutral';
}

// Analyze each comment
const analyzedComments = comments.map(comment => ({
  ...comment,
  sentiment: analyzeSentiment(comment.text || comment.message || '')
}));

// Calculate overall sentiment
const sentimentCounts = {
  positive: analyzedComments.filter(c => c.sentiment === 'positive').length,
  neutral: analyzedComments.filter(c => c.sentiment === 'neutral').length,
  negative: analyzedComments.filter(c => c.sentiment === 'negative').length
};

const total = comments.length;
const sentimentPercentage = {
  positive: total > 0 ? Math.round((sentimentCounts.positive / total) * 100) : 0,
  neutral: total > 0 ? Math.round((sentimentCounts.neutral / total) * 100) : 0,
  negative: total > 0 ? Math.round((sentimentCounts.negative / total) * 100) : 0
};

return {
  company: company,
  timestamp: new Date().toISOString(),
  totalComments: total,
  sentimentCounts: sentimentCounts,
  sentimentPercentage: sentimentPercentage,
  overallSentiment: sentimentCounts.positive > sentimentCounts.negative ? 'positive' :
                    sentimentCounts.negative > sentimentCounts.positive ? 'negative' : 'neutral',
  comments: analyzedComments
};
```

### 5. Формування Telegram нотифікації

```javascript
// Code node: Format Telegram Notification
const data = $input.item.json;
const company = data.company;
const changes = data.changes || [];

if (!data.hasChanges || changes.length === 0) {
  return {
    skip: true,
    message: 'No changes to notify'
  };
}

// Group changes by priority
const critical = changes.filter(c => c.priority === 'critical');
const high = changes.filter(c => c.priority === 'high');
const medium = changes.filter(c => c.priority === 'medium');
const low = changes.filter(c => c.priority === 'low');

let message = `🔔 *Зміни у конкурента: ${company}*\n\n`;

// Critical changes
if (critical.length > 0) {
  message += `⚠️ *КРИТИЧНІ ЗМІНИ:*\n`;
  critical.forEach(change => {
    message += `• ${change.field}: ${change.type}\n`;
  });
  message += '\n';
}

// High priority changes
if (high.length > 0) {
  message += `🔴 *Високий пріоритет:*\n`;
  high.forEach(change => {
    if (change.type === 'new_blog_posts') {
      message += `• ${change.count} нових статей у блозі\n`;
      change.newPosts.slice(0, 3).forEach(post => {
        message += `  - ${post.title}\n`;
      });
    } else {
      message += `• ${change.field}: зміна\n`;
    }
  });
  message += '\n';
}

// Medium priority changes
if (medium.length > 0) {
  message += `🟡 *Середній пріоритет:*\n`;
  medium.forEach(change => {
    message += `• ${change.field}: оновлено\n`;
  });
  message += '\n';
}

message += `🔗 [Переглянути сайт](${data.currentData.url})\n`;
message += `📊 Всього змін: ${changes.length}\n`;
message += `⏰ ${new Date().toLocaleString('uk-UA')}`;

return {
  skip: false,
  message: message,
  company: company,
  priority: critical.length > 0 ? 'critical' : high.length > 0 ? 'high' : 'medium'
};
```

### 6. Збереження в Google Sheets

```javascript
// Code node: Prepare Data for Google Sheets
const data = $input.item.json;

// Main monitoring data row
const mainRow = {
  'Date': new Date().toISOString(),
  'Company': data.company,
  'URL': data.url,
  'Title': data.seo?.title || '',
  'Description': data.seo?.description || '',
  'Blog Posts Count': data.blogPosts?.length || 0,
  'Social Posts Count': data.socialPosts?.length || 0,
  'Sentiment': data.sentiment?.overallSentiment || 'neutral',
  'AI Summary': data.aiSummary || '',
  'Priority': data.priority || 'medium',
  'Action Required': data.hasChanges ? 'Yes' : 'No'
};

// Blog posts rows (if any)
const blogRows = (data.blogPosts || []).map(post => ({
  'Date Found': new Date().toISOString(),
  'Company': data.company,
  'Title': post.title,
  'URL': post.link,
  'Published Date': post.publishedDate || '',
  'Summary': post.excerpt || '',
  'Keywords': '', // Will be filled by AI
  'Sentiment': '' // Will be filled by AI
}));

// Changes log rows (if any)
const changeRows = (data.changes || []).map(change => ({
  'Date Detected': new Date().toISOString(),
  'Company': data.company,
  'Change Type': change.type,
  'Old Value': JSON.stringify(change.oldValue || ''),
  'New Value': JSON.stringify(change.newValue || ''),
  'Priority': change.priority,
  'Status': 'New'
}));

return {
  mainRow: mainRow,
  blogRows: blogRows,
  changeRows: changeRows,
  company: data.company
};
```

### 7. Парсинг соцмереж - YouTube

```javascript
// Code node: Parse YouTube API Response
const items = $input.item.json.items || [];
const company = $input.item.json.company;

const videos = items.map(item => {
  const snippet = item.snippet || {};

  return {
    videoId: item.id?.videoId || item.id,
    title: snippet.title,
    description: snippet.description,
    publishedAt: snippet.publishedAt,
    channelTitle: snippet.channelTitle,
    thumbnail: snippet.thumbnails?.default?.url || '',
    thumbnailHigh: snippet.thumbnails?.high?.url || '',
    url: `https://www.youtube.com/watch?v=${item.id?.videoId || item.id}`
  };
});

return {
  company: company,
  platform: 'youtube',
  timestamp: new Date().toISOString(),
  videos: videos,
  count: videos.length
};
```

### 8. Парсинг Facebook Graph API

```javascript
// Code node: Parse Facebook API Response
const data = $input.item.json.data || [];
const company = $input.item.json.company;

const posts = data.map(post => ({
  id: post.id,
  message: post.message || '',
  createdAt: post.created_time,
  likes: post.likes?.summary?.total_count || 0,
  comments: post.comments?.summary?.total_count || 0,
  shares: post.shares?.count || 0,
  engagement: (post.likes?.summary?.total_count || 0) +
              (post.comments?.summary?.total_count || 0) +
              (post.shares?.count || 0),
  url: `https://www.facebook.com/${post.id}`
}));

// Sort by engagement
posts.sort((a, b) => b.engagement - a.engagement);

return {
  company: company,
  platform: 'facebook',
  timestamp: new Date().toISOString(),
  posts: posts.slice(0, 10), // Top 10 by engagement
  count: posts.length,
  totalEngagement: posts.reduce((sum, p) => sum + p.engagement, 0)
};
```

### 9. Об'єднання даних з різних джерел

```javascript
// Code node: Merge All Data Sources
const websiteData = $input.item.json.websiteData || {};
const blogData = $input.item.json.blogData || {};
const youtubeData = $input.item.json.youtubeData || {};
const facebookData = $input.item.json.facebookData || {};
const linkedinData = $input.item.json.linkedinData || {};
const previousData = $input.item.json.previousData || null;

const company = websiteData.company || 'Unknown';

// Merge all data
const mergedData = {
  company: company,
  timestamp: new Date().toISOString(),
  website: {
    url: websiteData.url,
    seo: websiteData.seo
  },
  blog: {
    posts: blogData.blogPosts || [],
    count: blogData.totalFound || 0
  },
  social: {
    youtube: {
      videos: youtubeData.videos || [],
      count: youtubeData.count || 0
    },
    facebook: {
      posts: facebookData.posts || [],
      count: facebookData.count || 0,
      totalEngagement: facebookData.totalEngagement || 0
    },
    linkedin: {
      posts: linkedinData.posts || [],
      count: linkedinData.count || 0
    }
  },
  summary: {
    totalBlogPosts: blogData.totalFound || 0,
    totalSocialPosts: (youtubeData.count || 0) +
                      (facebookData.count || 0) +
                      (linkedinData.count || 0),
    lastChecked: new Date().toISOString()
  }
};

// Detect changes if we have previous data
if (previousData) {
  const changes = [];

  // Compare and detect changes
  // (reuse the change detection logic from snippet #3)

  mergedData.changes = changes;
  mergedData.hasChanges = changes.length > 0;
}

return mergedData;
```

### 10. Rate Limiting Helper

```javascript
// Code node: Rate Limit Check
const company = $input.item.json.company;
const platform = $input.item.json.platform;

// Get current usage from global state (you'll need to set this up)
const currentHour = new Date().getHours();
const usageKey = `${platform}_${currentHour}`;

// These would be stored in n8n workflow static data
const rateLimits = {
  youtube: { quotaPerHour: 1000, costPerRequest: 100 },
  facebook: { callsPerHour: 200 },
  linkedin: { callsPerHour: 10 },
  twitter: { callsPerHour: 50 }
};

// Check if we can make this request
const limit = rateLimits[platform];
const currentUsage = 0; // Get from workflow static data

const canProceed = currentUsage < (limit.callsPerHour || limit.quotaPerHour);

if (!canProceed) {
  return {
    proceed: false,
    reason: `Rate limit reached for ${platform}`,
    waitUntil: new Date(Date.now() + 3600000).toISOString() // Next hour
  };
}

return {
  proceed: true,
  company: company,
  platform: platform,
  remainingQuota: (limit.callsPerHour || limit.quotaPerHour) - currentUsage
};
```

## Використання в n8n

1. Створіть Code node
2. Скопіюйте потрібний snippet
3. Адаптуйте під вашу структуру даних
4. Додайте error handling за потребою
5. Тестуйте на реальних даних

## Error Handling Template

```javascript
try {
  // Your code here
  const result = yourFunction();

  return {
    success: true,
    data: result
  };

} catch (error) {
  return {
    success: false,
    error: error.message,
    company: $json.company,
    timestamp: new Date().toISOString()
  };
}
```

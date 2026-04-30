# Best Practices для моніторингу конкурентів

## Етичні принципи

### ✅ Дозволено
- Публічний веб-скрапінг доступних сайтів
- Читання публічних блогів та новин
- Моніторинг публічних соцмереж
- Аналіз публічно доступної інформації
- Використання офіційних API

### ❌ Заборонено
- Обхід паролів або авторизації
- Скрапінг приватних даних користувачів
- Використання даних в комерційних цілях без дозволу
- Порушення Terms of Service сайтів
- DDoS-подібна активність (занадто часті запити)

## Технічні Best Practices

### 1. Rate Limiting

#### Загальні правила
```javascript
// Рекомендовані затримки між запитами
const delays = {
  sameDomain: 3000,      // 3 секунди між запитами до одного домену
  differentDomain: 1000, // 1 секунда між різними доменами
  apiCall: 2000,         // 2 секунди між API запитами
  afterError: 10000      // 10 секунд після помилки
};
```

#### Respect robots.txt
- Перевіряйте robots.txt перед скрапінгом
- Дотримуйтесь Crawl-delay директив
- Не скрапте заборонені сторінки

#### User Agent
```javascript
// Завжди вказуйте коректний User Agent
const headers = {
  'User-Agent': 'CompetitorMonitoringBot/1.0 (contact@yourcompany.com)'
};
```

### 2. Error Handling

#### Типи помилок та реакція

```javascript
// Code node: Comprehensive Error Handler
try {
  const result = await fetchData();
  return { success: true, data: result };

} catch (error) {
  // Categorize errors
  if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
    // Network error - retry after delay
    return {
      success: false,
      error: 'Network error',
      retry: true,
      retryAfter: 60000 // 1 minute
    };
  }

  if (error.response?.status === 429) {
    // Rate limit - wait longer
    return {
      success: false,
      error: 'Rate limit exceeded',
      retry: true,
      retryAfter: 3600000 // 1 hour
    };
  }

  if (error.response?.status === 404) {
    // Not found - don't retry
    return {
      success: false,
      error: 'Page not found',
      retry: false
    };
  }

  if (error.response?.status >= 500) {
    // Server error - retry after delay
    return {
      success: false,
      error: 'Server error',
      retry: true,
      retryAfter: 300000 // 5 minutes
    };
  }

  // Unknown error - log and notify
  return {
    success: false,
    error: error.message,
    retry: false,
    notify: true
  };
}
```

### 3. Caching Strategy

#### Коли використовувати cache
- Статичні дані (про компанію, контакти)
- Дані що рідко змінюються (pricing plans)
- API відповіді з обмеженою квотою

#### Коли НЕ використовувати cache
- Новини та блог пости
- Соцмережі
- Дані що часто змінюються

#### Приклад кешування

```javascript
// Code node: Smart Caching
const cacheKey = `${company}_${dataType}`;
const cacheTimeout = {
  'static': 7 * 24 * 60 * 60 * 1000,  // 7 днів
  'pricing': 24 * 60 * 60 * 1000,     // 1 день
  'blog': 6 * 60 * 60 * 1000,         // 6 годин
  'social': 1 * 60 * 60 * 1000        // 1 година
};

// Check cache
const cached = getFromCache(cacheKey);
if (cached && (Date.now() - cached.timestamp) < cacheTimeout[dataType]) {
  return cached.data;
}

// Fetch fresh data
const freshData = await fetchData();

// Store in cache
setCache(cacheKey, {
  data: freshData,
  timestamp: Date.now()
});

return freshData;
```

### 4. Data Quality

#### Валідація даних

```javascript
// Code node: Data Validation
function validateCompanyData(data) {
  const errors = [];

  // Required fields
  if (!data.company) errors.push('Missing company name');
  if (!data.url) errors.push('Missing URL');

  // URL validation
  try {
    new URL(data.url);
  } catch {
    errors.push('Invalid URL format');
  }

  // SEO data validation
  if (data.seo) {
    if (data.seo.title && data.seo.title.length > 200) {
      errors.push('Title too long (max 200 chars)');
    }
    if (data.seo.description && data.seo.description.length > 500) {
      errors.push('Description too long (max 500 chars)');
    }
  }

  // Blog posts validation
  if (data.blogPosts) {
    data.blogPosts.forEach((post, index) => {
      if (!post.title) errors.push(`Blog post ${index + 1}: missing title`);
      if (!post.link) errors.push(`Blog post ${index + 1}: missing link`);
    });
  }

  return {
    valid: errors.length === 0,
    errors: errors,
    data: data
  };
}
```

#### Очищення даних

```javascript
// Code node: Data Cleaning
function cleanData(data) {
  // Remove HTML tags
  const stripHtml = (str) => str.replace(/<[^>]*>/g, '').trim();

  // Normalize whitespace
  const normalizeWhitespace = (str) => str.replace(/\s+/g, ' ').trim();

  // Clean URLs
  const cleanUrl = (url) => {
    try {
      const parsed = new URL(url);
      // Remove tracking parameters
      ['utm_source', 'utm_medium', 'utm_campaign'].forEach(param => {
        parsed.searchParams.delete(param);
      });
      return parsed.toString();
    } catch {
      return url;
    }
  };

  return {
    ...data,
    seo: {
      title: data.seo?.title ? normalizeWhitespace(stripHtml(data.seo.title)) : null,
      description: data.seo?.description ? normalizeWhitespace(stripHtml(data.seo.description)) : null
    },
    blogPosts: (data.blogPosts || []).map(post => ({
      ...post,
      title: normalizeWhitespace(stripHtml(post.title)),
      link: cleanUrl(post.link)
    }))
  };
}
```

### 5. AI Usage Optimization

#### Оптимізація промптів для економії

```javascript
// Короткий промпт для швидкого аналізу
const quickPrompt = `
Analyze in 100 words:
${data}

Key points:
1. Main changes
2. New features
3. Action needed
`;

// Детальний промпт для глибокого аналізу
const detailedPrompt = `
Provide comprehensive analysis (500 words):
${data}

Include:
1. Detailed changes analysis
2. Competitive positioning
3. Market implications
4. Strategic recommendations
5. Priority actions
`;
```

#### Вибір моделі

```javascript
// Code node: Smart Model Selection
function selectModel(dataSize, priority) {
  if (dataSize < 1000 && priority === 'low') {
    return 'gpt-4o-mini'; // Дешевша модель для простих завдань
  }

  if (priority === 'critical') {
    return 'gpt-4o'; // Краща модель для важливого аналізу
  }

  return 'gpt-4o-mini'; // За замовчуванням
}
```

#### Batch Processing

```javascript
// Обробляйте декілька компаній в одному запиті до AI
const batchPrompt = `
Analyze these 5 competitors briefly (50 words each):

1. ${company1Data}
2. ${company2Data}
3. ${company3Data}
4. ${company4Data}
5. ${company5Data}

For each: main focus, new features, priority level.
`;
```

### 6. Scheduling Strategy

#### Частота моніторингу

| Тип даних | Рекомендована частота | Причина |
|-----------|----------------------|---------|
| Головна сторінка | 1 раз на день | Рідко змінюється |
| Блог | 2-3 рази на день | Нові пости можуть з'являтись |
| Pricing | 1 раз на тиждень | Ціни змінюються рідко |
| Facebook | 3-4 рази на день | Висока активність |
| LinkedIn | 1-2 рази на день | Середня активність |
| YouTube | 1 раз на день | Нові відео виходять рідко |

#### Оптимальний час запуску

```javascript
// Розклад для різних таймзон
const schedule = {
  morning: '09:00',    // Європейський ранок
  afternoon: '14:00',  // Європейський день / US ранок
  evening: '18:00'     // Європейський вечір / US день
};
```

### 7. Security Best Practices

#### Зберігання credentials

```
❌ НЕ зберігайте:
- API ключі в коді
- Паролі в workflow JSON
- Токени в файлах конфігурації

✅ Зберігайте:
- Використовуйте n8n Credentials Manager
- Зберігайте в environment variables
- Використовуйте secrets management tools
```

#### Логування

```javascript
// Code node: Safe Logging
function safeLog(data) {
  const sanitized = {
    ...data,
    // Remove sensitive data
    apiKey: undefined,
    token: undefined,
    password: undefined,
    // Mask emails
    email: data.email ? data.email.replace(/(.{3}).*@/, '$1***@') : undefined
  };

  return sanitized;
}
```

### 8. Monitoring and Alerts

#### Що моніторити

1. **Workflow Execution**
   - Успішність запусків
   - Час виконання
   - Помилки

2. **API Usage**
   - Кількість запитів
   - Витрати
   - Залишок квот

3. **Data Quality**
   - Кількість зібраних даних
   - Валідність даних
   - Дублікати

#### Alert Thresholds

```javascript
const alerts = {
  failureRate: 10,           // Alert if >10% of requests fail
  executionTime: 600000,     // Alert if execution >10 minutes
  apiCost: 50,               // Alert if daily cost >$50
  noDataCollected: 3,        // Alert if no data for 3 consecutive runs
  errorCount: 5              // Alert if >5 errors in single run
};
```

### 9. Cost Optimization

#### Reduce API Costs

```javascript
// 1. Use cheaper models where possible
const costEffectiveConfig = {
  simpleAnalysis: 'gpt-4o-mini',
  complexAnalysis: 'gpt-4o',
  maxTokens: 500 // Limit response length
};

// 2. Batch similar requests
// Instead of 10 separate API calls, make 1 batch call

// 3. Cache AI results
const aiCacheDuration = 24 * 60 * 60 * 1000; // 24 hours

// 4. Use streaming for long responses
// 5. Implement circuit breakers for expensive operations
```

#### Reduce Execution Time

```javascript
// 1. Parallel execution where possible
// Process multiple companies simultaneously

// 2. Skip unnecessary steps
if (!company.monitoring.blog) {
  // Skip blog fetching
}

// 3. Early exit on errors
if (response.status === 404) {
  return; // Don't continue processing
}

// 4. Optimize selectors
// Use efficient CSS selectors, avoid complex regex
```

### 10. Documentation

#### Що документувати

1. **Workflow Changes**
   ```
   Date: 2025-01-19
   Change: Added LinkedIn integration
   Reason: Track competitor professional content
   Impact: +5 minutes execution time, +$2/day costs
   ```

2. **API Endpoints**
   - URL
   - Параметри
   - Rate limits
   - Cost per request

3. **Selectors and Parsers**
   ```javascript
   // Company: Ringover
   // Last updated: 2025-01-19
   // Blog selector: article.post
   // Works: ✅
   // Notes: Standard WordPress structure
   ```

4. **Issues and Solutions**
   ```
   Issue: Facebook API returns 403
   Solution: Regenerated access token with correct permissions
   Date fixed: 2025-01-19
   ```

## Performance Benchmarks

### Цільові показники

| Метрика | Target | Acceptable | Critical |
|---------|--------|------------|----------|
| Workflow execution time | <5 min | <10 min | >15 min |
| Success rate | >95% | >90% | <85% |
| Data completeness | >90% | >80% | <70% |
| API cost per day | <$10 | <$20 | >$30 |
| False positives (changes) | <5% | <10% | >15% |

### Оптимізація під цільові показники

1. **Якщо execution time > 10 min:**
   - Додати parallel processing
   - Зменшити кількість компаній в одному запуску
   - Оптимізувати селектори

2. **Якщо success rate < 90%:**
   - Додати error handling
   - Збільшити timeouts
   - Покращити retry логіку

3. **Якщо cost > $20/день:**
   - Зменшити частоту AI запитів
   - Використовувати дешевші моделі
   - Додати кешування

## Висновок

Дотримання цих best practices забезпечить:
- ✅ Стабільну роботу системи
- ✅ Якісні дані
- ✅ Низькі витрати
- ✅ Етичний моніторинг
- ✅ Легке масштабування
- ✅ Просте обслуговування

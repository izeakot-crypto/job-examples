// Website Parser Tool
// Name: website_parser
// Description: Fetch and parse any website to extract useful information like title, description, headings, links, and main content. Input should be a full URL.

const input = $input.item.json.query || $input.item.json.input || '';

// Ensure URL has protocol
let url = input.trim();
if (!url.startsWith('http://') && !url.startsWith('https://')) {
  url = 'https://' + url;
}

try {
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8,uk;q=0.7'
    },
    redirect: 'follow'
  });

  const html = await response.text();

  if (!html || html.length < 100) {
    return { error: 'Empty response', url: url };
  }

  // Extract title
  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  const title = titleMatch ? titleMatch[1].trim() : null;

  // Extract meta description
  const descMatch = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)/i) ||
                    html.match(/<meta[^>]*content=["']([^"']+)["'][^>]*name=["']description["']/i);
  const description = descMatch ? descMatch[1].trim() : null;

  // Extract meta keywords
  const keywordsMatch = html.match(/<meta[^>]*name=["']keywords["'][^>]*content=["']([^"']+)/i);
  const keywords = keywordsMatch ? keywordsMatch[1].split(',').map(k => k.trim()) : [];

  // Extract H1
  const h1Matches = html.match(/<h1[^>]*>([^<]+)<\/h1>/gi) || [];
  const h1Tags = h1Matches.map(h => h.replace(/<[^>]+>/g, '').trim()).filter(h => h.length > 0);

  // Extract H2
  const h2Matches = html.match(/<h2[^>]*>([^<]+)<\/h2>/gi) || [];
  const h2Tags = h2Matches.map(h => h.replace(/<[^>]+>/g, '').trim()).filter(h => h.length > 0).slice(0, 10);

  // Extract all links
  const linkMatches = html.match(/href=["']([^"']+)["']/gi) || [];
  const links = [...new Set(linkMatches.map(l => {
    const match = l.match(/href=["']([^"']+)["']/i);
    return match ? match[1] : null;
  }).filter(l => l && l.startsWith('http')))].slice(0, 20);

  // Extract phone numbers
  const phoneMatches = html.match(/(?:\+7|8)[\s\-\(]*\d{3}[\s\-\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}/g) ||
                       html.match(/\+\d{1,3}[\s\-\(]*\d{2,4}[\s\-\)]*\d{2,4}[\s\-]*\d{2,4}/g) || [];
  const phones = [...new Set(phoneMatches)].slice(0, 5);

  // Extract emails
  const emailMatches = html.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || [];
  const emails = [...new Set(emailMatches)].filter(e => !e.includes('example') && !e.includes('test')).slice(0, 5);

  // Extract main text content (simplified)
  const cleanHtml = html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<nav[^>]*>[\s\S]*?<\/nav>/gi, '')
    .replace(/<header[^>]*>[\s\S]*?<\/header>/gi, '')
    .replace(/<footer[^>]*>[\s\S]*?<\/footer>/gi, '');

  const textContent = cleanHtml
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .substring(0, 2000);

  // Detect language
  const langMatch = html.match(/<html[^>]*lang=["']([^"']+)["']/i);
  const language = langMatch ? langMatch[1] : 'unknown';

  return {
    url: url,
    title: title,
    description: description,
    keywords: keywords,
    language: language,
    h1: h1Tags,
    h2: h2Tags.slice(0, 10),
    phones: phones,
    emails: emails,
    externalLinks: links.filter(l => !l.includes(new URL(url).hostname)).slice(0, 10),
    contentPreview: textContent.substring(0, 1000),
    pageSize: html.length
  };
} catch (error) {
  return {
    error: error.message,
    url: url
  };
}

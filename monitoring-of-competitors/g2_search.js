// G2 Search Tool
// Name: g2_search
// Description: Search for a company/product on G2.com to get ratings, reviews count, and product information. Input should be the company or product name.

const input = $input.item.json.query || $input.item.json.input || '';
const searchQuery = input.trim();

try {
  // Search G2 via their search page
  const searchUrl = `https://www.g2.com/search?query=${encodeURIComponent(searchQuery)}`;

  const response = await fetch(searchUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Referer': 'https://www.google.com/',
      'Cache-Control': 'no-cache'
    }
  });

  if (response.status === 403 || response.status === 429) {
    return {
      query: searchQuery,
      error: 'G2 blocked the request (anti-bot protection)',
      statusCode: response.status,
      suggestion: 'Try using Google search with "site:g2.com ' + searchQuery + '"',
      searchUrl: searchUrl
    };
  }

  const html = await response.text();

  if (!html || html.length < 1000) {
    return {
      query: searchQuery,
      error: 'No data received from G2',
      searchUrl: searchUrl
    };
  }

  // Parse search results
  const products = [];

  // Try to find product cards in search results
  // Pattern 1: JSON-LD data
  const jsonLdMatch = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/gi);
  if (jsonLdMatch) {
    for (const match of jsonLdMatch) {
      try {
        const jsonStr = match.replace(/<script[^>]*>/, '').replace(/<\/script>/, '');
        const data = JSON.parse(jsonStr);
        if (data['@type'] === 'Product' || data['@type'] === 'SoftwareApplication') {
          products.push({
            name: data.name,
            rating: data.aggregateRating?.ratingValue || null,
            reviewCount: data.aggregateRating?.reviewCount || null,
            description: (data.description || '').substring(0, 200),
            url: data.url || null
          });
        }
      } catch (e) {}
    }
  }

  // Pattern 2: Search result cards
  const ratingMatches = html.match(/(\d+\.?\d*)\s*(?:out of 5|\/5|\s*stars)/gi) || [];
  const reviewMatches = html.match(/(\d+[,\d]*)\s*reviews?/gi) || [];

  // Pattern 3: Product names in search results
  const productNameMatches = html.match(/<a[^>]*href="\/products\/([^"]+)"[^>]*>([^<]+)<\/a>/gi) || [];

  for (const nameMatch of productNameMatches.slice(0, 5)) {
    const urlMatch = nameMatch.match(/href="(\/products\/[^"]+)"/i);
    const textMatch = nameMatch.match(/>([^<]+)</);
    if (urlMatch && textMatch) {
      const existingProduct = products.find(p => p.name === textMatch[1].trim());
      if (!existingProduct) {
        products.push({
          name: textMatch[1].trim(),
          url: 'https://www.g2.com' + urlMatch[1],
          rating: null,
          reviewCount: null
        });
      }
    }
  }

  // Check if query matches any result
  const queryLower = searchQuery.toLowerCase();
  const matchingProducts = products.filter(p =>
    p.name && p.name.toLowerCase().includes(queryLower)
  );

  // Extract any ratings from page
  let pageRating = null;
  let pageReviews = null;

  const ratingMatch = html.match(/(\d+\.?\d*)\s*out of 5/i) ||
                      html.match(/\"ratingValue\"\s*:\s*\"?(\d+\.?\d*)/i);
  if (ratingMatch) pageRating = parseFloat(ratingMatch[1]);

  const reviewMatch = html.match(/(\d+[,\d]*)\s*reviews?/i) ||
                      html.match(/\"reviewCount\"\s*:\s*\"?(\d+)/i);
  if (reviewMatch) pageReviews = parseInt(reviewMatch[1].replace(/,/g, ''));

  return {
    query: searchQuery,
    searchUrl: searchUrl,
    found: products.length > 0 || matchingProducts.length > 0,
    productsCount: products.length,
    products: products.slice(0, 5),
    matchingProducts: matchingProducts,
    pageRating: pageRating,
    pageReviews: pageReviews,
    suggestion: products.length === 0 ? 'Product may not be listed on G2' : null
  };
} catch (error) {
  return {
    query: searchQuery,
    error: error.message,
    searchUrl: `https://www.g2.com/search?query=${encodeURIComponent(searchQuery)}`
  };
}

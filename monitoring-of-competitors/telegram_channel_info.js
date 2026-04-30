// Telegram Channel Info Tool
// Name: telegram_channel_info
// Description: Get information about a Telegram channel or group by fetching its public page. Input should be the Telegram URL or username (e.g., t.me/mango_office or just mango_office).

const input = $input.item.json.query || $input.item.json.input || '';

// Extract channel username from input
let channelUsername = input
  .replace('https://t.me/', '')
  .replace('http://t.me/', '')
  .replace('t.me/', '')
  .replace('@', '')
  .replace('/', '')
  .trim();

try {
  // Fetch the public Telegram page
  const url = `https://t.me/s/${channelUsername}`;
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9'
    }
  });

  const html = await response.text();

  if (!html || html.length < 500) {
    return {
      channelUsername: channelUsername,
      channelUrl: `https://t.me/${channelUsername}`,
      error: 'Channel not found or private',
      isPrivate: true
    };
  }

  // Parse channel info
  let channelName = null;
  let channelDescription = null;
  let subscribersCount = null;
  let photosCount = null;
  let videosCount = null;
  let linksCount = null;

  // Extract channel name
  const nameMatch = html.match(/<meta property="og:title" content="([^"]+)"/i) ||
                    html.match(/<div class="tgme_channel_info_header_title[^"]*"[^>]*>([^<]+)/i);
  if (nameMatch) channelName = nameMatch[1].trim();

  // Extract description
  const descMatch = html.match(/<meta property="og:description" content="([^"]+)"/i) ||
                    html.match(/<div class="tgme_channel_info_description[^"]*"[^>]*>([^<]+)/i);
  if (descMatch) channelDescription = descMatch[1].trim();

  // Extract subscribers count
  const subsMatch = html.match(/([\d\s,\.]+)\s*(?:subscribers?|members?|підписник)/i) ||
                    html.match(/<div class="tgme_channel_info_counter[^"]*"[^>]*>.*?([\d\s,\.]+)/i);
  if (subsMatch) {
    subscribersCount = parseInt(subsMatch[1].replace(/[\s,\.]/g, ''));
  }

  // Extract recent posts
  const postMatches = html.match(/<div class="tgme_widget_message_bubble[^"]*"[\s\S]*?<\/div>/gi) || [];
  const posts = [];

  // Find message texts and dates
  const messageTexts = html.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)<\/div>/gi) || [];
  const messageDates = html.match(/<time[^>]*datetime="([^"]+)"/gi) || [];

  for (let i = 0; i < Math.min(messageTexts.length, 5); i++) {
    let text = messageTexts[i]
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .substring(0, 200);

    let dateStr = null;
    if (messageDates[i]) {
      const dateMatch = messageDates[i].match(/datetime="([^"]+)"/);
      if (dateMatch) dateStr = dateMatch[1].split('T')[0];
    }

    if (text.length > 10) {
      posts.push({
        text: text,
        date: dateStr
      });
    }
  }

  // Determine activity level
  let activityLevel = 'unknown';
  if (posts.length >= 4) activityLevel = 'high';
  else if (posts.length >= 2) activityLevel = 'medium';
  else if (posts.length >= 1) activityLevel = 'low';
  else activityLevel = 'inactive';

  return {
    channelUsername: channelUsername,
    channelName: channelName,
    channelUrl: `https://t.me/${channelUsername}`,
    description: channelDescription,
    subscribersCount: subscribersCount,
    recentPosts: posts,
    postsCount: posts.length,
    lastPostDate: posts.length > 0 ? posts[0].date : null,
    activityLevel: activityLevel,
    isPrivate: false
  };
} catch (error) {
  return {
    error: error.message,
    channelUsername: channelUsername,
    channelUrl: `https://t.me/${channelUsername}`
  };
}

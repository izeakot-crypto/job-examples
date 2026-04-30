// YouTube Channel Info Tool
// Name: youtube_channel_info
// Description: Get information about a YouTube channel including recent videos, subscriber count, and channel description. Input should be the channel name or URL.

const input = $input.item.json.query || $input.item.json.input || '';

// Extract channel identifier from input
let channelQuery = input.replace('https://www.youtube.com/', '').replace('http://www.youtube.com/', '').replace('@', '');

// YouTube Data API Key
const apiKey = 'AIzaSyCPWX3Kl5L1c13TBi17OxAURU-PP5gd5iE';

try {
  // First, search for the channel
  const searchUrl = `https://www.googleapis.com/youtube/v3/search?part=snippet&q=${encodeURIComponent(channelQuery)}&type=channel&maxResults=1&key=${apiKey}`;
  const searchResponse = await fetch(searchUrl);
  const searchData = await searchResponse.json();

  if (!searchData.items || searchData.items.length === 0) {
    return { error: 'Channel not found', query: channelQuery };
  }

  const channelId = searchData.items[0].id.channelId;
  const channelTitle = searchData.items[0].snippet.title;

  // Get channel details
  const channelUrl = `https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails&id=${channelId}&key=${apiKey}`;
  const channelResponse = await fetch(channelUrl);
  const channelData = await channelResponse.json();

  // Get recent videos
  const videosUrl = `https://www.googleapis.com/youtube/v3/search?part=snippet&channelId=${channelId}&order=date&maxResults=5&type=video&key=${apiKey}`;
  const videosResponse = await fetch(videosUrl);
  const videosData = await videosResponse.json();

  const channel = channelData.items[0];
  const videos = videosData.items || [];

  return {
    channelName: channel.snippet.title,
    channelUrl: `https://www.youtube.com/channel/${channelId}`,
    description: channel.snippet.description.substring(0, 500),
    subscriberCount: channel.statistics.subscriberCount,
    videoCount: channel.statistics.videoCount,
    viewCount: channel.statistics.viewCount,
    country: channel.snippet.country || 'Unknown',
    recentVideos: videos.map(v => ({
      title: v.snippet.title,
      publishedAt: v.snippet.publishedAt,
      url: `https://www.youtube.com/watch?v=${v.id.videoId}`
    }))
  };
} catch (error) {
  return { error: error.message, query: channelQuery };
}

// YouTube Video Search Tool
// Name: youtube_search
// Description: Search YouTube for videos by keyword. Returns video titles, URLs, view counts and publish dates. Input should be a search query.

const query = $input.item.json.query || $input.item.json.input || '';

// YouTube Data API Key
const apiKey = 'AIzaSyCPWX3Kl5L1c13TBi17OxAURU-PP5gd5iE';

try {
  const url = `https://www.googleapis.com/youtube/v3/search?part=snippet&q=${encodeURIComponent(query)}&type=video&maxResults=10&order=relevance&key=${apiKey}`;
  const response = await fetch(url);
  const data = await response.json();

  if (!data.items || data.items.length === 0) {
    return { message: 'No videos found', query: query };
  }

  // Get video statistics
  const videoIds = data.items.map(v => v.id.videoId).join(',');
  const statsUrl = `https://www.googleapis.com/youtube/v3/videos?part=statistics&id=${videoIds}&key=${apiKey}`;
  const statsResponse = await fetch(statsUrl);
  const statsData = await statsResponse.json();

  const statsMap = {};
  statsData.items.forEach(v => {
    statsMap[v.id] = v.statistics;
  });

  return {
    query: query,
    resultsCount: data.items.length,
    videos: data.items.map(v => ({
      title: v.snippet.title,
      channelTitle: v.snippet.channelTitle,
      publishedAt: v.snippet.publishedAt,
      description: v.snippet.description.substring(0, 200),
      url: `https://www.youtube.com/watch?v=${v.id.videoId}`,
      viewCount: statsMap[v.id.videoId]?.viewCount || 'N/A',
      likeCount: statsMap[v.id.videoId]?.likeCount || 'N/A'
    }))
  };
} catch (error) {
  return { error: error.message, query: query };
}

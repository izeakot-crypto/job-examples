// Parse YouTube Data - FIXED v2
var response = $input.item.json;
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var company = editFieldsData.companyName || loopData.companyName || 'Unknown';
var autoDetect = $('Auto-detect YouTube Channel1').item.json;

// If channel not found
if (!autoDetect.autoDetected) {
  return {
    company: company,
    youtubeActivity: 'YouTube channel not found on site',
    youtubeVideoCount: 0,
    youtubeUrl: null
  };
}

// If API returned error
if (response.error || !response.items) {
  var errorMsg = response.error ? response.error.message : 'API error';
  return {
    company: company,
    youtubeActivity: 'YouTube API error: ' + errorMsg,
    youtubeVideoCount: 0,
    youtubeUrl: autoDetect.youtubeUrl
  };
}

// If no new videos
if (response.items.length === 0) {
  return {
    company: company,
    youtubeActivity: 'No new videos this week',
    youtubeVideoCount: 0,
    youtubeUrl: autoDetect.youtubeUrl
  };
}

var videos = response.items;
var videoCount = videos.length;
var latestVideo = videos[0];

return {
  company: company,
  youtubeActivity: videoCount + ' new videos this week. Latest: "' + latestVideo.snippet.title + '" (' + latestVideo.snippet.publishedAt.split('T')[0] + ')',
  youtubeVideoCount: videoCount,
  youtubeUrl: autoDetect.youtubeUrl,
  youtubeVideos: videos.slice(0, 3).map(function(v) {
    return {
      title: v.snippet.title,
      publishedAt: v.snippet.publishedAt,
      url: 'https://www.youtube.com/watch?v=' + v.id.videoId
    };
  })
};

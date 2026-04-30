// Auto-detect YouTube Channel - FIXED v2
var websiteHtml = $('Fetch Website1').item.json.data || $('Fetch Website1').item.json.body || '';
var loopData = $('Loop Companies1').item.json;
var editFieldsData = $('Edit Fields').item.json;
var companyName = editFieldsData.companyName || loopData.companyName || loopData.name || 'Unknown';

// Extended patterns for YouTube channels
var youtubePatterns = [
  /youtube\.com\/channel\/([a-zA-Z0-9_-]{20,30})/i,
  /youtube\.com\/@([a-zA-Z0-9_.-]+)/i,
  /youtube\.com\/c\/([a-zA-Z0-9_-]+)/i,
  /youtube\.com\/user\/([a-zA-Z0-9_-]+)/i,
  /href=["'][^"']*youtube\.com\/channel\/([a-zA-Z0-9_-]+)/i,
  /href=["'][^"']*youtube\.com\/@([a-zA-Z0-9_.-]+)/i
];

var channelId = null;
var channelUrl = null;
var channelHandle = null;

for (var i = 0; i < youtubePatterns.length; i++) {
  var match = websiteHtml.match(youtubePatterns[i]);
  if (match && match[1]) {
    var found = match[1];
    if (found.match(/^UC[a-zA-Z0-9_-]{22}$/)) {
      channelId = found;
      channelUrl = 'https://www.youtube.com/channel/' + found;
    } else {
      channelHandle = found;
      channelUrl = match[0].includes('@')
        ? 'https://www.youtube.com/@' + found
        : 'https://www.youtube.com/c/' + found;
    }
    break;
  }
}

return {
  company: companyName,
  youtubeChannelId: channelId,
  youtubeHandle: channelHandle,
  youtubeUrl: channelUrl,
  autoDetected: !!(channelId || channelHandle),
  htmlLength: websiteHtml.length
};

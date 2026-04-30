// VK Group Info Tool
// Name: vk_group_info
// Description: Get information about a VKontakte (VK) group or public page including members count, posts, and description. Input should be the VK group URL or ID (e.g., vk.com/mangotelecom or just mangotelecom).

const input = $input.item.json.query || $input.item.json.input || '';

// Extract group ID from input
let groupId = input
  .replace('https://vk.com/', '')
  .replace('http://vk.com/', '')
  .replace('vk.com/', '')
  .replace('/', '')
  .trim();

// VK API access token (service token - get from https://vk.com/dev)
// For now using without token - limited data
const apiVersion = '5.131';

try {
  // Get group info
  const groupUrl = `https://api.vk.com/method/groups.getById?group_id=${encodeURIComponent(groupId)}&fields=members_count,description,status,site,contacts,links,activity,verified,cover&v=${apiVersion}&lang=en`;
  const groupResponse = await fetch(groupUrl);
  const groupData = await groupResponse.json();

  if (groupData.error) {
    // Try without token - public data only
    const publicUrl = `https://vk.com/${groupId}`;
    return {
      groupId: groupId,
      groupUrl: publicUrl,
      error: 'VK API requires access token for detailed data',
      suggestion: 'Add VK service token to get full data',
      publicUrl: publicUrl
    };
  }

  const group = groupData.response[0];

  // Get recent posts (wall)
  const wallUrl = `https://api.vk.com/method/wall.get?domain=${encodeURIComponent(groupId)}&count=5&v=${apiVersion}`;
  const wallResponse = await fetch(wallUrl);
  const wallData = await wallResponse.json();

  let recentPosts = [];
  if (wallData.response && wallData.response.items) {
    recentPosts = wallData.response.items.map(post => ({
      date: new Date(post.date * 1000).toISOString().split('T')[0],
      text: (post.text || '').substring(0, 200),
      likes: post.likes?.count || 0,
      reposts: post.reposts?.count || 0,
      comments: post.comments?.count || 0,
      views: post.views?.count || 0
    }));
  }

  return {
    groupId: groupId,
    groupName: group.name,
    groupUrl: `https://vk.com/${group.screen_name || groupId}`,
    description: (group.description || '').substring(0, 500),
    status: group.status || '',
    membersCount: group.members_count || 0,
    activity: group.activity || '',
    verified: group.verified === 1,
    website: group.site || null,
    recentPosts: recentPosts,
    postsCount: recentPosts.length,
    lastPostDate: recentPosts.length > 0 ? recentPosts[0].date : null,
    activityLevel: recentPosts.length >= 3 ? 'high' : recentPosts.length >= 1 ? 'medium' : 'low'
  };
} catch (error) {
  return {
    error: error.message,
    groupId: groupId,
    groupUrl: `https://vk.com/${groupId}`,
    suggestion: 'VK API may require authentication'
  };
}

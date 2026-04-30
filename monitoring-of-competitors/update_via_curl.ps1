# N8n Workflow Update via Internal API
$ErrorActionPreference = "Stop"

$workflowId = "w5Pn8RXfEteblgbC"
$nodeName = "Format for Sheets3"
$apiUrl = "https://n8nletsdo.online/rest/workflows/" + $workflowId

# Session cookie
$sessionCookie = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjgzOGRiZWFjLTA0MmMtNGY0MS1hZDNjLTI3Y2RhNzAxNjA2MCIsImhhc2giOiJLQlg1dFBhRGEzIiwiYnJvd3NlcklkIjoiRDFmZTZJS3lUMUN0b1J3N3VsQzRmbllQWGJzenlKL2RqV1JCcTZ6YmRLUT0iLCJ1c2VkTWZhIjpmYWxzZSwiaWF0IjoxNzY2NDc2ODE4LCJleHAiOjE3NjcwODE2MTh9.hM5T6_xn2cWOSwk5HMKKM4bmxS1R6SDGyT8DSW8Vahc"

# New code for Format for Sheets3
$newCode = @'
// Format for Sheets - PASS THROUGH VERSION
const data = $input.item.json;
const ai = data.aiAnalysis || {};

const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return "-";
  if (arr.length === 0) return "-";
  return arr.join(", ");
};

const blogToString = (articles) => {
  if (!Array.isArray(articles)) return "-";
  if (articles.length === 0) return "-";
  return articles.map(a => a.title + " (" + (a.date || "?") + "): " + (a.summary || "").substring(0, 100) + "...").join(" | ");
};

const result = {
  "Дата": new Date().toISOString().split("T")[0],
  "Компанія": data.company || "Unknown",
  "URL": data.url || "",
  "Нові фічі": arrayToString(ai.newFeatures),
  "Проблеми": arrayToString(ai.problems),
  "Інсайти з коментарів": ai.reviewInsights || "-",
  "Новини (з останньої перевірки)": arrayToString(ai.news),
  "Статті в блозі (з останньої перевірки)": blogToString(ai.blogArticles),
  "YouTube активність": data.youtubeActivity || "-",
  "Facebook активність": data.facebookActivity || "-",
  "LinkedIn активність": data.linkedinActivity || "-",
  "Згадки на агрегаторах": data.aggregatorMentions || "-",
  "Кількість згадок в соцмережах": String(data.socialMentionsCount || 0),
  "Болі клієнтів з коментарів": arrayToString(ai.customerPains),
  "Хотілки клієнтів з коментарів": arrayToString(ai.customerWants),
  "AI Summary": ai.summary || "-",
  _originalData: { company: data.company, url: data.url, parsedAt: data.parsedAt },
  _isNewData: true
};

console.log("Format for Sheets - Company:", result["Компанія"]);
return result;
'@

Write-Host "Step 1: Getting current workflow..." -ForegroundColor Cyan

$headers = @{
    "Cookie" = "n8n-auth=" + $sessionCookie
}

try {
    # Get current workflow
    $workflow = Invoke-RestMethod -Uri $apiUrl -Method Get -Headers $headers
    Write-Host "Got workflow with $($workflow.nodes.Count) nodes" -ForegroundColor Green

    # Find the node
    $node = $workflow.nodes | Where-Object { $_.name -eq $nodeName }
    if ($null -eq $node) {
        Write-Host "ERROR: Node '$nodeName' not found!" -ForegroundColor Red
        exit 1
    }
    Write-Host "Found node: $($node.name) (ID: $($node.id))" -ForegroundColor Green

    # Update the code
    $node.parameters.jsCode = $newCode
    Write-Host "Updated node code in memory" -ForegroundColor Yellow

    # Save the workflow
    $bodyJson = $workflow | ConvertTo-Json -Depth 20 -Compress

    Write-Host "Step 2: Saving workflow..." -ForegroundColor Cyan
    $response = Invoke-RestMethod -Uri $apiUrl -Method Patch -Body $bodyJson -Headers $headers -ContentType "application/json"
    Write-Host "SUCCESS! Workflow updated." -ForegroundColor Green
    Write-Host "Version: $($response.versionId)"

} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    Write-Host "StatusCode: $($_.Exception.Response.StatusCode.value__)"
}


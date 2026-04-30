# Update Format for Sheets3 node via N8n internal API
$ErrorActionPreference = "Stop"

$workflowId = "w5Pn8RXfEteblgbC"
$apiUrl = "https://n8nletsdo.online/rest/workflows/" + $workflowId

# Session cookie
$sessionCookie = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjgzOGRiZWFjLTA0MmMtNGY0MS1hZDNjLTI3Y2RhNzAxNjA2MCIsImhhc2giOiJLQlg1dFBhRGEzIiwiYnJvd3NlcklkIjoiRDFmZTZJS3lUMUN0b1J3N3VsQzRmbllQWGJzenlKL2RqV1JCcTZ6YmRLUT0iLCJ1c2VkTWZhIjpmYWxzZSwiaWF0IjoxNzY2NDc2ODE4LCJleHAiOjE3NjcwODE2MTh9.hM5T6_xn2cWOSwk5HMKKM4bmxS1R6SDGyT8DSW8Vahc"

$headers = @{
    "Cookie" = "n8n-auth=" + $sessionCookie
}

# New code for Format for Sheets3 with _originalData and _isNewData
$newFormatCode = @'
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

try {
    # Get current workflow
    $workflow = Invoke-RestMethod -Uri $apiUrl -Method Get -Headers $headers
    Write-Host "  Got workflow with $($workflow.nodes.Count) nodes" -ForegroundColor Green

    # Find and update Format for Sheets3
    $formatNode = $workflow.nodes | Where-Object { $_.id -eq "79d14816-a09a-464e-91fb-a365e6e252b1" }
    if ($formatNode) {
        Write-Host "  Found Format for Sheets3 - updating code..." -ForegroundColor Yellow
        Write-Host "  OLD CODE (first 100 chars): $($formatNode.parameters.jsCode.Substring(0, [Math]::Min(100, $formatNode.parameters.jsCode.Length)))" -ForegroundColor DarkYellow

        # Update the code
        $formatNode.parameters.jsCode = $newFormatCode

        Write-Host "  NEW CODE (first 100 chars): $($newFormatCode.Substring(0, [Math]::Min(100, $newFormatCode.Length)))" -ForegroundColor DarkGreen
    } else {
        Write-Host "  ERROR: Format for Sheets3 not found!" -ForegroundColor Red
        exit 1
    }

    # Check if Check If Company Exists1 needs update too
    $checkNode = $workflow.nodes | Where-Object { $_.id -eq "66310e8c-9b80-4e44-b090-35885fdbde7a" }
    if ($checkNode) {
        # Check if it has the fixed code (looks for _rowId field)
        if ($checkNode.parameters.jsCode -notmatch "_rowId") {
            Write-Host "  Check If Company Exists1 also needs update!" -ForegroundColor Yellow
        } else {
            Write-Host "  Check If Company Exists1 already has updated code" -ForegroundColor Green
        }
    }

    # Save the workflow
    Write-Host "Step 2: Saving updated workflow..." -ForegroundColor Cyan

    # Convert to JSON and send PATCH request
    $bodyJson = $workflow | ConvertTo-Json -Depth 20 -Compress

    $response = Invoke-RestMethod -Uri $apiUrl -Method Patch -Body $bodyJson -Headers $headers -ContentType "application/json"
    Write-Host "  SUCCESS! Workflow updated." -ForegroundColor Green
    Write-Host "  Version: $($response.versionId)"
    Write-Host "  Updated at: $($response.updatedAt)"

} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    if ($_.Exception.Response) {
        Write-Host "StatusCode: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    }
}


# N8n API Update Script
$workflowId = "w5Pn8RXfEteblgbC"
$apiUrl = "https://n8nletsdo.online/api/v1/workflows/" + $workflowId

# Read the JSON file
$jsonContent = Get-Content '[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\update_format_nodes.json' -Raw

# Parse and convert to JSON string
$updateData = $jsonContent | ConvertFrom-Json
$nodesJson = $updateData.nodes | ConvertTo-Json -Compress

# Prepare the request body
$body = @{
    nodes = $nodesJson
} | ConvertTo-Json -Compress

# Session cookie from browser
$sessionCookie = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjgzOGRiZWFjLTA0MmMtNGY0MS1hZDNjLTI3Y2RhNzAxNjA2MCIsImhhc2giOiJLQlg1dFBhRGEzIiwiYnJvd3NlcklkIjoiRDFmZTZJS3lUMUN0b1J3N3VsQzRmbllQWGJzenlKL2RqV1JCcTZ6YmRLUT0iLCJ1c2VkTWZhIjpmYWxzZSwiaWF0IjoxNzY2NDc2ODE4LCJleHAiOjE3NjcwODE2MTh9.hM5T6_xn2cWOSwk5HMKKM4bmxS1R6SDGyT8DSW8Vahc"

# Make the request
$headers = @{
    "Content-Type" = "application/json"
    "Cookie" = "n8n-auth=" + $sessionCookie
}

try {
    $response = Invoke-RestMethod -Uri $apiUrl -Method Patch -Body $body -Headers $headers
    Write-Host "Success! Workflow updated."
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    Write-Host "Response: $($_.ErrorDetails.Message)"
}



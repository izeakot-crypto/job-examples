# Try different endpoints
$urls = @(
    "https://n8nletsdo.online/api/v1/workflows/w5Pn8RXfEteblgbC",
    "https://n8nletsdo.online/rest/workflows/w5Pn8RXfEteblgbC",
    "https://n8nletsdo.online/workflows/w5Pn8RXfEteblgbC"
)

$sessionCookie = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjgzOGRiZWFjLTA0MmMtNGY0MS1hZDNjLTI3Y2RhNzAxNjA2MCIsImhhc2giOiJLQlg1dFBhRGEzIiwiYnJvd3NlcklkIjoiRDFmZTZJS3lUMUN0b1J3N3VsQzRmbllQWGJzenlKL2RqV1JCcTZ6YmRLUT0iLCJ1c2VkTWZhIjpmYWxzZSwiaWF0IjoxNzY2NDc2ODE4LCJleHAiOjE3NjcwODE2MTh9.hM5T6_xn2cWOSwk5HMKKM4bmxS1R6SDGyT8DSW8Vahc"

$headers = @{
    "Cookie" = "n8n-auth=" + $sessionCookie
}

foreach ($url in $urls) {
    Write-Host "Trying: $url" -ForegroundColor Cyan
    try {
        $response = Invoke-WebRequest -Uri $url -Method Get -Headers $headers -ErrorAction Stop
        Write-Host "  SUCCESS! StatusCode: $($response.StatusCode)" -ForegroundColor Green
        Write-Host "  Content-Length: $($response.Content.Length)"
    } catch {
        Write-Host "  FAILED: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    }
}


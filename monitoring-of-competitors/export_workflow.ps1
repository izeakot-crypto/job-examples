$content = Get-Content '[USER_HOME]\.claude\projects\C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors\b1778487-f040-4546-9724-16894bbf5164\tool-results\mcp-n8n-flexible-n8n_get_workflow-1768218943451.txt' -Raw
$json = $content | ConvertFrom-Json
$wfText = $json[0].text
$wfText | Out-File -FilePath '[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\workflow_current.json' -Encoding utf8
Write-Host "Workflow exported to workflow_current.json"


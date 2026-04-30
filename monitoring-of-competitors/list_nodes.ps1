$content = Get-Content '[USER_HOME]\.claude\projects\C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors\b1778487-f040-4546-9724-16894bbf5164\tool-results\mcp-n8n-flexible-n8n_get_workflow-1768218943451.txt' -Raw
$json = $content | ConvertFrom-Json
$wfText = $json[0].text
$wf = $wfText | ConvertFrom-Json
Write-Host "Workflow: $($wf.name)"
Write-Host "Active: $($wf.active)"
Write-Host "Nodes count: $($wf.nodes.Count)"
Write-Host ""
Write-Host "NODES:"
foreach ($node in $wf.nodes) {
    Write-Host "  - $($node.name) [$($node.type)]"
}


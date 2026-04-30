$content = Get-Content '[USER_HOME]\.claude\projects\C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors\b1778487-f040-4546-9724-16894bbf5164\tool-results\mcp-n8n-flexible-n8n_get_workflow-1768218943451.txt' -Raw
$json = $content | ConvertFrom-Json
$wfText = $json[0].text
$wf = $wfText | ConvertFrom-Json

Write-Host "=== Loop Over Items node ===" -ForegroundColor Cyan
$loopNode = $wf.nodes | Where-Object { $_.name -eq "Loop Over Items" }
Write-Host ($loopNode | ConvertTo-Json -Depth 10)

Write-Host ""
Write-Host "=== Connections FROM Loop Over Items ===" -ForegroundColor Cyan
$connections = $wf.connections
if ($connections."Loop Over Items") {
    Write-Host ($connections."Loop Over Items" | ConvertTo-Json -Depth 10)
}

Write-Host ""
Write-Host "=== Connections TO Loop Over Items ===" -ForegroundColor Cyan
foreach ($nodeName in $connections.PSObject.Properties.Name) {
    $nodeConns = $connections.$nodeName
    if ($nodeConns.main) {
        foreach ($outputArr in $nodeConns.main) {
            foreach ($target in $outputArr) {
                if ($target.node -eq "Loop Over Items") {
                    Write-Host "$nodeName [output] -> Loop Over Items [input $($target.index)]"
                }
            }
        }
    }
}


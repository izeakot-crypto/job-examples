$content = Get-Content '[USER_HOME]\.claude\projects\C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors\b1778487-f040-4546-9724-16894bbf5164\tool-results\mcp-n8n-flexible-n8n_get_workflow-1768218943451.txt' -Raw
$json = $content | ConvertFrom-Json
$wfText = $json[0].text
$wf = $wfText | ConvertFrom-Json

Write-Host "=== CONNECTIONS TO AI Agent ===" -ForegroundColor Cyan
$connections = $wf.connections
foreach ($nodeName in $connections.PSObject.Properties.Name) {
    $nodeConns = $connections.$nodeName
    foreach ($output in $nodeConns.PSObject.Properties.Name) {
        $targets = $nodeConns.$output
        foreach ($target in $targets) {
            if ($target.node -eq "AI Agent") {
                Write-Host "$nodeName -> AI Agent (input $($target.index))"
            }
        }
    }
}

Write-Host ""
Write-Host "=== CONNECTIONS FROM Merge6 ===" -ForegroundColor Cyan
if ($connections."Merge6") {
    $connections."Merge6" | ConvertTo-Json -Depth 5
}

Write-Host ""
Write-Host "=== CONNECTIONS TO Merge6 ===" -ForegroundColor Cyan
foreach ($nodeName in $connections.PSObject.Properties.Name) {
    $nodeConns = $connections.$nodeName
    foreach ($output in $nodeConns.PSObject.Properties.Name) {
        $targets = $nodeConns.$output
        foreach ($target in $targets) {
            if ($target.node -eq "Merge6") {
                Write-Host "$nodeName -> Merge6 (input $($target.index))"
            }
        }
    }
}

Write-Host ""
Write-Host "=== Loop Over Items connections ===" -ForegroundColor Cyan
foreach ($nodeName in $connections.PSObject.Properties.Name) {
    $nodeConns = $connections.$nodeName
    foreach ($output in $nodeConns.PSObject.Properties.Name) {
        $targets = $nodeConns.$output
        foreach ($target in $targets) {
            if ($target.node -eq "Loop Over Items" -or $nodeName -eq "Loop Over Items") {
                Write-Host "$nodeName -> $($target.node)"
            }
        }
    }
}


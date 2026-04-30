$content = Get-Content '[USER_HOME]\.claude\projects\C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors\b1778487-f040-4546-9724-16894bbf5164\tool-results\mcp-n8n-flexible-n8n_get_workflow-1768218943451.txt' -Raw
$json = $content | ConvertFrom-Json
$wfText = $json[0].text
$wf = $wfText | ConvertFrom-Json

Write-Host "=== ALL CONNECTIONS ===" -ForegroundColor Cyan
$connections = $wf.connections
foreach ($nodeName in $connections.PSObject.Properties.Name) {
    $nodeConns = $connections.$nodeName
    if ($nodeConns.main) {
        for ($i = 0; $i -lt $nodeConns.main.Count; $i++) {
            $outputArr = $nodeConns.main[$i]
            foreach ($target in $outputArr) {
                Write-Host "$nodeName [out $i] -> $($target.node) [in $($target.index)]"
            }
        }
    }
}


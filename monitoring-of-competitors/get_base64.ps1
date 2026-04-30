$bytes = [System.IO.File]::ReadAllBytes('[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\update_format_nodes.json')
$text = [System.Text.Encoding]::UTF8.GetString($bytes)
[System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($text))


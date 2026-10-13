Get-Process -Name 'OpenAmer' | Where-Object { $_.Id -ne $pid } | ForEach-Object { Stop-Process -Id $_.Id -Force }
Write-Output "Desktop-Instanzen bereinigt"
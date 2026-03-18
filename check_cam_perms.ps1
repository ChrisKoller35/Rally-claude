$base = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"
Write-Host "Global:" (Get-ItemProperty $base).Value
Write-Host ""
Get-ChildItem $base | ForEach-Object {
    $name = $_.PSChildName
    $val = (Get-ItemProperty $_.PSPath).Value
    Write-Host "  $name = $val"
}

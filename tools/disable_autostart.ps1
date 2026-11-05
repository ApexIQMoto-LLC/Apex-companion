$ErrorActionPreference = 'Stop'
$path = Join-Path ([Environment]::GetFolderPath('Startup')) 'ApexIQ Companion.lnk'
if (Test-Path $path) { Remove-Item -LiteralPath $path -Force }
Write-Host 'ApexIQ Companion auto-start disabled for this Windows user.'

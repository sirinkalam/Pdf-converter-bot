$ErrorActionPreference = "Continue"

$python = "C:\Users\saswa\AppData\Local\Programs\Python\Python312\python.exe"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $projectRoot

while ($true) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path "$projectRoot\bot.supervisor.log" -Value "$ts supervisor starting bot"

    & $python "$projectRoot\main.py" 1>> "$projectRoot\bot.log" 2>> "$projectRoot\bot.err.log"

    $exitCode = $LASTEXITCODE
    $tsExit = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path "$projectRoot\bot.supervisor.log" -Value "$tsExit bot exited with code $exitCode; restarting in 5s"

    Start-Sleep -Seconds 5
}

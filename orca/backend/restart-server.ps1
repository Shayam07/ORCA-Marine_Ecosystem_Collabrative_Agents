# Kill ALL python processes on port 8000
$procs = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($p in $procs) {
        Stop-Process -Id $p.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

# Start fresh
Set-Location 'C:\Users\shaya\OneDrive\Desktop\New folder\orca\backend'
$proc = Start-Process -FilePath 'C:\Users\shaya\OneDrive\Desktop\New folder\orca\backend\venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','main:app','--host','0.0.0.0','--port','8000','--reload' -RedirectStandardOutput 'C:\Users\shaya\OneDrive\Desktop\New folder\.freebuff\backend.log' -RedirectStandardError 'C:\Users\shaya\OneDrive\Desktop\New folder\.freebuff\backend.log.err' -WindowStyle Hidden -PassThru
Write-Host "Started PID: $($proc.Id)"

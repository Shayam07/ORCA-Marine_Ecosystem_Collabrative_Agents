Set-Location 'C:\Users\shaya\OneDrive\Desktop\New folder\orca\backend'
$proc = Start-Process -FilePath 'C:\Users\shaya\OneDrive\Desktop\New folder\orca\backend\venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','main:app','--host','0.0.0.0','--port','8000','--reload' -RedirectStandardOutput 'C:\Users\shaya\OneDrive\Desktop\New folder\.freebuff\backend.log' -RedirectStandardError 'C:\Users\shaya\OneDrive\Desktop\New folder\.freebuff\backend.log.err' -WindowStyle Hidden -PassThru
Write-Host $proc.Id

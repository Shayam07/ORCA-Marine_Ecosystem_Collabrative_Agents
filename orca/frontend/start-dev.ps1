Set-Location 'C:\Users\shaya\OneDrive\Desktop\New folder\orca\frontend'
$proc = Start-Process -FilePath 'node.exe' -ArgumentList 'node_modules\vite\bin\vite.js' -RedirectStandardOutput 'C:\Users\shaya\OneDrive\Desktop\New folder\.freebuff\preview-cc651ef7-6215-43a6-82f2-a7d44454ef46.log' -RedirectStandardError 'C:\Users\shaya\OneDrive\Desktop\New folder\.freebuff\preview-cc651ef7-6215-43a6-82f2-a7d44454ef46.log.err' -WindowStyle Hidden -PassThru
Write-Host $proc.Id

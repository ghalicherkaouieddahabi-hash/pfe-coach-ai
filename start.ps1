# Coach-PFE — lancement Uvicorn (PowerShell)
Set-Location $PSScriptRoot
& .\venv\Scripts\uvicorn.exe main:app --reload --host 127.0.0.1 --port 8000

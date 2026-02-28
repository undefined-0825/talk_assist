cd C:\dev\talk_assist\backend
.\.venv\Scripts\Activate.ps1
$env:REDIS_DISABLED = "true"
uvicorn app.main:app --host 127.0.0.1 --port 8000

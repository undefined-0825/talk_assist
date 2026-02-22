@echo off
setlocal

REM backendフォルダへ移動
cd /d %~dp0

REM .env 読み込み
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        if not "%%A"=="" (
            set %%A=%%B
        )
    )
)

REM venv内のpythonを直接使用（activateしない）
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8000

endlocal
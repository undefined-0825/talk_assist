@echo off
setlocal

REM 1. バックエンド起動（別ウィンドウ）
cd /d %~dp0backend
start cmd /k start_api.bat

REM 2. 少し待つ
timeout /t 3 > nul

REM 3. ポート転送（Pixel 9 実機用）
adb reverse tcp:8000 tcp:8000

REM 4. Flutter 起動（実機指定）
cd /d %~dp0frontend
flutter run -d 46251FDAQ001TC

endlocal
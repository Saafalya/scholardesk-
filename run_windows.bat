@echo off
title Scholarship Screening Desk + Ollama
cd /d "%~dp0"
echo === Scholarship Screening Desk with Ollama ===
echo.

where python >nul 2>&1 || (echo [X] Python is missing. Install it from https://python.org then run this again. & pause & exit /b 1)
where ollama >nul 2>&1 || (echo [X] Ollama is missing. Install it from https://ollama.com then run this again. & pause & exit /b 1)

echo [1/4] Setting up Python packages (first run takes a minute or two)...
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt || (echo [X] Package install failed. & pause & exit /b 1)

echo [2/4] Starting Ollama...
ollama list >nul 2>&1 || (start "Ollama" /min ollama serve & timeout /t 5 /nobreak >nul)

echo [3/4] Checking for the llama3.2:3b model...
ollama list | findstr /i "llama3.2:3b" >nul || ollama pull llama3.2:3b

echo.
echo [4/4] Opening the app in your browser...
echo   In the sidebar, press "Test the model" once so the first case is quick.
echo   Close this window to stop the app.
echo.
streamlit run app.py
pause

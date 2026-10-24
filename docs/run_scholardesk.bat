@echo off
title Scholarship Screening Desk
cd /d "%~dp0"

where git >nul 2>&1 || (echo [X] Git is missing. Install it from https://git-scm.com then run this again. & pause & exit /b 1)

echo Getting the latest project code...
if exist scholardesk\.git (
  git -C scholardesk pull
) else (
  git clone https://github.com/Saafalya/scholardesk- scholardesk
)
call scholardesk\run_windows.bat

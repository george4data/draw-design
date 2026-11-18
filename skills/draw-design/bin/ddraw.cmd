@echo off
setlocal
set "DIR=%~dp0.."
set "PYTHONPATH=%DIR%\scripts;%PYTHONPATH%"
where py >nul 2>nul && (py -3 -m ddraw %*) || (python -m ddraw %*)

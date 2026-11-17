@echo off
REM Debug launcher: same as the "Lucy" shortcut, but with a console window
REM so you can see errors. For everyday use, use the shortcut instead.
"%USERPROFILE%\.venvs\gesture-volume\Scripts\python.exe" "%~dp0server.py" %*
pause

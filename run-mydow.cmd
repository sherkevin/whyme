@echo off
setlocal

REM One-command Docker launcher for Mydow PRD10.
REM Usage from cmd.exe:
REM   run-mydow.cmd

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_mydow_docker.ps1" %*
exit /b %ERRORLEVEL%

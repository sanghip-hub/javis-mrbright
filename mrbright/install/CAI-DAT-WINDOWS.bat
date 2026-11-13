@echo off
chcp 65001 >nul
title Cai dat Javis
cd /d "%~dp0"
REM Bam dup file nay de cai Javis. Can mang Internet (tai Python, Node, thu vien).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0javis\mrbright\install\cai-windows.ps1" -Nguon "%~dp0javis"

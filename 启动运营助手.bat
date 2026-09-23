@echo off
chcp 65001 >nul
title 米游社运营助手
color 0B
echo.
echo   ╔══════════════════════════════════════╗
echo   ║       米游社运营助手 v2.0            ║
echo   ║     All-in-One Ops Tool              ║
echo   ╚══════════════════════════════════════╝
echo.
echo   [*] 正在启动服务，请稍候...
echo.
cd /d "%~dp0"
python -m streamlit run app.py --server.port 8501
pause

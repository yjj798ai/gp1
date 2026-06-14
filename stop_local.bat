@echo off
title 停止股神圣杯系统
echo 正在停止所有服务...

:: 停止调度器
taskkill /fi "WINDOWTITLE eq gp1-scheduler" /f 2>nul
echo   ✅ 调度器已停止

:: 停止Streamlit
taskkill /fi "WINDOWTITLE eq gp1-streamlit" /f 2>nul
echo   ✅ Streamlit已停止

:: 杀掉残留的streamlit进程
taskkill /im python.exe /f 2>nul | findstr /i "streamlit" >nul
echo   ✅ 清理完成

echo.
echo 已全部停止
pause

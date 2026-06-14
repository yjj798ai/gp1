@echo off
title 股神圣杯系统 - 本地启动器
echo ============================================
echo   股神圣杯系统 - 启动 Streamlit + 调度器
echo ============================================
echo.

cd /d E:\AI\gp1\gp_project

:: 启动调度器（后台窗口）
echo [1/3] 启动采集调度器...
start "gp1-scheduler" /min cmd /c "python scheduler.py >> ..\logs\scheduler_console.log 2>&1"

:: 等5秒让调度器跑起来
timeout /t 3 /nobreak >nul

echo [2/3] 启动 Streamlit 服务...
start "gp1-streamlit" /min cmd /c "streamlit run main.py --server.port 8501 --server.headless true"

:: 等10秒等Streamlit启动
timeout /t 8 /nobreak >nul

echo [3/3] 打开浏览器...
start http://localhost:8501

echo.
echo ✅ 已启动！
echo   - 调度器: 窗口已最小化
echo   - Streamlit: http://localhost:8501
echo   - 如果浏览器没自动打开，手动访问上面地址
echo.
echo 按任意键关闭本窗口（服务仍在后台运行）
pause >nul

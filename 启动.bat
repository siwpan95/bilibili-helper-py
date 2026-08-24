@echo off
chcp 65001 > nul
echo ================================================
echo   B站视频下载助手 - 启动脚本
echo ================================================
echo.

REM 检查 Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 检查依赖...
pip show yt-dlp > nul 2>&1
if errorlevel 1 (
    echo 安装 yt-dlp...
    pip install yt-dlp
)

REM 检查 ffmpeg
where ffmpeg > nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 ffmpeg，视频合并功能可能受限
    echo 建议安装 ffmpeg：winget install ffmpeg
    echo.
)

REM 启动程序
echo [2/3] 启动程序...
python "%~dp0main.py"

pause

@echo off
chcp 65001 > nul
echo 打包 B站视频下载助手 为独立EXE...

REM 安装 PyInstaller
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)

REM 打包
pyinstaller --onefile ^
    --windowed ^
    --name "B站视频下载助手" ^
    --icon "icon.png" ^
    --add-data "icon.png;." ^
    --hidden-import "yt_dlp" ^
    --collect-all "yt_dlp" ^
    main.py

echo.
echo 打包完成！EXE 位于 dist 目录
pause

@echo off
chcp 65001 >nul
title 知寻 KnowSeek 一键启动
echo ============================================
echo   知寻 KnowSeek 企业级智能知识中枢
echo   一键启动脚本
echo ============================================
echo.

cd /d "%~dp0"

REM ============================================================
REM 说明：
REM  1) 本脚本用于本地开发一键启动（后端 8000 + 前端 5174）。
REM  2) 后端工作目录必须是 server\，db/向量库/上传目录均相对该目录定位。
REM  3) 若已有旧进程占用端口，脚本会提示并退出，请先结束旧进程再执行，
REM     否则可能出现"改了代码不生效"（旧进程仍在服务旧代码）。
REM  4) 生产环境请勿使用 --reload，并改用 nginx 托管 web\dist。
REM ============================================================

echo [0/4] 环境预检...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 python 命令，请先安装 Python 3.11+ 并加入 PATH
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo       Python %%v
netstat -ano | findstr LISTENING | findstr ":8000 " >nul
if not errorlevel 1 (
    echo [提示] 端口 8000 已被占用，可能是旧后端进程，请先结束后再启动
    netstat -ano | findstr LISTENING | findstr ":8000 "
    pause
    exit /b 1
)
netstat -ano | findstr LISTENING | findstr ":5174 " >nul
if not errorlevel 1 (
    echo [提示] 端口 5174 已被占用，可能是旧前端进程，请先结束后再启动
    netstat -ano | findstr LISTENING | findstr ":5174 "
    pause
    exit /b 1
)
echo       完成

echo [1/4] 检查后端依赖...
cd server
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 后端依赖安装失败，请检查 Python 环境
    pause
    exit /b 1
)
echo       完成

echo [2/4] 初始化数据库...
python scripts/init_db.py
if errorlevel 1 (
    echo [错误] 数据库初始化失败
    pause
    exit /b 1
)
echo       完成

echo [3/4] 启动后端服务 (http://127.0.0.1:8000) ...
start "KnowSeek-Backend" cmd /k "cd /d %~dp0server && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload > ..\server_uvicorn.log 2>&1"
echo       完成

echo [4/4] 安装前端依赖并启动 (http://127.0.0.1:5174) ...
cd /d "%~dp0web"
if not exist node_modules (
    call npm install
    if errorlevel 1 (
        echo [错误] 前端依赖安装失败
        pause
        exit /b 1
    )
)
start "KnowSeek-Frontend" cmd /k "cd /d %~dp0web && npm run dev -- --host 127.0.0.1 --port 5174"

echo.
echo ============================================
echo   启动完成！
echo   前端: http://127.0.0.1:5174
echo   后端: http://127.0.0.1:8000
echo   接口文档: http://127.0.0.1:8000/docs
echo ============================================
echo.
echo 提示：若后端代码有改动，请手动刷新后端窗口。
pause

@echo off
REM 影灵 CINE 启动脚本：从 data/task/llm_key.local.txt 读取本地密钥（该文件不入库/不随提交物）
REM 无密钥文件时自动降级为离线模式；也可手动 set CINE_LLM_API_KEY=<你的key>
setlocal
cd /d "%~dp0"
if exist "data\task\llm_key.local.txt" (
  set /p CINE_LLM_API_KEY=<data\task\llm_key.local.txt
)
echo 启动影灵 CINE @ http://127.0.0.1:8010
python -m uvicorn cine.main:app --port 8010
endlocal

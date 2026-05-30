@echo off
REM Git推送脚本 - 使用凭证

cd e:\VOICE\vibesing-labeling

REM 配置git凭证辅助程序
git config credential.helper manager

REM 推送到GitHub（会从凭证管理器获取或提示输入）
echo 正在推送到GitHub...
git push -u origin main

echo.
echo 推送完成！
echo 请检查 https://github.com/fengniudashen/VOICE_LABEL 确认文件已上传
pause

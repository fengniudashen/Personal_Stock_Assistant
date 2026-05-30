#!/usr/bin/env pwsh
# VibeSing 项目 GitHub 推送脚本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   VibeSing GitHub 自动推送脚本" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Git 安装
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git 未安装或不在 PATH 中" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Git 已安装: $(git --version)" -ForegroundColor Green
Write-Host ""

# 检查是否在正确的目录
$currentDir = Get-Location
$gitDir = Join-Path $currentDir ".git"
if (-not (Test-Path $gitDir)) {
    Write-Host "❌ 不在 Git 仓库目录中" -ForegroundColor Red
    Write-Host "请运行: cd e:\VOICE\vibesing-labeling" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 在 Git 仓库目录: $currentDir" -ForegroundColor Green
Write-Host ""

# 提示用户输入令牌
Write-Host "====== GitHub 个人访问令牌 (PAT) ======" -ForegroundColor Yellow
Write-Host ""
Write-Host "GitHub 已禁用密码认证。您需要创建个人访问令牌:" -ForegroundColor Yellow
Write-Host ""
Write-Host "步骤:"
Write-Host "1. 访问: https://github.com/settings/tokens"
Write-Host "2. 点击 'Generate new token (classic)'"
Write-Host "3. 选择 scopes: repo (和 write:repo_hook)"
Write-Host "4. 复制生成的令牌"
Write-Host ""

$token = Read-Host "请粘贴您的 GitHub 个人访问令牌"

if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Host "❌ 令牌不能为空" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "配置 Git 凭证..." -ForegroundColor Cyan

# 配置凭证
$credentialInput = @"
protocol=https
host=github.com
username=suiyuan9201
password=$token
"@

$credentialInput | git credential approve

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  凭证存储有问题，但继续尝试推送..." -ForegroundColor Yellow
}

Write-Host "✓ 凭证已配置" -ForegroundColor Green
Write-Host ""

# 检查远程仓库
Write-Host "检查远程仓库配置..." -ForegroundColor Cyan
$remotes = git remote -v
Write-Host $remotes -ForegroundColor Gray

Write-Host ""
Write-Host "========== 推送代码 ==========" -ForegroundColor Green
Write-Host ""

# 推送
git push -u origin main -v

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ 推送成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "访问您的仓库: https://github.com/fengniudashen/VOICE_LABEL" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "❌ 推送失败" -ForegroundColor Red
    Write-Host ""
    Write-Host "如果出现 'Invalid username or token' 错误:" -ForegroundColor Yellow
    Write-Host "- 确保令牌是有效的且尚未过期" -ForegroundColor Yellow
    Write-Host "- 令牌需要 'repo' scope 权限" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "完整说明请查看: GitHub_推送说明.md" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

# GitHub推送说明

## 问题
GitHub 不再支持用密码来进行 Git 操作。您需要创建一个**个人访问令牌（Personal Access Token，PAT）**。

## 解决方案

### 步骤 1: 创建 GitHub 个人访问令牌

1. 登录 GitHub: https://github.com/login
   - 邮箱: `suiyuan9201@gmail.com`
   - 密码: 您的密码

2. 点击右上角头像 → **Settings**

3. 左侧菜单 → **Developer settings** → **Personal access tokens** → **Tokens (classic)**

4. 点击 **Generate new token (classic)**

5. 填写信息：
   - **Note**: `VOICE_LABEL_PUSH` (或任意名称)
   - **Expiration**: 选择 90 days 或 No expiration
   
6. **Select scopes** 选择以下权限：
   ```
   ☑ repo (完全访问私有仓库)
   ☑ write:repo_hook
   ```

7. 点击 **Generate token**

8. **复制生成的令牌**（重要！只会显示一次）
   - 令牌格式类似: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 步骤 2: 使用令牌推送代码

打开 PowerShell，运行以下命令：

```powershell
cd e:\VOICE\vibesing-labeling

# 或者替换 origin 远程 URL 为使用令牌的形式
git remote set-url origin https://<YOUR_USERNAME>:<YOUR_TOKEN>@github.com/fengniudashen/VOICE_LABEL.git

# 例如（将 YOUR_TOKEN 替换为实际的令牌）:
git remote set-url origin https://suiyuan9201:<YOUR_TOKEN>@github.com/fengniudashen/VOICE_LABEL.git

# 然后推送
git push -u origin main
```

或者使用更安全的方法 - 使用凭证存储：

```powershell
# 将令牌保存到凭证存储
@"
protocol=https
host=github.com
username=suiyuan9201
password=<YOUR_TOKEN>
"@ | git credential approve

# 推送代码
git push -u origin main
```

### 步骤 3: 验证

推送完成后，访问: https://github.com/fengniudashen/VOICE_LABEL

您应该能看到所有文件已上传。

## 注意事项

- 🔐 **令牌安全**: 不要在版本控制中提交令牌，或在公开的地方分享它
- ⏰ **令牌过期**: 定期检查令牌过期时间，在过期前更新
- 🔄 **一次性**: 令牌只在创建时显示一次，之后无法重新查看
- 如果遗失，删除旧令牌并创建新的即可

## 常见问题

Q: 推送后如何删除或更新令牌?  
A: 在 Settings → Developer settings → Personal access tokens 中删除旧令牌，然后创建新的

Q: 通过 HTTPS 推送后会不会每次都要输入凭证?  
A: 使用凭证管理器或凭证存储后会自动保存，第一次输入后不需再输入

Q: 令牌意外泄露怎么办?  
A: 立即在 GitHub 上删除该令牌，创建新的令牌替换

---

**祝您上传成功！**

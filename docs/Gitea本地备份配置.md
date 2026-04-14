# Gitea 本地备份配置

## 概述

项目同时托管在 GitHub 和内网 Gitea 上，实现双备份。

| 远程仓库 | 地址 | 用途 |
|----------|------|------|
| origin (GitHub) | https://github.com/wangzhenhua896-glitch/exam-system.git | 公开/协作备份 |
| gitea (内网) | http://192.168.255.10:3000/Macbook/question-bank.git | 内网快速备份 |

## 已同步分支

- `master`
- `multi-fullscore-answers`

## 常用命令

```bash
# 推送到 Gitea（已配置令牌，无需输入密码）
git push gitea <branch-name>

# 推送到 GitHub
git push origin <branch-name>

# 查看所有远程仓库
git remote -v

# 从 Gitea 拉取
git pull gitea <branch-name>
```

## 新增分支同步

```bash
# 推送新分支到 Gitea
git push gitea <new-branch>

# 推送所有分支
git push gitea --all

# 推送所有标签
git push gitea --tags
```

## Gitea 信息

- **地址**: http://192.168.255.10:3000
- **仓库**: Macbook/question-bank
- **认证**: Token 认证（已嵌入 remote URL）

## 注意事项

- Gitea remote URL 中包含令牌，不要泄露 `.git/config` 文件
- `.env`、`deploy.sh`、`data/exam_system.db` 已在 `.gitignore` 中，不会被推送
- 如果令牌过期，需要更新 remote URL：
  ```bash
  git remote set-url gitea http://Macbook:<新令牌>@192.168.255.10:3000/Macbook/question-bank.git
  ```

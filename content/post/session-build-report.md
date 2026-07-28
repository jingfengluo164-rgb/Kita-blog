---
title: "建站交流纪要：从 Reimu 主题到 Cloudflare 上线"
description: "整理本次从 Hugo 主题安装、双分支同步、到 Cloudflare Pages 部署与静态站扩展相关的交流要点"
keywords: "Hugo,Reimu,Cloudflare,GitHub Actions,建站"

date: 2026-07-28T17:23:00+08:00
lastmod: 2026-07-28T17:23:00+08:00

math: false
mermaid: false

categories:
  - 建站笔记
tags:
  - Hugo
  - Cloudflare
  - GitHub Actions

---

本文记录本仓库从空壳到可公网访问期间的主要决策、踩坑与结论，便于后续扩写内容或排查问题时对照。

<!--more-->

## 1. 目标与最终形态

目标是搭建一套可公网访问的个人博客。最终链路为：

1. 本地用 **Hugo + hugo-theme-reimu** 维护源码
2. 推送到 **GitHub**（`raw` 为源码分支，`main` 为同步后的分支）
3. **Cloudflare Pages** 拉取仓库、执行 `hugo` 构建，对外提供静态站点

这是典型的 **静态站托管**：构建产物是 HTML/CSS/JS，没有自建长期运行的应用服务器。

## 2. 主题安装：方式 2（本地 themes）

主题采用 Git Submodule / 本地目录方式，而不是 Hugo Module。

| 项目 | 说明 |
| :--- | :--- |
| 主题路径 | 必须是 `themes/reimu/`，不能把主题文件直接摊在 `themes/` 根下 |
| 配置写法 | `hugo.toml` 中写 `theme = "reimu"` |
| 对比 Module | Module 写模块地址且主题不落在 `themes/`；本地方式便于手动改主题与对照文件 |

安装后若要深度定制，应按主题文档把 `params.yml`、`data/`、静态资源 **复制到站点外层** 覆盖，避免直接改主题目录，方便升级。

## 3. Git 与远程协作中的问题

交流中出现过多类 Git 问题，性质不同，需分开处理：

| 现象 | 原因 | 处理方向 |
| :--- | :--- | :--- |
| `remote origin already exists` | 重复 `git remote add` | 用 `git remote set-url` 修改地址 |
| Author identity unknown | 未配置 `user.name` / `user.email` | 本地自行配置身份后再 commit |
| `Connection was reset` / 连不上 `github.com:443` | 网络或未走代理 | 开代理、给 Git 配 proxy，或改 SSH |
| Cursor 提交编辑器 500 | IDE 内置 git-editor 异常 | 终端使用 `git commit -m "..."` |

本地若显示 `ahead of 'origin/raw' by N commit`，表示提交已在本地，只差推送成功。

## 4. 双分支与 GitHub Actions

教程约定：

- **`raw`**：未清洗 / 源码工作区，建议设为默认分支，方便看源码
- **`main`**：Action 清洗（如 `fix_cover.py`）后的结果，可供 Pages 构建

工作流文件：`.github/workflows/process-sync.yml`。

曾出现的失败：清洗后无文件变更时，`git commit` 返回非 0，导致后续 `git push` 未执行，`main` 长期只有初始 README。处理方式是：**无变更则跳过 commit，但仍强制推送到 `main`**。

Cloudflare 若构建的是空的 `main`，会报找不到 `hugo.toml`；`main` 同步完整后该问题消失。也可临时让 Pages 直接构建 `raw`。

## 5. Cloudflare Pages 构建要点

构建配置可用：

- Build command：`hugo --gc --minify`
- Output directory：`public`
- Root directory：留空
- Production branch：`main`（或内容完整的 `raw`）

关键环境变量：

```text
HUGO_VERSION=0.158.0
```

Reimu 主题要求 **Hugo ≥ 0.158.0（extended）**。若使用 Cloudflare 默认旧版（日志中曾见 `v0.147.7`），会因不存在 `.Site.Language.Locale` 而构建失败。

部署成功后，站点由 Cloudflare CDN 对外提供公网 URL，任意访客均可访问（默认公开），与本地 `hugo server` 仅本机可访问不同。

## 6. 内容应放在哪里

| 路径 | 含义 |
| :--- | :--- |
| `content/` | **正式内容目录**，文章与页面写在这里 |
| `themes/reimu/_example/` | 主题自带的 **结构示例**，只作参考，不要当生产内容目录改 |

主题要求的基本结构：

```text
content/
├── post/
│   ├── _index.md    # draft: true，用于禁用 post/index.html，不可删
│   └── *.md         # 文章
├── archives/
│   └── _index.md    # 归档页，不可省
├── about.md         # 关于（可选，建议有）
└── friend.md        # 友链（可选）
```

交流结束时站点几乎无正文；后续扩充应优先补文章与站点身份信息（`title`、`baseURL`、中文语言、作者与 `params.yml`），再考虑评论、友链等功能。

## 7. 静态站与「后端」

当前架构 **不能** 在 Hugo/Pages 里直接跑传统后端进程。需要接口或存储时，常见接法：

- 评论：Giscus / Waline / Twikoo 等（主题多已支持）
- 轻量 API：与现有托管同生态的 **Cloudflare Workers**
- 数据：Workers 搭配 KV / D1 / R2

Workers 可理解为跑在 Cloudflare 边缘的轻量后端（按请求执行），适合个人站 API，但不是替代所有大型服务端应用。

## 8. 后续建议清单

1. 完善 `hugo.toml`：真实 `baseURL`、站点标题、中文 `languageCode` 等
2. 将主题 `params.yml` 与 `data/` 复制到站点外层并改为自己的信息
3. 在 `content/post/` 持续写文章；补 `about.md` 等页面
4. 确认 Action 在每次 `raw` 推送后能稳定同步 `main`
5. 需要互动能力时，再单独引入 Workers 或第三方评论，而不是改静态构建模型

---

*本纪要基于建站过程中的交流整理，供本仓库后续维护参考。*
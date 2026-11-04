# 项目说明（给 AI 助手）

每日智慧：自动抓取几位上师的微博，做成适合 iPad / 电脑长时间播放的静态网站。
网址 https://little-bodhisattva.github.io/ ，仓库 `little-bodhisattva/little-bodhisattva.github.io`。
维护者不写代码：请用中文交流，讲清楚需要维护者在网页上做什么，代码改完后直接合并上线。

## 结构

- `accounts.txt`：要抓的微博账号（数字 ID / 主页链接 / 名字，名字会自动查 ID）。
- `scripts/fetch_weibo.py`：抓取（只用标准库 + 可选 Pillow 压图）。多账号、增量、补抓历史
  （`--backfill-until`、`--max-new`、`--only`）。cookie 来自 Secret `WEIBO_COOKIE`（只放 `SUB=...` 即可）。
- `scripts/fetch_music.py`：部署时读取 B 站公开收藏夹，生成 `docs/music/bilibili.json`。
- `docs/`：网站本体（GitHub Pages 用 Actions 部署这个目录）。
  - `data/posts.json`（所有微博，带 `uid`）、`data/profiles.json`（各账号头像昵称）、`images/`。
  - `app.js`（幻灯片/滚动、多上师筛选、音乐、时钟、夜间、离线）、`style.css`、`sw.js`（离线缓存）。
  - `music/playlist.txt`：背景音乐清单（YouTube / B 站 / 本地文件）。
- `.github/workflows/`：`daily.yml`（每天北京时间 7 点抓取+部署）、`backfill.yml`（手动补抓历史）、
  `pages.yml`（docs 改动后部署）。三个共用并发组 `daily-wisdom`。

## 约定

- 改网页后更新 `app.js` 里的 `BUILD` 版本号（显示在设置面板底部，用来确认设备拿到了新版本）。
- 新增本地设置要给默认值；需要一次性迁移旧设置时提升 `settings.v`。
- iPad Safari 注意：不要给可滚动区域加 mask-image，也不要给正文单独做 transform/opacity 动画
  （曾导致“正文空白”）；没有 WebKit 测试环境，改动样式要保守。
- 抓取失败要让 Action 变红并写清原因（cookie 失效、图床 403 等），不要静默跳过。
- 改动走分支 → PR → 合并到 `main`；不要直接改 `docs/data`、`docs/images`（由 Action 维护）。
- 本地测试：`cd docs && python3 -m http.server`；抓取需要 cookie，只能在 Actions 里真跑。

## 常见维护

- cookie 过期：Action 报“微博要求登录”。让维护者按 README 复制 `SUB` 更新 Secret，然后手动跑“每日抓取微博”。
- 加/减上师：编辑 `accounts.txt`；新账号首次抓 100 条，历史用“补抓历史微博”并填“只补哪些账号”。
- 图片总量接近 1 GB（GitHub Pages 上限）时提醒维护者。

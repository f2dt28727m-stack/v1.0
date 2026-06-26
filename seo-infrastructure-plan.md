# SEO 基建方案 —— QuizFig

> 目标：让每个问卷都能被搜索引擎收录；同时新增 / 删除 / 更新问卷时不需要改任何 SEO 配置就能自动同步。
> 约束：兼顾用户体验、稳定性、安全性。

---

## 1. 当前状态盘点

| 维度 | 现状 |
| --- | --- |
| 问卷数据 | `quizzes/*.json` 顶层 187 个；每个含 `title / category / tags / description / 12 questions / 16 results / emoji / likes` |
| 渲染方式 | 所有页面（首页 / 详情 / 答题）都靠 JS `fetch` 注入，HTML 主体是空的 |
| robots / sitemap | **完全缺失** |
| meta 标签 | 三个 HTML 的 `<title>` 全是写死的；无 description / canonical / OG / Twitter |
| URL | 全部 `?id=quiz_100` query 形式，无语义 |
| 结构化数据 | **无** |
| 部署 | Vercel (`@vercel/python` + `@vercel/static`)，`vercel.json` 已有 `api/index.py` + 静态资源 |
| 安全 | 客户端硬编码了 `apiKey: 'quiz_app_secret_key_2026'`（预先存在） |

**已经发现两个连带问题（顺手修）：**
1. `vercel.json` 里 Python 的 `includeFiles` 只有 `quizzes/**` 和 `config.json`，但 `api/index.py` 会读 `data/tags.json` → Vercel 部署上 `/api/tags` 一直会 500，本地能跑只是因为文件系统能看到。
2. `api/index.py` 旧版 `XSS 风险`：所有 quiz 数据将来若有 HTML 注入会原样输出（目前是安全的，但等下加 SSR 时必须全程 escape）。

---

## 2. 核心设计决策

### 2.1 URL 结构

采用 **`/quiz/<id>`** 作为主 URL，**额外兼容** `/quiz/<id>-<slug>` 形式（slug 仅作为美化的 keyword，解析时被丢弃）。

理由：
- 单一 ID 形式对**问卷改标题 / 改 slug**免疫，不会因内容更新产生 404
- 带 slug 的 URL 仍然能命中，方便站外链接的 keyword 引用
- Google 会把 canonical 指向 `/quiz/<id>`，slug 形式是 200 OK 但带 `rel=canonical` 自我收敛

### 2.2 渲染方式：**SSR via Vercel Python 函数**（不是静态预生成）

候选：
| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| **A. SSR（推荐）** Python 函数读 `quizzes/` 输出 HTML | 新增 / 删除 / 更新问卷**部署即生效**；代码少 | 冷启动有 50–200ms |
| B. 静态预渲染（build step） | CDN 直出最快 | 每次增减都要重新 build；和当前 `generate_quiz.py` 流程叠加复杂度高 |
| C. Edge Function + KV 存元数据 | 最快 + 热更新 | 要把 quiz 元数据迁出文件系统，工程量大 |

**选 A**，因为：
- 用户的"问卷不停增减"场景，每次改一个就要 build 太重
- SSR 配合边缘 cache 可以做到 95% 命中无冷启动
- 复用现有 `api/index.py`，改动面最小

### 2.3 缓存策略

- `Cache-Control: public, max-age=300, s-maxage=3600, stale-while-revalidate=86400`
  - 浏览器：5 分钟
  - Vercel Edge CDN：1 小时
  - SWR：1 天，部署时立即拉新一次就过
- 部署时 Vercel 自动让所有旧 instance 失效，所以"新增 / 删除问卷"只要部署就能看到

### 2.4 兼容性：问卷"不停增减"怎么覆盖

| 操作 | 自动同步方式 |
| --- | --- |
| **新增** `quizzes/quiz_201.json` | PR 合并 → Vercel 部署 → function cold start 时 `os.listdir('quizzes/')` 自动包含新文件 → sitemap 包含新 URL → `/quiz/quiz_201` 返回 SSR |
| **删除** 文件 | 部署 → 列表里少一个 → sitemap 立刻少一个 → 访问旧 URL 返回 404 |
| **更新** title / desc / 题目 | 部署 → SSR 输出新内容；已索引的 URL 上次抓取过的，旧内容在 SWR 窗口期返回，随后被新版本替换（Google 自然重新抓） |
| **批量** 一次加 10 个 | 一次部署就完事，不需要任何额外配置 |

**唯一需要做的事**：`git push` → Vercel 自动部署。无 SEO 配置文件需要改。

### 2.5 安全

- **HTML escape**：所有 quiz 数据进 HTML 都过 `html.escape(..., quote=True)`
- **路径白名单**：`/quiz/<id>` 的 id 必须匹配 `^[A-Za-z0-9_]+$`，防 path traversal
- **安全响应头**：`X-Content-Type-Options: nosniff`、`X-Frame-Options: SAMEORIGIN`、`Referrer-Policy: strict-origin-when-cross-origin`、`Permissions-Policy` 收紧地理 / 麦克风 / 摄像头
- **CSP**：第一版不上 CSP（会卡住现有 AdSense），后续可以加 nonce 模式
- **不暴露 API key**：服务器读 `config.json`，客户端只走 `/api/token` 拿 session token（这个本来就是已有设计）

### 2.6 用户体验

- SSR 详情页是 **self-contained 单文件**（CSS 内联、字体走系统栈），首屏 0 JS 也能看
- 移动端响应式：480px 断点
- 加载中 → 已加载**无白屏闪烁**（这点是 JS 详情页做不到的）
- 详情页 → 答题页用 `quiz.html?id=<id>` 静态文件，已有逻辑不动

---

## 3. 文件变更清单

> 文件路径相对仓库根 `/Users/jerrysrick/Desktop/0607/v1.0/`。

### 3.1 `api/index.py` —— 加 SEO 路由
- 新增 helpers：`h()`（HTML escape）、`slugify()`、`get_quiz_summary()`、`find_related_quizzes()`
- 新增路由：
  - `GET /robots.txt` → 文本
  - `GET /sitemap.xml` → 动态生成（从 `_quizzes`）
  - `GET /quiz/<id>` 或 `GET /quiz/<id>-<slug>` → SSR HTML
  - `GET /quiz/<id>-<slug>` 解析时丢弃 slug 段
- SSR HTML 包含：
  - `<title>` / `description` / `canonical` / `robots` / `theme-color`
  - `og:type=article` / `og:title` / `og:description` / `og:url` / `og:site_name`
  - `twitter:card=summary_large_image` / `twitter:title` / `twitter:description`
  - **Schema.org JSON-LD**：`Quiz` + `BreadcrumbList`
  - 可见内容：emoji、title、tags、description、问答数、结果数、Start Now CTA
  - 三个 section：About / Sample Questions（前 3 题）/ Possible Results（全结果）/ Related Quizzes（按 tag 重叠度算 4 个）
- 所有 quiz JSON 数据注入 HTML 前**全部 `h()` escape**
- API 路由保留原样，行为兼容

### 3.2 `vercel.json` —— rewrites + 修 includeFiles
- `includeFiles` 追加 `data/**`（修 tags.json 读不到的旧 bug）
- `routes` 顺序调整为：
  ```json
  [
    { "src": "/api/(.*)",     "dest": "/api/index.py" },
    { "src": "/quiz/(.+)",    "dest": "/api/index.py" },
    { "src": "/sitemap.xml",  "dest": "/api/index.py" },
    { "src": "/robots.txt",   "dest": "/api/index.py" },
    { "src": "/(.*)",         "dest": "/$1" }
  ]
  ```
  （顺序很关键：先匹配 SEO 路径，再 fallback 静态资源。）

### 3.3 `index.html` —— 首页 SEO
- 加 `description`、`canonical`、`og:*`、`twitter:*`
- 加 `WebSite` + `Organization` JSON-LD
- 内部链接 `quiz-detail.html?id=xxx` 全部改成 `/quiz/xxx`
- 保留 `?id=xxx` 形式作为 hash，方便老链接（Vercel 静态 `quiz-detail.html` 仍存在，并 JS 跳转 / 渲染）

### 3.4 `quiz.html` —— 答题页动态 meta
- 进入时用 JS 把 `document.title` 改成 `<quiz_title> | QuizFig`（已经有 fetch，可以从 `data.title` 拿）
- 注入 `link[rel=canonical]`，避免被当成首页内容
- 注入 og / twitter meta（分享时显示正确卡片）

### 3.5 `quiz-detail.html` —— 兼容旧链接
- 改成**客户端 301 跳转到 `/quiz/<id>`**，避免内容重复（首页 JS 改成新 URL 后，这文件只是历史入口兜底）
- 跳转前先 fetch `/api/quizzes/<id>` 验证存在；不存在才显示原 fallback

### 3.6 `local_server.py` —— 本地 dev
- `do_GET` 改成：`/api/`、`/quiz/`、`/sitemap.xml`、`/robots.txt` 全部走 WSGI，其它走静态
- 不动现有结构，diff 控制在 10 行内

### 3.7 `app.py`（Flask 本地备用）
- 同样补 `/quiz/<id>`、`/sitemap.xml`、`/robots.txt` 三个路由（共享 build 函数就行）
- 避免本地用 Flask 启服务时 SEO 路由不工作

---

## 4. 不做的事（明确边界）

| 不做 | 原因 |
| --- | --- |
| 不重写 `quiz.html`（答题页） | 用户每次答的是交互内容，SEO 价值低；JS 注入 meta 已够 |
| 不做首页 SSR | 首页主要是浏览，sitemap 已覆盖所有问卷；改首页 SSR 风险大收益小 |
| 不上 CSP | AdSense 第三方脚本需要宽松策略；后续可加 nonce 模式 |
| 不动 API key | 预先存在，单独 ticket 处理（建议改为 env var 注入） |
| 不做静态 build 脚本 | 选了 SSR 路线，build 反而是负担 |
| 不做分类索引页（`/category/popular` 等） | 第一版够用；列入 future |

---

## 5. 验证步骤

实施完成后跑：

```bash
# 1) 基础 SEO 资源
curl -s http://localhost:8000/robots.txt
curl -s http://localhost:8000/sitemap.xml | grep -c '<loc>'        # 应 ≈ 188
curl -sI http://localhost:8000/quiz/quiz_100 | head -5              # 200 + 安全头
curl -s  http://localhost:8000/quiz/quiz_100 | grep -E 'title|canonical|application/ld' | head -5

# 2) 兼容性：动态反映 quizzes/ 变化
cp quizzes/quiz_100.json /tmp/backup.json
echo '{"title":"X","category":"which_x","tags":["t"],"description":"d","questions":[],"results":[],"emoji":["?"]}' > quizzes/quiz_999.json
curl -s http://localhost:8000/sitemap.xml | grep quiz_999          # 出现
curl -s http://localhost:8000/quiz/quiz_999 | grep -E 'title'       # 渲染
rm quizzes/quiz_999.json
curl -s http://localhost:8000/sitemap.xml | grep quiz_999          # 没了
mv /tmp/backup.json quizzes/quiz_100.json

# 3) 安全
curl -s http://localhost:8000/quiz/..%2F..%2Fetc%2Fpasswd          # 404
curl -s "http://localhost:8000/quiz/<script>alert(1)</script>"     # 404

# 4) Lighthouse / PageSpeed Insights
# 在生产域跑 mobile + desktop，目标 SEO ≥ 95
```

部署后用 Google Search Console：
1. 验证域名
2. 提交 `https://<domain>/sitemap.xml`
3. 用 URL Inspection 抽查几个 `/quiz/<id>` 看是否被收录

---

## 6. 实施顺序（建议）

1. ✅ Phase A：先把 `api/index.py` / `vercel.json` / `local_server.py` 改好（半小时内），跑本地验证 5 个核心 URL
2. ✅ Phase B：改 `index.html`（meta + 链接），改 `quiz.html`（JS 注入 meta）
3. ✅ Phase C：把 `quiz-detail.html` 改成 301 跳转
4. ✅ Phase D：本地完整跑 验证步骤里的 1+2+3
5. 推送 → Vercel 部署 → 在 Search Console 提交 sitemap

---

## 7. Future（不在本次实施范围）

- 把 quiz 元数据迁到 Vercel KV / Postgres，做到**热更新**（不用 redeploy）—— 问卷频繁到一定程度才需要
- 分类索引页 `/category/<cat>`，给搜索引擎更多 landing page
- RSS / Atom feed for "新问卷"
- hreflang（如果以后做多语言）
- OG 图片自动生成（每张问卷一张 1200x630）
- 把 `apiKey: 'quiz_app_secret_key_2026'` 从客户端 JS 移除（pre-existing 安全债）

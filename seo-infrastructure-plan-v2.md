# SEO 基建方案 v2.0 —— QuizFig

> 基于 v1.0 审阅后修订。已实现部分标注 ✅，待实现部分标注 ⬜。
> 目标：安全、用户体验好、稳定、可拓展；新增/删除/更新问卷自动适应，无需手动配置。

---

## 1. 当前状态盘点

| 维度 | 现状 |
| --- | --- |
| 问卷数据 | `quizzes/*.json` 顶层 ~187 个；每个含 `title / category / tags / description / 12 questions / 16 results / emoji / likes` |
| SSR 引擎 | ✅ `api/index.py` 已实现 SSR、sitemap、robots、helpers（`h()`, `get_quiz_summary()`, `find_related_quizzes()`） |
| 本地 dev | ✅ `local_server.py` 已更新 WSGI 路由覆盖 `/quiz/`, `/sitemap.xml`, `/robots.txt` |
| Flask 备用 | ✅ `app.py` 已补充 SEO 路由 |
| Vercel 部署配置 | ⬜ `vercel.json` routes 缺 `/quiz/`, `/sitemap.xml`, `/robots.txt` 转发；`includeFiles` 缺 `data/**` |
| 首页 SEO meta | ⬜ `index.html` 缺 description/canonical/OG/JSON-LD；内部链接仍是 `quiz-detail.html?id=` |
| 答题页 SEO | ⬜ `quiz.html` title 写死 |
| 详情页兼容 | ⬜ `quiz-detail.html` 仍 JS 渲染，未做跳转（造成重复内容） |
| 结构化数据 | ⚠️ JSON-LD 中 `acceptedAnswer` 为 null |
| 社交媒体分享 | ⬜ 无默认 `og:image` |

---

## 2. 核心设计决策（与 v1.0 一致，已确认无问题）

### 2.1 URL 结构
- 主 URL：`/quiz/<id>`
- 兼容形式：`/quiz/<id>-<slug>`（slug 解析丢弃，仅美化）
- canonical 指向 `/quiz/<id>`

### 2.2 渲染方式：SSR via Vercel Python 函数
- 复用 `api/index.py`，新增/删除/更新问卷部署即生效
- 不做静态预生成

### 2.3 缓存策略
- `Cache-Control: public, max-age=300, s-maxage=3600, stale-while-revalidate=86400`
- 浏览器 5 分钟，CDN 1 小时，SWR 1 天

### 2.4 安全
- HTML escape 全覆盖
- Path traversal 防护（正则 `^[A-Za-z0-9_]+$`）
- 安全响应头齐备
- CSP 第一版不上（AdSense 兼容）
- Rate limiting + Turnstile 已有

---

## 3. 修订后的实施清单

> 按优先级 P0 → P1 → P2 排列。已完成跳过。

---

### P0-1：修复 `vercel.json`（阻塞部署）

**文件**：[vercel.json](file:///Users/jerrysrick/Desktop/0607/v1.0/vercel.json)

**改动**：

1. **`includeFiles` 追加 `"data/**"`**：修 tags.json 在 Vercel 读不到导致 500 的 bug

2. **`routes` 补充 SEO 路由**，顺序至关重要：

```json
"routes": [
    { "src": "/api/(.*)",     "dest": "/api/index.py" },
    { "src": "/quiz/(.+)",    "dest": "/api/index.py" },
    { "src": "/sitemap.xml",  "dest": "/api/index.py" },
    { "src": "/robots.txt",   "dest": "/api/index.py" },
    { "src": "/(.*)",         "dest": "/$1" }
]
```

**理由**：当前 catch-all 会吞掉 `/quiz/`, `/sitemap.xml`, `/robots.txt`，导致 SSR 不工作。

---

### P0-2：首页 `index.html` SEO 改造

**文件**：[index.html](file:///Users/jerrysrick/Desktop/0607/v1.0/index.html)

**改动**：

1. `<head>` 内添加 meta 标签：

```html
<meta name="description" content="Free personality quizzes, MBTI tests, 'Which X are you' games, and pop-culture character matches. Take a quiz, share with friends, and discover yourself.">
<link rel="canonical" href="https://quizfig.com/">
<meta property="og:type" content="website">
<meta property="og:title" content="QuizFig - Personality Tests">
<meta property="og:description" content="Free personality quizzes...">
<meta property="og:url" content="https://quizfig.com/">
<meta property="og:site_name" content="QuizFig">
<meta property="og:image" content="https://quizfig.com/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="QuizFig - Personality Tests">
<meta name="twitter:description" content="Free personality quizzes...">
<meta name="twitter:image" content="https://quizfig.com/og-default.png">
```

2. 在 `<head>` 末尾添加 JSON-LD：

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "QuizFig",
  "url": "https://quizfig.com/",
  "description": "...",
  "potentialAction": {
    "@type": "SearchAction",
    "target": "https://quizfig.com/?search={search_term_string}",
    "query-input": "required name=search_term_string"
  }
}
</script>
```

3. `goQuiz()` 函数修改：

```
// 改前：
window.location.href = 'quiz-detail.html?id=' + id;
// 改后：
window.location.href = '/quiz/' + id;
```

4. `goRandom()` 函数同样改为 `/quiz/` 路由形式

**理由**：首页是搜索引擎入口，需要完整 meta；内部链接改为 `/quiz/` 让 Google 通过爬行直接发现 SSR 页面。

---

### P0-3：`quiz-detail.html` 改为重定向（修复重复内容）

**文件**：[quiz-detail.html](file:///Users/jerrysrick/Desktop/0607/v1.0/quiz-detail.html)

**策略**：不要 JS 渲染详情，改为两阶段处理 ——

1. **服务端路径**：既然 SSR 已经有了 `/quiz/<id>` 返回完整 HTML，`quiz-detail.html` 作为纯静态文件永远不应该再渲染详情。保留它仅作为"老 URL 兜底入口"。

2. **改动**：
   - 删除所有 quiz 详情渲染 JS（`loadQuizData()`, `renderQuizDetail()`, `getQuizEmojis()`, `startQuiz()` 等）
   - 替换为简洁的重定向逻辑：

```javascript
// 从 URL ?id=xxx 提取 quiz_id，重定向到 /quiz/xxx
const urlParams = new URLSearchParams(window.location.search);
const quizId = urlParams.get('id');
if (quizId) {
    window.location.replace('/quiz/' + quizId);
} else {
    window.location.replace('/');
}
```

3. **额外防御**：在 `<head>` 中保留兜底：

```html
<meta name="robots" content="noindex, follow">
<link rel="canonical" href="https://quizfig.com/">
```

**理由**：
- `window.location.replace()` 在浏览器中立即跳转，不留 history entry
- Googlebot 执行 JS 后会跟随，不索引 `quiz-detail.html`
- `noindex` + `canonical` 作为防御，防止搜索引擎不执行 JS 时索引
- 这是**真正的防重复内容措施**，比方案 1.0 的"fetch 后再渲染"安全得多

---

### P1-1：`quiz.html` 答题页动态 meta（轻量）

**文件**：[quiz.html](file:///Users/jerrysrick/Desktop/0607/v1.0/quiz.html)

**改动**：在 JS 获取 quiz 数据后，注入以下 DOM 元素：

```javascript
// 从 quiz 数据中设置 title 和 meta
document.title = quizData.title + ' | QuizFig';

// 注入 canonical
let link = document.querySelector('link[rel="canonical"]');
if (!link) {
    link = document.createElement('link');
    link.rel = 'canonical';
    document.head.appendChild(link);
}
link.href = 'https://quizfig.com/quiz/' + quizId;

// 注入 OG
function setMeta(property, content) {
    let el = document.querySelector(`meta[property="${property}"]`);
    if (!el) {
        el = document.createElement('meta');
        el.setAttribute('property', property);
        document.head.appendChild(el);
    }
    el.setAttribute('content', content);
}
setMeta('og:title', quizData.title + ' | QuizFig');
setMeta('og:description', quizData.description || '');
setMeta('og:url', 'https://quizfig.com/quiz/' + quizId);
```

**理由**：当用户分享答题页链接时，社交卡片能正确展示。SEO 价值虽低，但社交分享体验值得花这几行代码。如果觉得价值不够，可砍掉此任务。

---

### P1-2：添加默认 `og:image`（社交分享卡片）

**文件**：[api/index.py](file:///Users/jerrysrick/Desktop/0607/v1.0/api/index.py)

**改动**：在 `build_quiz_html()` 的 `<head>` 中添加：

```html
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
```

同时在 `index.html` 中也添加相同的 og:image meta。

**要求**：需要设计师制作一张 `1200x630` 的默认 OG 图片放到项目根目录。

**理由**：没有 `og:image` 时，Twitter Card 会降级为无图，社交媒体分享体验差。一张默认图零成本解决。

---

### P2-1：Sitemap `lastmod` 使用文件真实修改时间

**文件**：[api/index.py](file:///Users/jerrysrick/Desktop/0607/v1.0/api/index.py) 的 `build_sitemap_xml()`

**改动**：

```python
def build_sitemap_xml():
    home_lastmod = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    urls = [
        f"""  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{home_lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>"""
    ]
    for qid in sorted(_quizzes.keys()):
        if qid == 'onequiz':
            continue
        # 用文件 mtime 作为 lastmod
        fpath = os.path.join(BASE_DIR, 'quizzes', f'{qid}.json')
        if os.path.exists(fpath):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc)
            lastmod = mtime.strftime('%Y-%m-%d')
        else:
            lastmod = home_lastmod
        urls.append(
            f"""  <url>
    <loc>{SITE_URL}/quiz/{h(qid)}</loc>
    <lastmod>{lastmod}</lastmod>
    ..."""
        )
```

**理由**：当前所有 URL 的 `lastmod` 都是当前时间，Google 无法区分哪些页面真正有更新。用文件 mtime 提供真实的更新信号。

---

### P2-2：JSON-LD `acceptedAnswer` 改进

**文件**：[api/index.py](file:///Users/jerrysrick/Desktop/0607/v1.0/api/index.py) 的 `build_quiz_html()`

**改动**：将 Schema.org `Quiz` 类型的 `hasPart` 中的 `acceptedAnswer` 改为第一个选项的 text：

```python
"hasPart": [
    {
        "@type": "Question",
        "name": q.get('text', ''),
        "suggestedAnswer": [
            {"@type": "Answer", "text": o.get("text", "")}
            for o in (q.get('options', []) or [])[:4]
        ],
    }
    for q in questions[:12]
],
```

**理由**：`acceptedAnswer: null` 在 Google Rich Results Test 中会报 warning。改为 `suggestedAnswer` 是合法的 Schema.org Quiz 结构，不会报错。

---

## 4. 不做的事（不变）

| 不做 | 原因 |
| --- | --- |
| 不做首页 SSR | 首页主要是浏览，sitemap 已覆盖所有问卷 |
| 不上 CSP | AdSense 需要宽松策略 |
| 不动 API key | 预先存在，单独处理 |
| 不做 OG 图片自动生成（每问卷一张） | 工程量大，先用默认图兜底 |

---

## 5. 验证步骤

```bash
# 1) 本地验证基础 SEO 资源
curl -s http://localhost:8000/robots.txt
curl -s http://localhost:8000/sitemap.xml | grep -c '<loc>'        # ≈ 188
curl -sI http://localhost:8000/quiz/quiz_100 | head -5              # 200 + 安全头
curl -s  http://localhost:8000/quiz/quiz_100 | grep -E 'title|canonical|application/ld' | head -5

# 2) 验证 quiz-detail.html 旧链接重定向
curl -s http://localhost:8000/quiz-detail.html | grep 'noindex'     # 应出现

# 3) 安全
curl -s http://localhost:8000/quiz/..%2F..%2Fetc%2Fpasswd          # 404
curl -s "http://localhost:8000/quiz/<script>alert(1)</script>"     # 404

# 4) 动态反映 quizzes/ 变化
echo '{"title":"TEST","category":"t","tags":["t"],"description":"d","questions":[],"results":[],"emoji":["?"]}' > quizzes/quiz_999.json
curl -s http://localhost:8000/sitemap.xml | grep quiz_999          # 出现
rm quizzes/quiz_999.json
curl -s http://localhost:8000/sitemap.xml | grep quiz_999          # 没了
```

---

## 6. 实施顺序

1. **P0-1**：`vercel.json`（解除阻塞，SEO 路由可工作）
2. **P0-2**：`index.html` meta + 链接改造
3. **P0-3**：`quiz-detail.html` 改为跳转
4. **P1-1**：`quiz.html` 动态 meta
5. **P1-2**：`api/index.py` + `index.html` 加默认 og:image
6. **P2-1**：`api/index.py` sitemap lastmod 改 mtime
7. **P2-2**：`api/index.py` JSON-LD 改进

部署后 Google Search Console 验证域名 → 提交 sitemap → URL Inspection 抽查。
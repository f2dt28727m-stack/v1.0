# -*- coding: utf-8 -*-
"""
Vercel Python serverless entry.
Routes:
  - /api/*                  data API (existing)
  - /quiz/<id>              SEO-friendly SSR HTML for a single quiz
  - /sitemap.xml            dynamic sitemap
  - /robots.txt             robots policy
  - /                       serves index.html (handled by Vercel static)
"""
import json
import random
import hashlib
import html
import os
import re
import threading
import time
import urllib.request
import urllib.parse
from collections import deque
from datetime import datetime, timezone

# ---------- Base dir resolution (works locally + on Vercel) ----------
possible_dirs = [
    os.path.dirname(os.path.abspath(__file__)),
    '/var/task',
    os.getcwd(),
]
BASE_DIR = None
for d in possible_dirs:
    if os.path.exists(os.path.join(d, 'quizzes')):
        BASE_DIR = d
        break
if BASE_DIR is None:
    BASE_DIR = possible_dirs[0]

# ---------- Site config ----------
# SITE_URL can be overridden via env var in Vercel (e.g. https://quizfig.com)
SITE_URL = os.environ.get('SITE_URL', 'https://quizfig.com').rstrip('/')
SITE_NAME = 'QuizFig'
SITE_TAGLINE = 'One More Quiz, Know Yourself Better.'
SITE_DESC = (
    'Free personality quizzes, MBTI tests, "Which X are you" games, and pop-culture '
    'character matches. Take a quiz, share with friends, and discover yourself.'
)

# ---------- Quiz data load (cold start) ----------
_quizzes = {}
_config = {}
try:
    config_path = os.path.join(BASE_DIR, 'config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            _config = json.load(f)

    quizzes_dir = os.path.join(BASE_DIR, 'quizzes')
    if os.path.exists(quizzes_dir):
        for f in os.listdir(quizzes_dir):
            # Only top-level .json (skip staging/ and archive/ directories)
            if not f.endswith('.json'):
                continue
            full_path = os.path.join(quizzes_dir, f)
            if os.path.isdir(full_path):
                continue
            qid = f.replace('.json', '')
            try:
                with open(full_path) as fp:
                    _quizzes[qid] = json.load(fp)
            except Exception as e:
                print(f"Error loading {f}: {e}")
    print(f"Loaded {len(_quizzes)} quizzes from {quizzes_dir}")
except Exception as e:
    print(f"Init error: {e}")


# ---------- Helpers ----------
def h(value):
    """HTML-escape a value for safe injection into HTML."""
    if value is None:
        return ''
    return html.escape(str(value), quote=True)


def slugify(text, max_len=60):
    """Make a URL-friendly slug from a title (lowercase, dash-separated, ascii)."""
    if not text:
        return ''
    s = text.lower()
    # strip non-alphanum
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    s = re.sub(r'-+', '-', s)
    return s[:max_len]


def get_quiz_summary(quiz_id):
    """Lightweight summary used by the API and SSR."""
    q = _quizzes.get(quiz_id)
    if not q:
        return None
    return {
        'quiz_id': quiz_id,
        'title': q.get('title', 'Untitled'),
        'category': q.get('category', 'General'),
        'tags': q.get('tags', []) or [],
        'description': q.get('description', ''),
        'emoji': q.get('emoji', ['❓', '✨', '🎯']),
        'question_count': len(q.get('questions', [])),
        'result_count': len(q.get('results', [])),
    }


def find_related_quizzes(quiz_id, summary, limit=4):
    """Pick up to `limit` related quizzes by tag overlap, excluding self."""
    if not summary or not summary['tags']:
        # fallback: just any other quizzes
        others = [qid for qid in _quizzes.keys() if qid != quiz_id and qid != 'onequiz']
        return [get_quiz_summary(q) for q in others[:limit] if get_quiz_summary(q)]

    target_tags = {t.lower() for t in summary['tags']}
    scored = []
    for qid, q in _quizzes.items():
        if qid == quiz_id or qid == 'onequiz':
            continue
        qt = q.get('tags') or []
        if not qt:
            continue
        overlap = len(target_tags.intersection({t.lower() for t in qt}))
        if overlap > 0:
            scored.append((overlap, qid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = []
    for _, qid in scored[:limit]:
        s = get_quiz_summary(qid)
        if s:
            out.append(s)
    return out


# ---------- Security: rate limit + Turnstile ----------
# Rate-limit state. In-memory only — fine for single instance, NOT shared across
# Vercel serverless instances. For global rate limiting set UPSTASH_REDIS_REST_URL
# + UPSTASH_REDIS_REST_TOKEN and the limiter will switch to Upstash automatically.
_request_log: dict = {}
_rl_lock = threading.Lock()
# Per-endpoint limits: (max_requests, window_seconds)
RATE_LIMITS = {
    'token':     (10, 60),
    'questions': (30, 60),
    'result':    (30, 60),
    'read':      (120, 60),
    'global':    (240, 60),
}
UPSTASH_URL = os.environ.get('UPSTASH_REDIS_REST_URL', '')
UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')


def _get_client_ip(environ):
    """Extract the real client IP from proxy headers."""
    cf = environ.get('HTTP_CF_CONNECTING_IP')
    if cf:
        return cf.strip()
    xff = environ.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    real = environ.get('HTTP_X_REAL_IP')
    if real:
        return real.strip()
    return environ.get('REMOTE_ADDR', 'unknown')


def _upstash_incr(key, window_s):
    """Atomically INCR a key in Upstash Redis with EXPIRE. Returns the new count, or -1 on failure / not configured."""
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return -1
    try:
        # Pipeline INCR + EXPIRE
        body = json.dumps([["INCR", key], ["EXPIRE", key, window_s]])
        req = urllib.request.Request(
            UPSTASH_URL.rstrip('/') + '/pipeline',
            data=body.encode('utf-8'),
            method='POST',
            headers={
                'Authorization': f'Bearer {UPSTASH_TOKEN}',
                'Content-Type': 'application/json',
            },
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        # Upstash pipeline returns list of [value, ...] per command
        return int(data[0]['result']) if data and 'result' in data[0] else -1
    except Exception as e:
        print(f"[upstash] error: {e}")
        return -1


def _check_rate_limit(environ, bucket):
    """Returns (allowed: bool, headers: dict, retry_after: int)."""
    ip = _get_client_ip(environ)
    max_req, window_s = RATE_LIMITS.get(bucket, (60, 60))

    # Try Upstash first (global across instances)
    if UPSTASH_URL and UPSTASH_TOKEN:
        key = f"rl:{bucket}:{ip}"
        count = _upstash_incr(key, window_s)
        if count >= 0:
            allowed = count <= max_req
            retry_after = window_s if not allowed else 0
            return allowed, {
                'X-RateLimit-Limit': str(max_req),
                'X-RateLimit-Remaining': str(max(max_req - count, 0)),
            }, retry_after

    # Fallback: in-memory sliding window (per-instance)
    key = f"{bucket}:{ip}"
    now = time.time()
    with _rl_lock:
        log = _request_log.setdefault(key, deque())
        while log and log[0] < now - window_s:
            log.popleft()
        if len(log) >= max_req:
            retry_after = int(window_s - (now - log[0])) if log else window_s
            return False, {
                'X-RateLimit-Limit': str(max_req),
                'X-RateLimit-Remaining': '0',
            }, retry_after
        log.append(now)
        return True, {
            'X-RateLimit-Limit': str(max_req),
            'X-RateLimit-Remaining': str(max_req - len(log)),
        }, 0


def verify_turnstile(token, remote_ip=None):
    """Verify a Cloudflare Turnstile token.
    Returns True if valid OR if TURNSTILE_SECRET is not configured (so the system
    works out of the box). Returns False only on real verification failure.
    """
    secret = os.environ.get('TURNSTILE_SECRET')
    if not secret:
        return True
    if not token:
        return False
    payload = {'secret': secret, 'response': token}
    if remote_ip:
        payload['remoteip'] = remote_ip
    try:
        body = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data=body,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        ok = bool(result.get('success'))
        if not ok:
            print(f"[turnstile] verify failed: {result}")
        return ok
    except Exception as e:
        # Fail OPEN: don't lock out users if Turnstile API is down.
        # Rate limiting is the backup defense.
        print(f"[turnstile] verify error (fail open): {e}")
        return True


def is_turnstile_configured():
    return bool(os.environ.get('TURNSTILE_SECRET'))


def _enforce_rate_limit(environ, start_response, bucket):
    """Returns (response_body, status, headers) if blocked, else None.
    If None, request is allowed to proceed. Also checks the global bucket."""
    for b in ('global', bucket):
        allowed, rl_headers, retry_after = _check_rate_limit(environ, b)
        if not allowed:
            return (json.dumps({'error': f'Rate limit exceeded ({b})'}), '429 TOO MANY REQUESTS',
                    {**api_headers('no'), **rl_headers, 'Retry-After': str(retry_after)})
    return None


# ---------- Header builders ----------
def base_headers(content_type='text/html; charset=utf-8', cache='short'):
    """Common security + cache headers for HTML responses."""
    cache_map = {
        'short':  'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400',
        'static': 'public, max-age=3600, s-maxage=86400',
        'no':     'no-store',
    }
    return {
        'Content-Type': content_type,
        'Cache-Control': cache_map.get(cache, cache_map['short']),
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    }


def api_headers(cache='short'):
    """Headers for JSON API responses (CORS + cache)."""
    cache_map = {
        'short':  'public, max-age=60, s-maxage=300, stale-while-revalidate=600',
        'static': 'public, max-age=600, s-maxage=3600',
    }
    h_ = {
        'Content-Type': 'application/json',
        'Cache-Control': cache_map.get(cache, cache_map['short']),
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    }
    return h_


# ---------- SSR: Quiz detail page ----------
def build_quiz_html(quiz_id, summary):
    """Render a complete SEO-friendly HTML page for a single quiz."""
    title = summary['title']
    description = summary['description'] or f"Take the {title} quiz on {SITE_NAME}."
    category = summary['category']
    tags = summary['tags']
    emoji_list = summary['emoji'] or ['❓', '✨', '🎯']
    emoji = h(emoji_list[0]) if emoji_list else '❓'
    qcount = summary['question_count']
    rcount = summary['result_count']
    canonical = f"{SITE_URL}/quiz/{h(quiz_id)}"

    full = _quizzes.get(quiz_id, {})
    questions = full.get('questions', []) or []
    results = full.get('results', []) or []

    # 1) Schema.org Quiz JSON-LD
    schema = {
        "@context": "https://schema.org",
        "@type": "Quiz",
        "name": title,
        "description": description,
        "url": canonical,
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "provider": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
        },
        "about": category.replace('_', ' ').title() if category else 'Personality',
        "keywords": ", ".join(tags) if tags else None,
        "hasPart": [
            {
                "@type": "Question",
                "name": q.get('text', ''),
                "acceptedAnswer": None,
            }
            for q in questions[:12]
        ],
    }
    schema = {k: v for k, v in schema.items() if v is not None}
    schema_ld = json.dumps(schema, ensure_ascii=False)

    # 2) Breadcrumb JSON-LD
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": SITE_URL + "/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": category.replace('_', ' ').title() if category else "Quizzes",
                "item": f"{SITE_URL}/?category={h(category)}",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": title,
                "item": canonical,
            },
        ],
    }
    breadcrumb_ld = json.dumps(breadcrumb, ensure_ascii=False)

    # 3) Tags as pills
    tag_pills = ''.join(
        f'<a class="tag" href="/?tag={h(t.lower().replace(" ", "_"))}">#{h(t)}</a>'
        for t in tags
    )

    # 4) Sample questions (first 3, for SEO copy)
    sample_q_html = ''
    for i, q in enumerate(questions[:3], 1):
        opts = q.get('options', []) or []
        opts_li = ''.join(
            f'<li>{h(o.get("text", ""))}</li>' for o in opts
        )
        sample_q_html += (
            f'<li class="sample-q">'
            f'<strong>Q{i}. {h(q.get("text", ""))}</strong>'
            f'<ul class="sample-opts">{opts_li}</ul>'
            f'</li>'
        )

    # 5) Possible results (names only)
    result_names = []
    for r in results:
        nm = r.get('title') or r.get('name') or r.get('mbtiType') or r.get('mbti') or ''
        if nm:
            result_names.append(nm)
    results_html = ''.join(
        f'<li>{h(n)}</li>' for n in result_names
    ) or '<li>Various personality outcomes</li>'

    # 6) Related quizzes
    related = find_related_quizzes(quiz_id, summary, limit=4)
    related_html = ''
    for r in related:
        e = h((r.get('emoji') or ['✨'])[0])
        related_html += (
            f'<li><a href="/quiz/{h(r["quiz_id"])}">'
            f'<span class="rel-emoji">{e}</span>'
            f'<span class="rel-title">{h(r["title"])}</span>'
            f'</a></li>'
        )
    if not related_html:
        related_html = '<li class="rel-empty">More quizzes coming soon.</li>'

    # 7) Build full HTML
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{h(title)} | {SITE_NAME}</title>
<meta name="description" content="{h(description)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#0f0f0f">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{h(title)} | {SITE_NAME}">
<meta property="og:description" content="{h(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{h(title)} | {SITE_NAME}">
<meta name="twitter:description" content="{h(description)}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ctext y='52' font-size='52'%3E%F0%9F%A7%A9%3C/text%3E%3C/svg%3E">
<script type="application/ld+json">{schema_ld}</script>
<script type="application/ld+json">{breadcrumb_ld}</script>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-EQQ75D1GWK"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-EQQ75D1GWK');
</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;color:#fff;line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:#A259FF;text-decoration:none}}
a:hover{{text-decoration:underline}}
.wrap{{max-width:720px;margin:0 auto;padding:0 20px 40px}}
.site-header{{position:sticky;top:0;background:rgba(15,15,15,.92);backdrop-filter:blur(8px);border-bottom:1px solid #222;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;z-index:10}}
.site-header .logo{{font-size:18px;font-weight:800;background:linear-gradient(90deg,#A259FF,#FF7AB6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.site-header a.home{{color:#888;font-size:13px}}
.breadcrumb{{font-size:12px;color:#666;padding:14px 0 4px}}
.breadcrumb a{{color:#888}}
.breadcrumb span{{color:#aaa}}
.hero{{padding:18px 0 8px}}
.hero h1{{font-size:28px;line-height:1.25;font-weight:800;margin-bottom:12px}}
.hero .emoji{{font-size:42px;margin-bottom:8px;display:block}}
.tags{{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 16px}}
.tag{{font-size:11px;color:#A259FF;background:rgba(162,89,255,.12);padding:4px 10px;border-radius:14px;font-weight:500}}
.lede{{color:#bbb;font-size:15px;margin:8px 0 18px}}
.meta-row{{display:flex;flex-wrap:wrap;gap:8px;color:#888;font-size:12px;margin:6px 0 18px}}
.meta-row span{{background:#1a1a1a;border:1px solid #222;padding:4px 10px;border-radius:12px}}
.cta{{display:block;text-align:center;background:linear-gradient(90deg,#A259FF,#FF7AB6);color:#000;font-weight:700;border-radius:30px;padding:16px 24px;font-size:16px;margin:8px 0 28px}}
.cta:hover{{text-decoration:none;filter:brightness(1.05)}}
section{{background:#141414;border:1px solid #222;border-radius:16px;padding:20px;margin:18px 0}}
section h2{{font-size:18px;margin-bottom:12px;font-weight:700}}
section p,section li{{color:#bbb;font-size:14px;line-height:1.7}}
.sample-q{{margin:0 0 14px;padding:0 0 0 6px;border-left:2px solid #333;padding-left:12px;list-style:none}}
.sample-q strong{{display:block;color:#fff;margin-bottom:6px;font-weight:600}}
.sample-opts{{list-style:none;padding:0}}
.sample-opts li{{padding:5px 0;color:#aaa;font-size:13px;border-top:1px solid #1f1f1f}}
.sample-opts li:first-child{{border-top:0}}
.results-list{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;padding:0;list-style:none}}
.results-list li{{background:#1a1a1a;border:1px solid #222;border-radius:10px;padding:10px 12px;font-size:13px;color:#ddd}}
.related{{list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.related li a{{display:flex;align-items:center;gap:8px;background:#1a1a1a;border:1px solid #222;border-radius:10px;padding:10px 12px;color:#fff;font-size:13px;line-height:1.3}}
.related li a:hover{{border-color:#A259FF;text-decoration:none}}
.rel-emoji{{font-size:18px;flex-shrink:0}}
.rel-title{{overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.rel-empty{{color:#666;font-size:13px;grid-column:1/-1;text-align:center;padding:12px}}
footer{{text-align:center;color:#555;font-size:12px;padding:20px 0;border-top:1px solid #1a1a1a;margin-top:30px}}
footer a{{color:#888;margin:0 6px}}
@media (max-width:480px){{
.hero h1{{font-size:22px}}
.hero .emoji{{font-size:36px}}
.related{{grid-template-columns:1fr}}
section{{padding:16px}}
}}
</style>
</head>
<body>
<header class="site-header">
  <a href="/" class="logo">{h(SITE_NAME)}</a>
  <a href="/" class="home">All Quizzes</a>
</header>
<div class="wrap">
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <a href="/">Home</a> &rsaquo;
    <a href="/?category={h(category)}">{h(category.replace('_', ' ').title())}</a> &rsaquo;
    <span>{h(title)}</span>
  </nav>
  <div class="hero">
    <span class="emoji">{emoji}</span>
    <h1>{h(title)}</h1>
    <div class="tags">{tag_pills}</div>
    <p class="lede">{h(description)}</p>
    <div class="meta-row">
      <span>{qcount} Questions</span>
      <span>{rcount} Possible Results</span>
      <span>Free &middot; No Sign-up</span>
      <span>~3 min</span>
    </div>
    <a class="cta" href="/quiz.html?id={h(quiz_id)}" rel="nofollow">Start Now &rsaquo;</a>
  </div>

  <section>
    <h2>About This Quiz</h2>
    <p>{h(description)}</p>
    <p style="margin-top:10px">This quiz uses MBTI-inspired traits to map your answers to a personality result. It's designed to be quick, fun, and shareable &mdash; no login required, and your answers stay in your browser.</p>
  </section>

  <section>
    <h2>Sample Questions</h2>
    <ol style="padding-left:18px">{sample_q_html}</ol>
  </section>

  <section>
    <h2>Possible Results</h2>
    <ul class="results-list">{results_html}</ul>
  </section>

  <section>
    <h2>Related Quizzes</h2>
    <ul class="related">{related_html}</ul>
  </section>
</div>
<footer>
  &copy; 2026 {h(SITE_NAME)} &middot;
  <a href="/">Home</a>&middot;
  <a href="/sitemap.xml">Sitemap</a>
</footer>
</body>
</html>"""
    return html_doc


# ---------- Sitemap & robots ----------
def build_sitemap_xml():
    """Generate sitemap.xml with home + every quiz URL."""
    lastmod = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    urls = [
        f"""  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>"""
    ]
    # Iterate deterministically by quiz id
    for qid in sorted(_quizzes.keys()):
        if qid == 'onequiz':
            continue
        urls.append(
            f"""  <url>
    <loc>{SITE_URL}/quiz/{h(qid)}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>"""
        )
    body = '<?xml version="1.0" encoding="UTF-8"?>\n'
    body += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    body += '\n'.join(urls)
    body += '\n</urlset>\n'
    return body


def build_robots_txt():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )


# ---------- Response helper ----------
def respond(start_response, status, headers, body):
    start_response(status, list(headers.items()))
    if isinstance(body, str):
        body = body.encode('utf-8')
    return [body]


# ---------- WSGI app ----------
def app(environ, start_response):
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET')

    # Read body
    try:
        body_size = int(environ.get('CONTENT_LENGTH', 0))
        body = environ['wsgi.input'].read(body_size).decode('utf-8') if body_size > 0 else ''
    except Exception:
        body = ''

    # CORS preflight (only for /api/*)
    if method == 'OPTIONS' and path.startswith('/api/'):
        return respond(start_response, '200 OK', api_headers('short'), '')

    # ---------- SEO: /robots.txt ----------
    if path == '/robots.txt':
        return respond(
            start_response, '200 OK',
            {**base_headers('text/plain; charset=utf-8', 'static'),
             'Content-Type': 'text/plain; charset=utf-8'},
            build_robots_txt(),
        )

    # ---------- SEO: /sitemap.xml ----------
    if path == '/sitemap.xml':
        return respond(
            start_response, '200 OK',
            {**base_headers('application/xml; charset=utf-8', 'static'),
             'Content-Type': 'application/xml; charset=utf-8'},
            build_sitemap_xml(),
        )

    # ---------- SEO: /quiz/<id> ----------
    if path.startswith('/quiz/') and method == 'GET':
        # tolerate trailing slash
        rest = path[len('/quiz/'):].rstrip('/')
        if not rest:
            return respond(start_response, '404 NOT FOUND',
                           base_headers('text/plain', 'no'),
                           'Quiz id required')
        # Allow optional slug suffix: /quiz/quiz_100-some-slug
        quiz_id = rest.split('-', 1)[0] if '-' in rest else rest
        # disallow path traversal / weird ids
        if not re.match(r'^[A-Za-z0-9_]+$', quiz_id):
            return respond(start_response, '404 NOT FOUND',
                           base_headers('text/plain', 'no'),
                           'Invalid quiz id')
        summary = get_quiz_summary(quiz_id)
        if not summary:
            return respond(start_response, '404 NOT FOUND',
                           base_headers('text/html; charset=utf-8', 'no'),
                           f'<!doctype html><meta charset="utf-8"><title>Not found</title>'
                           f'<h1>Quiz not found</h1><p><a href="/">Back to home</a></p>')
        return respond(
            start_response, '200 OK',
            base_headers('text/html; charset=utf-8', 'short'),
            build_quiz_html(quiz_id, summary),
        )

    # ---------- /api/token (POST, with optional Turnstile) ----------
    if path == '/api/token':
        if method != 'POST':
            return respond(start_response, '405 METHOD NOT ALLOWED', api_headers('no'),
                           json.dumps({'error': 'Use POST'}))

        blocked = _enforce_rate_limit(environ, start_response, 'token')
        if blocked is not None:
            return respond(start_response, blocked[1], blocked[2], blocked[0])

        # Turnstile verification (only if TURNSTILE_SECRET is configured)
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}
        turnstile_token = data.get('turnstile_token', '')

        if not verify_turnstile(turnstile_token, remote_ip=_get_client_ip(environ)):
            return respond(start_response, '401 UNAUTHORIZED', api_headers('no'),
                           json.dumps({'error': 'Turnstile verification failed'}))

        token = hashlib.sha256(str(random.random()).encode()).hexdigest()
        return respond(start_response, '200 OK', api_headers('no'),
                       json.dumps({'token': token}))

    # ---------- /api/quizzes (list) ----------
    if path == '/api/quizzes' or path == '/api/quizzes/':
        blocked = _enforce_rate_limit(environ, start_response, 'read')
        if blocked is not None:
            return respond(start_response, blocked[1], blocked[2], blocked[0])
        lst = [get_quiz_summary(qid) for qid in sorted(_quizzes.keys())
               if qid != 'onequiz' and get_quiz_summary(qid)]
        # Slim down payload
        slim = [{
            'quiz_id': s['quiz_id'],
            'title': s['title'],
            'category': s['category'],
            'tags': s['tags'],
            'emoji': s['emoji'],
            'likes': _quizzes[s['quiz_id']].get('likes', 0),
        } for s in lst]
        return respond(start_response, '200 OK', api_headers('short'),
                       json.dumps({'quizzes': slim}, ensure_ascii=False))

    # ---------- /api/quizzes/<id> ----------
    if path.startswith('/api/quizzes/') and method == 'GET':
        blocked = _enforce_rate_limit(environ, start_response, 'read')
        if blocked is not None:
            return respond(start_response, blocked[1], blocked[2], blocked[0])
        quiz_id = path.split('/api/quizzes/')[1]
        if not re.match(r'^[A-Za-z0-9_]+$', quiz_id):
            return respond(start_response, '400 BAD REQUEST', api_headers('no'),
                           json.dumps({'error': 'Invalid id'}))
        summary = get_quiz_summary(quiz_id)
        if not summary:
            return respond(start_response, '404 NOT FOUND', api_headers('no'),
                           json.dumps({'error': 'Quiz not found'}))
        return respond(start_response, '200 OK', api_headers('short'),
                       json.dumps(summary, ensure_ascii=False))

    # ---------- /api/tags ----------
    if path == '/api/tags' and method == 'GET':
        blocked = _enforce_rate_limit(environ, start_response, 'read')
        if blocked is not None:
            return respond(start_response, blocked[1], blocked[2], blocked[0])
        tags_file = os.path.join(BASE_DIR, 'data', 'tags.json')
        if os.path.exists(tags_file):
            with open(tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)
        else:
            tags_data = {}
        return respond(start_response, '200 OK', api_headers('static'),
                       json.dumps(tags_data, ensure_ascii=False))

    # ---------- /api/questions (POST) ----------
    if path == '/api/questions' and method == 'POST':
        blocked = _enforce_rate_limit(environ, start_response, 'questions')
        if blocked is not None:
            return respond(start_response, blocked[1], blocked[2], blocked[0])
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}
        token = data.get('token', '')
        if len(token) != 64:
            return respond(start_response, '401 UNAUTHORIZED', api_headers('no'),
                           json.dumps({'error': 'Unauthorized'}))
        quiz_id = data.get('quiz_id', 'quiz_1')
        quiz = _quizzes.get(quiz_id)
        if not quiz:
            return respond(start_response, '404 NOT FOUND', api_headers('no'),
                           json.dumps({'error': 'Quiz not found',
                                       'available': list(_quizzes.keys())}))
        questions = quiz.get('questions', [])
        for i, q in enumerate(questions):
            q['temp_id'] = f'q{i+1}'
        return respond(start_response, '200 OK', api_headers('no'),
                       json.dumps({'questions': questions,
                                   'quiz_id': quiz_id,
                                   'title': quiz.get('title', 'Quiz')},
                                  ensure_ascii=False))

    # ---------- /api/result (POST) ----------
    if path == '/api/result' and method == 'POST':
        blocked = _enforce_rate_limit(environ, start_response, 'result')
        if blocked is not None:
            return respond(start_response, blocked[1], blocked[2], blocked[0])
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}
        token = data.get('token', '')
        if len(token) != 64:
            return respond(start_response, '401 UNAUTHORIZED', api_headers('no'),
                           json.dumps({'error': 'Unauthorized'}))
        answers = data.get('answers', {})
        quiz_id = data.get('quiz_id', 'quiz_1')
        quiz = _quizzes.get(quiz_id)
        if not quiz:
            return respond(start_response, '404 NOT FOUND', api_headers('no'),
                           json.dumps({'error': 'Quiz not found'}))

        scores = {'E': 0, 'I': 0, 'S': 0, 'N': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}
        for q_id, opt_idx in answers.items():
            for q in quiz.get('questions', []):
                if str(q.get('qId')) == q_id or q.get('temp_id') == q_id:
                    opts = q.get('options', [])
                    try:
                        if 0 <= int(opt_idx) < len(opts):
                            score = opts[int(opt_idx)].get('score', '')
                            if isinstance(score, str) and score in scores:
                                scores[score] += 1
                            elif isinstance(score, dict):
                                for k, v in score.items():
                                    if k in scores:
                                        scores[k] += v
                    except (ValueError, TypeError):
                        pass
                    break

        mbti = ''
        mbti += 'E' if scores['E'] >= scores['I'] else 'I'
        mbti += 'S' if scores['S'] >= scores['N'] else 'N'
        mbti += 'T' if scores['T'] >= scores['F'] else 'F'
        mbti += 'J' if scores['J'] >= scores['P'] else 'P'

        result = None
        for r in quiz.get('results', []):
            if r.get('mbtiType') == mbti or r.get('mbti') == mbti:
                result = r
                break
        if not result:
            result = quiz.get('results', [{}])[0]

        total_ei = scores['E'] + scores['I'] or 1
        total_sn = scores['S'] + scores['N'] or 1
        total_tf = scores['T'] + scores['F'] or 1
        total_jp = scores['J'] + scores['P'] or 1

        return respond(start_response, '200 OK', api_headers('no'),
                       json.dumps({
                           'mbti_type': mbti,
                           'result': result,
                           'percentages': {
                               'extrovert_introvert': int(scores['E'] * 100 / total_ei),
                               'sensing_intuition': int(scores['S'] * 100 / total_sn),
                               'thinking_feeling': int(scores['T'] * 100 / total_tf),
                               'judging_perceiving': int(scores['J'] * 100 / total_jp),
                           }
                       }, ensure_ascii=False))

    # ---------- 404 ----------
    return respond(start_response, '404 NOT FOUND', api_headers('no'),
                   json.dumps({'error': 'Not found', 'path': path}))

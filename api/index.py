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
import hmac
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
from datetime import datetime, timezone, timedelta
from io import StringIO

# ---------- Base dir resolution (works locally + on Vercel) ----------
_api_dir = os.path.dirname(os.path.abspath(__file__))
possible_dirs = [
    _api_dir,                                    # /project/api/
    os.path.dirname(_api_dir),                   # /project/
    os.path.dirname(os.path.dirname(_api_dir)),  # /  (defensive)
    '/var/task',                                 # Vercel default
    os.getcwd(),                                 # last resort
]
BASE_DIR = None
for d in possible_dirs:
    if d and os.path.exists(os.path.join(d, 'quizzes')):
        BASE_DIR = d
        break
if BASE_DIR is None:
    BASE_DIR = _api_dir  # fall back to api/; downstream code will log 0 quizzes

# ---------- Site config ----------
# SITE_URL can be overridden via env var in Vercel (e.g. https://quizfig.com)
SITE_URL = os.environ.get('SITE_URL', 'https://quizfig.com').rstrip('/')
SITE_NAME = 'QuizFig'
SITE_TAGLINE = 'One More Quiz, Know Yourself Better.'
SITE_DESC = (
    'Free personality quizzes, MBTI tests, "Which X are you" games, and pop-culture '
    'character matches. Take a quiz, share with friends, and discover yourself.'
)

# ---------- GEO: Entity canonical references ----------
# Curated map from quiz subject (the first tag, lowercased) to canonical
# Wikipedia + Wikidata URLs. GEO needs `sameAs` on Person/MusicGroup schema so
# AI engines can resolve "QuizFig's Taylor Swift" to the canonical entity.
# Only well-known subjects are included — for unknown ones we omit sameAs
# rather than hallucinate a URL.
SUBJECT_SAMEAS = {
    'taylor swift': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Taylor_Swift',
        'wikidata':  'https://www.wikidata.org/wiki/Q26876',
        'kind':      'Person',
    },
    'sza': {
        'wikipedia': 'https://en.wikipedia.org/wiki/SZA',
        'wikidata':  'https://www.wikidata.org/wiki/Q15273932',
        'kind':      'Person',
    },
    'olivia rodrigo': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Olivia_Rodrigo',
        'wikidata':  'https://www.wikidata.org/wiki/Q96372810',
        'kind':      'Person',
    },
    'sabrina carpenter': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Sabrina_Carpenter',
        'wikidata':  'https://www.wikidata.org/wiki/Q22128117',
        'kind':      'Person',
    },
    'ice spice': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Ice_Spice',
        'wikidata':  'https://www.wikidata.org/wiki/Q110272164',
        'kind':      'Person',
    },
    'dua lipa': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Dua_Lipa',
        'wikidata':  'https://www.wikidata.org/wiki/Q28109438',
        'kind':      'Person',
    },
    'billie eilish': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Billie_Eilish',
        'wikidata':  'https://www.wikidata.org/wiki/Q56737814',
        'kind':      'Person',
    },
    'lana del rey': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Lana_Del_Rey',
        'wikidata':  'https://www.wikidata.org/wiki/Q18444288',
        'kind':      'Person',
    },
    'chappell roan': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Chappell_Roan',
        'wikidata':  'https://www.wikidata.org/wiki/Q106524586',
        'kind':      'Person',
    },
    'blackpink': {
        'wikipedia': 'https://en.wikipedia.org/wiki/Blackpink',
        'wikidata':  'https://www.wikidata.org/wiki/Q20909934',
        'kind':      'MusicGroup',
    },
    'newjeans': {
        'wikipedia': 'https://en.wikipedia.org/wiki/NewJeans',
        'wikidata':  'https://www.wikidata.org/wiki/Q111160994',
        'kind':      'MusicGroup',
    },
    'bts': {
        'wikipedia': 'https://en.wikipedia.org/wiki/BTS',
        'wikidata':  'https://www.wikidata.org/wiki/Q20881830',
        'kind':      'MusicGroup',
    },
}

# ---------- GEO: 16 MBTI type definitions ----------
# Used by the /mbti-types/ hub page and DefinedTerm JSON-LD on quiz pages.
MBTI_TYPES = [
    {'name': 'INTJ', 'title': 'The Architect',      'group': 'Analysts',   'description': 'Strategic, independent, and driven by long-term vision. INTJs value competence and prefer systems over chaos.'},
    {'name': 'INTP', 'title': 'The Logician',       'group': 'Analysts',   'description': 'Curious, theoretical, and idea-driven. INTPs love exploring abstract concepts and building mental models.'},
    {'name': 'ENTJ', 'title': 'The Commander',      'group': 'Analysts',   'description': 'Decisive, ambitious, and natural leaders. ENTJs turn vision into plan and plan into action.'},
    {'name': 'ENTP', 'title': 'The Debater',        'group': 'Analysts',   'description': 'Inventive, outspoken, and quick-witted. ENTPs love debate for its own sake and thrive on new ideas.'},
    {'name': 'INFJ', 'title': 'The Advocate',       'group': 'Diplomats',  'description': 'Insightful, principled, and quietly intense. INFJs are guided by deep values and a strong sense of purpose.'},
    {'name': 'INFP', 'title': 'The Mediator',       'group': 'Diplomats',  'description': 'Imaginative, empathetic, and value-driven. INFPs live in their inner world of feelings and ideals.'},
    {'name': 'ENFJ', 'title': 'The Protagonist',    'group': 'Diplomats',  'description': 'Charismatic, warm, and natural mentors. ENFJs lead with empathy and inspire others to grow.'},
    {'name': 'ENFP', 'title': 'The Campaigner',     'group': 'Diplomats',  'description': 'Enthusiastic, creative, and socially intuitive. ENFPs see possibilities everywhere and lift the energy of any room.'},
    {'name': 'ISTJ', 'title': 'The Logistician',    'group': 'Sentinels',  'description': 'Reliable, methodical, and dutiful. ISTJs honor commitments and prefer proven methods over experiments.'},
    {'name': 'ISFJ', 'title': 'The Defender',       'group': 'Sentinels',  'description': 'Warm, attentive, and quietly loyal. ISFJs care for people in practical, often unnoticed ways.'},
    {'name': 'ESTJ', 'title': 'The Executive',      'group': 'Sentinels',  'description': 'Organized, direct, and grounded. ESTJs bring order and accountability to groups and projects.'},
    {'name': 'ESFJ', 'title': 'The Consul',         'group': 'Sentinels',  'description': 'Sociable, conscientious, and community-minded. ESFJs hold groups together through care and coordination.'},
    {'name': 'ISTP', 'title': 'The Virtuoso',       'group': 'Explorers',  'description': 'Cool-headed, observant, and hands-on. ISTPs learn by doing and excel at troubleshooting under pressure.'},
    {'name': 'ISFP', 'title': 'The Adventurer',     'group': 'Explorers',  'description': 'Gentle, aesthetic, and present. ISFPs live in the moment and express themselves through action and art.'},
    {'name': 'ESTP', 'title': 'The Entrepreneur',   'group': 'Explorers',  'description': 'Energetic, perceptive, and action-oriented. ESTPs read rooms fast and move first.'},
    {'name': 'ESFP', 'title': 'The Entertainer',    'group': 'Explorers',  'description': 'Spontaneous, fun-loving, and warm. ESFPs make the moment brighter and pull others into it.'},
]
MBTI_TYPE_MAP = {t['name']: t for t in MBTI_TYPES}

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
    'questions': (60, 60),
    'result':    (60, 60),
    'read':      (180, 60),
    'global':    (300, 60),
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


# ---------- Completion counter (T+1 reporting) ----------
# 每天一个 hash: complete:YYYY-MM-DD -> { quiz_id: count }
# 100 天 TTL，hash 内字段在第一次写入后由 HINCRBY 自动维护。
# 这是 T+1 自建计数的数据层：写得轻、读得快、零额外依赖。
COMPLETION_TTL_SECONDS = 86400 * 100  # 100 天


def _record_completion(quiz_id):
    """Record one quiz completion for today (UTC). Fire-and-forget:
    never raises and never affects the /api/result response. Returns True
    if Upstash was hit, False if skipped (not configured / errored)."""
    if not UPSTASH_URL or not UPSTASH_TOKEN or not quiz_id:
        return False
    try:
        date_key = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        hash_key = f"complete:{date_key}"
        # HINCRBY field quiz_id 1 + EXPIRE hash_key 100d. Pipeline = 1 round trip.
        body = json.dumps([
            ["HINCRBY", hash_key, quiz_id, 1],
            ["EXPIRE", hash_key, COMPLETION_TTL_SECONDS],
        ])
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
            resp.read()
        return True
    except Exception as e:
        print(f"[upstash] completion counter error: {e}")
        return False


def _upstash_hgetall(key):
    """HGETALL via Upstash pipeline. Returns dict {field: int_count}, or {} on
    miss / error / not configured. Empty hash returns [] from Upstash."""
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return {}
    try:
        body = json.dumps([["HGETALL", key]])
        req = urllib.request.Request(
            UPSTASH_URL.rstrip('/') + '/pipeline',
            data=body.encode('utf-8'),
            method='POST',
            headers={
                'Authorization': f'Bearer {UPSTASH_TOKEN}',
                'Content-Type': 'application/json',
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if not data or 'result' not in data[0]:
            return {}
        flat = data[0]['result'] or []
        out = {}
        # HGETALL returns [field, value, field, value, ...]
        for i in range(0, len(flat) - 1, 2):
            try:
                out[flat[i]] = int(flat[i + 1])
            except (ValueError, TypeError):
                pass
        return out
    except Exception as e:
        print(f"[upstash] hgetall error: {e}")
        return {}


def _csv_escape(value):
    """Escape a value for CSV per RFC 4180. Wraps in quotes if it contains
    comma/quote/newline; doubles internal quotes."""
    s = '' if value is None else str(value)
    if any(c in s for c in (',', '"', '\n', '\r')):
        return '"' + s.replace('"', '""') + '"'
    return s


def _build_admin_daily_csv(date_str):
    """Build a CSV body for `date_str` (YYYY-MM-DD, must be < today UTC).
    Includes all known quizzes (0 if no completions), sorted by count desc."""
    counts = _upstash_hgetall(f"complete:{date_str}")
    rows = []
    for qid in sorted(_quizzes.keys()):
        if qid == 'onequiz':
            continue
        title = _quizzes[qid].get('title', 'Untitled')
        rows.append((qid, title, counts.get(qid, 0)))
    rows.sort(key=lambda r: (-r[2], r[0]))

    buf = StringIO()
    buf.write('date,quiz_id,quiz_title,count\n')
    for qid, title, cnt in rows:
        buf.write(f'{date_str},{_csv_escape(qid)},{_csv_escape(title)},{cnt}\n')
    return buf.getvalue()


def _admin_daily_csv(environ, start_response):
    """GET /api/admin/daily.csv?date=YYYY-MM-DD&key=XXX
    T+1 daily completion report. `date` defaults to yesterday UTC.
    Rejects today/future dates so reports stay reproducible.
    Auth: ADMIN_KEY env var compared in constant time against ?key=.
    """
    qs = urllib.parse.parse_qs(environ.get('QUERY_STRING', ''))
    provided_key = (qs.get('key') or [''])[0]
    expected_key = os.environ.get('ADMIN_KEY', '')

    if not expected_key:
        return respond(start_response, '503 SERVICE UNAVAILABLE', api_headers('no'),
                       json.dumps({'error': 'ADMIN_KEY env var is not set on server'}))
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        return respond(start_response, '401 UNAUTHORIZED', api_headers('no'),
                       json.dumps({'error': 'Invalid or missing key'}))

    # Resolve target date (default = yesterday UTC)
    date_str = (qs.get('date') or [''])[0].strip()
    if not date_str:
        date_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return respond(start_response, '400 BAD REQUEST', api_headers('no'),
                       json.dumps({'error': 'Invalid date format, use YYYY-MM-DD'}))

    # T+1 enforcement: requested date must be strictly before today (UTC)
    today_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if date_str >= today_utc:
        return respond(start_response, '400 BAD REQUEST', api_headers('no'),
                       json.dumps({'error': f'T+1 only: requested date must be before today UTC ({today_utc})'}))

    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return respond(start_response, '503 SERVICE UNAVAILABLE', api_headers('no'),
                       json.dumps({'error': 'Upstash not configured; no completion data available'}))

    try:
        csv_body = _build_admin_daily_csv(date_str)
    except Exception as e:
        return respond(start_response, '500 INTERNAL SERVER ERROR', api_headers('no'),
                       json.dumps({'error': f'Build failed: {e}'}))

    headers = api_headers('no')
    headers['Content-Type'] = 'text/csv; charset=utf-8'
    headers['Content-Disposition'] = f'attachment; filename="quizfig-completions-{date_str}.csv"'
    return respond(start_response, '200 OK', headers, csv_body)


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
def build_subject_section_html(full_quiz, tags):
    """Render the inner H2 section that surfaces the celebrity/group's
    widely-discussed MBTI typing. Returns '' when subject_meta is absent.

    Hedge language: "widely typed as", "fans and personality communities",
    "with some discussions also citing". Uses 'or' between alternate typings.
    """
    meta = full_quiz.get('subject_meta') or {}
    subject = (tags or ['Unknown'])[0]
    if not subject:
        return ''

    # Group (e.g. BLACKPINK, NewJeans): list all self-disclosed members
    if meta.get('is_group'):
        members = meta.get('members') or {}
        if not members:
            return ''
        member_html = ', '.join(
            f"{h(name)} (<strong>{h(typing)}</strong>)"
            for name, typing in members.items()
        )
        return (
            f"  <section>\n"
            f"    <h2>{h(subject)} Members&rsquo; MBTI Types</h2>\n"
            f"    <p>Each {h(subject)} member has her own widely-discussed MBTI type in fan communities: {member_html}. This free quiz matches you to the member whose personality type most closely mirrors yours.</p>\n"
            f"  </section>"
        )

    # Single celebrity
    primary = (meta.get('typing_primary') or '').strip()
    alternate = (meta.get('typing_alternate') or '').strip()
    pronoun = meta.get('pronoun') or 'they'
    if not primary:
        return ''

    # Build "with some discussions also citing <strong>X</strong> or <strong>Y</strong>"
    alt_html = ''
    if alternate:
        parts = [f"<strong>{h(p.strip())}</strong>" for p in alternate.split(' or ')]
        alt_html = ', with some discussions also citing ' + ' or '.join(parts)

    pronoun_cap = {'she': 'She', 'he': 'He', 'they': 'They'}.get(pronoun, 'They')

    return (
        f"  <section>\n"
        f"    <h2>{h(subject)}&rsquo;s MBTI: What Type Is {h(pronoun_cap)}?</h2>\n"
        f"    <p>{h(subject)} is widely typed as <strong>{h(primary)}</strong> by fans and personality communities{alt_html}. This free quiz helps you discover your own type and see which one matches your traits.</p>\n"
        f"  </section>"
    )


# ---------- GEO: FAQPage, entity, defined-term, hub builders ----------
def _subject_lookup(tags):
    if not tags:
        return ''
    return (tags[0] or '').strip().lower()


def _quiz_subject_kind(quiz_id, tags, full_quiz):
    meta = (full_quiz or {}).get('subject_meta') or {}
    if meta.get('is_group'):
        return 'MusicGroup'
    if meta.get('is_character_list'):
        return 'Thing'
    if meta.get('is_generic'):
        return ''
    sub = _subject_lookup(tags)
    if sub in SUBJECT_SAMEAS:
        return SUBJECT_SAMEAS[sub]['kind']
    return ''


def build_faq_for_quiz(quiz_id, summary, full_quiz, canonical):
    title = summary['title']
    meta  = (full_quiz or {}).get('subject_meta') or {}
    sub   = _subject_lookup(summary.get('tags') or [])
    qcount = summary.get('question_count', 12)
    rcount = summary.get('result_count', 16)

    faqs = []
    faqs.append({
        '@type': 'Question',
        'name': f"How long does the {title} take?",
        'acceptedAnswer': {'@type': 'Answer', 'text': f"Most people finish in about 3 minutes. The quiz has {qcount} short questions, each with 4 answer options. You can retake it any time."},
    })
    faqs.append({
        '@type': 'Question',
        'name': f"How accurate is the {title}?",
        'acceptedAnswer': {'@type': 'Answer', 'text': "The quiz uses MBTI-style trait mapping for entertainment and self-reflection. It is not a clinical or psychological assessment and should not be used to make life decisions. Treat your result as a starting point, not a verdict."},
    })

    if meta.get('is_group') and sub:
        members = meta.get('members') or {}
        member_list = ', '.join(f"{n} ({t})" for n, t in list(members.items())[:6]) if members else 'the group members'
        sub_title = sub.title()
        faqs.append({
            '@type': 'Question',
            'name': f"Which {sub_title} member matches my personality?",
            'acceptedAnswer': {'@type': 'Answer', 'text': f"Take the quiz to find out. {sub_title} members and their widely-discussed MBTI types include: {member_list}. The quiz maps your answers to the member whose personality profile is closest to yours."},
        })
    elif meta.get('is_character_list') and sub:
        results = full_quiz.get('results') or []
        names = [r.get('title') or r.get('name') or '' for r in results[:3]]
        names = [n for n in names if n]
        sample = ', '.join(names) if names else 'a roster of characters'
        sub_title = sub.title()
        faqs.append({
            '@type': 'Question',
            'name': f"Which {sub_title} character am I most like?",
            'acceptedAnswer': {'@type': 'Answer', 'text': f"Answer {qcount} questions and the quiz matches you to the {sub_title} character whose personality mirrors yours. Possible matches include: {sample}."},
        })
    elif sub in SUBJECT_SAMEAS:
        sub_title = sub.title()
        kind_label = 'artist' if SUBJECT_SAMEAS[sub]['kind'] == 'Person' else 'group'
        primary = (meta.get('typing_primary') or '').strip()
        alt = (meta.get('typing_alternate') or '').strip()
        typing_line = ''
        if primary:
            typing_line = f" Fans and personality communities widely type {sub_title} as {primary}"
            if alt:
                typing_line += f", with some discussions also citing {alt}"
            typing_line += '.'
        faqs.append({
            '@type': 'Question',
            'name': f"What is {sub_title}'s MBTI type?",
            'acceptedAnswer': {'@type': 'Answer', 'text': f"{sub_title} is a {kind_label} whose personality type is widely discussed in fan communities.{typing_line} This free quiz helps you discover your own type and see which one matches your traits."},
        })
    else:
        faqs.append({
            '@type': 'Question',
            'name': f"What personality types does the {title} include?",
            'acceptedAnswer': {'@type': 'Answer', 'text': f"The quiz maps your answers to {rcount} personality results. Each result combines the four MBTI dimensions (E/I, S/N, T/F, J/P) into a distinct profile. Take the quiz to see which one matches you."},
        })

    faqs.append({
        '@type': 'Question',
        'name': f"Can I share my {title} result?",
        'acceptedAnswer': {'@type': 'Answer', 'text': "Yes. After finishing, tap the share button to send your result to friends via your phone's share menu, or copy a link. Sharing works without an account."},
    })

    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'url': canonical,
        'mainEntity': faqs,
    }


def build_subject_entity_schema(quiz_id, summary, full_quiz, canonical):
    kind = _quiz_subject_kind(quiz_id, summary.get('tags') or [], full_quiz)
    if kind not in ('Person', 'MusicGroup'):
        return {}
    sub = _subject_lookup(summary.get('tags') or [])
    if not sub:
        return {}
    refs = SUBJECT_SAMEAS.get(sub, {})
    meta = (full_quiz or {}).get('subject_meta') or {}
    primary = (meta.get('typing_primary') or '').strip()
    alternate = (meta.get('typing_alternate') or '').strip()
    desc = summary.get('description') or ''
    same_as = []
    if refs.get('wikipedia'):
        same_as.append(refs['wikipedia'])
    if refs.get('wikidata'):
        same_as.append(refs['wikidata'])
    entity = {
        '@type': kind,
        'name': sub.title(),
        'url': refs.get('wikipedia') or canonical,
        'description': desc,
    }
    if same_as:
        entity['sameAs'] = same_as
    if primary:
        entity['additionalProperty'] = [{'@type': 'PropertyValue', 'name': 'MBTI type (widely discussed)', 'value': primary}]
    if alternate:
        ap = entity.get('additionalProperty') or []
        ap.append({'@type': 'PropertyValue', 'name': 'MBTI alternates (also discussed)', 'value': alternate.replace(' or ', ', ')})
        entity['additionalProperty'] = ap
    return entity


def build_defined_term_schema(quiz_id, summary, full_quiz, canonical):
    out = []
    seen = set()
    for r in (full_quiz.get('results') or []):
        code = (r.get('mbtiType') or r.get('mbti') or '').strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        meta = MBTI_TYPE_MAP.get(code)
        if not meta:
            continue
        out.append({
            '@context': 'https://schema.org',
            '@type': 'DefinedTerm',
            'name': code,
            'alternateName': meta['title'],
            'description': meta['description'],
            'inDefinedTermSet': {
                '@type': 'DefinedTermSet',
                'name': 'Myers-Briggs Type Indicator (MBTI)',
                'url': 'https://en.wikipedia.org/wiki/Myers%E2%80%93Briggs_Type_Indicator',
            },
            'url': f"{SITE_URL}/mbti-types/#{code.lower()}",
        })
    return out


def build_llms_txt():
    lines = []
    lines.append(f"# {SITE_NAME}")
    lines.append('')
    lines.append(f"> {SITE_TAGLINE}")
    lines.append('')
    lines.append(f"{SITE_NAME} is a free personality-quiz site with ~{len(_quizzes)} MBTI-style quizzes across celebrity matches, character picks, pop-culture typings, and self-discovery games. Each quiz is 12 questions, takes ~3 minutes, and returns a 4-letter MBTI result with a shareable description.")
    lines.append('')
    lines.append(f"## Main URLs")
    lines.append('')
    lines.append(f"- [Homepage]({SITE_URL}/): browse all quizzes")
    lines.append(f"- [MBTI Types Hub]({SITE_URL}/mbti-types/): all 16 personality types with definitions")
    lines.append(f"- [Characters Hub]({SITE_URL}/characters/): character-based quizzes by franchise")
    lines.append(f"- [Sitemap]({SITE_URL}/sitemap.xml): full quiz index")
    lines.append(f"- [Full content dump]({SITE_URL}/llms-full.txt): every quiz title, description, tags, and result list")
    lines.append('')
    lines.append("## Categories")
    lines.append('')
    cat_counts = {}
    for qid, q in _quizzes.items():
        if qid == 'onequiz':
            continue
        cat = (q.get('category') or 'general').strip() or 'general'
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    cat_label = {
        'which':       '"Which X Are You?" personality tests',
        'which_x':     '"Which X Are You?" personality tests',
        'how':         '"How X are you?" style quizzes',
        'whatwould':   '"What would X do?" scenario quizzes',
        'hidden':      '"Hidden X" or surprise-trait quizzes',
        'type':        'Type classifier quizzes',
        'match':       'Match / pairing quizzes',
        'pick':        'Pick / choose quizzes',
        'future':      'Future / projection quizzes',
        'degree':      '"What degree of X" intensity quizzes',
        'character':   'Character match quizzes',
        'mbti':        'MBTI tests',
        'personality': 'General personality',
        'trivia':      'Trivia',
        'aesthetic':   'Aesthetic & vibe quizzes',
    }
    for cat in sorted(cat_counts.keys(), key=lambda c: -cat_counts[c]):
        label = cat_label.get(cat, cat.replace('_', ' ').title() + ' quizzes')
        lines.append(f"- {label} ({cat_counts[cat]} quizzes)")
    lines.append('')
    lines.append("## Featured Quizzes")
    lines.append('')
    sorted_quizzes = sorted(
        ((qid, q) for qid, q in _quizzes.items() if qid != 'onequiz'),
        key=lambda kv: -(int(kv[1].get('likes') or 0)),
    )[:50]
    for qid, q in sorted_quizzes:
        title = (q.get('title') or 'Untitled').strip()
        desc = (q.get('description') or '').strip()
        if len(desc) > 140:
            desc = desc[:137] + '...'
        lines.append(f"- [{title}]({SITE_URL}/quiz/{qid}): {desc}")
    lines.append('')
    lines.append("## Optional")
    lines.append('')
    lines.append(f"- [Full content dump for AI training]({SITE_URL}/llms-full.txt)")
    lines.append(f"- [Sitemap for crawlers]({SITE_URL}/sitemap.xml)")
    lines.append(f"- [Robots policy]({SITE_URL}/robots.txt)")
    lines.append('')
    lines.append("## Common MBTI Comparisons (X vs Y)")
    lines.append('')
    lines.append(f"Each link points to a side-by-side comparison on the MBTI Types Hub with a `Comparison` schema.org block.")
    lines.append('')
    cmp_pairs = [
        ('INTJ', 'INTP'), ('INTJ', 'INFJ'), ('INFP', 'INFJ'), ('ENFP', 'ENTP'),
        ('ISTJ', 'ISFJ'), ('ENFJ', 'ENFP'), ('ESTJ', 'ENTJ'), ('ESFJ', 'ISFJ'),
    ]
    for a, b in cmp_pairs:
        anchor = f"{a.lower()}-vs-{b.lower()}"
        lines.append(f"- [{a} vs {b}]({SITE_URL}/mbti-types/#{anchor}): side-by-side traits and key difference")
    return '\n'.join(lines) + '\n'


def build_llms_full_txt():
    lines = []
    lines.append(f"# {SITE_NAME} \u2014 Full Content Dump")
    lines.append('')
    lines.append(f"> Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} \u2014 {len(_quizzes)} quizzes total.")
    lines.append('')
    lines.append(f"{SITE_DESC}")
    lines.append('')
    lines.append("---")
    lines.append('')
    for qid in sorted(_quizzes.keys()):
        if qid == 'onequiz':
            continue
        q = _quizzes.get(qid, {})
        title = (q.get('title') or 'Untitled').strip()
        desc = (q.get('description') or '').strip()
        cat = (q.get('category') or '').strip()
        tags = q.get('tags') or []
        meta = q.get('subject_meta') or {}
        results = q.get('results') or []
        url = f"{SITE_URL}/quiz/{qid}"
        lines.append(f"## {title}")
        lines.append('')
        lines.append(f"- URL: {url}")
        if cat:
            lines.append(f"- Category: {cat}")
        if tags:
            lines.append(f"- Tags: {', '.join(str(t) for t in tags)}")
        if desc:
            lines.append('')
            lines.append(desc)
        if meta.get('is_group'):
            members = meta.get('members') or {}
            if members:
                lines.append('')
                lines.append("**Members and MBTI types:**")
                for n, t in members.items():
                    lines.append(f"- {n}: {t}")
        elif meta.get('is_character_list'):
            char_lines = []
            for r in results:
                nm = (r.get('title') or r.get('name') or '').strip()
                mbti = (r.get('mbti') or '').strip()
                if nm and mbti:
                    char_lines.append(f"  - {nm}: {mbti}")
            if char_lines:
                lines.append('')
                lines.append("**Characters and MBTI types:**")
                lines.extend(char_lines)
        elif meta.get('typing_primary'):
            line = f"**MBTI (widely discussed):** {meta['typing_primary']}"
            if meta.get('typing_alternate'):
                line += f" (alternates: {meta['typing_alternate']})"
            lines.append('')
            lines.append(line)
        if results:
            lines.append('')
            lines.append("**Results:**")
            for r in results:
                nm = (r.get('title') or r.get('name') or r.get('mbtiType') or r.get('mbti') or '').strip()
                ds = (r.get('description') or '').strip()
                if nm:
                    if ds and len(ds) < 240:
                        lines.append(f"- {nm} \u2014 {ds}")
                    else:
                        lines.append(f"- {nm}")
        lines.append('')
    return '\n'.join(lines)


def _hub_style_block():
    return (
        "*{margin:0;padding:0;box-sizing:border-box}"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;color:#fff;line-height:1.6;-webkit-font-smoothing:antialiased}"
        "a{color:#A259FF;text-decoration:none}"
        "a:hover{text-decoration:underline}"
        ".wrap{max-width:880px;margin:0 auto;padding:0 20px 60px}"
        ".site-header{position:sticky;top:0;background:rgba(15,15,15,.92);backdrop-filter:blur(8px);border-bottom:1px solid #222;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;z-index:10}"
        ".site-header .logo{font-size:18px;font-weight:800;background:linear-gradient(90deg,#A259FF,#FF7AB6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}"
        ".site-header a.home{color:#888;font-size:13px}"
        ".breadcrumb{font-size:12px;color:#666;padding:14px 0 4px}"
        ".breadcrumb a{color:#888}"
        ".breadcrumb span{color:#aaa}"
        "h1{font-size:30px;line-height:1.2;font-weight:800;margin:18px 0 8px}"
        ".lede{color:#bbb;font-size:16px;margin:6px 0 22px}"
        "h2{font-size:20px;margin:30px 0 14px;font-weight:700}"
        ".group-label{font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;margin:24px 0 10px}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;list-style:none;padding:0}"
        ".grid li{background:#141414;border:1px solid #222;border-radius:12px;padding:14px 16px;list-style:none}"
        ".grid li h3{font-size:18px;margin-bottom:4px;font-weight:700}"
        ".grid li h3 a{color:#fff}"
        ".grid li p{color:#aaa;font-size:13px;line-height:1.55;margin:0}"
        "table{width:100%;border-collapse:collapse;margin:14px 0;font-size:14px}"
        "th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #222}"
        "th{background:#1a1a1a;color:#ddd;font-weight:600}"
        "td{color:#bbb}"
        ".cmp-card{background:#141414;border:1px solid #222;border-radius:14px;padding:18px 20px;margin:14px 0}"
        ".cmp-card h3{font-size:18px;margin-bottom:12px;font-weight:700}"
        ".cmp-card h3 a{color:#fff}"
        ".cmp-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:12px}"
        ".cmp-side{background:#1a1a1a;border:1px solid #262626;border-radius:10px;padding:12px 14px}"
        ".cmp-name{font-size:15px;font-weight:700;margin-bottom:6px;color:#fff}"
        ".cmp-title{color:#A259FF;font-weight:500;font-size:13px}"
        ".cmp-side p{color:#bbb;font-size:13px;line-height:1.55;margin:0}"
        ".cmp-focus{color:#ddd;font-size:14px;line-height:1.65;margin:8px 0 0;padding-top:10px;border-top:1px solid #262626}"
        "footer{text-align:center;color:#555;font-size:12px;padding:24px 0;border-top:1px solid #1a1a1a;margin-top:40px}"
        "footer a{color:#888;margin:0 6px}"
        "@media (max-width:480px){.grid{grid-template-columns:1fr 1fr}.cmp-grid{grid-template-columns:1fr}h1{font-size:24px}}"
    )


def build_mbti_types_hub_html():
    title = f"All 16 MBTI Types Explained | {SITE_NAME}"
    desc = ("A complete guide to all 16 Myers-Briggs personality types \u2014 what each "
            "type means, its core traits, and which QuizFig quizzes match that type. "
            "INTJ, INFP, ENFP, ISTJ, ESFP, and more.")
    canonical = f"{SITE_URL}/mbti-types/"

    groups = {}
    for t in MBTI_TYPES:
        groups.setdefault(t['group'], []).append(t)

    type_to_quizzes = {t['name']: [] for t in MBTI_TYPES}
    for qid, q in _quizzes.items():
        if qid == 'onequiz':
            continue
        for r in (q.get('results') or []):
            code = (r.get('mbtiType') or r.get('mbti') or '').strip().upper()
            if code in type_to_quizzes and len(type_to_quizzes[code]) < 3:
                type_to_quizzes[code].append({'qid': qid, 'title': q.get('title', 'Untitled')})

    itemlist = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': 'All 16 MBTI Personality Types',
        'url': canonical,
        'itemListOrder': 'https://schema.org/ItemListOrderAscending',
        'numberOfItems': len(MBTI_TYPES),
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': t['name'], 'url': f"{canonical}#{t['name'].lower()}"} for i, t in enumerate(MBTI_TYPES)],
    }
    itemlist_ld = json.dumps(itemlist, ensure_ascii=False)

    dts = {
        '@context': 'https://schema.org',
        '@type': 'DefinedTermSet',
        'name': 'Myers-Briggs Type Indicator (MBTI) \u2014 16 Types',
        'description': desc,
        'url': canonical,
        'hasDefinedTerm': [{'@type': 'DefinedTerm', 'name': t['name'], 'alternateName': t['title'], 'description': t['description']} for t in MBTI_TYPES],
    }
    dts_ld = json.dumps(dts, ensure_ascii=False)

    # ---------- GEO: Top MBTI comparisons (Comparison JSON-LD + side-by-side cards) ----------
    # Each pair is a high-volume "X vs Y" search. The AI can cite these directly
    # when users ask "what's the difference between INTJ and INTP".
    mbti_comparisons = [
        {'a': 'INTJ', 'b': 'INTP', 'focus': 'Both are quiet, idea-driven Analysts who prize competence. The split is J vs P: INTJs commit to a single long-term plan and execute it, while INTPs keep exploring alternatives. INTJ asks "what should we build?"; INTP asks "what else could this be?"'},
        {'a': 'INTJ', 'b': 'INFJ', 'focus': 'Both Ni-dominant and future-oriented, but INTJ leads with T (systems, logic) and INFJ with F (values, people). INTJ optimizes for what works; INFJ optimizes for what is right. The two often mistype each other in online tests.'},
        {'a': 'INFP', 'b': 'INFJ', 'focus': 'Both Diplomats with a rich inner world. INFPs are Fi-dom — their feelings lead. INFJs are Ni-dom with Fe — they intuit outcomes for others. INFPs express; INFJs advise. They are the most commonly confused NF pair.'},
        {'a': 'ENFP', 'b': 'ENTP', 'focus': 'Both energetic, idea-rich, quick-witted Extraverts. ENFPs are feeling-first — they champion people and possibilities. ENTPs are thinking-first — they love debate and dismantling ideas. ENFPs ask "what if?"; ENTPs ask "does that hold up?"'},
        {'a': 'ISTJ', 'b': 'ISFJ', 'focus': 'Both quiet, dependable Sentinels. ISTJs lead with Sensing-Thinking: rules, order, duty. ISFJs lead with Sensing-Feeling: care, memory, loyalty. ISTJ maintains the system; ISFJ maintains the people inside it.'},
        {'a': 'ENFJ', 'b': 'ENFP', 'focus': 'Both warm, sociable Diplomats. ENFJs (Fe-dom) organize people around a vision and feel responsible for group harmony. ENFPs (Ne-dom) chase novelty and pull others into possibilities. ENFJ is the mentor; ENFP is the spark.'},
        {'a': 'ESTJ', 'b': 'ENTJ', 'focus': 'Both decisive Judgers who lead. ESTJs manage what is — operations, policy, and accountability today. ENTJs (Ni aux) design what could be — strategy, structure, and long-horizon plans. ESTJ is the executor; ENTJ is the architect.'},
        {'a': 'ESFJ', 'b': 'ISFJ', 'focus': 'Both caring Sentinels. ESFJs are extraverted — they host, coordinate, and host the social web. ISFJs are introverted — they remember the small things and care quietly. Same value (care for people), different reach.'},
    ]
    comparison_sections_html = ''
    comparison_ld_blocks = []
    for c in mbti_comparisons:
        ca = MBTI_TYPE_MAP.get(c['a'])
        cb = MBTI_TYPE_MAP.get(c['b'])
        if not ca or not cb:
            continue
        anchor = f"{c['a'].lower()}-vs-{c['b'].lower()}"
        comparison_sections_html += (
            f'<div class="cmp-card" id="{h(anchor)}">\n'
            f'  <h3><a href="#{h(anchor)}">{h(c["a"])} vs {h(c["b"])}</a></h3>\n'
            f'  <div class="cmp-grid">\n'
            f'    <div class="cmp-side">\n'
            f'      <div class="cmp-name">{h(c["a"])} <span class="cmp-title">\u2014 {h(ca["title"])}</span></div>\n'
            f'      <p>{h(ca["description"])}</p>\n'
            f'    </div>\n'
            f'    <div class="cmp-side">\n'
            f'      <div class="cmp-name">{h(c["b"])} <span class="cmp-title">\u2014 {h(cb["title"])}</span></div>\n'
            f'      <p>{h(cb["description"])}</p>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'  <p class="cmp-focus"><strong>Key difference:</strong> {h(c["focus"])}</p>\n'
            f'</div>\n'
        )
        comparison_ld_blocks.append({
            '@context': 'https://schema.org',
            '@type': 'Comparison',
            'name': f"{c['a']} vs {c['b']} \u2014 MBTI Personality Type Comparison",
            'description': c['focus'],
            'url': f"{canonical}#{anchor}",
            'about': [
                {'@type': 'DefinedTerm', 'name': c['a'], 'alternateName': ca['title'], 'description': ca['description'], 'url': f"{canonical}#{c['a'].lower()}"},
                {'@type': 'DefinedTerm', 'name': c['b'], 'alternateName': cb['title'], 'description': cb['description'], 'url': f"{canonical}#{c['b'].lower()}"},
            ],
        })
    comparison_ld_html = '\n'.join(
        f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>'
        for b in comparison_ld_blocks
    )

    group_order = ['Analysts', 'Diplomats', 'Sentinels', 'Explorers']
    sections_html = ''
    for g in group_order:
        types_g = groups.get(g, [])
        if not types_g:
            continue
        sections_html += f'<div class="group-label">{h(g)}</div>\n'
        sections_html += '<ul class="grid">\n'
        for t in types_g:
            related = type_to_quizzes.get(t['name']) or []
            related_html = ''
            if related:
                related_html = '<p style="margin-top:8px;font-size:12px;color:#888">Quizzes: ' + ', '.join(f'<a href="/quiz/{h(r["qid"])}">{h(r["title"])}</a>' for r in related) + '</p>'
            sections_html += (
                f'<li id="{h(t["name"].lower())}">\n'
                f'  <h3><a href="#{h(t["name"].lower())}">{h(t["name"])}</a> &mdash; {h(t["title"])}</h3>\n'
                f'  <p>{h(t["description"])}</p>\n'
                f'  {related_html}\n'
                f'</li>\n'
            )
        sections_html += '</ul>\n'

    table_rows = ''
    for t in MBTI_TYPES:
        table_rows += (
            f'<tr>'
            f'<td><a href="#{h(t["name"].lower())}"><strong>{h(t["name"])}</strong></a></td>'
            f'<td>{h(t["title"])}</td>'
            f'<td>{h(t["group"])}</td>'
            f'<td>{h(t["description"])}</td>'
            f'</tr>\n'
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{h(title)}">
<meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{h(title)}">
<meta name="twitter:description" content="{h(desc)}">
<script type="application/ld+json">{itemlist_ld}</script>
<script type="application/ld+json">{dts_ld}</script>
{comparison_ld_html}
<style>{_hub_style_block()}</style>
</head>
<body>
<header class="site-header">
  <a href="/" class="logo">{h(SITE_NAME)}</a>
  <a href="/" class="home">All Quizzes</a>
</header>
<div class="wrap">
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <a href="/">Home</a> &rsaquo; <span>MBTI Types</span>
  </nav>
  <h1>All 16 MBTI Personality Types Explained</h1>
  <p class="lede">{h(desc)}</p>

  <h2>Quick Reference: All 16 Types</h2>
  <table>
    <thead><tr><th>Type</th><th>Title</th><th>Group</th><th>Core Description</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>

  <h2>Browse by Group</h2>
  {sections_html}

  <h2>Common MBTI Comparisons</h2>
  <p style="color:#bbb;font-size:14px;line-height:1.7;margin-bottom:14px">Side-by-side comparisons of the MBTI pairs people most often ask about. Each card highlights the core difference and links to the full type description.</p>
  {comparison_sections_html}

  <h2>How to use this page</h2>
  <p style="color:#bbb;font-size:14px;line-height:1.7">Each card above summarizes one of the 16 MBTI types and links to QuizFig quizzes that map to it. The four groups (Analysts, Diplomats, Sentinels, Explorers) come from the 16Personalities framework. MBTI is a popular self-reflection tool, not a clinical diagnosis &mdash; treat your result as a starting point, not a label.</p>
</div>
<footer>
  &copy; 2026 {h(SITE_NAME)} &middot;
  <a href="/">Home</a> &middot;
  <a href="/mbti-types/">MBTI Types</a> &middot;
  <a href="/characters/">Characters</a> &middot;
  <a href="/#about">About</a>
</footer>
</body>
</html>"""
    return html_doc


def build_characters_hub_html():
    title = f"Character Personality Quizzes \u2014 Match Yourself | {SITE_NAME}"
    desc = ("Free personality quizzes that match you to a fictional character. "
            "From Harry Potter to Genshin Impact, BLACKPINK to Roblox, find the "
            "character whose personality mirrors yours.")
    canonical = f"{SITE_URL}/characters/"

    by_subject = {}
    for qid, q in _quizzes.items():
        if qid == 'onequiz':
            continue
        meta = q.get('subject_meta') or {}
        if not meta.get('is_character_list'):
            continue
        tags = q.get('tags') or []
        if not tags:
            continue
        subject = tags[0]
        by_subject.setdefault(subject, []).append({
            'qid': qid,
            'title': q.get('title', 'Untitled'),
            'description': q.get('description', ''),
            'rcount': len(q.get('results', []) or []),
        })

    sorted_subjects = sorted(by_subject.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    sections_html = ''
    for subject, quizzes in sorted_subjects:
        sections_html += f'<div class="group-label">{h(subject)}</div>\n'
        sections_html += '<ul class="grid">\n'
        for q in quizzes:
            sections_html += (
                f'<li>\n'
                f'  <h3><a href="/quiz/{h(q["qid"])}">{h(q["title"])}</a></h3>\n'
                f'  <p>{h(q["description"])}</p>\n'
                f'  <p style="margin-top:6px;font-size:12px;color:#888">{q["rcount"]} possible characters</p>\n'
                f'</li>\n'
            )
        sections_html += '</ul>\n'

    itemlist = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': 'Character Personality Quizzes by Franchise',
        'url': canonical,
        'numberOfItems': sum(len(v) for _, v in sorted_subjects),
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': q['title'], 'url': f"{SITE_URL}/quiz/{q['qid']}"}
            for i, (_, quizzes) in enumerate(sorted_subjects) for q in quizzes[:1]
        ],
    }
    itemlist_ld = json.dumps(itemlist, ensure_ascii=False)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{h(title)}">
<meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{h(title)}">
<meta name="twitter:description" content="{h(desc)}">
<script type="application/ld+json">{itemlist_ld}</script>
<style>{_hub_style_block()}</style>
</head>
<body>
<header class="site-header">
  <a href="/" class="logo">{h(SITE_NAME)}</a>
  <a href="/" class="home">All Quizzes</a>
</header>
<div class="wrap">
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <a href="/">Home</a> &rsaquo; <span>Character Quizzes</span>
  </nav>
  <h1>Character Personality Quizzes</h1>
  <p class="lede">{h(desc)}</p>

  <h2>Browse by Franchise</h2>
  {sections_html}

  <h2>About these quizzes</h2>
  <p style="color:#bbb;font-size:14px;line-height:1.7">Each quiz on this page maps your answers to a character whose personality type is widely discussed by fans. Results use the MBTI framework for comparison; they're meant for fun and self-reflection, not as a clinical assessment.</p>
</div>
<footer>
  &copy; 2026 {h(SITE_NAME)} &middot;
  <a href="/">Home</a> &middot;
  <a href="/mbti-types/">MBTI Types</a> &middot;
  <a href="/characters/">Characters</a> &middot;
  <a href="/#about">About</a>
</footer>
</body>
</html>"""
    return html_doc


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
                "suggestedAnswer": [
                    {"@type": "Answer", "text": o.get("text", "")}
                    for o in (q.get('options', []) or [])[:4]
                ],
            }
            for q in questions[:12]
        ],
    }
    schema = {k: v for k, v in schema.items() if v is not None}
    schema_ld = json.dumps(schema, ensure_ascii=False)

    # 1b) GEO: FAQPage JSON-LD
    faq_ld = json.dumps(build_faq_for_quiz(quiz_id, summary, full, canonical), ensure_ascii=False)

    # 1c) GEO: Person / MusicGroup entity JSON-LD (only if we have a canonical subject)
    entity_obj = build_subject_entity_schema(quiz_id, summary, full, canonical)
    entity_ld = json.dumps(entity_obj, ensure_ascii=False) if entity_obj else ''

    # 1d) GEO: DefinedTerm[] for each MBTI result on the page
    defined_terms = build_defined_term_schema(quiz_id, summary, full, canonical)
    defined_terms_ld = '\n'.join(
        f'<script type="application/ld+json">{json.dumps(t, ensure_ascii=False)}</script>'
        for t in defined_terms
    )

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

    # 7) Subject MBTI section (only for real-person / real-group quizzes with subject_meta)
    subject_section_html = build_subject_section_html(full, tags)

    # 8) Build full HTML
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
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ctext y='52' font-size='52'%3E%F0%9F%A7%A9%3C/text%3E%3C/svg%3E">
<script type="application/ld+json">{schema_ld}</script>
<script type="application/ld+json">{breadcrumb_ld}</script>
<script type="application/ld+json">{faq_ld}</script>
{('<script type="application/ld+json">' + entity_ld + '</script>') if entity_ld else ''}
{defined_terms_ld}
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

{subject_section_html}

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
  <a href="/">Home</a> &middot;
  <a href="/#about">About Us</a> &middot;
  <a href="/#contact">Contact Us</a> &middot;
  <a href="/#privacy">Privacy Policy</a>
</footer>
<!-- Footer Ad Script (Adsterra Social Bar) -->
<script src="https://pl29731037.effectivecpmnetwork.com/e9/6d/d8/e96dd8df6601a8ae07af1bd836296417.js"></script>
</body>
</html>"""
    return html_doc


# ---------- Sitemap & robots ----------
def build_sitemap_xml():
    """Generate sitemap.xml with home + every quiz URL + GEO hub pages."""
    home_lastmod = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    urls = [
        f"""  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{home_lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>""",
        # GEO: hub pages for AI discoverability
        f"""  <url>
    <loc>{SITE_URL}/mbti-types/</loc>
    <lastmod>{home_lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>""",
        f"""  <url>
    <loc>{SITE_URL}/characters/</loc>
    <lastmod>{home_lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>""",
        # GEO: machine-readable entry points (also link from robots.txt)
        f"""  <url>
    <loc>{SITE_URL}/llms.txt</loc>
    <lastmod>{home_lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>""",
        f"""  <url>
    <loc>{SITE_URL}/llms-full.txt</loc>
    <lastmod>{home_lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>""",
    ]
    # Iterate deterministically by quiz id
    for qid in sorted(_quizzes.keys()):
        if qid == 'onequiz':
            continue
        # Use file mtime for accurate lastmod signal
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
    # GEO: explicitly allow major AI crawlers. The wildcard above already permits
    # them, but listing them as named agents signals intent and survives more
    # conservative parsers (e.g. Cloudflare bot rules that match by exact name).
    lines = [
        "# Default policy",
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "",
        "# AI crawlers (GEO) — keep allowed so generative engines can index us",
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: ChatGPT-User",
        "Allow: /",
        "",
        "User-agent: OAI-SearchBot",
        "Allow: /",
        "",
        "User-agent: ClaudeBot",
        "Allow: /",
        "",
        "User-agent: Claude-Web",
        "Allow: /",
        "",
        "User-agent: anthropic-ai",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        "User-agent: Perplexity-User",
        "Allow: /",
        "",
        "User-agent: Google-Extended",
        "Allow: /",
        "",
        "User-agent: Applebot-Extended",
        "Allow: /",
        "",
        "User-agent: Amazonbot",
        "Allow: /",
        "",
        "User-agent: cohere-ai",
        "Allow: /",
        "",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        f"Sitemap: {SITE_URL}/llms.txt",
    ]
    return "\n".join(lines) + "\n"


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

    # ---------- GEO: /llms.txt ----------
    if path == '/llms.txt':
        return respond(
            start_response, '200 OK',
            base_headers('text/plain; charset=utf-8', 'static'),
            build_llms_txt(),
        )

    # ---------- GEO: /llms-full.txt ----------
    if path == '/llms-full.txt':
        return respond(
            start_response, '200 OK',
            base_headers('text/plain; charset=utf-8', 'static'),
            build_llms_full_txt(),
        )

    # ---------- GEO: /mbti-types/ hub ----------
    if path in ('/mbti-types', '/mbti-types/'):
        return respond(
            start_response, '200 OK',
            base_headers('text/html; charset=utf-8', 'static'),
            build_mbti_types_hub_html(),
        )

    # ---------- GEO: /characters/ hub ----------
    if path in ('/characters', '/characters/'):
        return respond(
            start_response, '200 OK',
            base_headers('text/html; charset=utf-8', 'static'),
            build_characters_hub_html(),
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
        # Resolve each pair; on ties, pick deterministically from a hash of
        # the dimension scores so the same answers always yield the same MBTI,
        # but there's no systematic bias toward E/S/T/J (the old `>=` behavior).
        # Important: keep position stable so the output is always a valid MBTI.
        _mbti_chars = ['', '', '', '']
        _ties = []
        for _i, (_left, _right) in enumerate((('E', 'I'), ('S', 'N'), ('T', 'F'), ('J', 'P'))):
            if scores[_left] > scores[_right]:
                _mbti_chars[_i] = _left
            elif scores[_left] < scores[_right]:
                _mbti_chars[_i] = _right
            else:
                _ties.append((_i, _left, _right))
        if _ties:
            _h = int(hashlib.md5(json.dumps(scores, sort_keys=True).encode()).hexdigest(), 16)
            for _i, _left, _right in _ties:
                _mbti_chars[_i] = _left if (_h & 1) else _right
                _h >>= 1
        mbti = ''.join(_mbti_chars)

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

        # T+1 completion counter: fire-and-forget, never fails the result.
        _record_completion(quiz_id)

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

    # ---------- /api/admin/daily.csv (GET) — T+1 completion report ----------
    if path == '/api/admin/daily.csv' and method == 'GET':
        return _admin_daily_csv(environ, start_response)

    # ---------- 404 ----------
    return respond(start_response, '404 NOT FOUND', api_headers('no'),
                   json.dumps({'error': 'Not found', 'path': path}))

# -*- coding: utf-8 -*-
"""Local test for T+1 CSV generation. Mocks Upstash in-process."""
import os
import sys
import io
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

# Inject test env vars BEFORE importing the module
os.environ['ADMIN_KEY'] = 'test-key-12345'
os.environ['UPSTASH_REDIS_REST_URL'] = 'https://mock.upstash.io'
os.environ['UPSTASH_REDIS_REST_TOKEN'] = 'mock-token'

# Mock the http Upstash calls
class MockRedis:
    def __init__(self):
        self.store = {}  # key -> dict (hash) or str (string)
    def hgetall(self, key):
        return dict(self.store.get(key, {}))
    def hincrby(self, key, field, by):
        h = self.store.setdefault(key, {})
        h[field] = int(h.get(field, 0)) + int(by)
        return h[field]
    def expire(self, key, sec):
        pass  # noop in mock

MOCK = MockRedis()

# Patch the module to use the mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import api.index as idx

def fake_upstash_hgetall(key):
    return MOCK.hgetall(key)

def fake_record_completion(quiz_id):
    if not quiz_id:
        return False
    date_key = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    hash_key = f"complete:{date_key}"
    MOCK.hincrby(hash_key, quiz_id, 1)
    return True

idx._upstash_hgetall = fake_upstash_hgetall
idx._record_completion = fake_record_completion

# Inject a couple of fake quizzes for testing
idx._quizzes['test_quiz_a'] = {'title': 'Test Quiz A 你好, 朋友 "quoted"', 'questions': [], 'results': []}
idx._quizzes['test_quiz_b'] = {'title': 'Test Quiz B\nWith newline', 'questions': [], 'results': []}
idx._quizzes['test_quiz_c'] = {'title': 'Test Quiz C (zero completions)', 'questions': [], 'results': []}
idx._quizzes['onequiz'] = {'title': 'should be excluded'}

# --- Test 1: record completions ---
# Note: _record_completion always writes to TODAY (UTC). The T+1 CSV endpoint
# only allows reading YESTERDAY (UTC), so to test the end-to-end we write
# directly to yesterday's hash via the mock.
print('=== Test 1: seed yesterday\'s completions via mock ===')
yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
y_hash = f"complete:{yesterday}"
MOCK.hincrby(y_hash, 'test_quiz_a', 3)
MOCK.hincrby(y_hash, 'test_quiz_b', 1)
print(f'Seeded into {y_hash}: {MOCK.store[y_hash]}')

# --- Test 2: build CSV ---
print('=== Test 2: build_admin_daily_csv ===')
yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
csv_body = idx._build_admin_daily_csv(yesterday)

# Parse with the csv module (handles quoted multi-line fields correctly)
import csv as csvmod
rows = list(csvmod.reader(io.StringIO(csv_body)))
header = rows[0]
data = rows[1:]
assert header == ['date', 'quiz_id', 'quiz_title', 'count'], f'bad header: {header!r}'

by_id = {r[1]: r for r in data}
assert by_id['test_quiz_a'][3] == '3', f'a count wrong: {by_id["test_quiz_a"]!r}'
assert by_id['test_quiz_b'][3] == '1', f'b count wrong: {by_id["test_quiz_b"]!r}'
assert by_id['test_quiz_c'][3] == '0', f'c count wrong: {by_id["test_quiz_c"]!r}'

# Sort order: a(3) > b(1) > c(0); ties broken by quiz_id asc
a_idx = next(i for i, r in enumerate(data) if r[1] == 'test_quiz_a')
b_idx = next(i for i, r in enumerate(data) if r[1] == 'test_quiz_b')
c_idx = next(i for i, r in enumerate(data) if r[1] == 'test_quiz_c')
assert a_idx < b_idx < c_idx, f'sort order wrong: a={a_idx} b={b_idx} c={c_idx}'

# onequiz must not appear
assert 'onequiz' not in {r[1] for r in data}, 'onequiz should be excluded'

# All non-zero rows must be at the top, zeros below
nonzero = [r for r in data if r[3] != '0']
zero = [r for r in data if r[3] == '0']
if nonzero and zero:
    assert data.index(nonzero[-1]) < data.index(zero[0]), 'zeros leaked above non-zeros'

# Date column consistent
assert all(r[0] == yesterday for r in data), 'date column inconsistent'
print(f'OK: {len(data)} rows parsed, sort/escape/sort all correct')

# --- Test 3: auth (no key, wrong key, right key) ---
print('\n=== Test 3: admin endpoint auth & T+1 guard ===')

def make_environ(qs):
    return {
        'PATH_INFO': '/api/admin/daily.csv',
        'REQUEST_METHOD': 'GET',
        'QUERY_STRING': qs,
        'CONTENT_LENGTH': '0',
        'wsgi.input': io.BytesIO(b''),
    }

captured = {}
def start_response(status, headers):
    captured['status'] = status
    captured['headers'] = dict(headers)

# No key
captured.clear()
body = b''.join(idx._admin_daily_csv(make_environ('date=' + yesterday), start_response))
print(f'no key   -> {captured["status"]} {body[:80]!r}')
assert captured['status'].startswith('401')

# Wrong key
captured.clear()
body = b''.join(idx._admin_daily_csv(make_environ(f'date={yesterday}&key=WRONG'), start_response))
print(f'wrong    -> {captured["status"]} {body[:80]!r}')
assert captured['status'].startswith('401')

# Right key, no date (should default to yesterday)
captured.clear()
body = b''.join(idx._admin_daily_csv(make_environ('key=test-key-12345'), start_response))
print(f'right+nd -> {captured["status"]} header_date={captured["headers"].get("Content-Disposition")!r}')
assert captured['status'].startswith('200')
assert yesterday in captured['headers']['Content-Disposition']
assert b'test_quiz_a' in body

# Right key, today (should 400)
captured.clear()
today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
body = b''.join(idx._admin_daily_csv(make_environ(f'date={today}&key=test-key-12345'), start_response))
print(f'today    -> {captured["status"]} {body[:80]!r}')
assert captured['status'].startswith('400'), f'T+1 guard failed: {captured["status"]}'

# Right key, future date (should 400)
captured.clear()
future = (datetime.now(timezone.utc) + timedelta(days=3)).strftime('%Y-%m-%d')
body = b''.join(idx._admin_daily_csv(make_environ(f'date={future}&key=test-key-12345'), start_response))
print(f'future   -> {captured["status"]} {body[:80]!r}')
assert captured['status'].startswith('400')

# Right key, bad date format (should 400)
captured.clear()
body = b''.join(idx._admin_daily_csv(make_environ('date=2026/06/12&key=test-key-12345'), start_response))
print(f'bad fmt  -> {captured["status"]} {body[:80]!r}')
assert captured['status'].startswith('400')

# Right key, valid old date (should 200)
captured.clear()
body = b''.join(idx._admin_daily_csv(make_environ('date=2025-01-15&key=test-key-12345'), start_response))
print(f'old date -> {captured["status"]} body_len={len(body)}')
assert captured['status'].startswith('200')
assert b'2025-01-15,test_quiz_a' in body, 'expected test_quiz_a row in old-date CSV'

print('\nAll tests passed.')

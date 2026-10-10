/*
 * QuizFig consent & advertising loader
 * ------------------------------------------------------------
 * - Google Consent Mode v2: default-denied for ad/analytics storage
 *   in EEA + UK + Switzerland; updated on visitor choice.
 * - GA4 (gtag) and Google AdSense are loaded ONLY through this file,
 *   so no advertising/measurement cookie is set before consent where
 *   the law requires it.
 * - Child-directed pages (window.__QF_CONF.child === 1, or a child
 *   result from /api/geo) load NO ads and NO analytics at all.
 *
 * Geo resolution order:
 *   1. window.__QF_CONF.country  (set by SSR if available)
 *   2. localStorage cache (< 24h)
 *   3. GET /api/geo?id=<quizId>  (edge endpoint, reads Vercel geo header)
 * Unknown geo is treated conservatively as in-scope (banner shown).
 */
(function () {
  'use strict';

  var CONF = window.__QF_CONF || {};
  var GA4_ID = 'G-EQQ75D1GWK';
  var ADSENSE_CLIENT = 'ca-pub-9900304220798571';

  // Google's EU User Consent Policy scope: EEA member states + UK + CH + IS/LI/NO
  var CONSENT_REGIONS = {
    AT: 1, BE: 1, BG: 1, HR: 1, CY: 1, CZ: 1, DK: 1, EE: 1, FI: 1, FR: 1,
    DE: 1, GR: 1, HU: 1, IE: 1, IT: 1, LV: 1, LT: 1, LU: 1, MT: 1, NL: 1,
    PL: 1, PT: 1, RO: 1, SK: 1, SI: 1, ES: 1, SE: 1,
    IS: 1, LI: 1, NO: 1, GB: 1, CH: 1
  };

  var KEY_CONSENT = 'qf_consent_v1';
  var GEO_TTL_MS = 24 * 60 * 60 * 1000;

  var st = {
    country: (CONF.country || '').toUpperCase(),
    child: CONF.child === 1 || CONF.child === true,
    choice: null,        // 'granted' | 'denied' | null
    gtagLoaded: false,
    adsLoaded: false,
    readyCbs: []
  };

  // ---------- storage helpers ----------
  function readJSON(key) {
    try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; }
  }
  function writeJSON(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { /* private mode */ }
  }
  function readChoice() {
    var c = readJSON(KEY_CONSENT);
    if (c && (c.ad === 'granted' || c.ad === 'denied')) return c.ad;
    return null;
  }
  function saveChoice(ad) {
    st.choice = ad;
    writeJSON(KEY_CONSENT, { v: 1, ad: ad, ts: Date.now() });
  }

  function getQuizId() {
    try {
      return new URLSearchParams(window.location.search).get('id') || '';
    } catch (e) { return ''; }
  }

  function geoCacheKey() {
    return 'qf_geo_v1_' + (CONF.page || 'x') + '_' + (getQuizId() || 'home');
  }

  // ---------- gtag / Consent Mode v2 ----------
  function pushGtag() {
    window.dataLayer = window.dataLayer || [];
    if (!window.gtag) {
      window.gtag = function () { window.dataLayer.push(arguments); };
    }
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA4_ID;
    document.head.appendChild(s);
    window.gtag('js', new Date());
    st.gtagLoaded = true;
  }

  // Consent defaults. functionality_storage/security_storage stay granted
  // (per Google's own recommendation); ad + analytics signals are gated.
  function setConsent(mode, signals) {
    window.gtag('consent', mode, {
      ad_storage: signals.ad,
      ad_user_data: signals.ad,
      ad_personalization: signals.ad,
      analytics_storage: signals.analytics,
      functionality_storage: 'granted',
      security_storage: 'granted',
      wait_for_update: 500
    });
  }

  function configGtag() {
    window.gtag('config', GA4_ID, { anonymize_ip: true });
  }

  // ---------- AdSense ----------
  function loadAdsense() {
    if (st.adsLoaded || st.child) return;
    st.adsLoaded = true;
    var s = document.createElement('script');
    s.async = true;
    s.crossOrigin = 'anonymous';
    s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + ADSENSE_CLIENT;
    document.head.appendChild(s);
    s.addEventListener('load', function () {
      try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) {}
      st.readyCbs.forEach(function (cb) { try { cb(); } catch (e) {} });
      st.readyCbs = [];
    });
  }

  // Public hook for future manual <ins> slots (see quiz.html renderResultAd).
  window.QFConsent = {
    whenReady: function (cb) {
      if (st.adsLoaded) { cb(); } else { st.readyCbs.push(cb); }
    },
    reopenBanner: showBanner,
    state: st
  };

  // ---------- decision flow ----------
  function proceed() {
    // Child-directed page: zero ads, zero analytics (COPPA-safe posture).
    if (st.child) return;

    var inScope = !st.country || !!CONSENT_REGIONS[st.country];
    st.choice = readChoice();

    if (!inScope) {
      // Outside EEA/UK/CH: no banner required; signals default granted.
      pushGtag();
      setConsent('default', { ad: 'granted', analytics: 'granted' });
      configGtag();
      loadAdsense();
      return;
    }

    // In scope (or geo unknown): default denied, ask first.
    pushGtag();
    setConsent('default', { ad: 'denied', analytics: 'denied' });
    configGtag();

    if (st.choice === 'granted' || st.choice === 'denied') {
      var v = st.choice;
      setConsent('update', { ad: v, analytics: v });
      // Denied -> Consent Mode signals cause Google to serve limited ads.
      loadAdsense();
    } else {
      showBanner();
    }
  }

  function decide(ad) {
    saveChoice(ad);
    setConsent('update', { ad: ad, analytics: ad });
    loadAdsense();
    hideBanner();
  }

  // ---------- banner UI ----------
  function injectStyles() {
    var css = '' +
      '#qf-consent{position:fixed;left:0;right:0;bottom:0;z-index:99999;' +
      'background:#141414;color:#eee;border-top:1px solid #2a2a2a;' +
      'box-shadow:0 -8px 30px rgba(0,0,0,.5);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
      '#qf-consent .qc-wrap{max-width:860px;margin:0 auto;padding:16px 20px;display:flex;' +
      'flex-wrap:wrap;align-items:center;gap:12px}' +
      '#qf-consent .qc-txt{flex:1 1 320px;font-size:13px;color:#ccc}' +
      '#qf-consent .qc-txt a{color:#c79bff;text-decoration:underline}' +
      '#qf-consent .qc-btns{display:flex;gap:10px;flex-shrink:0}' +
      '#qf-consent button{border:0;border-radius:22px;padding:10px 20px;font-size:13px;font-weight:700;cursor:pointer}' +
      '#qf-consent .qc-accept{background:linear-gradient(90deg,#A259FF,#FF7AB6);color:#111}' +
      '#qf-consent .qc-reject{background:transparent;color:#bbb;border:1px solid #444}' +
      '@media (max-width:520px){#qf-consent .qc-btns{width:100%}#qf-consent button{flex:1}}';
    var style = document.createElement('style');
    style.id = 'qf-consent-style';
    style.textContent = css;
    document.head.appendChild(style);
  }

  function showBanner() {
    if (st.child || document.getElementById('qf-consent')) return;
    injectStyles();
    var box = document.createElement('div');
    box.id = 'qf-consent';
    box.innerHTML =
      '<div class="qc-wrap">' +
        '<div class="qc-txt">' +
          'We and Google use cookies and similar technologies to measure traffic and show ads. ' +
          'We only store advertising/analytics cookies after your consent. You can accept or reject — ' +
          'you will still see non-personalized ads if you reject. See our ' +
          '<a href="/privacy">Privacy Policy</a> for details.' +
        '</div>' +
        '<div class="qc-btns">' +
          '<button type="button" class="qc-reject">Reject all</button>' +
          '<button type="button" class="qc-accept">Accept all</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(box);
    box.querySelector('.qc-accept').addEventListener('click', function () { decide('granted'); });
    box.querySelector('.qc-reject').addEventListener('click', function () { decide('denied'); });
  }

  function hideBanner() {
    var b = document.getElementById('qf-consent');
    if (b) b.remove();
  }

  // ---------- geo bootstrap ----------
  function startWithGeo(country, child) {
    if (country) st.country = country.toUpperCase();
    if (child) st.child = true;
    proceed();
  }

  function fetchGeo() {
    var qid = getQuizId();
    var url = '/api/geo' + (qid ? '?id=' + encodeURIComponent(qid) : '');
    fetch(url, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) throw new Error('bad geo');
        var payload = { country: d.country || '', child: !!d.child, ts: Date.now() };
        writeJSON(geoCacheKey(), payload);
        startWithGeo(payload.country, payload.child);
      })
      .catch(function () {
        // Conservative fallback: unknown location => ask for consent.
        startWithGeo('', st.child);
      });
  }

  // SSR may already have told us the child flag / country.
  if (st.child || st.country) {
    proceed();
    // Still refresh geo in the background for non-SSR fields; do not block ads.
    if (!st.country) fetchGeo();
    return;
  }

  var cached = readJSON(geoCacheKey());
  if (cached && cached.ts && (Date.now() - cached.ts < GEO_TTL_MS)) {
    startWithGeo(cached.country, cached.child);
    return;
  }
  fetchGeo();
})();

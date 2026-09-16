/**
 * tone3000-client.ts — TONE3000 OAuth + API client
 *
 * A zero-dependency helper for integrating with the TONE3000 API.
 * Uses built-in WebCrypto and fetch — no npm install required.
 *
 * Quick start:
 *   1. Import the flow initiator for your use case
 *   2. Call it when the user triggers the integration (e.g. clicks "Browse Tones")
 *   3. In your callback handler, call handleOAuthCallback()
 *   4. Use T3KClient to make authenticated API requests
 */
import { T3K_API } from './config.js';
// ─── Internal PKCE helpers ────────────────────────────────────────────────────
async function randomBase64url(bytes) {
    const buf = crypto.getRandomValues(new Uint8Array(bytes));
    return btoa(String.fromCharCode(...buf))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  
}
async function sha256Base64url(input) {
    /*const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
    return btoa(String.fromCharCode(...new Uint8Array(hash)))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');*/
    const hash = CryptoJS.SHA256(input);
    const base64 = hash.toString(CryptoJS.enc.Base64);
    return base64
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');
}
async function buildPkceParams() {
    const codeVerifier = await randomBase64url(32);
    const [codeChallenge, state] = await Promise.all([
        sha256Base64url(codeVerifier),
        randomBase64url(16),
    ]);
    sessionStorage.setItem('t3k_code_verifier', codeVerifier);
    sessionStorage.setItem('t3k_state', state);
    return { codeVerifier, codeChallenge, state };
}
function buildAuthorizeUrl(publishableKey, redirectUri, extra, pkce) {
    const url = new URL(`${T3K_API}/api/v1/oauth/authorize`);
    url.searchParams.set('client_id', publishableKey);
    url.searchParams.set('redirect_uri', redirectUri);
    url.searchParams.set('response_type', 'code');
    url.searchParams.set('code_challenge', pkce.codeChallenge);
    url.searchParams.set('code_challenge_method', 'S256');
    url.searchParams.set('state', pkce.state);
    for (const [k, v] of Object.entries(extra))
        url.searchParams.set(k, v);
    return url.toString();
}
// ─── Flow initiators ──────────────────────────────────────────────────────────
/**
 * **Select Flow** — Send the user to TONE3000 to browse and pick a tone.
 *
 * Use this when your app wants to let users discover tones from the TONE3000
 * catalog. After the user selects a tone, they're redirected back to your app
 * with an authorization code and the selected `tone_id`.
 *
 * Optional `options`: `gears` (underscore-separated, e.g. `amp_pedal`), `format`
 * (e.g. `nam`, `aida-x`), `architecture` (numeric), `menubar` (UI hint) — each is
 * forwarded as an authorize query param when set.
 */
export async function startSelectFlow(publishableKey, redirectUri, options) {
    const pkce = await buildPkceParams();
    const extra = { prompt: 'select_tone' };
    if (options?.gears)
        extra.gears = options.gears;
    if (options?.format)
        extra.format = options.format;
    if (options?.menubar)
        extra.menubar = 'true';
    if (options?.architecture)
        extra.architecture = options.architecture.toString();
    if (options?.loginHint)
        extra.login_hint = options.loginHint;
    // Opts the flow into in-flow preview players (audition tones from the search
    // results, profiles, and tone detail without leaving TONE3000).
    if (options?.preview)
        extra.preview = 'true';
    window.location.href = buildAuthorizeUrl(publishableKey, redirectUri, extra, pkce);
}
/**
 * **Select Flow (Popup)** — Open TONE3000 tone browsing and selection in a popup window.
 *
 * Same as `startSelectFlow` but opens in a popup. The user stays on your app while
 * browsing TONE3000. When a tone is selected, the popup relays the result back via
 * `postMessage` or `BroadcastChannel` — handle it with `handleOAuthCallbackFromPopup`.
 * Supports the same optional `gears`, `format`, `architecture`, and `menubar`
 * as `startSelectFlow`.
 */
export async function startSelectFlowPopup(publishableKey, redirectUri, options) {
    // Set before window.open so the popup inherits this flag via sessionStorage copy;
    // remove it from the parent immediately so only the popup retains it.
    sessionStorage.setItem('t3k_popup_mode', '1');
    const pkce = await buildPkceParams();
    const extra = { prompt: 'select_tone' };
    if (options?.gears)
        extra.gears = options.gears;
    if (options?.format)
        extra.format = options.format;
    if (options?.menubar)
        extra.menubar = 'true';
    if (options?.architecture)
        extra.architecture = options.architecture.toString();
    if (options?.loginHint)
        extra.login_hint = options.loginHint;
    // Opts the flow into in-flow preview players (audition tones from the search
    // results, profiles, and tone detail without leaving TONE3000).
    if (options?.preview)
        extra.preview = 'true';
    const url = buildAuthorizeUrl(publishableKey, redirectUri, extra, pkce);
    const width = 480;
    const height = 720;
    const left = Math.round(window.screenX + (window.outerWidth - width) / 2);
    const top = Math.round(window.screenY + (window.outerHeight - height) / 2);
    const popup = window.open(url, 't3k_select', `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no,status=no,resizable=yes,scrollbars=yes`);
    sessionStorage.removeItem('t3k_popup_mode');
    return popup;
}
/**
 * Handle an OAuth callback relayed from a select popup.
 *
 * Pass events from both a `message` listener and a `BroadcastChannel('t3k_oauth')`
 * listener to this function. Returns `null` if the event is not a TONE3000 callback.
 * Verifies state, exchanges the code for tokens, and returns the same result shape
 * as `handleOAuthCallback`.
 */
export async function handleOAuthCallbackFromPopup(publishableKey, redirectUri, event) {
    if (event.data?.type !== 't3k_oauth_callback')
        return null;
    const { code, state: returnedState, error, tone_id: toneId, model_id: modelId, canceled } = event.data;
    const storedState = sessionStorage.getItem('t3k_state');
    const codeVerifier = sessionStorage.getItem('t3k_code_verifier');
    sessionStorage.removeItem('t3k_state');
    sessionStorage.removeItem('t3k_code_verifier');
    if (returnedState !== storedState)
        return { ok: false, error: 'state_mismatch' };
    // User closed without signing in — no code to exchange
    if (canceled && !code)
        return { ok: false, error: 'canceled' };
    if (error)
        return { ok: false, error };
    if (!code || !codeVerifier)
        return { ok: false, error: 'missing_code' };
    const res = await fetch(`${T3K_API}/api/v1/oauth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
            grant_type: 'authorization_code',
            code,
            code_verifier: codeVerifier,
            redirect_uri: redirectUri,
            client_id: publishableKey,
        }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        return { ok: false, error: err.error ?? 'token_exchange_failed' };
    }
    const data = await res.json();
    const tokens = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_at: Date.now() + data.expires_in * 1000,
    };
    return { ok: true, tokens, toneId, modelId, ...(canceled ? { canceled: true } : {}) };
}
/**
 * **Load Tone Flow** — Send the user to TONE3000 to authenticate and load a specific tone.
 *
 * Use this when your app already has a `tone_id` and wants to ensure the user
 * is authenticated and has access to that tone. TONE3000 handles the auth check
 * and redirects back immediately — no tone browsing required.
 *
 * If the tone is private or has been deleted, TONE3000 shows an error page
 * where the user can browse for a replacement. In that case, the `tone_id` in
 * the callback may differ from the one you requested. Any `gears`, `format`,
 * or `architecture` filters you pass are applied to that replacement browse view.
 *
 * @param gears - Optional underscore-separated gear filter (e.g. 'amp_amp-cab')
 * @param format - Optional format filter (e.g. 'nam', 'aida-x')
 */
export async function startLoadToneFlow(publishableKey, redirectUri, toneId, options) {
    const pkce = await buildPkceParams();
    const extra = { prompt: 'load_tone', tone_id: String(toneId) };
    if (options?.gears)
        extra.gears = options.gears;
    if (options?.format)
        extra.format = options.format;
    if (options?.menubar)
        extra.menubar = 'true';
    if (options?.architecture)
        extra.architecture = options.architecture.toString();
    if (options?.loginHint)
        extra.login_hint = options.loginHint;
    window.location.href = buildAuthorizeUrl(publishableKey, redirectUri, extra, pkce);
}
/**
 * **Load Tone Flow (Popup)** — Open TONE3000 in a popup to authenticate and load a specific tone.
 *
 * Same as `startLoadToneFlow` but opens in a popup. When the flow completes, the
 * popup relays the result back via `postMessage` or `BroadcastChannel` — handle it
 * with `handleOAuthCallbackFromPopup`. Any `gears`, `format`, or `architecture`
 * filters you pass are applied if the user needs to browse for a replacement tone.
 */
export async function startLoadToneFlowPopup(publishableKey, redirectUri, toneId, options) {
    // Set before window.open so the popup inherits this flag via sessionStorage copy;
    // remove it from the parent immediately so only the popup retains it.
    sessionStorage.setItem('t3k_popup_mode', '1');
    const pkce = await buildPkceParams();
    const extra = { prompt: 'load_tone', tone_id: String(toneId) };
    if (options?.gears)
        extra.gears = options.gears;
    if (options?.format)
        extra.format = options.format;
    if (options?.menubar)
        extra.menubar = 'true';
    if (options?.architecture)
        extra.architecture = options.architecture.toString();
    if (options?.loginHint)
        extra.login_hint = options.loginHint;
    const url = buildAuthorizeUrl(publishableKey, redirectUri, extra, pkce);
    const width = 480;
    const height = 700;
    const left = Math.round(window.screenX + (window.outerWidth - width) / 2);
    const top = Math.round(window.screenY + (window.outerHeight - height) / 2);
    const popup = window.open(url, 't3k_load_tone', `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no,status=no,resizable=yes,scrollbars=yes`);
    sessionStorage.removeItem('t3k_popup_mode');
    return popup;
}
/**
 * **Load Tone Flow (Popup, model_id variant)** — Open TONE3000 in a popup to
 * authenticate and load a tone resolved from a specific model. Optional
 * `gears`, `format`, or `architecture` apply if the user browses for a replacement.
 */
export async function startLoadToneFlowPopupByModelId(publishableKey, redirectUri, modelId, options) {
    sessionStorage.setItem('t3k_popup_mode', '1');
    const pkce = await buildPkceParams();
    const extra = { prompt: 'load_tone', model_id: String(modelId) };
    if (options?.gears)
        extra.gears = options.gears;
    if (options?.format)
        extra.format = options.format;
    if (options?.menubar)
        extra.menubar = 'true';
    if (options?.architecture)
        extra.architecture = options.architecture.toString();
    if (options?.loginHint)
        extra.login_hint = options.loginHint;
    const url = buildAuthorizeUrl(publishableKey, redirectUri, extra, pkce);
    const width = 480;
    const height = 700;
    const left = Math.round(window.screenX + (window.outerWidth - width) / 2);
    const top = Math.round(window.screenY + (window.outerHeight - height) / 2);
    const popup = window.open(url, 't3k_load_tone', `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no,status=no,resizable=yes,scrollbars=yes`);
    sessionStorage.removeItem('t3k_popup_mode');
    return popup;
}
/**
 * **Load Model Flow** — Send the user to TONE3000 to authenticate and load a specific model.
 *
 * Use this when your app has a `model_id` and wants to load that exact model.
 * Unlike the Load Tone flow, if the model is inaccessible, TONE3000 redirects
 * back to your app with `error=access_denied` rather than offering a replacement.
 * Your callback handler must check for this error.
 */
export async function startLoadModelFlow(publishableKey, redirectUri, modelId) {
    const pkce = await buildPkceParams();
    window.location.href = buildAuthorizeUrl(publishableKey, redirectUri, { prompt: 'load_model', model_id: String(modelId) }, pkce);
}
/**
 * **Standard Flow** — Send the user to TONE3000 to connect their account.
 *
 * Use this when your app wants long-lived access to the TONE3000 API without
 * having the user browse or select a tone during auth. After connecting, your
 * app can fetch any tone by ID using the access token.
 */
export async function startStandardFlow(publishableKey, redirectUri, options) {
    const pkce = await buildPkceParams();
    const extra = {};
    if (options?.loginHint)
        extra.login_hint = options.loginHint;
    window.location.href = buildAuthorizeUrl(publishableKey, redirectUri, extra, pkce);
}
/**
 * **LAN-relay Flow** — For headless devices on a LAN. The "device" (here, the
 * laptop's Vite dev server) opens an HTTP listener at an RFC1918 address; the
 * user scans a QR with their phone, completes auth in the phone browser, and
 * the OAuth code lands at the device's LAN listener via tone3000's bridge.
 *
 * This helper only generates the authorize URL — actually receiving the
 * callback requires a real LAN listener (see vite-plugin-lan-bridge.ts in this
 * repo for the dev-time implementation, or your device firmware in
 * production). PKCE state is stored in sessionStorage as with the other
 * flows; pair this call with `exchangeCode()` once the listener captures
 * code+state.
 *
 * @param lanCallbackUri  The redirect_uri the device's listener will receive.
 *                        Must be `http://` to RFC1918 / link-local
 *                        (10/8, 172.16-31, 192.168/16, 169.254/16).
 */
export async function startLanRelayFlow(publishableKey, lanCallbackUri) {
    const pkce = await buildPkceParams();
    const authorizeUrl = buildAuthorizeUrl(publishableKey, lanCallbackUri, {}, pkce);
    return { authorizeUrl, state: pkce.state };
}
/**
 * Exchange an authorization code for tokens. Used by `handleOAuthCallback`
 * (URL-driven callbacks) and by the LAN-relay demo (callbacks that arrive via
 * the LAN listener and are forwarded to the React UI by the dev plugin).
 *
 * Verifies that `returnedState` matches the value `buildPkceParams()` stored
 * in sessionStorage, then redeems the code with the verifier. The PKCE
 * values are cleared from sessionStorage regardless of outcome.
 */
export async function exchangeCode(publishableKey, redirectUri, code, returnedState) {
    const storedState = sessionStorage.getItem('t3k_state');
    const codeVerifier = sessionStorage.getItem('t3k_code_verifier');
    sessionStorage.removeItem('t3k_state');
    sessionStorage.removeItem('t3k_code_verifier');
    if (returnedState !== storedState)
        return { ok: false, error: 'state_mismatch' };
    if (!codeVerifier)
        return { ok: false, error: 'missing_verifier' };
    const res = await fetch(`${T3K_API}/api/v1/oauth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
            grant_type: 'authorization_code',
            code,
            code_verifier: codeVerifier,
            redirect_uri: redirectUri,
            client_id: publishableKey,
        }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        return { ok: false, error: err.error ?? 'token_exchange_failed' };
    }
    const data = await res.json();
    return {
        ok: true,
        tokens: {
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            expires_at: Date.now() + data.expires_in * 1000,
        },
    };
}
// ─── Callback handler ─────────────────────────────────────────────────────────
/**
 * Handle the OAuth callback after TONE3000 redirects back to your app.
 *
 * Call this once when your callback page loads and detects a `?code=` or
 * `?error=` query parameter. It verifies the state, exchanges the code for
 * tokens, and returns a typed result object.
 *
 * Always check `result.ok` before using the tokens. A `result.ok === false`
 * with `error === 'access_denied'` is expected for the Load Model flow when
 * the model is private — handle it by showing the user an appropriate error UI.
 */
export async function handleOAuthCallback(publishableKey, redirectUri) {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const error = params.get('error');
    const returnedState = params.get('state');
    const toneId = params.get('tone_id') ?? undefined;
    const modelId = params.get('model_id') ?? undefined;
    const canceled = params.get('canceled') === 'true';
    const storedState = sessionStorage.getItem('t3k_state');
    const codeVerifier = sessionStorage.getItem('t3k_code_verifier');
    // Clean up PKCE state regardless of outcome
    sessionStorage.removeItem('t3k_state');
    sessionStorage.removeItem('t3k_code_verifier');
    // Verify state to prevent CSRF
    if (returnedState !== storedState) {
        return { ok: false, error: 'state_mismatch' };
    }
    // User closed without signing in — no code to exchange
    if (canceled && !code) {
        return { ok: false, error: 'canceled' };
    }
    // Access denied — e.g. model is private and user clicked "Back"
    if (error) {
        return { ok: false, error };
    }
    if (!code || !codeVerifier) {
        return { ok: false, error: 'missing_code' };
    }
    const res = await fetch(`${T3K_API}/api/v1/oauth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
            grant_type: 'authorization_code',
            code,
            code_verifier: codeVerifier,
            redirect_uri: redirectUri,
            client_id: publishableKey,
        }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        return { ok: false, error: err.error ?? 'token_exchange_failed' };
    }
    const data = await res.json();
    const tokens = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_at: Date.now() + data.expires_in * 1000,
    };
    return { ok: true, tokens, toneId, modelId, ...(canceled ? { canceled: true } : {}) };
}
// ─── Search query building ────────────────────────────────────────────────────
/**
 * Serialize SearchTonesParams into the query string /api/v1/tones/search
 * expects. Exported so a UI can preview the exact request it's about to make
 * without re-deriving the separator rules.
 *
 * gears, sizes, tags and makes are underscore-separated. creators is
 * comma-separated: usernames may contain an underscore, so the API can't use
 * one as a delimiter there. Callers pass plain arrays and never see this.
 */
export function buildSearchTonesQuery(params) {
    const qs = new URLSearchParams();
    if (params?.query)
        qs.set('query', params.query);
    if (params?.page)
        qs.set('page', String(params.page));
    if (params?.pageSize)
        qs.set('page_size', String(params.pageSize));
    if (params?.sort)
        qs.set('sort', params.sort);
    if (params?.gears?.length)
        qs.set('gears', params.gears.join('_'));
    if (params?.format)
        qs.set('format', params.format);
    if (params?.sizes?.length)
        qs.set('sizes', params.sizes.join('_'));
    if (params?.tags?.length)
        qs.set('tags', params.tags.join('_'));
    if (params?.makes?.length)
        qs.set('makes', params.makes.join('_'));
    if (params?.creators?.length)
        qs.set('creators', params.creators.join(','));
    if (params?.architecture != null)
        qs.set('architecture', String(params.architecture));
    return qs;
}
// ─── Token refresh ────────────────────────────────────────────────────────────
/** Exchange a refresh token for a new access token. */
export async function refreshTokens(refreshToken, publishableKey) {
    const res = await fetch(`${T3K_API}/api/v1/oauth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
            grant_type: 'refresh_token',
            refresh_token: refreshToken,
            client_id: publishableKey,
        }),
    });
    if (!res.ok)
        throw new Error('Token refresh failed');
    const data = await res.json();
    return {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_at: Date.now() + data.expires_in * 1000,
    };
}
// ─── Authenticated API client ─────────────────────────────────────────────────
const STORAGE_KEY = 't3k_tokens';
/**
 * T3KClient — Authenticated API client with automatic token refresh.
 *
 * Create one instance at module scope. Tokens are stored in sessionStorage
 * by default — they survive page refreshes within a tab but are cleared when
 * the tab closes. For cross-session persistence without re-auth, store the
 * refresh token server-side and call POST /api/v1/oauth/token on page load.
 *
 * @param publishableKey - Your `t3k_pub_` key (same as `client_id` in OAuth)
 * @param onAuthRequired - Called when tokens are missing or expired beyond refresh.
 *                         Typically you'd call startStandardFlow() here to silently
 *                         re-authenticate (the user won't see a login screen if
 *                         they still have an active TONE3000 session).
 */
export class T3KClient {
    publishableKey;
    onAuthRequired;
    refreshPromise = null;
    constructor(publishableKey, onAuthRequired) {
        this.publishableKey = publishableKey;
        this.onAuthRequired = onAuthRequired;
    }
    setTokens(tokens) {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    }
    getTokens() {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
    }
    clearTokens() {
        sessionStorage.removeItem(STORAGE_KEY);
    }
    isConnected() {
        return this.getTokens() !== null;
    }
    async getAccessToken() {
        const tokens = this.getTokens();
        if (!tokens) {
            this.onAuthRequired();
            throw new Error('Not authenticated');
        }
        // Proactively refresh 60 s before expiry to avoid mid-request failures
        if (Date.now() > tokens.expires_at - 60_000) {
            if (!this.refreshPromise) {
                this.refreshPromise = refreshTokens(tokens.refresh_token, this.publishableKey)
                    .then((t) => { this.setTokens(t); this.refreshPromise = null; return t; })
                    .catch((err) => {
                    this.clearTokens();
                    this.refreshPromise = null;
                    this.onAuthRequired();
                    throw err;
                });
            }
            return (await this.refreshPromise).access_token;
        }
        return tokens.access_token;
    }
    /** Make an authenticated request to the TONE3000 API. */
    async fetch(path, init) {
        const token = await this.getAccessToken();
        const res = await globalThis.fetch(`${T3K_API}${path}`, {
            ...init,
            headers: { ...init?.headers, Authorization: `Bearer ${token}` },
        });
        // Retry once on 401 — handles expiry race conditions between refresh check and request
        if (res.status === 401) {
            const stored = this.getTokens();
            if (stored) {
                this.setTokens({ ...stored, expires_at: 0 }); // force a refresh on next call
                const retryToken = await this.getAccessToken();
                return globalThis.fetch(`${T3K_API}${path}`, {
                    ...init,
                    headers: { ...init?.headers, Authorization: `Bearer ${retryToken}` },
                });
            }
        }
        return res;
    }
    // ── Resource methods ──────────────────────────────────────────────────────────
    /** Get the authenticated user's profile. */
    async getUser() {
        const res = await this.fetch('/api/v1/user');
        if (!res.ok)
            throw new Error(`getUser failed: ${res.status}`);
        return res.json();
    }
    /**
     * Get a tone by ID. Returns tone metadata only — models are not embedded.
     * To get download URLs, call `listModels(tone.id)` after fetching the tone.
     */
    async getTone(id) {
        const res = await this.fetch(`/api/v1/tones/${id}`);
        if (!res.ok)
            throw new Error(`getTone failed: ${res.status}`);
        return res.json();
    }
    /** Get a model by ID. */
    async getModel(id) {
        const res = await this.fetch(`/api/v1/models/${id}`);
        if (!res.ok)
            throw new Error(`getModel failed: ${res.status}`);
        return res.json();
    }
    /** Search and filter the TONE3000 tone catalog. */
    async searchTones(params) {
        const res = await this.fetch(`/api/v1/tones/search?${buildSearchTonesQuery(params)}`);
        if (!res.ok)
            throw new Error(`searchTones failed: ${res.status}`);
        return res.json();
    }
    /** Get tones created by the authenticated user. */
    async listCreatedTones(params) {
        const qs = new URLSearchParams();
        if (params?.page)
            qs.set('page', String(params.page));
        if (params?.pageSize)
            qs.set('page_size', String(params.pageSize));
        const res = await this.fetch(`/api/v1/tones/created?${qs}`);
        if (!res.ok)
            throw new Error(`listCreatedTones failed: ${res.status}`);
        return res.json();
    }
    /** Get tones favorited by the authenticated user. */
    async listFavoritedTones(params) {
        const qs = new URLSearchParams();
        if (params?.page)
            qs.set('page', String(params.page));
        if (params?.pageSize)
            qs.set('page_size', String(params.pageSize));
        const res = await this.fetch(`/api/v1/tones/favorited?${qs}`);
        if (!res.ok)
            throw new Error(`listFavoritedTones failed: ${res.status}`);
        return res.json();
    }
    /** List models for a tone. */
    async listModels(toneId, params) {
        const qs = new URLSearchParams();
        qs.set('tone_id', String(toneId));
        if (params?.page)
            qs.set('page', String(params.page));
        if (params?.pageSize)
            qs.set('page_size', String(params.pageSize));
        if (params?.architecture != null)
            qs.set('architecture', String(params.architecture));
        const res = await this.fetch(`/api/v1/models?${qs}`);
        if (!res.ok)
            throw new Error(`listModels failed: ${res.status}`);
        return res.json();
    }
    /** Get public users, sortable by activity metrics. */
    async listUsers(params) {
        const qs = new URLSearchParams();
        if (params?.sort)
            qs.set('sort', params.sort);
        if (params?.page)
            qs.set('page', String(params.page));
        if (params?.pageSize)
            qs.set('page_size', String(params.pageSize));
        if (params?.query)
            qs.set('query', params.query);
        const res = await this.fetch(`/api/v1/users?${qs}`);
        if (!res.ok)
            throw new Error(`listUsers failed: ${res.status}`);
        return res.json();
    }
    /**
     * Download a model file and trigger a browser file download.
     * The `model_url` from the API must be fetched with Bearer auth — use this
     * method rather than calling fetch(model_url) directly.
     */
    async downloadModel(modelUrl, name) {
        // Strip the base URL so client.fetch() can prepend T3K_API + auth header
        const path = modelUrl.replace(T3K_API, '');
        const res = await this.fetch(path);
        if (!res.ok)
            throw new Error(`Download failed: ${res.status}`);
        // Use the extension from the storage URL with a human-readable name
        const storageFilename = new URL(modelUrl).pathname.split('/').pop() ?? '';
        const ext = storageFilename.includes('.') ? '.' + storageFilename.split('.').pop() : '';
        const sanitized = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        const filename = sanitized + ext;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement('a'), { href: url, download: filename });
        a.click();
        URL.revokeObjectURL(url);
    }
}

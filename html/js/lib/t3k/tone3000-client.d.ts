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
import type { User, Tone, Model, PublicUser, PaginatedResponse, SearchTonesParams, ListModelsParams, ListCreatedTonesParams, ListFavoritedTonesParams, ListUsersParams } from './types';
export interface T3KTokens {
    access_token: string;
    refresh_token: string;
    /** Unix timestamp (ms) when the access token expires. */
    expires_at: number;
}
/** Result of handleOAuthCallback(). Always check `ok` before using fields. */
export type OAuthCallbackResult = {
    ok: true;
    tokens: T3KTokens;
    toneId?: string;
    modelId?: string;
    canceled?: boolean;
} | {
    ok: false;
    error: string;
};
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
export declare function startSelectFlow(publishableKey: string, redirectUri: string, options?: {
    gears?: string;
    format?: string;
    menubar?: boolean;
    loginHint?: string;
    architecture?: number;
    preview?: boolean;
}): Promise<void>;
/**
 * **Select Flow (Popup)** — Open TONE3000 tone browsing and selection in a popup window.
 *
 * Same as `startSelectFlow` but opens in a popup. The user stays on your app while
 * browsing TONE3000. When a tone is selected, the popup relays the result back via
 * `postMessage` or `BroadcastChannel` — handle it with `handleOAuthCallbackFromPopup`.
 * Supports the same optional `gears`, `format`, `architecture`, and `menubar`
 * as `startSelectFlow`.
 */
export declare function startSelectFlowPopup(publishableKey: string, redirectUri: string, options?: {
    gears?: string;
    format?: string;
    menubar?: boolean;
    loginHint?: string;
    architecture?: number;
    preview?: boolean;
}): Promise<Window | null>;
/**
 * Handle an OAuth callback relayed from a select popup.
 *
 * Pass events from both a `message` listener and a `BroadcastChannel('t3k_oauth')`
 * listener to this function. Returns `null` if the event is not a TONE3000 callback.
 * Verifies state, exchanges the code for tokens, and returns the same result shape
 * as `handleOAuthCallback`.
 */
export declare function handleOAuthCallbackFromPopup(publishableKey: string, redirectUri: string, event: MessageEvent): Promise<OAuthCallbackResult | null>;
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
export declare function startLoadToneFlow(publishableKey: string, redirectUri: string, toneId: number | string, options?: {
    gears?: string;
    format?: string;
    menubar?: boolean;
    loginHint?: string;
    architecture?: number;
}): Promise<void>;
/**
 * **Load Tone Flow (Popup)** — Open TONE3000 in a popup to authenticate and load a specific tone.
 *
 * Same as `startLoadToneFlow` but opens in a popup. When the flow completes, the
 * popup relays the result back via `postMessage` or `BroadcastChannel` — handle it
 * with `handleOAuthCallbackFromPopup`. Any `gears`, `format`, or `architecture`
 * filters you pass are applied if the user needs to browse for a replacement tone.
 */
export declare function startLoadToneFlowPopup(publishableKey: string, redirectUri: string, toneId: number | string, options?: {
    gears?: string;
    format?: string;
    menubar?: boolean;
    loginHint?: string;
    architecture?: number;
}): Promise<Window | null>;
/**
 * **Load Tone Flow (Popup, model_id variant)** — Open TONE3000 in a popup to
 * authenticate and load a tone resolved from a specific model. Optional
 * `gears`, `format`, or `architecture` apply if the user browses for a replacement.
 */
export declare function startLoadToneFlowPopupByModelId(publishableKey: string, redirectUri: string, modelId: number | string, options?: {
    gears?: string;
    format?: string;
    menubar?: boolean;
    loginHint?: string;
    architecture?: number;
}): Promise<Window | null>;
/**
 * **Load Model Flow** — Send the user to TONE3000 to authenticate and load a specific model.
 *
 * Use this when your app has a `model_id` and wants to load that exact model.
 * Unlike the Load Tone flow, if the model is inaccessible, TONE3000 redirects
 * back to your app with `error=access_denied` rather than offering a replacement.
 * Your callback handler must check for this error.
 */
export declare function startLoadModelFlow(publishableKey: string, redirectUri: string, modelId: number | string): Promise<void>;
/**
 * **Standard Flow** — Send the user to TONE3000 to connect their account.
 *
 * Use this when your app wants long-lived access to the TONE3000 API without
 * having the user browse or select a tone during auth. After connecting, your
 * app can fetch any tone by ID using the access token.
 */
export declare function startStandardFlow(publishableKey: string, redirectUri: string, options?: {
    loginHint?: string;
}): Promise<void>;
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
export declare function startLanRelayFlow(publishableKey: string, lanCallbackUri: string): Promise<{
    authorizeUrl: string;
    state: string;
}>;
/**
 * Exchange an authorization code for tokens. Used by `handleOAuthCallback`
 * (URL-driven callbacks) and by the LAN-relay demo (callbacks that arrive via
 * the LAN listener and are forwarded to the React UI by the dev plugin).
 *
 * Verifies that `returnedState` matches the value `buildPkceParams()` stored
 * in sessionStorage, then redeems the code with the verifier. The PKCE
 * values are cleared from sessionStorage regardless of outcome.
 */
export declare function exchangeCode(publishableKey: string, redirectUri: string, code: string, returnedState: string): Promise<OAuthCallbackResult>;
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
export declare function handleOAuthCallback(publishableKey: string, redirectUri: string): Promise<OAuthCallbackResult>;
/**
 * Serialize SearchTonesParams into the query string /api/v1/tones/search
 * expects. Exported so a UI can preview the exact request it's about to make
 * without re-deriving the separator rules.
 *
 * gears, sizes, tags and makes are underscore-separated. creators is
 * comma-separated: usernames may contain an underscore, so the API can't use
 * one as a delimiter there. Callers pass plain arrays and never see this.
 */
export declare function buildSearchTonesQuery(params?: SearchTonesParams): URLSearchParams;
/** Exchange a refresh token for a new access token. */
export declare function refreshTokens(refreshToken: string, publishableKey: string): Promise<T3KTokens>;
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
export declare class T3KClient {
    private readonly publishableKey;
    private readonly onAuthRequired;
    private refreshPromise;
    constructor(publishableKey: string, onAuthRequired: () => void);
    setTokens(tokens: T3KTokens): void;
    getTokens(): T3KTokens | null;
    clearTokens(): void;
    isConnected(): boolean;
    private getAccessToken;
    /** Make an authenticated request to the TONE3000 API. */
    fetch(path: string, init?: RequestInit): Promise<Response>;
    /** Get the authenticated user's profile. */
    getUser(): Promise<User>;
    /**
     * Get a tone by ID. Returns tone metadata only — models are not embedded.
     * To get download URLs, call `listModels(tone.id)` after fetching the tone.
     */
    getTone(id: number | string): Promise<Tone>;
    /** Get a model by ID. */
    getModel(id: number | string): Promise<Model>;
    /** Search and filter the TONE3000 tone catalog. */
    searchTones(params?: SearchTonesParams): Promise<PaginatedResponse<Tone>>;
    /** Get tones created by the authenticated user. */
    listCreatedTones(params?: ListCreatedTonesParams): Promise<PaginatedResponse<Tone>>;
    /** Get tones favorited by the authenticated user. */
    listFavoritedTones(params?: ListFavoritedTonesParams): Promise<PaginatedResponse<Tone>>;
    /** List models for a tone. */
    listModels(toneId: number | string, params?: ListModelsParams): Promise<PaginatedResponse<Model>>;
    /** Get public users, sortable by activity metrics. */
    listUsers(params?: ListUsersParams): Promise<PaginatedResponse<PublicUser>>;
    /**
     * Download a model file and trigger a browser file download.
     * The `model_url` from the API must be fetched with Bearer auth — use this
     * method rather than calling fetch(model_url) directly.
     */
    downloadModel(modelUrl: string, name: string): Promise<void>;
}

/**
 * Cookie names for the httpOnly JWT relay (docs/07_FRONTEND_ARCHITECTURE.md:
 * "app/api/ -- Next.js route handlers (auth cookie relay only)"). Internal
 * users only -- public respondents never get a session (docs/10).
 *
 * JWTs live only in httpOnly cookies, never in localStorage/JS-readable
 * storage, so an XSS in the SPA can't exfiltrate them. Client code never
 * reads or attaches the token itself -- every internal API call goes
 * through /api/proxy/[...path], which reads the cookie server-side and
 * attaches the Authorization header there.
 */
export const ACCESS_COOKIE = "drp_access";
export const REFRESH_COOKIE = "drp_refresh";

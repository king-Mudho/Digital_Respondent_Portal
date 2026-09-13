"""
Throttling for public, unauthenticated respondent-facing endpoints.

docs/10_INVITATION_AND_CONSENT.md: "validation attempts are throttled per
token (to blunt guessing of the manual entry code) and per source IP." This
class handles the per-token half; DRF's built-in AnonRateThrottle (see
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]) handles per-IP.
"""

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Per-IP throttle for internal sign-in only.

    Sign-in previously shared the generic "anon" bucket with every public
    respondent endpoint. A research team behind one office NAT is a single
    IP, so ordinary staff logins competed for the same 30/minute allowance
    as respondent token validation -- and DRF's 429 surfaced in the UI as
    "Invalid username or password", which sends someone hunting for a
    password problem that doesn't exist. Its own scope keeps brute-force
    protection without that cross-talk.
    """

    scope = "login"


class PerTokenThrottle(SimpleRateThrottle):
    scope = "invitation_token"

    def get_cache_key(self, request, view):
        token = request.query_params.get("t") or request.data.get("token")
        if not token:
            # Not a token-bearing request (e.g. an internal JWT-authed
            # endpoint) -- nothing for this throttle to key on.
            return None
        return self.cache_format % {"scope": self.scope, "ident": token}

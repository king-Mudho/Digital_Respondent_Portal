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


class RespondentRateThrottle(AnonRateThrottle):
    """Per-IP throttle for the public respondent journey.

    These endpoints previously used the generic `anon` scope at 30/minute.
    One respondent's journey costs roughly 8-10 calls (validate, eligibility,
    consent, PROIT profile and one verify per fact, Kobo redirect or
    appointment). Zimbabwe's mobile networks put many subscribers behind
    shared carrier-grade NAT addresses, so when an invitation wave goes out
    on WhatsApp, three or four genuine respondents on one carrier IP in the
    same minute were enough to be told to wait -- mid-consent. Found
    2026-09-14 when the E2E suite reproduced exactly that.

    Raising it costs little: link tokens are 32 random bytes and not
    guessable at any rate, and manual codes are 8 characters from 36 symbols
    (2.8 trillion combinations) -- finding one of ~400 valid codes from a
    single IP takes on the order of a century even at this rate. The code
    space is the real defence; PerTokenThrottle still caps attempts per
    token independently of this.
    """

    scope = "respondent"


class PerTokenThrottle(SimpleRateThrottle):
    scope = "invitation_token"

    def get_cache_key(self, request, view):
        token = request.query_params.get("t") or request.data.get("token")
        if not token:
            # Not a token-bearing request (e.g. an internal JWT-authed
            # endpoint) -- nothing for this throttle to key on.
            return None
        return self.cache_format % {"scope": self.scope, "ident": token}

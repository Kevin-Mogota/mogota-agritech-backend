from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    HISTORICAL DEV SHORTCUT — no longer used (see settings.REST_FRAMEWORK, which
    now points at the real rest_framework.authentication.SessionAuthentication
    instead of this class). Kept only so old references/notes in this codebase
    still resolve; real CSRF protection is implemented via CsrfCookieView +
    the frontend sending X-CSRFToken, per Django's standard CSRF flow.
    """
    def enforce_csrf(self, request):
        return

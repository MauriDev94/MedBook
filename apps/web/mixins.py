"""View mixins for the web UI: role checks and rate limiting."""

import math

from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import render

from apps.core.roles import is_admin, is_doctor, is_patient


class RoleRequiredMixin(UserPassesTestMixin):
    """Let the view run only for users that pass one of `role_predicates`.

    Anonymous visitors are redirected to LOGIN_URL with `?next=`; signed-in
    users with another role get 403 (UserPassesTestMixin's behaviour). The
    predicates are the ones the DRF permission classes use.
    """

    role_predicates = ()

    def test_func(self):
        return any(predicate(self.request.user) for predicate in self.role_predicates)


class PatientRequiredMixin(RoleRequiredMixin):
    role_predicates = (is_patient,)


class StaffRequiredMixin(RoleRequiredMixin):
    """Doctors and admins."""

    role_predicates = (is_doctor, is_admin)


class ThrottleMixin:
    """Rate limit POST requests with the API's DRF throttle classes.

    Same scopes, rates and cache keys as the API (apps.core.throttling), so
    a web form and its API endpoint share one budget per IP. Rejected
    requests get the `web/throttled.html` page with status 429.
    """

    throttle_classes = ()

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            throttles = [throttle_class() for throttle_class in self.throttle_classes]
            waits = [t.wait() for t in throttles if not t.allow_request(request, self)]
            if waits:
                return self.throttled(request, waits)
        return super().dispatch(request, *args, **kwargs)

    def throttled(self, request, waits):
        seconds = max(1, math.ceil(max(wait or 0 for wait in waits)))
        # The page talks in minutes: the sign-up window is an hour long
        context = {"minutes": math.ceil(seconds / 60)}
        response = render(request, "web/throttled.html", context, status=429)
        response["Retry-After"] = str(seconds)
        return response

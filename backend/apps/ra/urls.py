from django.urls import path

from .views import AccountStatusView, AdministerView, AssignKIIView, AssignMainView, CallersView, CreditOverrideView, MyWorkView, TeamView

app_name = "ra"

urlpatterns = [
    path("ra/my-work/", MyWorkView.as_view(), name="my-work"),
    path("ra/team/", TeamView.as_view(), name="team"),
    path("ra/assign-main/", AssignMainView.as_view(), name="assign-main"),
    path("ra/assign-kii/", AssignKIIView.as_view(), name="assign-kii"),
    path("ra/accounts/<int:pk>/status/", AccountStatusView.as_view(), name="account-status"),
    path("ra/callers/", CallersView.as_view(), name="callers"),
    path("ra/credits/<int:pk>/override/", CreditOverrideView.as_view(), name="credit-override"),
    path("ra/administer/<str:kind>/<str:ident>/", AdministerView.as_view(), name="administer"),
]

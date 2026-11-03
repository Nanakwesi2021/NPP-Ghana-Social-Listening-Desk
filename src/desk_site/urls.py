from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="desk:overview", permanent=False)),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name="desk/password_change.html",
        success_url=reverse_lazy("password_change_done"),
    ), name="password_change"),
    path("password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="desk/password_change_done.html",
    ), name="password_change_done"),
    path("admin/", admin.site.urls),
    path("", include("desk.urls")),
]

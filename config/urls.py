from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.urls import include, path

admin.site.site_header = "ArabNutriVision administration"
admin.site.site_title = "ArabNutriVision"

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("nutrition.urls")),
]

if settings.STATIC_SITE:   # static edition: sign-in handled by Supabase in the browser
    from nutrition import static_views
    urlpatterns = [path("accounts/login/", static_views.login, name="login"),
                   path("accounts/logout/", static_views.login, name="logout")] + [
        u for u in urlpatterns if getattr(u, "name", None) not in ("login", "logout")]

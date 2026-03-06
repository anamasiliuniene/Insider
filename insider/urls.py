from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.home, name="home"),

# authentication
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="insider/login.html"),
        name="login"
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    path("sessions/", views.session_list, name="sessions"),

    path("sessions/check-in/<int:address_id>/", views.check_in, name="check_in"),
    path("sessions/check-out/<int:session_id>/", views.check_out, name="check_out"),

    path("sessions/<int:session_id>/edit/", views.edit_session, name="edit_session"),
    path("sessions/<int:session_id>/approve/", views.approve_session, name="approve_session"),
    path("sessions/<int:session_id>/reject/", views.reject_session, name="reject_session"),
]
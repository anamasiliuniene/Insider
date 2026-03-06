from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.home, name="home"),

    # Authentication
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="insider/login.html"),
        name="login"
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # Password reset (optional)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="insider/password_reset.html"),
        name="password_reset"
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="insider/password_reset_done.html"),
        name="password_reset_done"
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="insider/password_reset_confirm.html"),
        name="password_reset_confirm"
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="insider/password_reset_complete.html"),
        name="password_reset_complete"
    ),

    # Sessions
    path("sessions/", views.session_list, name="sessions"),
    path("sessions/check-in/<int:address_id>/", views.check_in, name="check_in"),
    path("sessions/check-out/<int:session_id>/", views.check_out, name="check_out"),
    path("sessions/<int:session_id>/edit/", views.edit_session, name="edit_session"),
    path("sessions/<int:session_id>/approve/", views.approve_session, name="approve_session"),
    path("sessions/<int:session_id>/reject/", views.reject_session, name="reject_session"),

    # Invitations
    # Invitations
    path("invitations/", views.invitations_list, name="invitations_list"),
    path("invitations/send/", views.send_invitation, name="send_invitation"),
    path("invitations/accept/<str:token>/", views.accept_invite, name="accept_invite"),
    path("invitations/<int:invitation_id>/resend/", views.resend_invitation, name="resend_invitation"),
]
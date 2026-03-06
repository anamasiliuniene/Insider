from datetime import date, datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import login
from .models import Address, SessionApproval, WorkSession
from django.shortcuts import render
from .forms import InvitationSendForm, InvitationAcceptForm
import secrets
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from .models import Invitation


@login_required
def send_invitation(request):
    if request.method == 'POST':
        form = InvitationSendForm(request.POST)
        if form.is_valid():
            invitation = form.save(commit=False)
            # Generate a unique token
            invitation.token = secrets.token_urlsafe(32)
            invitation.accepted = False
            invitation.save()

            # Build invitation link
            invite_url = request.build_absolute_uri(
                reverse('accept_invite', args=[invitation.token])
            )

            # Send the email
            send_mail(
                'You are invited to Worktime App',
                f'Click here to set up your account: {invite_url}',
                'noreply@yourapp.com',
                [invitation.email],
            )

            return redirect('invitations_list')
    else:
        form = InvitationSendForm()  # ✅ correct form here
    return render(request, 'insider/send_invitation.html', {'form': form})

@login_required
def resend_invitation(request, invitation_id):
    # Only managers/admins can resend
    if request.user.role not in ["manager", "admin"]:
        return redirect("sessions")

    invitation = get_object_or_404(Invitation, id=invitation_id)

    # Build invitation link
    invite_url = request.build_absolute_uri(
        reverse('accept_invite', args=[invitation.token])
    )

    # Send the email again
    send_mail(
        'You are invited to Worktime App',
        f'Click here to set up your account: {invite_url}',
        'noreply@yourapp.com',
        [invitation.email],
    )

    return redirect('invitations_list')

def accept_invite(request, token):
    invitation = get_object_or_404(Invitation, token=token, accepted=False)
    if request.method == 'POST':
        form = InvitationAcceptForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = invitation.email
            user.role = 'worker'  # default role for invited users
            user.save()
            invitation.accepted = True
            invitation.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = InvitationAcceptForm()  # ✅ correct form here
    return render(request, 'insider/invite.html', {'form': form})


@login_required
def invitations_list(request):
    # Only allow managers/admins
    if request.user.role not in ["manager", "admin"]:
        return redirect("sessions")

    invitations = Invitation.objects.all().order_by("-created_at")

    context = {
        "invitations": invitations,
    }
    return render(request, "insider/invitations_list.html", context)

# ----------------------
# Home / Landing Redirect
# ----------------------
def home(request):
    """
    Redirect users based on role:
    - Worker or Manager → session list
    - Others (e.g., admin) → Django admin
    """
    if request.user.role in ["worker", "manager"]:
        return redirect("sessions")
    return redirect("/admin/")


# ----------------------
# Check In / Check Out
# ----------------------
@login_required
def check_in(request, address_id):
    """
    Start a new work session for the logged-in worker.
    Prevents multiple active sessions for the same worker.
    """
    address = get_object_or_404(Address, id=address_id)

    # Prevent multiple active sessions
    active_session = WorkSession.objects.filter(
        worker=request.user, check_out__isnull=True
    ).first()
    if active_session:
        return redirect("sessions")

    WorkSession.objects.create(
        worker=request.user,
        address=address,
        check_in=timezone.now(),
        check_in_latitude=request.POST.get("latitude"),
        check_in_longitude=request.POST.get("longitude"),
    )

    return redirect("sessions")


@login_required
def check_out(request, session_id):
    """
    End an active session.
    Only allowed if session belongs to the user (or editable via can_edit)
    and check_out is not already set.
    """
    session = get_object_or_404(WorkSession, id=session_id)

    if not session.can_edit(request.user) or session.check_out is not None:
        return redirect("sessions")

    session.check_out = timezone.now()
    session.check_out_latitude = request.POST.get("latitude")
    session.check_out_longitude = request.POST.get("longitude")
    session.last_edited_by = request.user
    session.save()

    return redirect("sessions")


# ----------------------
# Session List
# ----------------------
@login_required
def session_list(request):
    user = request.user

    # Filter sessions based on user role
    if user.role == "worker":
        sessions = WorkSession.objects.filter(worker=user).order_by("-check_in")
    elif user.role in ["manager", "admin"]:
        sessions = WorkSession.objects.all().order_by("-check_in")
    else:
        sessions = WorkSession.objects.none()

    # Active session for the user
    active_session = sessions.filter(check_out__isnull=True, worker=user).first()

    # Available addresses to check in
    available_addresses = Address.objects.all()

    # Prepare session data with row class
    session_data = []
    for s in sessions:
        # Determine highlight class
        if active_session and s.id == active_session.id:
            cls = "table-primary"
        elif s.status == "verified":
            cls = "table-success"
        elif s.status == "pending":
            cls = "table-warning"
        elif s.status == "rejected":
            cls = "table-danger"
        else:
            cls = ""

        session_data.append({
            "id": s.id,
            "worker": s.worker,
            "address": s.address,
            "check_in": s.check_in,
            "check_out": s.check_out,
            "duration": s.duration,
            "payment": s.payment,
            "status": s.status,
            "last_edited_at": s.last_edited_at,
            "last_edited_by": s.last_edited_by,
            "row_class": cls,  # <<< precomputed class
        })

    context = {
        "sessions": session_data,
        "active_session": active_session,
        "available_addresses": available_addresses,
        "allowed_roles": ["manager", "admin"],  # for buttons
    }

    return render(request, "insider/sessions.html", context)


# ----------------------
# Edit Session
# ----------------------
@login_required
def edit_session(request, session_id):
    """
    Edit check_in and check_out times for a session.
    Only editable if can_edit(user) is True.
    """
    session = get_object_or_404(WorkSession, id=session_id)

    if not session.can_edit(request.user):
        return redirect("sessions")

    if request.method == "POST":
        check_in = request.POST.get("check_in")
        check_out = request.POST.get("check_out")

        # Convert ISO strings to aware datetime
        if check_in:
            session.check_in = timezone.make_aware(
                datetime.fromisoformat(check_in)
            )
        if check_out:
            session.check_out = timezone.make_aware(
                datetime.fromisoformat(check_out)
            )

        session.last_edited_by = request.user
        session.save()

        return redirect("sessions")

    return render(request, "insider/edit_session.html", {"session": session})


# ----------------------
# Approve / Reject Session
# ----------------------
@login_required
def approve_session(request, session_id):
    """
    Manager or admin approves a session.
    """
    session = get_object_or_404(WorkSession, id=session_id)

    if request.user.role not in ["manager", "admin"]:
        return redirect("sessions")

    SessionApproval.objects.update_or_create(
        session=session,
        defaults={"manager": request.user, "approved": True},
    )

    return redirect("sessions")


@login_required
def reject_session(request, session_id):
    """
    Manager or admin rejects a session.
    """
    session = get_object_or_404(WorkSession, id=session_id)

    if request.user.role not in ["manager", "admin"]:
        return redirect("sessions")

    SessionApproval.objects.update_or_create(
        session=session,
        defaults={"manager": request.user, "approved": False},
    )

    return redirect("sessions")



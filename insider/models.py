from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = [
        ("worker", "Worker"),
        ("manager", "Manager"),
        ("admin", "Admin"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="worker")


class Object(models.Model):
    address = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    allowed_radius = models.FloatField(default=100)  # meters for GPS validation

    def __str__(self):
        return self.address


class WorkSessionQuerySet(models.QuerySet):
    def by_week(self, week_start_date):
        week_start = timezone.make_aware(datetime.combine(week_start_date, time.min))
        week_end = week_start + timedelta(days=7)
        return self.filter(check_in__gte=week_start, check_in__lt=week_end)

    def by_address(self, address):
        return self.filter(object__address__icontains=address)

    def by_worker(self, worker):
        return self.filter(worker=worker)


class WorkSession(models.Model):
    STATUS_CHOICES = [
        ("verified", "Verified"),
        ("pending", "Pending approval"),
        ("rejected", "Rejected")
    ]

    worker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    object = models.ForeignKey(Object, on_delete=models.CASCADE, related_name="sessions")

    check_in = models.DateTimeField()
    check_in_latitude = models.FloatField()
    check_in_longitude = models.FloatField()

    check_out = models.DateTimeField(null=True, blank=True)
    check_out_latitude = models.FloatField(null=True, blank=True)
    check_out_longitude = models.FloatField(null=True, blank=True)

    breaks = models.JSONField(default=list, blank=True)
    # Example: [{"start": "2026-03-05T10:30:00", "end": "2026-03-05T10:45:00"}]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    last_edited_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="edited_sessions")
    last_edited_at = models.DateTimeField(null=True, blank=True)

    hourly_rate = models.DecimalField(max_digits=7, decimal_places=2, default=15.0)  # for payment calculation
    objects = WorkSessionQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["worker", "check_in"]),
            models.Index(fields=["object", "check_in"]),
            models.Index(fields=["status"]),
        ]

    @staticmethod
    def _parse_break_dt(value):
        parsed = datetime.fromisoformat(value)
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    @property
    def status_color(self):
        return {
            "verified": "green",
            "pending": "yellow",
            "rejected": "red",
        }.get(self.status, "gray")

    def can_edit(self, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.role == "admin":
            return True
        return user.role == "worker" and user.pk == self.worker_id

    def clean(self):
        errors = {}

        if self.worker_id and self.worker.role != "worker":
            errors["worker"] = "Work session must belong to a user with worker role."

        if self.check_out and self.check_out < self.check_in:
            errors["check_out"] = "Check-out must be later than check-in."

        if self.last_edited_by_id and not self.can_edit(self.last_edited_by):
            errors["last_edited_by"] = "Only the session owner worker or admin can edit this session."

        break_seconds = 0
        for idx, chunk in enumerate(self.breaks):
            if not isinstance(chunk, dict) or "start" not in chunk or "end" not in chunk:
                errors["breaks"] = "Each break must include start and end ISO datetime values."
                break
            try:
                start = self._parse_break_dt(chunk["start"])
                end = self._parse_break_dt(chunk["end"])
            except (TypeError, ValueError):
                errors["breaks"] = f"Break #{idx + 1} has invalid datetime format."
                break
            if end <= start:
                errors["breaks"] = f"Break #{idx + 1} end must be after start."
                break
            if start < self.check_in:
                errors["breaks"] = f"Break #{idx + 1} starts before check-in."
                break
            if self.check_out and end > self.check_out:
                errors["breaks"] = f"Break #{idx + 1} ends after check-out."
                break
            break_seconds += (end - start).total_seconds()

        if self.check_out:
            total_seconds = (self.check_out - self.check_in).total_seconds()
            if break_seconds > total_seconds:
                errors["breaks"] = "Break duration cannot exceed total session duration."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.last_edited_by_id:
            self.last_edited_at = timezone.now()
            if self.last_edited_by.role == "worker":
                self.status = "pending"
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def duration(self):
        """Total hours minus breaks"""
        if not self.check_out:
            return Decimal("0")
        total_seconds = Decimal(str((self.check_out - self.check_in).total_seconds()))
        for b in self.breaks:
            start = self._parse_break_dt(b["start"])
            end = self._parse_break_dt(b["end"])
            total_seconds -= Decimal(str((end - start).total_seconds()))
        if total_seconds <= 0:
            return Decimal("0")
        return total_seconds / Decimal("3600")

    @property
    def payment(self):
        return (self.duration * self.hourly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class SessionApproval(models.Model):
    session = models.OneToOneField(WorkSession, on_delete=models.CASCADE, related_name="approval")
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name="approvals")
    approved = models.BooleanField(null=True)  # None = pending, True = approved, False = rejected
    reviewed_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    def clean(self):
        errors = {}
        if self.manager.role not in {"manager", "admin"}:
            errors["manager"] = "Only manager or admin can review sessions."
        if self.session.worker_id == self.manager_id:
            errors["manager"] = "Manager cannot review their own session."
        if self.approved is not None and self.session.status != "pending":
            errors["session"] = "Only pending sessions can be approved or rejected."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.approved is True:
            self.session.status = "verified"
        elif self.approved is False:
            self.session.status = "rejected"
        else:
            self.session.status = "pending"
        self.session.save(update_fields=["status"])
        return super().save(*args, **kwargs)

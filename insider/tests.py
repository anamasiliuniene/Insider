from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Object, SessionApproval, User, WorkSession


class WorkSessionRulesTests(TestCase):
    def setUp(self):
        self.worker = User.objects.create_user(username="worker1", password="x", role="worker")
        self.other_worker = User.objects.create_user(username="worker2", password="x", role="worker")
        self.manager = User.objects.create_user(username="manager1", password="x", role="manager")
        self.admin = User.objects.create_user(username="admin1", password="x", role="admin")
        self.obj = Object.objects.create(
            address="Main St 1",
            latitude=54.0,
            longitude=25.0,
            allowed_radius=100,
        )

    def create_session(self, worker):
        check_in = timezone.now() - timedelta(hours=8)
        check_out = timezone.now()
        return WorkSession.objects.create(
            worker=worker,
            object=self.obj,
            check_in=check_in,
            check_out=check_out,
            check_in_latitude=54.0,
            check_in_longitude=25.0,
            check_out_latitude=54.0,
            check_out_longitude=25.0,
            breaks=[],
            hourly_rate=Decimal("20.00"),
        )

    def test_worker_can_edit_own_session_and_becomes_pending(self):
        session = self.create_session(self.worker)
        session.last_edited_by = self.worker
        session.save()
        session.refresh_from_db()
        self.assertEqual(session.status, "pending")
        self.assertIsNotNone(session.last_edited_at)

    def test_worker_cannot_edit_other_workers_session(self):
        session = self.create_session(self.worker)
        session.last_edited_by = self.other_worker
        with self.assertRaises(ValidationError):
            session.save()

    def test_admin_can_edit_any_session(self):
        session = self.create_session(self.worker)
        session.last_edited_by = self.admin
        session.status = "verified"
        session.save()
        session.refresh_from_db()
        self.assertEqual(session.last_edited_by, self.admin)
        self.assertEqual(session.status, "verified")

    def test_manager_approval_changes_status(self):
        session = self.create_session(self.worker)
        session.status = "pending"
        session.save()
        approval = SessionApproval.objects.create(session=session, manager=self.manager, approved=True)
        session.refresh_from_db()
        self.assertTrue(approval.approved)
        self.assertEqual(session.status, "verified")

    def test_non_manager_cannot_approve(self):
        session = self.create_session(self.worker)
        session.status = "pending"
        session.save()
        with self.assertRaises(ValidationError):
            SessionApproval.objects.create(session=session, manager=self.other_worker, approved=True)

    def test_payment_is_decimal(self):
        session = self.create_session(self.worker)
        self.assertEqual(session.payment, Decimal("160.00"))

    def test_status_color_mapping(self):
        session = self.create_session(self.worker)
        session.status = "verified"
        self.assertEqual(session.status_color, "green")
        session.status = "pending"
        self.assertEqual(session.status_color, "yellow")
        session.status = "rejected"
        self.assertEqual(session.status_color, "red")

"""اختبارات عقود الصيانة السنوية وزياراتها."""

from datetime import date, timedelta

import database as db


def _contract(session, client, **kw):
    kw.setdefault("start_date", date.today() - timedelta(days=30))
    kw.setdefault("end_date", date.today() + timedelta(days=335))
    kw.setdefault("status", "Active")
    kw.setdefault("visits_per_year", 4)
    c = db.Contract(client_id=client.id, **kw)
    session.add(c)
    session.commit()
    return c


class TestContractStatus:

    def test_active_within_period(self, session, client):
        assert _contract(session, client).is_active is True

    def test_not_active_after_end(self, session, client):
        c = _contract(session, client,
                      start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))
        assert c.is_active is False
        assert c.alert_level == "expired"

    def test_not_active_before_start(self, session, client):
        c = _contract(session, client,
                      start_date=date.today() + timedelta(days=10),
                      end_date=date.today() + timedelta(days=375))
        assert c.is_active is False

    def test_cancelled_is_never_active(self, session, client):
        c = _contract(session, client, status="Cancelled")
        assert c.is_active is False

    def test_cancelled_shows_inactive_not_valid(self, session, client):
        """
        عقد ملغى كان يظهر "ساري" في خانة السريان لأن alert_level أعاد
        "none" — وهي القيمة نفسها التي تعني "ضمن المدة".
        """
        c = _contract(session, client, status="Cancelled")
        assert c.alert_level == "inactive"

    def test_suspended_is_inactive(self, session, client):
        assert _contract(session, client, status="Suspended").alert_level == "inactive"

    def test_soon_within_60_days(self, session, client):
        c = _contract(session, client,
                      start_date=date.today() - timedelta(days=300),
                      end_date=date.today() + timedelta(days=45))
        assert c.alert_level == "soon"
        assert c.days_remaining == 45

    def test_unknown_without_end_date(self, session, client):
        assert _contract(session, client, end_date=None).alert_level == "unknown"

    def test_boundary_60_days_is_soon(self, session, client):
        c = _contract(session, client, end_date=date.today() + timedelta(days=60))
        assert c.alert_level == "soon"

    def test_boundary_61_days_is_normal(self, session, client):
        c = _contract(session, client, end_date=date.today() + timedelta(days=61))
        assert c.alert_level == "none"


class TestVisits:

    def test_counts_only_done_visits(self, session, client):
        c = _contract(session, client, visits_per_year=4)
        session.add_all([
            db.ContractVisit(contract_id=c.id, visit_date=date.today(), status="Done"),
            db.ContractVisit(contract_id=c.id, visit_date=date.today(), status="Scheduled"),
            db.ContractVisit(contract_id=c.id, visit_date=date.today(), status="Missed"),
        ])
        session.commit()
        session.refresh(c)
        assert c.visits_done == 1
        assert c.visits_remaining == 3

    def test_remaining_never_negative(self, session, client):
        """تنفيذ زيارات أكثر من المتعاقد عليه يجب ألا ينتج رقمًا سالبًا."""
        c = _contract(session, client, visits_per_year=1)
        session.add_all([
            db.ContractVisit(contract_id=c.id, visit_date=date.today(), status="Done"),
            db.ContractVisit(contract_id=c.id, visit_date=date.today(), status="Done"),
        ])
        session.commit()
        session.refresh(c)
        assert c.visits_remaining == 0

    def test_next_visit_is_earliest_scheduled(self, session, client):
        c = _contract(session, client)
        session.add_all([
            db.ContractVisit(contract_id=c.id,
                             visit_date=date.today() + timedelta(days=60),
                             status="Scheduled"),
            db.ContractVisit(contract_id=c.id,
                             visit_date=date.today() + timedelta(days=20),
                             status="Scheduled"),
            db.ContractVisit(contract_id=c.id,
                             visit_date=date.today() + timedelta(days=5),
                             status="Done"),
        ])
        session.commit()
        session.refresh(c)
        assert c.next_visit_date == date.today() + timedelta(days=20)

    def test_scheduled_past_date_is_overdue(self, session, client):
        c = _contract(session, client)
        v = db.ContractVisit(contract_id=c.id,
                             visit_date=date.today() - timedelta(days=5),
                             status="Scheduled")
        session.add(v)
        session.commit()
        assert v.is_overdue is True

    def test_done_visit_never_overdue(self, session, client):
        c = _contract(session, client)
        v = db.ContractVisit(contract_id=c.id,
                             visit_date=date.today() - timedelta(days=100),
                             status="Done")
        session.add(v)
        session.commit()
        assert v.is_overdue is False

    def test_deleting_contract_removes_its_visits(self, session, client):
        c = _contract(session, client)
        session.add(db.ContractVisit(contract_id=c.id, visit_date=date.today()))
        session.commit()
        session.delete(c)
        session.commit()
        assert session.query(db.ContractVisit).count() == 0


class TestContractFinance:

    def test_totals_from_linked_invoices(self, session, client, project):
        c = _contract(session, client, value=120000)
        session.add_all([
            db.Invoice(project_id=project.id, contract_id=c.id,
                       amount=30000, status="Paid"),
            db.Invoice(project_id=project.id, contract_id=c.id,
                       amount=20000, status="Unpaid"),
            db.Invoice(project_id=project.id, amount=99999,
                       status="Unpaid"),  # غير مرتبطة بالعقد
        ])
        session.commit()
        session.refresh(c)
        assert c.total_invoiced == 50000
        assert c.total_unpaid == 20000

    def test_deleting_contract_keeps_invoice(self, session, client, project):
        """حذف العقد يجب ألا يحذف فواتيره — خطر فقدان بيانات مالية."""
        c = _contract(session, client)
        inv = db.Invoice(project_id=project.id, contract_id=c.id, amount=5000)
        session.add(inv)
        session.commit()

        inv.contract_id = None      # كما تفعل الواجهة قبل الحذف
        session.delete(c)
        session.commit()

        assert session.query(db.Invoice).count() == 1
        assert session.query(db.Invoice).first().contract_id is None


class TestContractQueries:

    def test_expiring_excludes_cancelled(self, session, client):
        _contract(session, client, status="Cancelled",
                  end_date=date.today() - timedelta(days=5))
        _contract(session, client, status="Active",
                  end_date=date.today() + timedelta(days=10))
        result = db.expiring_contracts(session)
        assert len(result) == 1
        assert result[0].status == "Active"

    def test_search_by_number_and_status(self, session, client):
        _contract(session, client, contract_number="AMC-2026-001",
                  title="عقد برج المملكة")
        _contract(session, client, contract_number="AMC-2026-002",
                  title="عقد الواحة", status="Cancelled")

        assert len(db.search_contracts(session, text="001")) == 1
        assert len(db.search_contracts(session, text="الواحة")) == 1
        assert len(db.search_contracts(session, status="Active")) == 1
        assert len(db.search_contracts(session)) == 2

    def test_due_visits_ignores_far_future(self, session, client):
        c = _contract(session, client)
        session.add_all([
            db.ContractVisit(contract_id=c.id,
                             visit_date=date.today() + timedelta(days=5),
                             status="Scheduled"),
            db.ContractVisit(contract_id=c.id,
                             visit_date=date.today() + timedelta(days=200),
                             status="Scheduled"),
        ])
        session.commit()
        assert len(db.due_contract_visits(session, within_days=30)) == 1

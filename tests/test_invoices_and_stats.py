"""اختبارات الفواتير، إحصاءات لوحة المعلومات، وسلامة العلاقات."""

from datetime import date, timedelta

import database as db


class TestInvoices:

    def test_unpaid_past_due_is_overdue(self, session, project):
        i = db.Invoice(project_id=project.id, amount=1000, status="Unpaid",
                       due_date=date.today() - timedelta(days=1))
        session.add(i)
        session.commit()
        assert i.is_overdue is True

    def test_paid_invoice_never_overdue(self, session, project):
        """فاتورة مسدَّدة يجب ألا تظهر متأخرة مهما مضى على تاريخها."""
        i = db.Invoice(project_id=project.id, amount=1000, status="Paid",
                       due_date=date.today() - timedelta(days=365))
        session.add(i)
        session.commit()
        assert i.is_overdue is False

    def test_no_due_date_is_not_overdue(self, session, project):
        i = db.Invoice(project_id=project.id, amount=1000,
                       status="Unpaid", due_date=None)
        session.add(i)
        session.commit()
        assert i.is_overdue is False

    def test_project_totals(self, session, project):
        session.add_all([
            db.Invoice(project_id=project.id, amount=5000, status="Paid"),
            db.Invoice(project_id=project.id, amount=3000, status="Unpaid"),
        ])
        session.commit()
        session.refresh(project)
        assert project.total_invoiced == 8000
        assert project.total_unpaid == 3000

    def test_none_amount_does_not_crash_totals(self, session, project):
        """قيمة فارغة يجب أن تُعامل كصفر لا أن تُسقط الحساب."""
        session.add(db.Invoice(project_id=project.id, amount=None, status="Unpaid"))
        session.commit()
        session.refresh(project)
        assert project.total_invoiced == 0


class TestRelationships:

    def test_deleting_client_keeps_projects(self, session, client, project):
        """
        حذف العميل كان يحذف مشاريعه وفواتيرها ومعداتها بصمت (cascade).
        الآن يبقى المشروع ويصبح بلا عميل.
        """
        session.delete(client)
        session.commit()
        p = session.query(db.Project).first()
        assert p is not None
        assert p.client_id is None
        assert p.client_name == ""

    def test_deleting_project_removes_equipment_and_invoices(self, session, project):
        session.add_all([
            db.Equipment(project_id=project.id, name="طفاية"),
            db.Invoice(project_id=project.id, amount=1000),
        ])
        session.commit()
        session.delete(project)
        session.commit()
        assert session.query(db.Equipment).count() == 0
        assert session.query(db.Invoice).count() == 0


class TestDashboardStats:

    def test_stats_include_contract_keys(self, session):
        stats = db.dashboard_stats(session)
        for key in ("total_contracts", "active_contracts", "contracts_value",
                    "contract_alerts", "due_visits", "equipment_alerts",
                    "total_invoiced", "total_unpaid", "overdue_invoices"):
            assert key in stats, f"مفتاح مفقود: {key}"

    def test_empty_database_does_not_crash(self, session):
        """قاعدة فارغة تمامًا — أول تشغيل للبرنامج."""
        stats = db.dashboard_stats(session)
        assert stats["total_projects"] == 0
        assert stats["total_invoiced"] == 0
        assert stats["contracts_value"] == 0

    def test_value_counts_active_contracts_only(self, session, client):
        session.add_all([
            db.Contract(client_id=client.id, status="Active", value=100000,
                        start_date=date.today() - timedelta(days=10),
                        end_date=date.today() + timedelta(days=300)),
            db.Contract(client_id=client.id, status="Cancelled", value=500000,
                        start_date=date.today() - timedelta(days=10),
                        end_date=date.today() + timedelta(days=300)),
            db.Contract(client_id=client.id, status="Active", value=200000,
                        start_date=date(2025, 1, 1),
                        end_date=date(2025, 12, 31)),  # منتهٍ
        ])
        session.commit()
        stats = db.dashboard_stats(session)
        assert stats["total_contracts"] == 3
        assert stats["active_contracts"] == 1
        assert stats["contracts_value"] == 100000


class TestSearch:

    def test_search_projects_by_text_and_status(self, session, client):
        session.add_all([
            db.Project(name="برج المملكة", client_id=client.id, status="Install"),
            db.Project(name="مجمع الواحة", client_id=client.id, status="Design"),
        ])
        session.commit()
        assert len(db.search_projects(session, text="المملكة")) == 1
        assert len(db.search_projects(session, status="Design")) == 1
        assert len(db.search_projects(session)) == 2

    def test_special_characters_are_escaped(self, session, client):
        """
        الرمز % في LIKE يعني "أي شيء". بلا تهريب يعيد البحث عن "%" كل
        السجلات بدل السجل الذي يحويه فعلًا.
        """
        session.add_all([
            db.Project(name="مشروع 100% إنجاز", client_id=client.id),
            db.Project(name="مشروع عادي", client_id=client.id),
        ])
        session.commit()
        assert len(db.search_projects(session, text="100%")) == 1

"""اختبارات منطق المعدات والفحص الدوري."""

from datetime import date, timedelta

import database as db


def _eq(session, project, **kw):
    e = db.Equipment(project_id=project.id, name=kw.pop("name", "طفاية"), **kw)
    session.add(e)
    session.commit()
    return e


class TestInspectionDates:

    def test_next_inspection_is_last_plus_interval(self, session, project):
        e = _eq(session, project,
                last_inspection_date=date(2026, 1, 1), interval_days=180)
        assert e.next_inspection_date == date(2026, 6, 30)

    def test_no_last_inspection_means_no_next_date(self, session, project):
        e = _eq(session, project, last_inspection_date=None, interval_days=180)
        assert e.next_inspection_date is None
        assert e.days_until_due is None


class TestAlertLevel:
    """
    alert_level هو ما يلوّن الشاشة والتقارير ويحدّد ما يظهر للدفاع المدني،
    فأي خلل فيه يعني معدة متأخرة تبدو سليمة.
    """

    def test_overdue_when_past_due(self, session, project):
        e = _eq(session, project,
                last_inspection_date=date.today() - timedelta(days=400),
                interval_days=180)
        assert e.alert_level == "overdue"
        assert e.days_until_due < 0

    def test_soon_within_30_days(self, session, project):
        # فحص قبل 160 يومًا بدورة 180 => يستحق بعد 20 يومًا
        e = _eq(session, project,
                last_inspection_date=date.today() - timedelta(days=160),
                interval_days=180)
        assert e.alert_level == "soon"

    def test_none_when_comfortably_ahead(self, session, project):
        e = _eq(session, project,
                last_inspection_date=date.today(), interval_days=180)
        assert e.alert_level == "none"

    def test_unknown_when_never_inspected(self, session, project):
        """معدة بلا تاريخ فحص أخطر من المتأخرة — يجب ألا تُعامل كسليمة."""
        e = _eq(session, project, last_inspection_date=None)
        assert e.alert_level == "unknown"

    def test_boundary_exactly_30_days_is_soon(self, session, project):
        e = _eq(session, project,
                last_inspection_date=date.today() - timedelta(days=150),
                interval_days=180)
        assert e.days_until_due == 30
        assert e.alert_level == "soon"

    def test_boundary_31_days_is_not_soon(self, session, project):
        e = _eq(session, project,
                last_inspection_date=date.today() - timedelta(days=149),
                interval_days=180)
        assert e.days_until_due == 31
        assert e.alert_level == "none"


class TestUpcomingInspections:

    def test_includes_overdue_soon_and_unknown(self, session, project):
        _eq(session, project, name="متأخرة",
            last_inspection_date=date.today() - timedelta(days=400),
            interval_days=180)
        _eq(session, project, name="قريبة",
            last_inspection_date=date.today() - timedelta(days=160),
            interval_days=180)
        _eq(session, project, name="لم تفحص", last_inspection_date=None)
        _eq(session, project, name="سليمة",
            last_inspection_date=date.today(), interval_days=180)

        names = [e.name for e in db.upcoming_inspections(session)]
        assert "سليمة" not in names
        assert set(names) == {"متأخرة", "قريبة", "لم تفحص"}

    def test_overdue_sorted_first(self, session, project):
        _eq(session, project, name="قريبة",
            last_inspection_date=date.today() - timedelta(days=160),
            interval_days=180)
        _eq(session, project, name="متأخرة",
            last_inspection_date=date.today() - timedelta(days=400),
            interval_days=180)
        assert db.upcoming_inspections(session)[0].name == "متأخرة"

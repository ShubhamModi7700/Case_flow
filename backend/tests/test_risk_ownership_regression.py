from types import SimpleNamespace
from app.services.risk import calculate_case_risk


def _case(**overrides):
    values = dict(title='Umfirmierung', description='', management_summary='',
                  risk_reason='', next_action='Anschreiben prüfen', status='New',
                  primary_deadline=None, category='Other', responsible_person='',
                  financial_amount=None, tasks=[])
    values.update(overrides)
    return SimpleNamespace(**values)


def test_missing_owner_alone_not_high():
    result = calculate_case_risk(_case())
    assert result.level != 'High'
    assert 'Fallverantwortung' in result.reason


def test_actual_deadline_still_high():
    from datetime import date, timedelta
    result = calculate_case_risk(_case(primary_deadline=date.today() - timedelta(days=1)))
    assert result.level == 'High'


def test_owner_does_not_override_manual_risk():
    case = _case(risk='Low')
    from app.services.risk import refresh_risk_suggestion
    refresh_risk_suggestion(case)
    assert case.risk == 'Low'

from app.services.department_service import DepartmentService
from app.services.risk_service import RiskService


def test_negated_red_flags_are_not_marked_high_risk():
    result = RiskService().detect_risk(
        "头痛三天，但没有胸痛、无呼吸困难，也没有肢体无力",
        "3天",
    )

    assert result.risk_level == "LOW"
    assert set(result.negated_signals) >= {"胸痛", "呼吸困难", "肢体无力"}


def test_one_negation_applies_to_a_coordinated_symptom_list():
    result = RiskService().detect_risk("头痛，但没有胸痛、呼吸困难和肢体无力", "3天")

    assert result.risk_level == "LOW"
    assert set(result.negated_signals) >= {"胸痛", "呼吸困难", "肢体无力"}


def test_adversative_clause_ends_negation_scope():
    result = RiskService().detect_risk("没有胸痛，但现在呼吸困难")

    assert result.risk_level == "HIGH"
    assert "呼吸困难" in result.matched_signals


def test_chest_pain_with_dyspnea_is_high_risk():
    result = RiskService().detect_risk("胸痛并伴有呼吸困难和冷汗", "半小时")

    assert result.risk_level == "HIGH"
    assert "胸痛" in result.matched_signals
    assert "呼吸困难" in result.matched_signals


def test_sudden_severe_headache_is_high_risk():
    result = RiskService().detect_risk("刚刚突发剧烈头痛，说话不清")

    assert result.risk_level == "HIGH"
    assert "突发剧烈头痛" in result.matched_signals


def test_long_running_symptom_is_medium_risk():
    result = RiskService().detect_risk("最近总是胃不舒服", "持续两周")

    assert result.risk_level == "MEDIUM"


def test_department_rule_ignores_negated_symptoms():
    result = DepartmentService().recommend_department("头痛，但没有胸痛")

    assert result.primary_department == "神经内科"
    assert "心内科" not in result.alternative_departments

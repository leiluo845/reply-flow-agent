from __future__ import annotations

from decimal import Decimal

import pytest

from replyflow.roi import ROI_PRESETS, ROIInputs, calculate_roi


def _inputs(**overrides: object) -> ROIInputs:
    values: dict[str, object] = {
        "monthly_volume": 1000,
        "l1_share": Decimal("0.4"),
        "l2_share": Decimal("0.4"),
        "l3_share": Decimal("0.2"),
        "manual_minutes_per_email": Decimal("8"),
        "ai_minutes_l1": Decimal("0.3"),
        "ai_minutes_l2": Decimal("2.5"),
        "ai_minutes_l3": Decimal("5"),
        "labor_cost_per_hour": Decimal("25"),
        "model_cost_per_email": Decimal("0.02"),
        "maintenance_cost_monthly": Decimal("300"),
        "error_probability": Decimal("0.01"),
        "expected_loss_per_error": Decimal("40"),
    }
    values.update(overrides)
    return ROIInputs(**values)  # type: ignore[arg-type]


def test_calculate_roi_uses_decimal_and_accounts_for_residual_manual_emails() -> None:
    result = calculate_roi(_inputs())

    assert result.l1_emails == Decimal("400.0")
    assert result.l2_emails == Decimal("400.0")
    assert result.l3_emails == Decimal("200.0")
    assert result.manual_hours == Decimal("133.3333333333333333333333333")
    assert result.ai_hours == Decimal("35.33333333333333333333333333")
    assert result.hours_saved.quantize(Decimal("0.01")) == Decimal("98.00")
    assert result.labor_saved_value == Decimal("2450.00")
    assert result.model_cost == Decimal("20.00")
    assert result.maintenance_cost == Decimal("300.00")
    assert result.risk_cost == Decimal("400.00")
    assert result.net_benefit == Decimal("1730.00")
    assert result.per_email_net_contribution == Decimal("2.03")
    assert result.break_even_volume == 148


def test_zero_volume_has_zero_variable_cost_and_no_break_even_requirement() -> None:
    result = calculate_roi(_inputs(monthly_volume=0))

    assert result.net_benefit == Decimal("-300.00")
    assert result.model_cost == Decimal("0.00")
    assert result.risk_cost == Decimal("0.00")
    assert result.break_even_volume == 148


def test_unrouted_share_stays_manual_and_is_not_counted_as_savings() -> None:
    result = calculate_roi(
        _inputs(
            l1_share=Decimal("0.2"),
            l2_share=Decimal("0"),
            l3_share=Decimal("0"),
        )
    )

    # 200 routed emails save 7.7 minutes each; 800 residual emails remain manual.
    assert result.hours_saved.quantize(Decimal("0.01")) == Decimal("25.67")


def test_non_positive_per_email_contribution_has_no_break_even_volume() -> None:
    result = calculate_roi(
        _inputs(
            labor_cost_per_hour=Decimal("1"),
            model_cost_per_email=Decimal("10"),
            maintenance_cost_monthly=Decimal("300"),
        )
    )

    assert result.per_email_net_contribution < Decimal("0")
    assert result.break_even_volume is None


def test_higher_l3_share_or_review_time_reduces_net_benefit() -> None:
    baseline = calculate_roi(_inputs())
    high_l3 = calculate_roi(
        _inputs(l1_share=Decimal("0.2"), l2_share=Decimal("0.2"), l3_share=Decimal("0.6"))
    )
    slower_review = calculate_roi(_inputs(ai_minutes_l3=Decimal("8")))

    assert high_l3.net_benefit < baseline.net_benefit
    assert slower_review.net_benefit < baseline.net_benefit


@pytest.mark.parametrize(
    "field,value",
    [
        ("monthly_volume", -1),
        ("l1_share", Decimal("1.1")),
        ("error_probability", Decimal("1.1")),
        ("manual_minutes_per_email", Decimal("-0.1")),
    ],
)
def test_invalid_assumptions_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        ROIInputs(**{**_inputs().__dict__, field: value})  # type: ignore[arg-type]


def test_presets_are_complete_and_ordered_for_comparison() -> None:
    assert list(ROI_PRESETS) == ["保守", "基准", "乐观"]
    results = {name: calculate_roi(inputs) for name, inputs in ROI_PRESETS.items()}
    assert results["保守"].net_benefit < results["基准"].net_benefit < results["乐观"].net_benefit

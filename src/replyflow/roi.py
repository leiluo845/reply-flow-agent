from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


MONEY_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ROIInputs:
    """Monthly sensitivity-analysis assumptions; not observed business results."""

    monthly_volume: int
    l1_share: Decimal
    l2_share: Decimal
    l3_share: Decimal
    manual_minutes_per_email: Decimal
    ai_minutes_l1: Decimal
    ai_minutes_l2: Decimal
    ai_minutes_l3: Decimal
    labor_cost_per_hour: Decimal
    model_cost_per_email: Decimal
    maintenance_cost_monthly: Decimal
    error_probability: Decimal
    expected_loss_per_error: Decimal

    def __post_init__(self) -> None:
        if self.monthly_volume < 0:
            raise ValueError("monthly_volume must be non-negative")
        shares = (self.l1_share, self.l2_share, self.l3_share)
        if any(value < ZERO or value > Decimal("1") for value in shares):
            raise ValueError("processing shares must be between 0 and 1")
        if sum(shares, ZERO) > Decimal("1"):
            raise ValueError("processing shares cannot exceed 1")
        non_negative = (
            self.manual_minutes_per_email,
            self.ai_minutes_l1,
            self.ai_minutes_l2,
            self.ai_minutes_l3,
            self.labor_cost_per_hour,
            self.model_cost_per_email,
            self.maintenance_cost_monthly,
            self.error_probability,
            self.expected_loss_per_error,
        )
        if any(value < ZERO for value in non_negative):
            raise ValueError("ROI assumptions cannot be negative")
        if self.error_probability > Decimal("1"):
            raise ValueError("error_probability must be between 0 and 1")


@dataclass(frozen=True)
class ROIResult:
    l1_emails: Decimal
    l2_emails: Decimal
    l3_emails: Decimal
    manual_hours: Decimal
    ai_hours: Decimal
    hours_saved: Decimal
    labor_saved_value: Decimal
    model_cost: Decimal
    maintenance_cost: Decimal
    risk_cost: Decimal
    net_benefit: Decimal
    per_email_net_contribution: Decimal
    break_even_volume: int | None


def calculate_roi(inputs: ROIInputs) -> ROIResult:
    volume = Decimal(inputs.monthly_volume)
    l1 = volume * inputs.l1_share
    l2 = volume * inputs.l2_share
    l3 = volume * inputs.l3_share
    manual_hours = volume * inputs.manual_minutes_per_email / Decimal("60")
    ai_hours = (
        l1 * inputs.ai_minutes_l1 + l2 * inputs.ai_minutes_l2 + l3 * inputs.ai_minutes_l3
    ) / Decimal("60")
    # Only the AI-routed share creates savings. Any residual share remains on
    # the original manual path and therefore must not be counted as saved time.
    processed_share = inputs.l1_share + inputs.l2_share + inputs.l3_share
    processed_manual_hours = volume * processed_share * inputs.manual_minutes_per_email / Decimal("60")
    hours_saved = processed_manual_hours - ai_hours
    labor_saved_value = _money(hours_saved * inputs.labor_cost_per_hour)
    model_cost = _money(volume * inputs.model_cost_per_email)
    maintenance_cost = _money(inputs.maintenance_cost_monthly)
    risk_cost = _money(volume * inputs.error_probability * inputs.expected_loss_per_error)
    net_benefit = _money(labor_saved_value - model_cost - maintenance_cost - risk_cost)
    per_email_net = _money(
        (
            inputs.l1_share * (inputs.manual_minutes_per_email - inputs.ai_minutes_l1)
            + inputs.l2_share * (inputs.manual_minutes_per_email - inputs.ai_minutes_l2)
            + inputs.l3_share * (inputs.manual_minutes_per_email - inputs.ai_minutes_l3)
        )
        / Decimal("60")
        * inputs.labor_cost_per_hour
        - inputs.model_cost_per_email
        - inputs.error_probability * inputs.expected_loss_per_error
    )
    if per_email_net <= ZERO:
        break_even_volume = None
    else:
        break_even_volume = int(
            (inputs.maintenance_cost_monthly / per_email_net).to_integral_value(rounding=ROUND_CEILING)
        )
    return ROIResult(
        l1_emails=l1,
        l2_emails=l2,
        l3_emails=l3,
        manual_hours=manual_hours,
        ai_hours=ai_hours,
        hours_saved=hours_saved,
        labor_saved_value=labor_saved_value,
        model_cost=model_cost,
        maintenance_cost=maintenance_cost,
        risk_cost=risk_cost,
        net_benefit=net_benefit,
        per_email_net_contribution=per_email_net,
        break_even_volume=break_even_volume,
    )


ROI_PRESETS: dict[str, ROIInputs] = {
    "保守": ROIInputs(
        monthly_volume=3000,
        l1_share=Decimal("0.20"),
        l2_share=Decimal("0.50"),
        l3_share=Decimal("0.30"),
        manual_minutes_per_email=Decimal("8"),
        ai_minutes_l1=Decimal("0.5"),
        ai_minutes_l2=Decimal("4"),
        ai_minutes_l3=Decimal("7"),
        labor_cost_per_hour=Decimal("20"),
        model_cost_per_email=Decimal("0.03"),
        maintenance_cost_monthly=Decimal("500"),
        error_probability=Decimal("0.02"),
        expected_loss_per_error=Decimal("50"),
    ),
    "基准": ROIInputs(
        monthly_volume=3000,
        l1_share=Decimal("0.40"),
        l2_share=Decimal("0.40"),
        l3_share=Decimal("0.20"),
        manual_minutes_per_email=Decimal("8"),
        ai_minutes_l1=Decimal("0.3"),
        ai_minutes_l2=Decimal("2.5"),
        ai_minutes_l3=Decimal("5"),
        labor_cost_per_hour=Decimal("25"),
        model_cost_per_email=Decimal("0.02"),
        maintenance_cost_monthly=Decimal("300"),
        error_probability=Decimal("0.01"),
        expected_loss_per_error=Decimal("40"),
    ),
    "乐观": ROIInputs(
        monthly_volume=3000,
        l1_share=Decimal("0.60"),
        l2_share=Decimal("0.30"),
        l3_share=Decimal("0.10"),
        manual_minutes_per_email=Decimal("8"),
        ai_minutes_l1=Decimal("0.2"),
        ai_minutes_l2=Decimal("1.5"),
        ai_minutes_l3=Decimal("3"),
        labor_cost_per_hour=Decimal("30"),
        model_cost_per_email=Decimal("0.015"),
        maintenance_cost_monthly=Decimal("200"),
        error_probability=Decimal("0.005"),
        expected_loss_per_error=Decimal("30"),
    ),
}

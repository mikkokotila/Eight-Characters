"""What each plan lets an account keep: the caps the store checks when an account asks
for a change (docs/Developer/Accounts.md, Plans). An account's plan is its user
record's `plan` (records.Plan).

Every plan keeps 50 charts with unrestricted couples until plans are sold. Then the basic plan keeps one couple
per saved chart, and pro as many as wanted (the owner, 2026-10-17; #96): this table is
the one place that changes. A cap is checked when a change is asked for, never when
settings are read, so an account whose plan shrinks keeps, and reads, everything it
holds, and adds only within the cap.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from eight_characters.accounts.records import CHART_LIMIT, PLANS, Plan


@dataclass(frozen=True)
class PlanLimits:
    # How many couples one saved chart may be in; None for no cap.
    couples_per_chart: int | None
    # The write allowance, never a constraint on reading retained records.
    charts_per_account: int | None = CHART_LIMIT

    def __post_init__(self) -> None:
        if self.couples_per_chart is not None and (
            type(self.couples_per_chart) is not int or self.couples_per_chart < 1
        ):
            raise ValueError('A plan lets a chart be in one couple at least.')
        if self.charts_per_account is not None and (
            type(self.charts_per_account) is not int or self.charts_per_account < 1
        ):
            raise ValueError('A chart allowance is a positive integer or None.')


UNRESTRICTED: Final = PlanLimits(couples_per_chart=None)

LIMITS: Final[Mapping[Plan, PlanLimits]] = {
    'free': UNRESTRICTED,
    'basic': UNRESTRICTED,
    'pro': UNRESTRICTED,
    'max': UNRESTRICTED,
}


def check_limits(limits: Mapping[Plan, PlanLimits]) -> Mapping[Plan, PlanLimits]:
    """The table, if it names every plan and no other; ValueError otherwise."""
    if set(limits) != set(PLANS):
        raise ValueError(f'The limits must name each plan: {", ".join(PLANS)}.')
    return limits

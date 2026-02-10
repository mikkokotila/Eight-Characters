from dataclasses import dataclass
from datetime import date, datetime, timedelta

from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_TRUE_SOLAR,
    HOUR_BASIS_TRUE_SOLAR,
    ZI_CONVENTION_WHOLE_ZI_23,
    ConventionSettings,
)


STEMS = ('甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸')
BRANCHES = ('子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥')

FIRST_MONTH_STEM_BY_YEAR_STEM_MOD5 = (2, 4, 6, 8, 0)
ZI_HOUR_STEM_BY_DAY_STEM_MOD5 = (0, 2, 4, 6, 8)


@dataclass(frozen=True)
class Pillar:
    stem_idx: int
    branch_idx: int

    def validate_polarity(self) -> None:
        if self.stem_idx % 2 != self.branch_idx % 2:
            raise ValueError(
                f'Polarity violation: stem={self.stem_idx}, branch={self.branch_idx}'
            )


@dataclass(frozen=True)
class DayPillarResult:
    pillar: Pillar
    effective_date: date
    jdn: int
    idx0: int


def gregorian_to_jdn(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + ((153 * m + 2) // 5) + 365 * y + (y // 4) - (y // 100) + (y // 400) - 32045


def day_index_from_jdn(jdn: int) -> int:
    return (jdn - 11) % 60


def year_pillar(civil_year: int, birth_jd_tt: float, lichun_jd_tt: float) -> tuple[Pillar, int]:
    bazi_year = civil_year - 1 if birth_jd_tt < lichun_jd_tt else civil_year
    pillar = Pillar(
        stem_idx=(bazi_year - 4) % 10,
        branch_idx=(bazi_year - 4) % 12,
    )
    pillar.validate_polarity()
    return pillar, bazi_year


def month_branch_index_from_longitude(lambda_apparent_deg: float) -> int:
    lam = lambda_apparent_deg % 360.0
    if 315.0 <= lam < 345.0:
        return 2
    if lam >= 345.0 or lam < 15.0:
        return 3
    if 15.0 <= lam < 45.0:
        return 4
    if 45.0 <= lam < 75.0:
        return 5
    if 75.0 <= lam < 105.0:
        return 6
    if 105.0 <= lam < 135.0:
        return 7
    if 135.0 <= lam < 165.0:
        return 8
    if 165.0 <= lam < 195.0:
        return 9
    if 195.0 <= lam < 225.0:
        return 10
    if 225.0 <= lam < 255.0:
        return 11
    if 255.0 <= lam < 285.0:
        return 0
    return 1


def month_pillar(lambda_apparent_deg: float, year_stem_idx: int) -> Pillar:
    month_branch_idx = month_branch_index_from_longitude(lambda_apparent_deg)
    month_num = (month_branch_idx - 2) % 12
    first_month_stem = FIRST_MONTH_STEM_BY_YEAR_STEM_MOD5[year_stem_idx % 5]
    month_stem_idx = (first_month_stem + month_num) % 10
    pillar = Pillar(stem_idx=month_stem_idx, branch_idx=month_branch_idx)
    pillar.validate_polarity()
    return pillar


def effective_day_date(
    civil_dt_local: datetime,
    tst_dt: datetime,
    conventions: ConventionSettings,
) -> date:
    conventions.validate()
    if conventions.day_boundary_basis == DAY_BOUNDARY_BASIS_TRUE_SOLAR:
        basis_dt = tst_dt
    else:
        basis_dt = civil_dt_local

    result_date = basis_dt.date()
    if conventions.zi_convention == ZI_CONVENTION_WHOLE_ZI_23 and basis_dt.hour == 23:
        result_date += timedelta(days=1)
    return result_date


def day_pillar(
    civil_dt_local: datetime,
    tst_dt: datetime,
    conventions: ConventionSettings,
) -> DayPillarResult:
    day_date = effective_day_date(civil_dt_local, tst_dt, conventions)
    jdn = gregorian_to_jdn(day_date.year, day_date.month, day_date.day)
    idx0 = day_index_from_jdn(jdn)
    pillar = Pillar(
        stem_idx=idx0 % 10,
        branch_idx=idx0 % 12,
    )
    pillar.validate_polarity()
    return DayPillarResult(
        pillar=pillar,
        effective_date=day_date,
        jdn=jdn,
        idx0=idx0,
    )


def hour_branch_index(hour_value: int) -> int:
    if hour_value == 23 or hour_value == 0:
        return 0
    return ((hour_value + 1) // 2) % 12


def hour_pillar(
    day_stem_idx: int,
    civil_dt_local: datetime,
    tst_dt: datetime,
    conventions: ConventionSettings,
) -> Pillar:
    if conventions.hour_basis == HOUR_BASIS_TRUE_SOLAR:
        basis_dt = tst_dt
    else:
        basis_dt = civil_dt_local

    branch_idx = hour_branch_index(basis_dt.hour)
    zi_hour_stem_idx = ZI_HOUR_STEM_BY_DAY_STEM_MOD5[day_stem_idx % 5]
    stem_idx = (zi_hour_stem_idx + branch_idx) % 10
    pillar = Pillar(stem_idx=stem_idx, branch_idx=branch_idx)
    pillar.validate_polarity()
    return pillar

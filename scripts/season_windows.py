"""Reviewed archive-date windows, not proof of competition or model estimate type."""
from datetime import date
from common import DataError, validate_season

# Nonoverlapping archive labels around COVID-delayed seasons. Month-end bounds
# accommodate archive records; they do not label every date as a regular-season game.
ARCHIVE_EXCEPTIONS = {
    '2019-20': ('2019-07-01', '2020-10-31'),
    '2020-21': ('2020-11-01', '2021-07-31'),
    '2021-22': ('2021-08-01', '2022-06-30'),
}


def archive_window(season):
    validate_season(season, 'Regular Season')
    start = int(season[:4])
    lower, upper = ARCHIVE_EXCEPTIONS.get(season, (f'{start}-07-01', f'{start+1}-06-30'))
    return date.fromisoformat(lower), date.fromisoformat(upper)


def validate_archive_date(season, value):
    lower, upper = archive_window(season)
    try:
        stamp = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise DataError('Invalid historical archive date') from exc
    if not lower <= stamp <= upper:
        raise DataError(f'Historical archive date outside reviewed {season} window {lower} to {upper}')
    return stamp

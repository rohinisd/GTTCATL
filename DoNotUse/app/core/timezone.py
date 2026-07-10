"""India Standard Time helpers.

The dashboard is used in Karnataka, India. We store wall-clock IST as naive
datetimes so that the ISO strings sent to the browser (which have no timezone
suffix) are interpreted as local time and display correctly.
"""
from datetime import datetime, timezone, timedelta, date

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Current IST time as a naive datetime (no tzinfo)."""
    return datetime.now(IST).replace(tzinfo=None)


def today_ist() -> date:
    """Current date in IST."""
    return datetime.now(IST).date()

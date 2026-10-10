"""The SEC's structured data set listings and the calendar quarters the panels are keyed by.

Neither the file names nor the hosts are stable enough for a URL template: 13F data sets were
calendar quarters (`2023q4_form13f.zip`) until 2023 and are three-month windows ending in
February, May, August and November since (`01mar2024-31may2024_form13f.zip`), and newer files
moved from `/files/structureddata/` to `/files/datastandardsinnovation/`. So the data set page
is read and every linked file of the wanted kind is taken as listed.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urljoin

import pandas as pd

FORM_13F_SUFFIX = "_form13f.zip"
INSIDER_SUFFIX = "_form345.zip"

_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_QUARTER = re.compile(r"(\d{4})q([1-4])")
_WINDOW = re.compile(r"(\d{2}[a-z]{3}\d{4})-(\d{2}[a-z]{3}\d{4})")


@dataclass(frozen=True)
class DatasetFile:
    """One downloadable data set. `label` is its name without the suffix and keys its stored
    panel; `first_day` and `last_day` bound the filing dates it covers."""

    label: str
    url: str
    first_day: date
    last_day: date


def list_dataset_files(page_html: str, page_url: str, suffix: str) -> list[DatasetFile]:
    """Every file ending in `suffix` linked from a data set page, oldest first."""
    found: dict[str, DatasetFile] = {}
    for href in _HREF.findall(page_html):
        name = href.rsplit("/", 1)[-1]
        if not name.lower().endswith(suffix):
            continue
        label = name[: -len(suffix)].lower()
        bounds = label_bounds(label)
        if bounds is None:
            continue
        found[label] = DatasetFile(label, urljoin(page_url, href), *bounds)
    return sorted(found.values(), key=lambda f: (f.first_day, f.label))


def label_bounds(label: str) -> tuple[date, date] | None:
    """First and last filing date covered by a data set label, or None if it is neither a
    `yyyyqN` quarter nor a `ddmonyyyy-ddmonyyyy` window."""
    if m := _QUARTER.fullmatch(label):
        return quarter_bounds(int(m.group(1)), int(m.group(2)))
    if m := _WINDOW.fullmatch(label):
        first, last = (datetime.strptime(g, "%d%b%Y").replace(tzinfo=UTC).date() for g in m.groups())
        return first, last
    return None


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    first = date(year, 3 * quarter - 2, 1)
    following = date(year + 1, 1, 1) if quarter == 4 else date(year, 3 * quarter + 1, 1)
    return first, following - timedelta(days=1)


def quarter_of(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 3 + 1


def quarter_label(day: date) -> str:
    year, quarter = quarter_of(day)
    return f"{year}q{quarter}"


def quarters_between(first: date, last: date) -> list[tuple[int, int]]:
    """Every calendar quarter touching [first, last], in order."""
    result = []
    year, quarter = quarter_of(first)
    while quarter_bounds(year, quarter)[0] <= last:
        result.append((year, quarter))
        year, quarter = (year + 1, 1) if quarter == 4 else (year, quarter + 1)
    return result


# EDGAR accepts filings until 22:00 Eastern; one accepted after 17:30 carries the next business
# day's filing date, so 22:00 Eastern on its filing date is the latest a filing can have been
# accepted. Data sets give only the date, so that bound stands in for the acceptance time:
# never earlier than the truth, which keeps every point-in-time read free of look-ahead.
_EDGAR_CLOSE_HOUR = 22
_EASTERN = "America/New_York"


def latest_acceptance(filing_date: date) -> pd.Timestamp:
    """The latest UTC instant a filing with this filing date can have been accepted."""
    local = pd.Timestamp(datetime.combine(filing_date, time(_EDGAR_CLOSE_HOUR)))
    return local.tz_localize(_EASTERN).tz_convert("UTC")


def eastern_to_utc(moment: datetime) -> pd.Timestamp:
    return pd.Timestamp(moment).tz_localize(_EASTERN).tz_convert("UTC")


def instant(as_of: date | datetime) -> pd.Timestamp:
    """`as_of` as a UTC instant. A date means its first moment (00:00 UTC), before anything
    accepted that day."""
    if isinstance(as_of, datetime):
        if as_of.tzinfo is None:
            raise ValueError("as_of datetimes must be timezone-aware")
        return pd.Timestamp(as_of).tz_convert("UTC")
    return pd.Timestamp(datetime.combine(as_of, time(0)), tz="UTC")


def parse_sec_date(text: str) -> date:
    """Data set dates are `DD-MON-YYYY` (`14-MAY-2024`)."""
    return datetime.strptime(text.strip(), "%d-%b-%Y").replace(tzinfo=UTC).date()

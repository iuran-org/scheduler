import re
import pytz
from datetime import timedelta


def parse_timezone(timezone_str: str) -> pytz.timezone:
    """
    Parse timezone string yang mendukung format:
    - Nama timezone (Asia/Jakarta)
    - GMT offset (GMT+7, GMT-7)
    - UTC offset (UTC+8, UTC-8)
    """
    offset_pattern = re.compile(r'^(GMT|UTC)([+-])(\d{1,2})$')
    match = offset_pattern.match(timezone_str.replace(" ", ""))

    if match:
        sign = 1 if match.group(2) == "+" else -1
        hours = int(match.group(3))
        offset = timedelta(hours=sign * hours)
        return pytz.FixedOffset(int(offset.total_seconds() / 60))

    try:
        return pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone format: {timezone_str}")

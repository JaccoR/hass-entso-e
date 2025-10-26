import re
from datetime import timedelta


def get_interval_minutes(iso8601_interval: str) -> int:
    """
    Convert an ISO 8601 duration string to total minutes.
    Example: 'PT15M' -> 15
    """

    return int(re.match(r"PT(\d+)M", iso8601_interval).group(1))


def bucket_time(ts, bucket_size):
    """
    Get the bucket time for the interval.

    e.g. for a bucket size of 15 minutes, the time 10:07 would be rounded down to 10:00,
    """
    return ts - timedelta(
        minutes=ts.minute % bucket_size, seconds=ts.second, microseconds=ts.microsecond
    )

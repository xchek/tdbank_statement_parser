from decimal import Decimal

import dateparser
from dateparser import date

DEBIT: str = "debit"
CREDIT: str = "credit"


def get_date(s: str) -> date:
    if parsed := dateparser.parse(s):
        return parsed.date()


def normalize_date(metadata: dict, datestr: str) -> date:
    test_posted_date = get_date(f"{datestr}/{metadata['statement_period_start'].year}")
    if (
        metadata["statement_period_start"]
        <= test_posted_date
        <= metadata["statement_period_end"]
    ):
        return test_posted_date
    else:
        return get_date(f"{datestr}/{metadata['statement_period_start'].year + 1}")


def to_decimal(s: str) -> Decimal:
    return Decimal(s.replace(",", ""))

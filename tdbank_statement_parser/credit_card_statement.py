"""
Parses monthly TD Bank credit card statements / bills (PDF).
"""

import re
from functools import partial

from pydash import py_

from .common import *

default_table_heading = re.compile(
    r"^\s*Activity Date\s{1,}"
    r"Post Date\s{1,}"
    r"Reference Number\s{1,}"
    r"Description\s{1,}"
    r"Amount$"
)

default_table_row = re.compile(
    r"^\s*(?P<activity_date>\w{3} \d+)?\s{4,}"
    r"(?P<post_date>\w{3} \d+)?\s{4,}"
    r"(?P<reference_number>\d+)?\s{4,}"
    r"(?P<description>.*?)\s{4,}"
    r"(?P<amount>[\d\,\.]+)\s*(?P<credit_flag>CR)?$"
)


def normalize_credit_card_statement(
    record: dict, table_name: str, metadata: dict
) -> dict:
    if table_name not in {"Transactions", "Fees", "Interest Charged"}:
        if table_name == "Totals Year to Date":
            record["value"] = to_decimal(record["value"])
        elif table_name == "Interest Charge Calculation":
            record["annual_percentage_rate"] = to_decimal(
                record["annual_percentage_rate"]
            )
            record["balance_subject_to_interest_rate"] = to_decimal(
                record["balance_subject_to_interest_rate"]
            )
            record["interest_charge"] = to_decimal(record["interest_charge"])
        return {k: v for k, v in record.items() if v != None}

    _normalize_date = partial(normalize_date, metadata)

    transaction_type = record["transaction_type"] = (
        CREDIT if record.pop("credit_flag") else DEBIT
    )

    normalize_map = {
        "activity_date": _normalize_date,
        "post_date": _normalize_date,
        "amount": to_decimal,
    }

    result = (
        py_(record)
        .map_values(lambda v, k: normalize_map.get(k, py_.clean)(v) if v else None)
        .value()
    )

    if transaction_type == DEBIT and result.get("amount"):
        result["amount"] *= -1

    return {k: v for k, v in result.items() if v != None}


parse_config = {
    "normalize": normalize_credit_card_statement,
    "metadata_patterns": [
        (
            r"Account Number Ending in\:\s*\d{4}\s+"
            r"(?P<statement_period_start>\w+\s+\d+,?\s+\d+)\s*\-\s*"
            r"(?P<statement_period_end>\w+\s+\d+,?\s+\d+)",
            get_date,
        ),
        (
            r"See reverse for changes to address\s+[A-Z]\s*\d{4}-\d{4}\s*[A-Z]\s*"
            r"(?P<primary_account_number>\d+)\s*\w?\s*$",
            py_.clean,
        ),
        (r"Previous balance +\$(?P<previous_balance>[0-9,.]+)$", to_decimal),
        (r"Payments *[-+]? *\$(?P<payments>[0-9,.]+)\s+", to_decimal),
        (r"Other Credits *[-+]? *\$(?P<other_credits>[0-9,.]+)\s+", to_decimal),
        (r"Purchases *[-+]? *\$(?P<purchases>[0-9,.]+)\s+", to_decimal),
        (r"Balance Transfers *[-+]? *\$(?P<balance_transfers>[0-9,.]+)\s+", to_decimal),
        (r"Cash Advances *[-+]? *\$(?P<cash_advances>[0-9,.]+)\s+", to_decimal),
        (r"Fees Charged *[-+]? *\$(?P<fees_charged>[0-9,.]+)\s+", to_decimal),
        (r"Interest Charged *[-+]? *\$(?P<interest_charged>[0-9,.]+)\s+", to_decimal),
        (r"New Balance *[-+]? *\$(?P<new_balance>[0-9,.]+) *(CR)? *", to_decimal),
        (r"Past Due Amount *[-+]? *\$(?P<past_due_amount>[0-9,.]+)\s+", to_decimal),
        (r"Credit Limit *[-+]? *\$(?P<credit_limit>[0-9,.]+)\s+", to_decimal),
        (r"Available Credit *[-+]? *\$(?P<available_credit>[0-9,.]+)\s+", to_decimal),
        (
            r"Available Credit for Cash *[-+]? *\$(?P<available_credit_for_cash>[0-9,.]+)\s+",
            to_decimal,
        ),
        (
            r"Statement Closing Date *(?P<statement_closing_date>\d{2}/\d{2}/\d{4})\s+",
            get_date,
        ),
        (r"Days in Billing Cycle *(?P<days_in_period>\d+)", int),
        (
            r"Minimum Payment Due *[-+]? *\$(?P<minimum_payment_due>[0-9,.]+)\s+",
            to_decimal,
        ),
        (r"Payment Due Date *(?P<payment_due_date>\w{3} *\d+,? *\d{4})\s+", get_date),
        (
            r"Previous Points Balance *[-+]? *(?P<previous_points_balance>[0-9,]+)\s+",
            lambda x: int(x.replace(",", "")),
        ),
        (
            r"1 Point \(1\%\) Earned on All Purchases *[-+]? *(?P<point_earned_on_all_purchases>[0-9,]+)\s+",
            lambda x: int(x.replace(",", "")),
        ),
        (
            r"Plus 1 Point Earned on 2\% Category *[-+]? *(?P<two_percent_category_points>[0-9,]+)\s+",
            lambda x: int(x.replace(",", "")),
        ),
        (
            r"Plus 2 Point Earned on 3\% Category *[-+]? *(?P<three_percent_category_points>[0-9,]+)\s+",
            lambda x: int(x.replace(",", "")),
        ),
        (
            r"New Points Balance *[-+]? *(?P<new_points_balance>[0-9,]+)\s+",
            lambda x: int(x.replace(",", "")),
        ),
    ],
    "tables": {
        "Transactions": {
            "transaction_type": None,  # BOTH
            "table_name": "Transactions",
            "table_name_re": r"^Transactions(\s+\(continued\))?\s*$",
            "n_lines_after_header": 3,
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Fees": {
            "transaction_type": DEBIT,
            "table_name": "Fees",
            "table_name_re": r"^Fees(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Interest Charged": {
            "transaction_type": DEBIT,
            "table_name": "Interest Charged",
            "table_name_re": r"^Interest Charged(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Totals Year to Date": {
            "transaction_type": None,
            "table_name": "Totals Year to Date",
            "table_name_re": r"^ *\d{4} Totals Year to Date$",
            "table_start": re.compile("^ *Total fees charged in \d{4}"),
            "n_lines_after_header": 1,
            "table_row": re.compile(r"^ +(?P<key>.*?) {4,}\$(?P<value>[0-9,.]+) *$"),
        },
        "Interest Charge Calculation": {
            "transaction_type": None,
            "table_name": "Interest Charge Calculation",
            "table_name_re": r"^Interest Charge Calculation$",
            "table_start": re.compile(
                r"Your Annual Percentage Rate \(APR\) is the annual interest rate on your account\."
            ),
            "n_lines_after_header": 4,
            "table_row": re.compile(
                r"^(?P<balance_type>.*?)\s{4,}"
                r"(?P<annual_percentage_rate>[0-9.]+)\% *\(?(?P<apr_type>\w)\)?\s{4,}"
                r"\$(?P<balance_subject_to_interest_rate>[0-9,.]+)\s{4,}"
                r"\$(?P<interest_charge>[0-9,.]+) *$"
            ),
        },
    },
}

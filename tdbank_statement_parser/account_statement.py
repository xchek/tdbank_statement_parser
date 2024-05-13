"""
Defines structured elements from TD Bank checking / savings account statements (PDF).
"""

import re
from datetime import datetime
from functools import partial

from pydash import py_

from .common import *

default_ending_re = (
    r", (?P<medium_identifier>\*+\d+),?\s*AUT (?P<authorization_date>\d{6})"
    r"\s*(?P<transaction_medium>(?:(?:VISA|INTL) )?(?:DDA|ATM)? *"
    r"(?:PURCHASE|PUR|WITHDRAW|CHECK DEPOSI|MIXED DEPOSI|CASH DEPOSIT|CASH|TRANSFER|PURCH W/CB|REF)"
    r")?\s*(?P<authorization_location>.*?)\s{2,}(?P<authorization_info>.*?)"
    r"(?:\s*\* (?P<authorization_state>[A-Z]{2}))?$"
)

statement_description_patterns = {
    "ACH DEBIT": (r"^ACH DEBIT, (?P<transaction_note>.*)$", DEBIT),
    "ACH DEPOSIT": (
        r"^ACH DEPOSIT, (?P<transaction_note>(?P<authorization_location>.*) "
        r"(DIR DEP|Trans\:|ACH OUT|PAYROLL|DIRECT DEP|PAYMENT) "
        r"(?P<medium_identifier>.*?)|.*?)$",
        CREDIT,
    ),
    "ATM CASH DEPOSIT": (r"ATM CASH DEPOSIT" + default_ending_re, CREDIT),
    "ATM CHECK DEPOSIT": (r"ATM CHECK DEPOSIT" + default_ending_re, CREDIT),
    "ATM MIXED DEPOSIT": (r"ATM MIXED DEPOSIT" + default_ending_re, CREDIT),
    "CREDIT": (r"CREDIT, (?P<transaction_note>.*)$", CREDIT),
    "DEBIT": (r"^DEBIT$", DEBIT),
    "DEBIT CARD CREDIT": (r"^DEBIT CARD CREDIT" + default_ending_re, CREDIT),
    "DEBIT CARD PAYMENT": (r"^DEBIT CARD PAYMENT" + default_ending_re, DEBIT),
    "DEBIT CARD PURCHASE": (r"^DEBIT CARD PURCHASE" + default_ending_re, DEBIT),
    "DEBIT POS": (r"^DEBIT POS" + default_ending_re, DEBIT),
    "DEPOSIT": (r"^DEPOSIT$", CREDIT),
    "ELECTRONIC PMT-WEB": (r"^ELECTRONIC PMT-WEB, (?P<transaction_note>.*?)$", DEBIT),
    "INTL DEBIT CARD PUR": (r"^INTL DEBIT CARD PUR" + default_ending_re, DEBIT),
    "INTL TXN FEE": (r"^INTL TXN FEE, INTL TXN FEE$", DEBIT),
    "MAINTENANCE FEE": (r"^MAINTENANCE FEE$", DEBIT),
    "MAINTENANCE FEE REFUND": (r"^MAINTENANCE FEE REFUND$", CREDIT),
    "MOBILE DEPOSIT": (r"^MOBILE DEPOSIT$", CREDIT),
    "NONTD ATM DEBIT": (r"^NONTD ATM DEBIT" + default_ending_re, DEBIT),
    "NONTD ATM FEE": (r"^NONTD ATM FEE(?:, NONTD ATM FEE)?$", DEBIT),
    "OVERDRAFT PD": (r"^OVERDRAFT PD$", DEBIT),
    "TD ATM DEBIT": (r"^TD ATM DEBIT" + default_ending_re, DEBIT),
    "VISA TRANSFER": (r"VISA TRANSFER" + default_ending_re, CREDIT),
    "WITHDRAWAL TRANSFER": (
        r"WITHDRAWAL TRANSFER, To (?P<transfer_account>.\w+ \d+)$",
        DEBIT,
    ),
    "ZERO DOLLAR CR": (r"ZERO DOLLAR CR, (?P<authorization_location>.*?)$", CREDIT),
    "eTransfer Credit": (
        r"^eTransfer Credit, Online Xfer\s*Transfer from (?P<transfer_account>\w+ \d+)$",
        CREDIT,
    ),
    "eTransfer Debit": (
        r"^eTransfer Debit, ((?P<transaction_medium>Online Xfer\s*Transfer|Transfer) to)"
        r" (?P<transfer_account>\w+ \d+)$",
        DEBIT,
    ),
}


amazon_parse_re = re.compile(
    r"(?P<amazon_method>(AMAZON|AMZN) (MKTPLACE PMTS|COM|MKTP US|PRIME))\s*"
    r"(?P<amazon_trans_id>[A-Z0-9 ]*)\s*$"
)

default_table_heading = re.compile(r"^POSTING DATE\s{2,}DESCRIPTION\s{4,}AMOUNT$")
default_table_row = re.compile(
    r"^(?P<posting_date>\d+\/\d+)\s{4,}(?P<description>.*?)\s{4,}(?P<amount>[\d\,\.]+)$"
)


def parse_desc(desc: str) -> dict:
    result = None
    for k, v in statement_description_patterns.items():
        rgx, trans_type = v
        if m := re.search(rgx, desc, flags=re.I):
            result = {
                "transaction_info": k,
                **m.groupdict(),
                "transaction_type": trans_type,
            }
            break
    return py_.pick_by(result)


def normalize_account_statement(rec: dict, table_name: str, metadata: dict) -> dict:
    _normalize_date = partial(normalize_date, metadata)

    normalize_map = {
        "check_date": _normalize_date,
        "amount": to_decimal,
        "posting_date": _normalize_date,
        "parsed_desc": py_.pick_by,
        "description": py_.identity,
    }

    normalize_parsed_desc = {
        "authorization_date": lambda x: datetime.strptime(x, "%m%d%y"),
    }

    if desc := rec.get("description", ""):
        if result := parse_desc(desc):
            if info := result.get("authorization_info"):
                result.pop("authorization_info")
                if info.replace(" ", "").isdigit():
                    result["authorization_phone"] = info.replace(" ", "")
                else:
                    result["authorization_city"] = info
            if auth_loc := result.get("authorization_location"):
                if m := amazon_parse_re.search(auth_loc):
                    result.update(m.groupdict())

            rec["parsed_desc"] = (
                py_(result)
                .map_values(lambda v, k: normalize_parsed_desc.get(k, py_.clean)(v))
                .value()
            )

    result = (
        py_(rec).map_values(lambda v, k: normalize_map.get(k, py_.clean)(v)).value()
    )
    # TODO: Generalize expense tagging.
    # result['classified_expense'] = auto_find_tag(result)
    trans_type = result["transaction_type"] = (
        py_(parse_config["tables"]).get(table_name).get("transaction_type").value()
    )
    if trans_type == DEBIT:
        result["amount"] *= -1
    return result


parse_config = {
    "normalize": normalize_account_statement,
    "metadata_patterns": [
        (
            r"Statement Period\:\s+"
            r"(?P<statement_period_start>\w+\s+\d+\s+\d+)\-"
            r"(?P<statement_period_end>\w+\s+\d+\s+\d+)",
            get_date,
        ),
        (r"Cust Ref \#\:\s+(?P<customer_reference_number>.+?)\s*$", py_.clean),
        (r"Primary Account \#\:\s+(?P<primary_account_number>.+?)\s*$", py_.clean),
        (r"Beginning Balance\s+(?P<beginning_balance>[0-9.,]+)($|\s{10})", to_decimal),
        (
            r"Electronic Deposits\s+(?P<electronic_deposits>[0-9.,]+)($|\s{10})",
            to_decimal,
        ),
        (r"Checks Paid\s+(?P<checks_paid>[0-9.,]+)($|\s{10})", to_decimal),
        (
            r"Electronic Payments\s+(?P<electronic_payments>[0-9.,]+)($|\s{10})",
            to_decimal,
        ),
        (r"Ending Balance\s+(?P<ending_balance>[0-9.,]+)($|\s{10})", to_decimal),
        (
            r"Average Collected Balance\s+(?P<average_collected_balance>[0-9.,]+)($|\s{10})",
            to_decimal,
        ),
        (
            r"Interest Earned This Period\s+(?P<interest_earned_this_period>[0-9.,]+)($|\s{10})",
            to_decimal,
        ),
        (
            r"Interest Paid Year-to-Date\s+(?P<interest_paid_ytd>[0-9.,]+)($|\s{10})",
            to_decimal,
        ),
        (
            r"Annual Percentage Yield Earned\s+(?P<annual_percent_yield_earned>[0-9.,]+)\%($|\s{10})",
            to_decimal,
        ),
        (r"Days in Period\s+(?P<days_in_period>[0-9.,]+)($|\s{10})", int),
    ],
    "tables": {
        "Deposits": {
            "transaction_type": CREDIT,
            "table_name": "Deposits",
            "table_name_re": r"^Deposits(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Electronic Deposits": {
            "transaction_type": CREDIT,
            "table_name": "Electronic Deposits",
            "table_name_re": r"^Electronic Deposits(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Electronic Payments": {
            "transaction_type": DEBIT,
            "table_name": "Electronic Payments",
            "table_name_re": r"^Electronic Payments(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Other Withdrawals": {
            "transaction_type": DEBIT,
            "table_name": "Other Withdrawals",
            "table_name_re": r"^Other Withdrawals(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Other Credits": {
            "transaction_type": CREDIT,
            "table_name": "Other Credits",
            "table_name_re": r"^Other Credits(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Service Charges": {
            "transaction_type": DEBIT,
            "table_name": "Service Charges",
            "table_name_re": r"^Service Charges(\s+\(continued\))?\s*$",
            "table_start": default_table_heading,
            "table_row": default_table_row,
        },
        "Checks Paid": {
            "transaction_type": DEBIT,
            "table_name": "Checks Paid",
            "table_name_re": r"^Checks Paid\s+No\. Checks\:\s*\d+\s+",
            "table_start": re.compile(r"^DATE\s{4,}SERIAL NO\.\s{4,}AMOUNT$"),
            "table_row": re.compile(
                r"^(?P<posting_date>\d+\/\d+)\s{4,}(?P<serial_number>.*?)\s{4,}(?P<amount>[\d\,\.]+)$"
            ),
        },
    },
}

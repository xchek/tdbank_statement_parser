import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from hashlib import md5
from pathlib import Path

import dateparser
import pdftotext
from pydash import py_

# from classify import auto_find_tag


default_ending_re = r", (?P<medium_identifier>\*+\d+),?\s*AUT (?P<authorization_date>\d{6})\s*(?P<transaction_medium>(?:(?:VISA|INTL) )?(?:DDA|ATM)? *(?:PURCHASE|PUR|WITHDRAW|CHECK DEPOSI|MIXED DEPOSI|CASH DEPOSIT|CASH|TRANSFER|PURCH W/CB|REF))?\s*(?P<authorization_location>.*?)\s{2,}(?P<authorization_info>.*?)(?:\s*\* (?P<authorization_state>[A-Z]{2}))?$"

DEBIT: str = "debit"
CREDIT: str = "credit"

statement_patterns = {
    "ACH DEBIT": (r"^ACH DEBIT, (?P<transaction_note>.*)$", DEBIT),
    "ACH DEPOSIT": (
        r"^ACH DEPOSIT, (?P<transaction_note>(?P<authorization_location>.*) (DIR DEP|Trans\:|ACH OUT|PAYROLL|DIRECT DEP|PAYMENT) (?P<medium_identifier>.*?)|.*?)$",
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
        r"^eTransfer Debit, ((?P<transaction_medium>Online Xfer\s*Transfer|Transfer) to) (?P<transfer_account>\w+ \d+)$",
        DEBIT,
    ),
}


amazon_parse_re = re.compile(
    r"(?P<amazon_method>(AMAZON|AMZN) (MKTPLACE PMTS|COM|MKTP US|PRIME))\s*(?P<amazon_trans_id>[A-Z0-9 ]*)\s*$"
)


def parse_desc(desc):
    result = None
    for k, v in statement_patterns.items():
        rgx, trans_type = v
        if m := re.search(rgx, desc, flags=re.I):
            result = {
                "transaction_info": k,
                **m.groupdict(),
                "transaction_type": trans_type,
            }
            break
    return py_.pick_by(result)


default_table_heading = re.compile(r"^POSTING DATE\s{2,}DESCRIPTION\s{4,}AMOUNT$")
default_table_row = re.compile(
    r"^(?P<posting_date>\d+\/\d+)\s{4,}(?P<description>.*?)\s{4,}(?P<amount>[\d\,\.]+)$"
)

parse_config = {
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
}


def to_decimal(x):
    return Decimal(x.replace(",", ""))


def parse_lines(lines):
    n = 0
    config = None
    data = defaultdict(list)
    while n < len(lines):
        if lines[n].strip():
            if config:
                if re.search(
                    r"(^\s+Subtotal\:\s+[\d\,\.]*\s*$|Call 1-800-937-2000 for 24-hour)",
                    lines[n],
                ):
                    config = None
                else:
                    if m := config["table_row"].search(lines[n]):
                        data[config["table_name"]].append(m.groupdict())
                    else:
                        data[config["table_name"]][-1]["description"] = "\n".join(
                            [
                                data[config["table_name"]][-1]["description"],
                                lines[n].strip(),
                            ]
                        )
            if (
                found_config := py_(parse_config.values())
                .filter(lambda x: re.search(x["table_name_re"], lines[n], flags=re.I))
                .head()
                .value()
            ):
                config = found_config
                if config["table_start"].search(lines[n + 1]):
                    n += 2
                    continue
        n += 1
    return data


def parse_statement(filepath):
    def normalize_date(datestr):
        test_posted_date = dateparser.parse(
            f"{datestr}/{metadata['statement_period_start'].year}"
        )
        if (
            metadata["statement_period_start"]
            <= test_posted_date
            <= metadata["statement_period_end"]
        ):
            return test_posted_date
        else:
            return dateparser.parse(
                f"{datestr}/{metadata['statement_period_start'].year + 1}"
            )

    normalize_map = {
        "check_date": normalize_date,
        "amount": to_decimal,
        "posting_date": normalize_date,
        "parsed_desc": py_.pick_by,
        "description": py_.identity,
    }

    normalize_parsed_desc = {
        "authorization_date": lambda x: datetime.strptime(x, "%m%d%y"),
    }

    def normalize(rec, table_name):
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
        # result['classified_expense'] = auto_find_tag(result)

        trans_type = result["transaction_type"] = (
            py_(parse_config).get(table_name).get("transaction_type").value()
        )
        if trans_type == DEBIT:
            result["amount"] *= -1
        return result

    parsed_pdf = list(pdftotext.PDF(open(filepath, "rb"), physical=True))
    rgxs = [
        (
            r"Statement Period\:\s+(?P<statement_period_start>\w+\s+\d+\s+\d+)\-(?P<statement_period_end>\w+\s+\d+\s+\d+)",
            dateparser.parse,
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
    ]

    activity = dict(
        parse_lines(list(line for page in parsed_pdf for line in page.splitlines()))
    )
    metadata = {
        k: parser(v)
        for rgx, parser in rgxs
        for m in [re.search(rgx, parsed_pdf[0], flags=re.I | re.M)]
        if m
        for k, v in m.groupdict().items()
    }
    return {
        "file_md5": md5(open(filepath, "rb").read()).hexdigest(),
        "filename": Path(filepath).name,
        "nPages": len(parsed_pdf),
        "metadata": metadata,
        "activity": {
            k: list(map(lambda x: normalize(x, k), v)) for k, v in activity.items()
        },
    }

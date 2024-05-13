import re
import sys
from collections import defaultdict
from hashlib import md5
from pathlib import Path

import pdftotext
from pydash import py_

from .account_statement import parse_config as account_parse_config
from .credit_card_statement import parse_config as credit_card_parse_config

table_cutoff = re.compile(
    r"(^\s+Subtotal\:\s+[\d\,\.]*\s*$|"
    r"Call 1-800-937-2000 for 24-hour|"
    r"TOTAL \w+ FOR THIS PERIOD\s*[$0-9.]+$|"
    r"is based on a full calendar year and does not)"
)


def parse_lines(parse_config: dict, lines: list) -> dict:
    """With the given configuration, parse tables and metadata from the list of text lines.

    Args:
        parse_config (dict): Defines how to extract elements (see ./*_statement.py).
        lines (list): The PDF text contents as a list of strings.

    Returns:
        dict: Structured statement activity tables.
    """
    n = 0
    config = None
    data = defaultdict(list)
    while n < len(lines):
        if lines[n].strip():
            if config:
                if table_cutoff.search(lines[n]):
                    config = None
                    n += 1
                    continue
                else:
                    if m := config["table_row"].search(lines[n]):
                        data[config["table_name"]].append(m.groupdict())
                    else:
                        try:
                            if "description" in data[config["table_name"]][-1]:
                                data[config["table_name"]][-1]["description"] = (
                                    "\n".join(
                                        [
                                            data[config["table_name"]][-1][
                                                "description"
                                            ],
                                            lines[n].strip(),
                                        ]
                                    )
                                )
                        except IndexError as ex:
                            print(
                                {
                                    "error": "Unexpected line occurrence occurred with no previous record.",
                                    "exception": str(ex),
                                },
                                file=sys.stdout,
                            )
            if (
                found_config := py_(parse_config["tables"].values())
                .filter(lambda x: re.search(x["table_name_re"], lines[n], flags=re.I))
                .head()
                .value()
            ):
                config = found_config
                if "Interest Charge Calculation" in config.get("table_name", ""):
                    w = 3
                if config["table_start"].search(lines[n + 1]):
                    n += config.get("n_lines_after_header", 2)
                    continue
        else:
            config = None
        n += 1
    return data


def get_content_type_config(text: str) -> dict:
    """
    Discern a content type based on the first page of the statement.

    Returns the parser configuration for a checking/savings account or a credit card account.
    """
    if re.search(r"STATEMENT OF ACCOUNT", text):
        return account_parse_config
    elif re.search(r"Please make check or money order payable to: TD Bank, N.A.", text):
        return credit_card_parse_config
    raise Exception("Cannot discern content-type of the file.")


def parse(filepath: str) -> dict:
    """Parse a TD Bank statement into logical parts.

    Args:
        filepath (str): The file path to a TD Bank credit card or account statement.

    Returns:
        dict: {
            file_md5: str,
            filename: str,
            nPages: int,
            metadata: dict[str -> any],
            activity: dict[str -> [dict]]   # Tabular data defined in parse_config.tables
        }
    """
    parsed_pdf = list(pdftotext.PDF(open(filepath, "rb"), physical=True))
    content_parse_config = get_content_type_config(parsed_pdf[0])

    normalize = content_parse_config.get("normalize", py_.identity)

    activity_tables = dict(
        parse_lines(
            content_parse_config,
            list(line for page in parsed_pdf for line in page.splitlines()),
        )
    )

    metadata = {}
    if metadata_patterns := content_parse_config.get("metadata_patterns"):
        metadata = {
            k: normalize_value(v)
            for rgx, normalize_value in metadata_patterns
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
            table_name: list(
                map(lambda x: normalize(x, table_name, metadata), records_list)
            )
            for table_name, records_list in activity_tables.items()
        },
    }

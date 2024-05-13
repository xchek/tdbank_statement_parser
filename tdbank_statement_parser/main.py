import fileinput
import json
import sys
from glob import glob

from pydash import py_

from tdbank_statement_parser.parser import parse


def main():
    if not (
        input_paths := [
            y
            for x in (py_.tail(sys.argv) or fileinput.input())
            if x.strip() and x.strip().endswith(".pdf")
            for y in glob(x)
        ]
    ):
        print(
            json.dumps({"message": "Please pass paths to PDF statements."}),
            file=sys.stderr,
        )
    else:
        input_paths = [y for x in input_paths for y in glob(x)]
        print(
            json.dumps({"message": f"Processing {len(input_paths)} files."}),
            file=sys.stderr,
        )

        for p in sorted(input_paths):
            record = parse(p)
            print(json.dumps(record, default=str), file=sys.stdout)
            print(
                {
                    "message": "Processed file.",
                    "filepath": p,
                    "counts": {k: len(v) for k, v in record["activity"].items() if v},
                },
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()

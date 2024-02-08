import json
import sys
from pydash import py_
import fileinput
from tdbank_statement_parser.parse_statement import parse_statement



def main():
  input_paths = [x.strip() for x in (py_.tail(sys.argv) or fileinput.input()) if x.strip() and x.strip().endswith('.pdf')]
  print(json.dumps({"message": f"Processing {len(input_paths)} files."}), file=sys.stderr)

  if not input_paths:
    print(json.dumps({"message": "Please pass paths to PDF statements."}), file=sys.stderr)
  else:
    for p in sorted(input_paths):
      record = parse_statement(p)
      print(json.dumps(record, default=str), file=sys.stdout)
      print({
        "message": "Processed file...",
        "filepath": p
      }, file=sys.stderr)


if __name__ == "__main__":
  main()

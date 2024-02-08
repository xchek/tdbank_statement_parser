## Usage:

Pass a list of paths to the `main.py` script. The script outputs parsed JSON blobs to stdout and logs status messages to stderr.

```bash
find -type f -name "*.pdf" | python tdbank_statement_parser/main.py > data.ndjson
```

### Or

```bash
python tdbank_statement_parser/main.py  **/*.pdf
```

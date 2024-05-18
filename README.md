## Usage:


Acquire TD Bank statements (PDF) manually or with the automated helper script.


```bash
$ python tdbank_statement_parser/dl_statements.py --help
usage: dl_statements.py [-h] [output_directory]

TD Bank account statement downloader.

positional arguments:
  output_directory  Specify the output directory (defaults to ./data/ otherwise)

options:
  -h, --help        show this help message and exit
```


`dl_statements.py` waits 4 minutes on the login page, allowing time for credentials to be manually entered and for 2FA. When redirected to the dashboard, the script takes over and begins downloading all statements for all accounts. Output directory sample shown below.

```bash
.
└── data
    ├── audit
    ├── TD_CONVENIENCE_CHECKING_x5555
    │   ├── 2023
    │   │   ├── View PDF Statement_2023-10-11.pdf
    │   │   ├── View PDF Statement_2023-11-11.pdf
    │   │   └── ...
    │   └── 2024
    │       ├── View PDF Statement_2024-03-11.pdf
    │       ├── View PDF Statement_2024-04-11.pdf
    │       └── ...
    ├── TD_CONVENIENCE_CHECKING_x6666
    │   └── ...
    ├── TD_Cash_x9999
    │   └── ...
    ├── TD_SIMPLE_SAVINGS_x1010
    │   └── ...
    ├── TD_SIMPLE_SAVINGS_x5555
    │   └── ...
    └── TD_SIMPLE_SAVINGS_x8888
        └── ...
```


Pass a list of paths to the `main.py` script. The script outputs parsed JSON blobs to stdout and logs status messages to stderr.


```bash
$ find -type f -name "*.pdf" | python tdbank_statement_parser/main.py > data.ndjson
...
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-02-11.pdf', 'counts': {'Electronic Deposits': 9, 'Checks Paid': 1, 'Electronic Payments': 39}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-03-11.pdf', 'counts': {'Electronic Deposits': 4, 'Checks Paid': 1, 'Electronic Payments': 49}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-04-11.pdf', 'counts': {'Deposits': 1, 'Electronic Deposits': 2, 'Checks Paid': 1, 'Electronic Payments': 18, 'Service Charges': 1}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-05-11.pdf', 'counts': {'Electronic Deposits': 4, 'Checks Paid': 1, 'Electronic Payments': 12, 'Service Charges': 1}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-06-11.pdf', 'counts': {'Electronic Deposits': 8, 'Checks Paid': 1, 'Electronic Payments': 18, 'Other Withdrawals': 2, 'Service Charges': 1}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-07-11.pdf', 'counts': {'Electronic Deposits': 3, 'Electronic Payments': 29, 'Service Charges': 1}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-08-11.pdf', 'counts': {'Electronic Deposits': 4, 'Electronic Payments': 32, 'Other Withdrawals': 1, 'Service Charges': 1}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-09-11.pdf', 'counts': {'Electronic Deposits': 2, 'Electronic Payments': 46}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-10-11.pdf', 'counts': {'Electronic Deposits': 2, 'Other Credits': 1, 'Electronic Payments': 41}}
{'message': 'Processed file.', 'filepath': '/bank/checking/View PDF Statement_2020-11-11.pdf', 'counts': {'Electronic Deposits': 3, 'Electronic Payments': 36, 'Service Charges': 1}}
...
```


### Or


```bash
$ python tdbank_statement_parser/main.py  **/*.pdf
```


### Standard output JSON lines:
```json
{
  "file_md5": "deadbeefdeadbeefdeadbeefdeadbeef",
  "filename": "View PDF Statement_2018-02-10.pdf",
  "nPages": 7,
  "metadata": {
    "statement_period_start": "2018-01-11",
    "statement_period_end": "2018-02-10",
    "customer_reference_number": "9999999999-888-F-***",
    "primary_account_number": "999-9999999",
    "beginning_balance": "9999.99",
    "electronic_deposits": "8888.88",
    "electronic_payments": "8888.88",
    "ending_balance": "9999.99",
    "average_collected_balance": "0.00",
    "interest_earned_this_period": "0.00",
    "interest_paid_ytd": "0.00",
    "annual_percent_yield_earned": "0.00",
    "days_in_period": 31
  },
  "activity": {
    "Electronic Deposits": [
      {
        "posting_date": "2018-01-16",
        "description": "VISA TRANSFER, *****99999999999, AUT 011318 VISA TRANSFER\nP2P JANE DOE       VISA DIRECT * CA",
        "amount": "800.00",
        "parsed_desc": {
          "transaction_info": "VISA TRANSFER",
          "medium_identifier": "*****99999999999",
          "authorization_date": "2018-01-13",
          "transaction_medium": "VISA TRANSFER",
          "authorization_location": "P2P JANE DOE",
          "authorization_state": "CA",
          "transaction_type": "credit",
          "authorization_city": "VISA DIRECT"
        },
        "transaction_type": "credit"
      }
    ],
    "Electronic Payments": [
      {
        "posting_date": "2018-01-16",
        "description": "eTransfer Debit, Online Xfer\nTransfer to CK 5555555555",
        "amount": "-20.00",
        "parsed_desc": {
          "transaction_info": "eTransfer Debit",
          "transaction_medium": "Online Xfer Transfer",
          "transfer_account": "CK 5555555555",
          "transaction_type": "debit"
        },
        "transaction_type": "debit"
      },
      {
        "posting_date": "2018-12-03",
        "description": "DEBIT CARD PURCHASE, *****01233456789, AUT 120218 VISA DDA PUR\nAMAZON COM A064B5F05          AMZN COM BILL * WA",
        "amount": "-30.09",
        "parsed_desc": {
            "transaction_info": "DEBIT CARD PURCHASE",
            "medium_identifier": "*****01233456789",
            "authorization_date": "2018-12-02",
            "transaction_medium": "VISA DDA PUR",
            "authorization_location": "AMAZON COM A064B5F05",
            "authorization_state": "WA",
            "transaction_type": "debit",
            "authorization_city": "AMZN COM BILL",
            "amazon_method": "AMAZON COM",
            "amazon_trans_id": "A064B5F05"
        },
        "transaction_type": "debit"
      },
    ],
    "Transactions": [
        ...
    ],
    "Fees": [
        ...
    ],
    "Interest Charged": [
        ...
    ],
    "Totals Year to Date": [
        ...
    ],
    "Interest Charge Calculation": [
        ...
    ],
    "Deposits": [
        ...
    ],
    "Electronic Deposits": [
        ...
    ],
    "Electronic Payments": [
        ...
    ],
    "Other Withdrawals": [
        ...
    ],
    "Other Credits": [
        ...
    ],
    "Service Charges": [
        ...
    ],
    "Checks Paid": [
        ...
    ],
  }
}
```


Feedback is greatly appreciated & welcome!

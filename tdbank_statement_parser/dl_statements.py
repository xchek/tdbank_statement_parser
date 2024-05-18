"""
Automated browser script to download TD Bank account statements.
"""

import os
import random
import re
import time
from argparse import ArgumentParser
from pathlib import Path

from faker import Faker
from playwright.sync_api import Playwright, expect, sync_playwright

fake = Faker()


def run(playwright: Playwright, args) -> None:
    data_dir = args.output_directory
    audit_file = data_dir / "audit"
    if audit_file.exists():
        audit_log = {
            a: b
            for x in audit_file.open("r").readlines()
            if x.strip()
            for a, b in [x.strip().split(",")]
            if a and b
        }
    else:
        audit_file.open("w")
        audit_log = {}

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(user_agent=fake.chrome())
    page = context.new_page()

    page.goto("https://onlinebanking.tdbank.com/")

    expect(
        page.get_by_role("menuitem", name="Accounts").locator("span")
    ).to_be_attached(
        timeout=240_000
    )  # waits 4 minutes for user to manually login
    time.sleep(4)

    account_rows = page.locator("tr.ngp-financial-table-body-row")

    for account_row in account_rows.all()[::-1]:
        account_row.click()
        account_header = page.locator(
            "select[ng-model='selectedAccountCopy'] > option[selected]"
        ).element_handle()
        account_id = re.sub(
            r"[^a-zA-Z0-9]+", "_", account_header.get_attribute("label")
        ).strip("_")
        account_dir = data_dir / account_id
        account_dir.mkdir(exist_ok=True)
        page.get_by_role("button", name="Statements").click()
        year_select = page.locator("select#docYearValue,select[ng-model='docYear']")
        years = [x.inner_html().strip() for x in year_select.locator("option").all()]
        for year in years[::-1]:
            year_select.select_option(year)
            time.sleep(random.uniform(1, 3))
            expect(page.locator(".td-spinner")).to_have_class(
                "td-spinner ng-scope ng-hide"
            )

            month_rows = page.locator(
                "table.td-table > tbody > tr.ng-scope"
                ",.ngp-table.ngp-account-document-table > tbody > tr.ngp-tr.ngp-rows"
            )
            n_months = month_rows.count()
            if not n_months:
                continue
            year_dir = account_dir / year
            year_dir.mkdir(exist_ok=True)
            for month_row in month_rows.all()[::-1]:
                elem = month_row.element_handle()
                month_id = re.sub(r"[\s\W]+", "_", elem.inner_text().strip())
                record_id = f"{account_id}|{year}|{month_id}"
                if record_id not in audit_log:
                    with page.expect_download() as download_info:
                        elem.query_selector(
                            ".ngp-icon-download,[td-ui-icon=download]"
                        ).click()
                    if download := download_info.value:
                        file_path = year_dir / download.suggested_filename
                        download.save_as(str(file_path))
                        print(f"SAVED: {str(file_path)}")
                        audit_log[record_id] = str(file_path)
                        audit_file.open("a").write(f"{record_id},{str(file_path)}\n")
                else:
                    print(f"EXISTS: {audit_log[record_id]}")

        page.get_by_role("menuitem", name="Accounts").locator("span").click()
    context.close()
    browser.close()


def main():
    parser = ArgumentParser(
        description="TD Bank account statement downloader.",
    )
    parser.add_argument(
        dest="output_directory",
        nargs="?",
        default=Path(os.getcwd()) / "data",
        help="Specify the output directory (defaults to ./data/ otherwise)",
    )
    args = parser.parse_args()

    with sync_playwright() as playwright:
        run(playwright, args)


if __name__ == "__main__":
    main()

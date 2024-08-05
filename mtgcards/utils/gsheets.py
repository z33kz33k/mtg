"""

    mtgcards.utils.sheets.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Google Sheets as backend/frontend.

    @author: z33k

"""
import logging

import gspread

from mtgcards.utils import timed
from mtgcards.utils.check_type import generic_iterable_type_checker, type_checker

_log = logging.getLogger(__name__)


@type_checker(str, str)
def _worksheet(spreadsheet: str, worksheet: str) -> gspread.Worksheet:
    creds_file = "scraping_service_account.json"
    client = gspread.service_account(filename=creds_file)
    spreadsheet = client.open(spreadsheet)
    worksheet = spreadsheet.worksheet(worksheet)
    return worksheet


@timed("retrieving from Google Sheets")
def retrieve_from_gsheets_cols(
        spreadsheet: str, worksheet: str, cols=(1, ), start_row=1,
        ignore_none=True) -> tuple[list[str], ...]:
    """Retrieve a list of string values from a Google Sheets worksheet for each specified column.
    """
    if any(col < 1 for col in cols) or start_row < 1:
        raise ValueError("A column and a start row must be positive integers")
    _log.info(
        f"Retrieving records from '{spreadsheet}/{worksheet}' Google sheet (columns {cols})...")
    worksheet = _worksheet(spreadsheet, worksheet)
    columns = []
    for col in cols:
        values = worksheet.col_values(col, value_render_option="UNFORMATTED_VALUE")[start_row-1:]
        if ignore_none:
            values = [value for value in values if value is not None]
        columns.append(values)
    return tuple(columns)


@timed("saving to Google Sheets")
@generic_iterable_type_checker(str)
def save_to_gsheets_col(
        values: list[str], spreadsheet: str, worksheet: str, col=1, start_row=1) -> None:
    """Save a list of strings to a Google Sheets worksheet's specified column.
    """
    if col < 1 or start_row < 1:
        raise ValueError("Column and start row must be positive integers")
    _log.info(
        f"Saving {len(values)} record(s) to '{spreadsheet}/{worksheet}' Google sheet "
        f"(column {col})...")
    worksheet = _worksheet(spreadsheet, worksheet)
    worksheet.insert_rows([[value] for value in values], row=start_row)

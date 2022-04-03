"""

    mtgcards.utils.py
    ~~~~~~~~~~~~~~~~~
    Utilities.

    @author: z33k

"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from contexttimer import Timer

Json = Dict[str, Any]
INPUTDIR, OUTPUTDIR = Path("input"), Path("output")
if not INPUTDIR.exists():
    raise OSError(f"Default input directory not found at: {INPUTDIR}.")
if not OUTPUTDIR.exists():
    raise OSError(f"Default output directory not found at: {OUTPUTDIR}.")


def timed_request(url: str, postdata: Optional[Json] = None,
                  return_json=False) -> Union[List[Json], Json, str]:
    print(f"Retrieving data from: '{url}'...")
    with Timer() as t:
        if postdata:
            data = requests.post(url, json=postdata)
        else:
            data = requests.get(url)
    print(f"Request completed in {t.elapsed:.3f} seconds.")
    if return_json:
        return data.json()
    return data.text


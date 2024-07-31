"""

    mtgcards.utils.files.py
    ~~~~~~~~~~~~~~~~~~~~~~~

    Files-related utilities.

"""
import os
import shutil
from logging import getLogger
from pathlib import Path
from time import sleep

import requests
from tqdm import tqdm

from mtgcards.const import PathLike
from mtgcards.utils.check_type import type_checker

_log = getLogger(__name__)


@type_checker(PathLike)
def getdir(path: PathLike, create_missing=True) -> Path:
    """Return a directory at ``path`` creating it (and all its needed parents) if missing.
    """
    dir_ = Path(path)
    if not dir_.exists() and create_missing:
        _log.warning(f"Creating missing directory at: '{dir_.resolve()}'...")
        dir_.mkdir(parents=True, exist_ok=True)
    else:
        if dir_.is_file():
            raise NotADirectoryError(f"Not a directory: '{dir_.resolve()}'")
    return dir_


@type_checker(PathLike)
def getfile(path: PathLike, ext="") -> Path:
    """Return an existing file at ``path``.
    """
    f = Path(path)
    if not f.is_file():
        raise FileNotFoundError(f"Not a file: '{f.resolve()}'")
    if ext and not f.suffix.lower() == ext.lower():
        raise ValueError(f"Not a {ext!r} file")
    return f


@type_checker(str)
def recursive_removedir(dirpath: str, check_delay: int = 500) -> None:
    """Remove directory at ``dirpath`` and it contents recursively. Check after delay (default is
    500ms), if something still exists, list it.
    """
    dir_ = getdir(dirpath, create_missing=False)
    if dir_ is not None:
        shutil.rmtree(dir_, ignore_errors=True)
        sleep(check_delay / 1000)
        if dir_.exists():
            _log.warning(
                f"Problems encountered while trying to remove: {dir_}. Content which hasn't been "
                f"removed: {os.listdir(dir_)}")
        else:
            _log.info(f"Removed successfully: {dir_} and its contents.")
    else:
        _log.info(f"Nothing to remove at {dirpath}.")


@type_checker(str, str)
def remove_by_ext(ext: str, destdir: str, recursive=False, opposite=False) -> int:
    """Remove from ``destdir`` files by provided extension. Optionally, remove all files of
    different extension.

    Extension shall include the leading period, e.g. ".py"

    Returns:
        number of removed files
    """
    def remove(f: Path, removed_lst: list[Path]) -> None:
        f.unlink()
        if not f.exists():
            removed_lst.append(f)
            _log.info(f"Removed {f}.")
        else:
            _log.warning(f"Unable to remove file: {f}.")

    destdir = getdir(destdir)
    removed = []
    gb = "**/*" if recursive else "*"
    files = [f for f in destdir.glob(gb) if f.is_file()]
    for file in files:
        if opposite:
            if file.suffix != ext:
                remove(file, removed)
        else:
            if file.suffix == ext:
                remove(file, removed)

    return len(removed)


def download_file(url: str, file_name="", dst_dir="") -> None:
    """Download a file at ``url`` to destination specified by ``file_name`` and ``dst_dir``.

    Mostly, as suggested by GPT3.

    Args:
        url: URL of the file to be downloaded.
        file_name: Optional name for saved file. Default is the downloaded file's name.
        dst_dir: Optional destination directory for saving. Default is the CWD.
    """
    if not file_name:
        file_name = Path(url).name
    # send an HTTP request to the URL
    response = requests.get(url, stream=True)
    # get the total file size in bytes
    file_size = int(response.headers.get("Content-Length", 0))
    divisor = 1024

    dst = Path(file_name) if not dst_dir else getdir(dst_dir) / file_name
    # create a progress bar object
    progress = tqdm(response.iter_content(divisor), f"Downloading '{dst.resolve()}'...",
                    total=file_size, unit="B", unit_scale=True, unit_divisor=divisor)

    # open a file for writing
    with open(dst, "wb") as f:
        # iterate over the file content in chunks
        for chunk in progress:
            # write each chunk to the file
            f.write(chunk)
            # update the progress bar manually
            progress.update(len(chunk))

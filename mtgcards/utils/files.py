"""

    mtgcards.utils.files.py
    ~~~~~~~~~~~~~~~~~~~~~~~

    Files-related utilities.

"""
import os
import shutil
from logging import ERROR, getLogger
from pathlib import Path
from time import sleep
from typing import Optional

import requests
from logdecorator import log_on_error
from tqdm import tqdm

from mtgcards.utils.validate import type_checker

log = getLogger(__name__)


@log_on_error(
    ERROR, "Error on getting {file_location}: {e!r}.", on_exceptions=(OSError, ValueError),
    reraise=True, logger=log)
@type_checker(str)
def getfile(file_location: str, absolute=False, sanity_check=True) -> Path:
    """Return a Path object pointing at a file according to string `file_location` provided.

    By default, perform a sanity check on the provided location.
    """
    try:
        file = Path(file_location)
    except OSError as e:
        raise OSError(f"Cannot read provided location: {file_location} ({e}).")
    if sanity_check:
        if not file.exists():
            raise FileNotFoundError(f"Nothing at: {file}.")
        if not file.is_file():
            raise FileNotFoundError(f"Not a file: {file}.")
    if absolute:
        return file.absolute()
    else:
        try:
            result = file.relative_to(Path("..").absolute()) if file.is_absolute() else file
        # this can hiccup if `file` is absolute and `Path(".").absolute()` doesn't make sense for it
        # so, we fall back from an attempt at returning a relative path to returning an absolute
        # one (because that is what was fed on input anyway)
        except ValueError:
            result = file
        return result


@log_on_error(
    ERROR, "Error on getting {dir_location}: {e!r}.", on_exceptions=(OSError, ValueError),
    reraise=True, logger=log)
@type_checker(str)
def getdir(dir_location: str, absolute=False, create_missing=True) -> Optional[Path]:
    """Return a Path object pointing at a directory according to string `dir_location` provided.

    If nothing exists at ``dir_location``, create a directory according to it (including any
    needed parents along the way). If ``dir_location`` points to an existing file,
    raise `ValueError`.
    """
    try:
        dir_ = Path(dir_location)
    except OSError as e:
        raise OSError(f"Cannot read provided location: {dir_location} ({e}).")

    if not dir_.exists():
        if create_missing:
            log.info(f"Creating missing directory at: {dir_}...")
            dir_.mkdir(parents=True, exist_ok=True)
            return dir_
        return
    else:
        if dir_.is_file():
            raise NotADirectoryError(f"Not a directory: {dir_}.")
    return dir_ if not absolute else dir_.absolute()


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
            log.warning(f"Problems encountered while trying to remove: {dir_}. "
                        f"Content which hasn't been removed: {os.listdir(dir_)}")
        else:
            log.info(f"Removed successfully: {dir_} and its contents.")
    else:
        log.info(f"Nothing to remove at {dirpath}.")


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
            log.info(f"Removed {f}.")
        else:
            log.warning(f"Unable to remove file: {f}.")

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
    progress = tqdm(response.iter_content(divisor), f"Downloading '{dst.resolve()}'",
                    total=file_size, unit="B", unit_scale=True, unit_divisor=divisor)

    # open a file for writing
    with open(dst, "wb") as f:
        # iterate over the file content in chunks
        for chunk in progress:
            # write each chunk to the file
            f.write(chunk)
            # update the progress bar manually
            progress.update(len(chunk))

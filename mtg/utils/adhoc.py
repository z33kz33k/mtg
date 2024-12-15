"""

    mtg.utils.adhoc.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Ad hoc utilities.

    @author: z33k

"""
import json
import logging
import shutil

from mtg.yt import CHANNELS_DIR

_log = logging.getLogger(__name__)


def to_id_channels():
    new_channels_dir = CHANNELS_DIR.with_name("channels2")
    new_channels_dir.mkdir()
    for channel_dir in [p for p in CHANNELS_DIR.iterdir() if p.is_dir()]:
        files = [p for p in channel_dir.iterdir() if p.is_file()]
        if not files:
            _log.warning(f"No files in {channel_dir}")
            continue
        channel_id = json.loads(files[0].read_text(encoding="utf-8")).get("id")
        if not channel_id:
            _log.warning(f"No ID in {channel_dir}")
            continue

        new_dir, count = new_channels_dir / channel_id, 0
        while new_dir.exists():
            count += 1
            new_dir = new_channels_dir / f"{channel_id}_({count})"
        new_dir.mkdir()

        if channel_dir.name.startswith("c_"):
            prefix = channel_dir.name[2:]
        elif channel_dir.name.startswith("@"):
            prefix = channel_dir.name[1:]
        else:
            _log.warning(f"Invalid channel name: {channel_dir}")
            continue

        for f in files:
            filename = f.name.removeprefix(prefix + "_")
            dst =  new_dir / f"{new_dir.name}___{filename}"
            _log.info(f"Copying {f} to {dst}...")
            shutil.copy(f, dst)

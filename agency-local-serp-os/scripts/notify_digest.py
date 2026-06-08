#!/usr/bin/env python3
"""Morning digest: one summary line of board state. Run after issuing work orders."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from lib import board_scan, notify
by = board_scan.grouped(ROOT)
c = {k: len(by.get(k, [])) for k, *_ in board_scan.COLS}
msg = (f"Daily: {c.get('approval',0)} need approval · {c.get('queued',0)} queued · "
       f"{c.get('progress',0)} running · {c.get('held',0)} failed/held")
notify.send(msg, level="digest")
print(msg)

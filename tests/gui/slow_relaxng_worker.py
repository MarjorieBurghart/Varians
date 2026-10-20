# -*- coding: utf-8 -*-
"""Faux processus de validation pour les tests : comme relaxng_worker, mais
attend ``sys.argv[1]`` secondes avant chaque réponse (compilation lente)."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from relaxng_worker import handle_request  # noqa: E402

delay = float(sys.argv[1])
writer = os.fdopen(1, "wb", closefd=False)
for line in os.fdopen(0, "rb", closefd=False):
    if not line.strip():
        continue
    time.sleep(delay)
    writer.write(json.dumps(handle_request(json.loads(line))).encode("utf-8") + b"\n")
    writer.flush()

# -*- coding: utf-8 -*-
"""Faux processus de validation pour les tests : comme relaxng_worker, mais
la compilation d'un schéma nommé « bloque.rng » commence (elle est annoncée)
et ne finit jamais, comme celle de certains schémas TEI par libxml2."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from relaxng_worker import handle_request  # noqa: E402

writer = os.fdopen(1, "wb", closefd=False)


def send(data):
    writer.write(json.dumps(data).encode("utf-8") + b"\n")
    writer.flush()


for line in os.fdopen(0, "rb", closefd=False):
    if not line.strip():
        continue
    request = json.loads(line)
    schema = request.get("schema") or ""
    if schema.endswith("bloque.rng"):
        send({"id": request.get("id"), "compiling": schema})
        while True:
            time.sleep(60)
    send(handle_request(request))

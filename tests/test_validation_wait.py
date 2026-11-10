# -*- coding: utf-8 -*-
"""Une validation demandée (F8, enregistrement) n'arrête la fenêtre que deux
secondes au plus ; au-delà, son résultat est affiché à son arrivée
(validation_worker ; essais dans tests/gui, où le délai est allongé)."""
import validation_worker


def test_a_requested_validation_waits_two_seconds_at_most():
    assert validation_worker.SYNC_WAIT_MSEC == 2000
    assert not hasattr(validation_worker, "SYNC_TIMEOUT_MSEC")

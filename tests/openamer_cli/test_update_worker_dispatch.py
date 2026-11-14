"""A live existing updater marker defers new workers, never their completion."""
import os
import time
from unittest.mock import patch

from openamer_cli import kanban_db_dispatch as dispatch


def budget():
    return dispatch._tick_spawn_budget(None, dispatch.DispatchResult(), max_spawn=None, max_in_progress=None, board=None)


def test_live_update_marker_defers_dispatch(tmp_path):
    (tmp_path / '.openamer-update-in-progress').write_text(f'{os.getpid()}\n{int(time.time())}\n')
    with patch('openamer_constants.get_openamer_home', return_value=tmp_path), patch.object(dispatch, '_memory_pressure_level', return_value='normal'):
        assert budget() == (False, None)


def test_expired_update_marker_does_not_park_dispatch_forever(tmp_path):
    (tmp_path / '.openamer-update-in-progress').write_text(f'{os.getpid()}\n{int(time.time()) - 1300}\n')
    with patch('openamer_constants.get_openamer_home', return_value=tmp_path), patch.object(dispatch, '_memory_pressure_level', return_value='normal'):
        assert budget() == (True, None)


def test_dead_owner_does_not_block_dispatch(tmp_path):
    (tmp_path / '.openamer-update-in-progress').write_text(f'99999999\n{int(time.time())}\n')
    with patch('openamer_constants.get_openamer_home', return_value=tmp_path), patch.object(dispatch, '_memory_pressure_level', return_value='normal'):
        assert budget() == (True, None)

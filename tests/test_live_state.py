import contextlib
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def sentry_span(*args, **kwargs):
    yield None


arielbot_stub = types.ModuleType("arielbot")
ariel_sentry_stub = types.ModuleType("arielbot.ariel_sentry")
ariel_sentry_stub.sentry_span = sentry_span
sys.modules.setdefault("arielbot", arielbot_stub)
sys.modules.setdefault("arielbot.ariel_sentry", ariel_sentry_stub)

live_state = load_module("ariel_live_state_under_test", "arielbot/plugins/Core/ariel_live_state.py")
ariel_database = load_module("ariel_database_under_test", "arielbot/plugins/Core/ariel_database.py")


class LiveRestartSuppressionTest(unittest.TestCase):
    def test_suppresses_restart_under_five_minutes(self):
        self.assertTrue(live_state.should_suppress_live_push(1_000, 1_299))

    def test_does_not_suppress_at_five_minutes(self):
        self.assertFalse(live_state.should_suppress_live_push(1_000, 1_300))

    def test_does_not_suppress_without_last_live_end_time(self):
        self.assertFalse(live_state.should_suppress_live_push(None, 1_299))

    def test_does_not_suppress_negative_elapsed_time(self):
        self.assertFalse(live_state.should_suppress_live_push(1_300, 1_299))


class LiveStateDatabaseTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "data.sqlite"
        self.previous_db_path = os.environ.get("ARIEL_DB_PATH")
        os.environ["ARIEL_DB_PATH"] = str(self.db_path)

    async def asyncTearDown(self):
        if self.previous_db_path is None:
            os.environ.pop("ARIEL_DB_PATH", None)
        else:
            os.environ["ARIEL_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    async def test_select_live_check_uid_returns_last_live_end_time(self):
        async with ariel_database.DataManager() as manager:
            await manager.insert_bot_status((200, 300, 1, 1))
            await manager.insert_sub_target(("100", "Alice", 1))
            await manager.insert_sub_channel(("100", 300, 200))
            await manager.update_sub_target_live_end(("Alice", 0, 12_345, "100"))
            rows = await manager.select_live_check_uid()

        self.assertEqual(rows, [("100", 0, 12_345)])

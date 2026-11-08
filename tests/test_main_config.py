"""Harness entrypoint configuration contracts."""

import unittest
from unittest.mock import Mock, patch

from voice_bridge import main


class MainConfigTests(unittest.TestCase):
    def test_main_loads_database_url_from_environment(self):
        config = Mock()
        harness = Mock()
        with (
            patch.object(main.HarnessConfig, "from_env", return_value=config) as from_env,
            patch.object(main, "Harness", return_value=harness),
        ):
            main.main()
        from_env.assert_called_once_with()
        harness.add_service.assert_called_once_with("bridge", main.bridge_service)
        harness.run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

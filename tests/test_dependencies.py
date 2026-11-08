"""Deployment dependency contracts."""

import tomllib
import unittest
from pathlib import Path


class HarnessDependencyTests(unittest.TestCase):
    def test_harness_pin_includes_postgres_operational_state(self):
        pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
        self.assertIn(
            "automation-harness[postgres]>=0.5.0,<0.6",
            pyproject["project"]["dependencies"],
        )


if __name__ == "__main__":
    unittest.main()

"""The api module docstring must document the /boot-check contract."""

import unittest

import voice_bridge.api as api_module


class ApiModuleDocstringTests(unittest.TestCase):
    def test_api_module_docstring_mentions_boot_check(self):
        doc = api_module.__doc__ or ""
        self.assertIn("/boot-check", doc)

    def test_api_module_docstring_mentions_boot_token_contract(self):
        doc = api_module.__doc__ or ""
        self.assertIn("VOICE_BRIDGE_BOOT_TOKEN", doc)
        self.assertIn("503", doc)


if __name__ == "__main__":
    unittest.main()

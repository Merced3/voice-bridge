"""s16le mono↔stereo wire conversion."""

import unittest

from voice_bridge.audio import mono_to_stereo, stereo_to_mono


class ConversionTests(unittest.TestCase):
    def test_mono_to_stereo_duplicates_samples(self):
        mono = b"\x01\x00\x02\x00"  # two samples
        self.assertEqual(mono_to_stereo(mono), b"\x01\x00\x01\x00\x02\x00\x02\x00")

    def test_stereo_to_mono_keeps_left(self):
        stereo = b"\x01\x00\x09\x00\x02\x00\x08\x00"  # (1,9), (2,8)
        self.assertEqual(stereo_to_mono(stereo), b"\x01\x00\x02\x00")

    def test_round_trip(self):
        mono = bytes(range(200))
        self.assertEqual(stereo_to_mono(mono_to_stereo(mono)), mono)

    def test_trailing_partial_sample_dropped(self):
        self.assertEqual(mono_to_stereo(b"\x01\x00\x02"), b"\x01\x00\x01\x00")
        self.assertEqual(stereo_to_mono(b"\x01\x00\x09"), b"")


if __name__ == "__main__":
    unittest.main()

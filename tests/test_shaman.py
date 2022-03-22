import unittest

from blender_asset_tracer.pack import shaman


class ParseEndpointTest(unittest.TestCase):
    def test_path_slashyness(self):
        self.assertEqual(
            ("https://endpoint/", "123"),
            shaman.parse_endpoint("shaman://endpoint#123"),
        )
        self.assertEqual(
            ("https://endpoint/", "123"),
            shaman.parse_endpoint("shaman://endpoint/#123"),
        )
        self.assertEqual(
            ("https://endpoint/root", "just/some/path"),
            shaman.parse_endpoint("shaman://endpoint/root#just/some/path"),
        )
        self.assertEqual(
            ("https://endpoint/root/is/longer/", "123"),
            shaman.parse_endpoint("shaman://endpoint/root/is/longer/#123"),
        )

    def test_schemes_with_plus(self):
        self.assertEqual(
            ("https://endpoint/", "123"),
            shaman.parse_endpoint("shaman+https://endpoint/#123"),
        )
        self.assertEqual(
            ("http://endpoint/", "123"),
            shaman.parse_endpoint("shaman+http://endpoint/#123"),
        )

    def test_checkout_ids(self):
        self.assertEqual(
            ("https://endpoint/", ""),
            shaman.parse_endpoint("shaman+https://endpoint/"),
        )

        # Not a valid ID, but the parser should handle it gracefully anyway
        self.assertEqual(
            ("http://endpoint/", "ïđ"),
            shaman.parse_endpoint("shaman+http://endpoint/#%C3%AF%C4%91"),
        )

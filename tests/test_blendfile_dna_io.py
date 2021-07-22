import unittest
from unittest import mock

from blender_asset_tracer.blendfile import dna, dna_io


class StringTest(unittest.TestCase):
    def test_trim_utf8(self):
        fileobj = mock.Mock()
        # Sinhala for 'beer'. This is exactly 15 bytes in UTF-8, so the last
        # character won't fit in the field (due to the 0-byte required).
        dna_io.BigEndianTypes.write_string(fileobj, "බියර්", 15)

        expect_bytes = ("බියර්"[:-1]).encode("utf8") + b"\0"
        fileobj.write.assert_called_with(expect_bytes)

    def test_utf8(self):
        fileobj = mock.Mock()
        # Sinhala for 'beer'. This is exactly 15 bytes in UTF-8,
        # so with the 0-byte it just fits.
        dna_io.BigEndianTypes.write_string(fileobj, "බියර්", 16)

        expect_bytes = "බියර්".encode("utf8") + b"\0"
        fileobj.write.assert_called_with(expect_bytes)

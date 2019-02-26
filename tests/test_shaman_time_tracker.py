import unittest
from unittest import mock

from blender_asset_tracer.pack.shaman import time_tracker


class TimeTrackerTest(unittest.TestCase):
    @mock.patch('time.monotonic')
    def test_empty_class(self, mock_monotonic):
        class TestClass:
            pass

        mock_monotonic.side_effect = [1.25, 4.75]
        with time_tracker.track_time(TestClass, 'some_attr'):
            pass

        # noinspection PyUnresolvedReferences
        self.assertEqual(3.5, TestClass.some_attr)

    @mock.patch('time.monotonic')
    def test_with_value(self, mock_monotonic):
        class TestClass:
            some_attr = 4.125

        mock_monotonic.side_effect = [1.25, 4.75]
        with time_tracker.track_time(TestClass, 'some_attr'):
            pass

        self.assertEqual(3.5 + 4.125, TestClass.some_attr)

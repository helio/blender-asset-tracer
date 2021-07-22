import pathlib
import sys
import unittest

import mypy.api

import blender_asset_tracer


class MypyRunnerTest(unittest.TestCase):
    def test_run_mypy(self):
        # This test doesn't work with Tox, it raises an AssertionError:
        # /path/to/blender-asset-tracer/.tox/py37/lib/python3.7/site-packages is in the PYTHONPATH.
        # Please change directory so it is not.
        for path in sys.path:
            if "/.tox/" in path and path.endswith("/site-packages"):
                self.skipTest("Mypy doesn't like Tox")

        path = pathlib.Path(blender_asset_tracer.__file__).parent
        result = mypy.api.run(["--incremental", "--ignore-missing-imports", str(path)])

        stdout, stderr, status = result

        messages = []
        if stderr:
            messages.append(stderr)
        if stdout:
            messages.append(stdout)
        if status:
            messages.append("Mypy failed with status %d" % status)
        if messages and not all(msg.startswith("Success: ") for msg in messages):
            self.fail("\n".join(["Mypy errors:"] + messages))

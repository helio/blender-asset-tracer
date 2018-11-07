import pathlib
import unittest

import mypy.api

import blender_asset_tracer


class MypyRunnerTest(unittest.TestCase):
    def test_run_mypy(self):
        path = pathlib.Path(blender_asset_tracer.__file__).parent
        result = mypy.api.run(['--incremental', '--ignore-missing-imports', str(path)])

        stdout, stderr, status = result

        messages = []
        if stderr:
            messages.append(stderr)
        if stdout:
            messages.append(stdout)
        if status:
            messages.append('Mypy failed with status %d' % status)
        if messages:
            self.fail('\n'.join(['Mypy errors:'] + messages))

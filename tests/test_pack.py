import collections
import logging
import pathlib
import sys
import tempfile
import typing

from blender_asset_tracer import blendfile, pack, bpathlib
from blender_asset_tracer.blendfile import dna
from abstract_test import AbstractBlendFileTest


class AbstractPackTest(AbstractBlendFileTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.getLogger('blender_asset_tracer.pack').setLevel(logging.DEBUG)
        logging.getLogger('blender_asset_tracer.blendfile.open_cached').setLevel(logging.DEBUG)
        logging.getLogger('blender_asset_tracer.blendfile.open_cached').setLevel(logging.DEBUG)
        logging.getLogger('blender_asset_tracer.blendfile.BlendFile').setLevel(logging.DEBUG)

    def setUp(self):
        super().setUp()
        self.tdir = tempfile.TemporaryDirectory(suffix='-packtest')
        self.tpath = pathlib.Path(self.tdir.name)
        # self.tpath = pathlib.Path('/tmp/tempdir-packtest')
        # self.tpath.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tdir.cleanup()

    @staticmethod
    def rewrites(packer: pack.Packer):
        return {path: action.rewrites
                for path, action in packer._actions.items()
                if action.rewrites}


class PackTest(AbstractPackTest):
    def test_strategise_no_rewrite_required(self):
        infile = self.blendfiles / 'doubly_linked.blend'

        packer = pack.Packer(infile, self.blendfiles, self.tpath)
        packer.strategise()

        packed_files = (
            'doubly_linked.blend',
            'linked_cube.blend',
            'basic_file.blend',
            'material_textures.blend',
            'textures/Bricks/brick_dotted_04-bump.jpg',
            'textures/Bricks/brick_dotted_04-color.jpg',
        )
        for pf in packed_files:
            path = self.blendfiles / pf
            act = packer._actions[path]
            self.assertEqual(pack.PathAction.KEEP_PATH, act.path_action, 'for %s' % pf)
            self.assertEqual(self.tpath / pf, act.new_path, 'for %s' % pf)

        self.assertEqual({}, self.rewrites(packer))

    def test_strategise_rewrite(self):
        ppath = self.blendfiles / 'subdir'
        infile = ppath / 'doubly_linked_up.blend'

        packer = pack.Packer(infile, ppath, self.tpath)
        packer.strategise()

        external_files = (
            'linked_cube.blend',
            'basic_file.blend',
            'material_textures.blend',
            'textures/Bricks/brick_dotted_04-bump.jpg',
            'textures/Bricks/brick_dotted_04-color.jpg',
        )
        # /tmp/target + /workspace/bat/tests/blendfiles → /tmp/target/workspace/bat/tests/blendfiles
        extpath = pathlib.Path(self.tpath, '_outside_project', *self.blendfiles.parts[1:])

        act = packer._actions[ppath / 'doubly_linked_up.blend']
        self.assertEqual(pack.PathAction.KEEP_PATH, act.path_action, 'for doubly_linked_up.blend')
        self.assertEqual(self.tpath / 'doubly_linked_up.blend', act.new_path,
                         'for doubly_linked_up.blend')
        for fn in external_files:
            path = self.blendfiles / fn
            act = packer._actions[path]
            self.assertEqual(pack.PathAction.FIND_NEW_LOCATION, act.path_action, 'for %s' % fn)
            self.assertEqual(extpath / fn, act.new_path, 'for %s' % fn)

        to_rewrite = (
            'linked_cube.blend',
            'material_textures.blend',
            'subdir/doubly_linked_up.blend',
        )
        rewrites = self.rewrites(packer)
        self.assertEqual([self.blendfiles / fn for fn in to_rewrite],
                         sorted(rewrites.keys()))

        # Library link referencing basic_file.blend should (maybe) be rewritten.
        rw_linked_cube = rewrites[self.blendfiles / 'linked_cube.blend']
        self.assertEqual(1, len(rw_linked_cube))
        self.assertEqual(b'LILib', rw_linked_cube[0].block_name)
        self.assertEqual(b'//basic_file.blend', rw_linked_cube[0].asset_path)

        # Texture links to image assets should (maybe) be rewritten.
        rw_mattex = rewrites[self.blendfiles / 'material_textures.blend']
        self.assertEqual(2, len(rw_mattex))
        rw_mattex.sort()  # for repeatable tests
        self.assertEqual(b'IMbrick_dotted_04-bump', rw_mattex[0].block_name)
        self.assertEqual(b'//textures/Bricks/brick_dotted_04-bump.jpg', rw_mattex[0].asset_path)
        self.assertEqual(b'IMbrick_dotted_04-color', rw_mattex[1].block_name)
        self.assertEqual(b'//textures/Bricks/brick_dotted_04-color.jpg', rw_mattex[1].asset_path)

        # Library links from doubly_linked_up.blend to the above to blend files should be rewritten.
        rw_dbllink = rewrites[self.blendfiles / 'subdir/doubly_linked_up.blend']
        self.assertEqual(2, len(rw_dbllink))
        rw_dbllink.sort()  # for repeatable tests
        self.assertEqual(b'LILib', rw_dbllink[0].block_name)
        self.assertEqual(b'//../linked_cube.blend', rw_dbllink[0].asset_path)
        self.assertEqual(b'LILib.002', rw_dbllink[1].block_name)
        self.assertEqual(b'//../material_textures.blend', rw_dbllink[1].asset_path)

    def test_execute_rewrite_no_touch_origs(self):
        infile, _ = self._pack_with_rewrite()

        # The original file shouldn't be touched.
        bfile = blendfile.open_cached(infile, assert_cached=False)
        libs = sorted(bfile.code_index[b'LI'])

        self.assertEqual(b'LILib', libs[0].id_name)
        self.assertEqual(b'//../linked_cube.blend', libs[0][b'name'])
        self.assertEqual(b'LILib.002', libs[1].id_name)
        self.assertEqual(b'//../material_textures.blend', libs[1][b'name'])

    def test_execute_rewrite(self):
        infile, _ = self._pack_with_rewrite()

        extpath = pathlib.Path('//_outside_project', *self.blendfiles.parts[1:])
        extbpath = bpathlib.BlendPath(extpath)

        # Those libraries should be properly rewritten.
        bfile = blendfile.open_cached(self.tpath / infile.name, assert_cached=False)
        libs = sorted(bfile.code_index[b'LI'])
        self.assertEqual(b'LILib', libs[0].id_name)
        self.assertEqual(extbpath / b'linked_cube.blend', libs[0][b'name'])
        self.assertEqual(b'LILib.002', libs[1].id_name)
        self.assertEqual(extbpath / b'material_textures.blend', libs[1][b'name'])

    def test_execute_rewrite_cleanup(self):
        infile, packer = self._pack_with_rewrite()

        # Rewritten blend files shouldn't be in the temp directory any more;
        # they should have been moved to the final directory (not copied).
        self.assertTrue(packer._rewrite_in.exists())
        self.assertEqual([], list(packer._rewrite_in.iterdir()))

        # After closing the packer, the tempdir should also be gone.
        packer.close()
        self.assertFalse(packer._rewrite_in.exists())

    def _pack_with_rewrite(self):
        ppath = self.blendfiles / 'subdir'
        infile = ppath / 'doubly_linked_up.blend'

        packer = pack.Packer(infile, ppath, self.tpath)
        packer.strategise()
        packer.execute()

        return infile, packer

    def test_noop(self):
        ppath = self.blendfiles / 'subdir'
        infile = ppath / 'doubly_linked_up.blend'

        packer = pack.Packer(infile, ppath, self.tpath, noop=True)
        packer.strategise()
        packer.execute()

        self.assertEqual([], list(self.tpath.iterdir()))

        # The original file shouldn't be touched.
        bfile = blendfile.open_cached(infile)
        libs = sorted(bfile.code_index[b'LI'])

        self.assertEqual(b'LILib', libs[0].id_name)
        self.assertEqual(b'//../linked_cube.blend', libs[0][b'name'])
        self.assertEqual(b'LILib.002', libs[1].id_name)
        self.assertEqual(b'//../material_textures.blend', libs[1][b'name'])

    def test_missing_files(self):
        infile = self.blendfiles / 'missing_textures.blend'
        packer = pack.Packer(infile, self.blendfiles, self.tpath)
        packer.strategise()

        self.assertEqual(
            [self.blendfiles / 'textures/HDRI/Myanmar/Golden Palace 2, Old Bagan-1k.exr',
             self.blendfiles / 'textures/Textures/Marble/marble_decoration-color.png'],
            sorted(packer.missing_files)
        )

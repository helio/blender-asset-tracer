import collections
import logging
import pathlib
import sys
import tempfile
import typing

from blender_asset_tracer import blendfile, pack
from blender_asset_tracer.blendfile import dna
from abstract_test import AbstractBlendFileTest


class AbstractPackTest(AbstractBlendFileTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.getLogger('blender_asset_tracer.pack').setLevel(logging.DEBUG)

    def setUp(self):
        super().setUp()
        self.tdir = tempfile.TemporaryDirectory()
        self.tpath = pathlib.Path(self.tdir.name)

    def tearDown(self):
        self.tdir.cleanup()

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
        self.assertEqual({self.blendfiles / fn: self.tpath / fn
                          for fn in packed_files},
                         packer._packed_paths)

        for pf in packed_files:
            path = self.blendfiles / pf
            act = packer._actions[path]
            self.assertEqual(pack.PathAction.KEEP_PATH, act.path_action, 'for %s' % pf)
            self.assertEqual(self.tpath / pf, act.new_path, 'for %s' % pf)

        self.assertEqual({}, packer._rewrites)

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
        self.assertEqual(self.tpath / 'doubly_linked_up.blend',
                         packer._packed_paths[ppath / 'doubly_linked_up.blend'])

        # /tmp/target + /workspace/bat/tests/blendfiles → /tmp/target/workspace/bat/tests/blendfiles
        extpath = pathlib.Path(self.tpath, '_outside_project', *self.blendfiles.parts[1:])
        for fn in external_files:
            self.assertEqual(extpath / fn,
                             packer._packed_paths[self.blendfiles / fn],
                             'for %s' % fn)

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
        self.assertEqual([self.blendfiles / fn for fn in to_rewrite],
                         sorted(packer._rewrites.keys()))

        # Library link referencing basic_file.blend should (maybe) be rewritten.
        rw_linked_cube = packer._rewrites[self.blendfiles / 'linked_cube.blend']
        self.assertEqual(1, len(rw_linked_cube))
        self.assertEqual(b'LILib', rw_linked_cube[0].block_name)
        self.assertEqual(b'//basic_file.blend', rw_linked_cube[0].asset_path)

        # Texture links to image assets should (maybe) be rewritten.
        rw_mattex = packer._rewrites[self.blendfiles / 'material_textures.blend']
        self.assertEqual(2, len(rw_mattex))
        rw_mattex.sort()  # for repeatable tests
        self.assertEqual(b'IMbrick_dotted_04-bump', rw_mattex[0].block_name)
        self.assertEqual(b'//textures/Bricks/brick_dotted_04-bump.jpg', rw_mattex[0].asset_path)
        self.assertEqual(b'IMbrick_dotted_04-color', rw_mattex[1].block_name)
        self.assertEqual(b'//textures/Bricks/brick_dotted_04-color.jpg', rw_mattex[1].asset_path)

        # Library links from doubly_linked_up.blend to the above to blend files should be rewritten.
        rw_dbllink = packer._rewrites[self.blendfiles / 'subdir/doubly_linked_up.blend']
        self.assertEqual(2, len(rw_dbllink))
        rw_dbllink.sort()  # for repeatable tests
        self.assertEqual(b'LILib', rw_dbllink[0].block_name)
        self.assertEqual(b'//../linked_cube.blend', rw_dbllink[0].asset_path)
        self.assertEqual(b'LILib.002', rw_dbllink[1].block_name)
        self.assertEqual(b'//../material_textures.blend', rw_dbllink[1].asset_path)

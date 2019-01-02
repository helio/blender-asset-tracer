import logging
import pathlib
import typing

import tempfile
from unittest import mock

from blender_asset_tracer import blendfile, pack, bpathlib
from blender_asset_tracer.pack import progress
from abstract_test import AbstractBlendFileTest


class AbstractPackTest(AbstractBlendFileTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.getLogger('blender_asset_tracer.compressor').setLevel(logging.DEBUG)
        logging.getLogger('blender_asset_tracer.pack').setLevel(logging.DEBUG)
        logging.getLogger('blender_asset_tracer.blendfile.open_cached').setLevel(logging.DEBUG)
        logging.getLogger('blender_asset_tracer.blendfile.open_cached').setLevel(logging.DEBUG)
        logging.getLogger('blender_asset_tracer.blendfile.BlendFile').setLevel(logging.DEBUG)

    def setUp(self):
        super().setUp()
        self.tdir = tempfile.TemporaryDirectory(suffix='-packtest')
        self.tpath = pathlib.Path(self.tdir.name)

    def tearDown(self):
        super().tearDown()
        self.tdir.cleanup()

    @staticmethod
    def rewrites(packer: pack.Packer):
        return {path: action.rewrites
                for path, action in packer._actions.items()
                if action.rewrites}

    def outside_project(self) -> pathlib.Path:
        """Return the '_outside_project' path for files in self.blendfiles."""
        # /tmp/target + /workspace/bat/tests/blendfiles → /tmp/target/workspace/bat/tests/blendfiles
        extpath = pathlib.Path(self.tpath, '_outside_project', *self.blendfiles.parts[1:])
        return extpath


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
        self.assertEqual(len(packed_files), len(packer._actions))

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
        extpath = self.outside_project()

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

    def test_strategise_relative_only(self):
        infile = self.blendfiles / 'absolute_path.blend'

        packer = pack.Packer(infile, self.blendfiles, self.tpath,
                             relative_only=True)
        packer.strategise()

        packed_files = (
            'absolute_path.blend',
            # Linked with a relative path:
            'textures/Bricks/brick_dotted_04-color.jpg',
            # This file links to textures/Textures/Buildings/buildings_roof_04-color.png,
            # but using an absolute path, so that file should be skipped.
        )
        for pf in packed_files:
            path = self.blendfiles / pf
            act = packer._actions[path]
            self.assertEqual(pack.PathAction.KEEP_PATH, act.path_action, 'for %s' % pf)
            self.assertEqual(self.tpath / pf, act.new_path, 'for %s' % pf)

        self.assertEqual(len(packed_files), len(packer._actions))
        self.assertEqual({}, self.rewrites(packer))

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

        extpath = pathlib.PurePosixPath('//_outside_project', *self.blendfiles.parts[1:])
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

    def test_rewrite_sequence(self):
        ppath = self.blendfiles / 'subdir'
        infile = ppath / 'image_sequence_dir_up.blend'

        with pack.Packer(infile, ppath, self.tpath) as packer:
            packer.strategise()
            packer.execute()

        bf = blendfile.open_cached(self.tpath / infile.name, assert_cached=False)
        scene = bf.code_index[b'SC'][0]
        ed = scene.get_pointer(b'ed')
        seq = ed.get_pointer((b'seqbase', b'first'))
        seq_strip = seq.get_pointer(b'strip')

        imgseq_path = (self.blendfiles / 'imgseq').absolute()
        as_bytes = str(imgseq_path.relative_to(imgseq_path.anchor)).encode()
        relpath = bpathlib.BlendPath(b'//_outside_project') / as_bytes

        # The image sequence base path should be rewritten.
        self.assertEqual(b'SQ000210.png', seq[b'name'])
        self.assertEqual(relpath, seq_strip[b'dir'])

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

    def test_exclude_filter(self):
        # Files shouldn't be reported missing if they should be ignored.
        infile = self.blendfiles / 'image_sequencer.blend'
        with pack.Packer(infile, self.blendfiles, self.tpath) as packer:
            packer.exclude('*.png', '*.nonsense')
            packer.strategise()
            packer.execute()

        self.assertFalse((self.tpath / 'imgseq').exists())

    def test_exclude_filter_missing_files(self):
        # Files shouldn't be reported missing if they should be ignored.
        infile = self.blendfiles / 'missing_textures.blend'
        with pack.Packer(infile, self.blendfiles, self.tpath) as packer:
            packer.exclude('*.png')
            packer.strategise()

        self.assertEqual(
            [self.blendfiles / 'textures/HDRI/Myanmar/Golden Palace 2, Old Bagan-1k.exr'],
            list(packer.missing_files)
        )

    def test_output_path(self):
        infile = self.blendfiles / 'basic_file.blend'
        packer = pack.Packer(infile, self.blendfiles.parent, self.tpath)
        packer.strategise()

        self.assertEqual(
            self.tpath / self.blendfiles.name / infile.name,
            packer.output_path
        )

    def test_infofile(self):
        blendname = 'subdir/doubly_linked_up.blend'
        infile = self.blendfiles / blendname

        packer = pack.Packer(infile, self.blendfiles, self.tpath)
        packer.strategise()
        packer.execute()

        infopath = self.tpath / 'pack-info.txt'
        self.assertTrue(infopath.exists())
        info = infopath.open().read().splitlines(keepends=False)
        self.assertEqual(blendname, info[-1].strip())

    def test_compression(self):
        blendname = 'subdir/doubly_linked_up.blend'
        imgfile = self.blendfiles / blendname

        packer = pack.Packer(imgfile, self.blendfiles, self.tpath, compress=True)
        packer.strategise()
        packer.execute()

        dest = self.tpath / blendname
        self.assertTrue(dest.exists())
        self.assertTrue(blendfile.open_cached(dest).is_compressed)

        for bpath in self.tpath.rglob('*.blend'):
            if bpath == dest:
                # Only test files that were bundled as dependency; the main
                # file was tested above already.
                continue
            self.assertTrue(blendfile.open_cached(bpath).is_compressed,
                            'Expected %s to be compressed' % bpath)
            break
        else:
            self.fail('Expected to have Blend files in the BAT pack.')

        for imgpath in self.tpath.rglob('*.jpg'):
            with imgpath.open('rb') as imgfile:
                magic = imgfile.read(3)
            self.assertEqual(b'\xFF\xD8\xFF', magic,
                             'Expected %s to NOT be compressed' % imgpath)
            break
        else:
            self.fail('Expected to have JPEG files in the BAT pack.')


class ProgressTest(AbstractPackTest):
    def test_strategise(self):
        cb = mock.Mock(progress.Callback)
        infile = self.blendfiles / 'subdir/doubly_linked_up.blend'
        with pack.Packer(infile, self.blendfiles, self.tpath) as packer:
            packer.progress_cb = cb
            packer.strategise()

        self.assertEqual(1, cb.pack_start.call_count)
        self.assertEqual(0, cb.pack_done.call_count)

        expected_calls = [
            mock.call(self.blendfiles / 'subdir/doubly_linked_up.blend'),
            mock.call(self.blendfiles / 'linked_cube.blend'),
            mock.call(self.blendfiles / 'basic_file.blend'),
            mock.call(self.blendfiles / 'material_textures.blend'),
        ]
        cb.trace_blendfile.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(len(expected_calls), cb.trace_blendfile.call_count)

        expected_calls = [
            mock.call(self.blendfiles / 'linked_cube.blend'),
            mock.call(self.blendfiles / 'basic_file.blend'),
            mock.call(self.blendfiles / 'material_textures.blend'),
            mock.call(self.blendfiles / 'textures/Bricks/brick_dotted_04-color.jpg'),
            mock.call(self.blendfiles / 'textures/Bricks/brick_dotted_04-bump.jpg'),
        ]
        cb.trace_asset.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(len(expected_calls), cb.trace_asset.call_count)

        self.assertEqual(0, cb.rewrite_blendfile.call_count)
        self.assertEqual(0, cb.transfer_file.call_count)
        self.assertEqual(0, cb.transfer_file_skipped.call_count)
        self.assertEqual(0, cb.transfer_progress.call_count)
        self.assertEqual(0, cb.missing_file.call_count)

    def test_execute_with_rewrite(self):
        cb = mock.Mock(progress.Callback)
        infile = self.blendfiles / 'subdir/doubly_linked_up.blend'
        with pack.Packer(infile, infile.parent, self.tpath) as packer:
            packer.progress_cb = cb
            packer.strategise()
            packer.execute()

        self.assertEqual(1, cb.pack_start.call_count)
        self.assertEqual(1, cb.pack_done.call_count)

        # rewrite_blendfile should only be called paths in a blendfile are
        # actually rewritten.
        cb.rewrite_blendfile.assert_called_with(self.blendfiles / 'subdir/doubly_linked_up.blend')
        self.assertEqual(1, cb.rewrite_blendfile.call_count)

        # mock.ANY is used for temporary files in temporary paths, because they
        # are hard to predict.
        extpath = self.outside_project()
        expected_calls = [
            mock.call(mock.ANY, self.tpath / 'doubly_linked_up.blend'),
            mock.call(mock.ANY, self.tpath / 'pack-info.txt'),
            mock.call(mock.ANY, extpath / 'linked_cube.blend'),
            mock.call(mock.ANY, extpath / 'basic_file.blend'),
            mock.call(mock.ANY, extpath / 'material_textures.blend'),
            mock.call(self.blendfiles / 'textures/Bricks/brick_dotted_04-color.jpg',
                      extpath / 'textures/Bricks/brick_dotted_04-color.jpg'),
            mock.call(self.blendfiles / 'textures/Bricks/brick_dotted_04-bump.jpg',
                      extpath / 'textures/Bricks/brick_dotted_04-bump.jpg'),
        ]
        cb.transfer_file.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(len(expected_calls), cb.transfer_file.call_count)

        self.assertEqual(0, cb.transfer_file_skipped.call_count)
        self.assertGreaterEqual(cb.transfer_progress.call_count, 6,
                                'transfer_progress() should be called at least once per asset')
        self.assertEqual(0, cb.missing_file.call_count)

    def test_missing_files(self):
        cb = mock.Mock(progress.Callback)
        infile = self.blendfiles / 'missing_textures.blend'
        with pack.Packer(infile, self.blendfiles, self.tpath) as packer:
            packer.progress_cb = cb
            packer.strategise()
            packer.execute()

        self.assertEqual(1, cb.pack_start.call_count)
        self.assertEqual(1, cb.pack_done.call_count)

        cb.rewrite_blendfile.assert_not_called()
        cb.transfer_file.assert_has_calls([
            mock.call(infile, self.tpath / 'missing_textures.blend'),
            mock.call(mock.ANY, self.tpath / 'pack-info.txt'),
        ], any_order=True)

        self.assertEqual(0, cb.transfer_file_skipped.call_count)
        self.assertGreaterEqual(cb.transfer_progress.call_count, 1,
                                'transfer_progress() should be called at least once per asset')

        expected_calls = [
            mock.call(self.blendfiles / 'textures/HDRI/Myanmar/Golden Palace 2, Old Bagan-1k.exr'),
            mock.call(self.blendfiles / 'textures/Textures/Marble/marble_decoration-color.png'),
        ]
        cb.missing_file.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(len(expected_calls), cb.missing_file.call_count)

    def test_particle_cache(self):
        # The particle cache uses a glob to indicate which files to pack.
        cb = mock.Mock(progress.Callback)
        infile = self.blendfiles / 'T55539-particles/particle.blend'
        with pack.Packer(infile, self.blendfiles, self.tpath) as packer:
            packer.progress_cb = cb
            packer.strategise()
            packer.execute()

        # We should have all the *.bphys files now.
        count = len(list((self.tpath / 'T55539-particles/blendcache_particle').glob('*.bphys')))
        self.assertEqual(27, count)

        # Physics files + particle.blend + pack_info.txt
        self.assertGreaterEqual(cb.transfer_progress.call_count, 29,
                                'transfer_progress() should be called at least once per asset')

    def test_particle_cache_with_ignore_glob(self):
        cb = mock.Mock(progress.Callback)
        infile = self.blendfiles / 'T55539-particles/particle.blend'
        with pack.Packer(infile, self.blendfiles, self.tpath) as packer:
            packer.progress_cb = cb
            packer.exclude('*.bphys')
            packer.strategise()
            packer.execute()

        # We should have none of the *.bphys files now.
        count = len(list((self.tpath / 'T55539-particles/blendcache_particle').glob('*.bphys')))
        self.assertEqual(0, count)

        # Just particle.blend + pack_info.txt
        self.assertGreaterEqual(cb.transfer_progress.call_count, 2,
                                'transfer_progress() should be called at least once per asset')

    def test_smoke_cache(self):
        # The smoke cache uses a glob to indicate which files to pack.
        cb = mock.Mock(progress.Callback)
        infile = self.blendfiles / 'T55542-smoke/smoke_cache.blend'
        with pack.Packer(infile, self.blendfiles, self.tpath) as packer:
            packer.progress_cb = cb
            packer.strategise()
            packer.execute()

        # We should have all the *.bphys files now.
        count = len(list((self.tpath / 'T55542-smoke/blendcache_smoke_cache').glob('*.bphys')))
        self.assertEqual(10, count)

        # Physics files + smoke_cache.blend + pack_info.txt
        self.assertGreaterEqual(cb.transfer_progress.call_count, 12,
                                'transfer_progress() should be called at least once per asset')


class AbortTest(AbstractPackTest):
    def test_abort_strategise(self):
        infile = self.blendfiles / 'subdir/doubly_linked_up.blend'
        packer = pack.Packer(infile, self.blendfiles, self.tpath)

        class AbortingCallback(progress.Callback):
            def trace_blendfile(self, filename: pathlib.Path):
                # Call abort() somewhere during the strategise() call.
                if filename.name == 'linked_cube.blend':
                    packer.abort()

        packer.progress_cb = AbortingCallback()
        with packer, self.assertRaises(pack.Aborted):
            packer.strategise()

    def test_abort_transfer(self):
        infile = self.blendfiles / 'subdir/doubly_linked_up.blend'
        packer = pack.Packer(infile, self.blendfiles, self.tpath)

        first_file_size = infile.stat().st_size

        class AbortingCallback(progress.Callback):
            def transfer_progress(self, total_bytes: int, transferred_bytes: int):
                # Call abort() somewhere during the file transfer.
                if total_bytes > first_file_size * 1.1:
                    packer.abort()

        packer.progress_cb = AbortingCallback()
        with packer:
            packer.strategise()
            with self.assertRaises(pack.Aborted):
                packer.execute()

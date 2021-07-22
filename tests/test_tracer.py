import collections
import logging
import sys
import typing

from blender_asset_tracer import trace, blendfile
from blender_asset_tracer.blendfile import dna
from tests.abstract_test import AbstractBlendFileTest

# Mimicks a BlockUsage, but without having to set the block to an expected value.
Expect = collections.namedtuple(
    "Expect", "type full_field dirname_field basename_field asset_path is_sequence"
)


class AbstractTracerTest(AbstractBlendFileTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.getLogger("blender_asset_tracer.tracer").setLevel(logging.DEBUG)


class AssetHoldingBlocksTest(AbstractTracerTest):
    def setUp(self):
        self.bf = blendfile.BlendFile(self.blendfiles / "basic_file.blend")

    def test_simple_file(self):
        # This file should not depend on external assets.
        blocks_seen = 0
        seen_scene = seen_ob = False

        for block in trace.asset_holding_blocks(self.bf.blocks):
            assert isinstance(block, blendfile.BlendFileBlock)
            blocks_seen += 1

            # The four-letter-code blocks don't refer to assets, so they
            # shouldn't be yielded.
            self.assertEqual(2, len(block.code))

            # World blocks should not yielded either.
            self.assertNotEqual(b"WO", block.code)

            # Do some arbitrary tests that convince us stuff is read well.
            if block.code == b"SC":
                seen_scene = True
                self.assertEqual(b"SCScene", block.id_name)
                continue

            if block.code == b"OB":
                seen_ob = True
                self.assertEqual("OBümlaut", block.get((b"id", b"name"), as_str=True))
                continue

        self.assertTrue(seen_scene)
        self.assertTrue(seen_ob)

        # Many of the data blocks are skipped, because asset_holding_blocks() only
        # yields top-level, directly-understandable blocks.
        #
        # The numbers here are taken from whatever the code does now; I didn't
        # count the actual blocks in the actual blend file.
        self.assertEqual(965, len(self.bf.blocks))
        self.assertEqual(4, blocks_seen)


class DepsTest(AbstractTracerTest):
    @staticmethod
    def field_name(field: dna.Field) -> typing.Optional[str]:
        if field is None:
            return None
        return field.name.name_full.decode()

    def assert_deps(self, blend_fname, expects: dict):
        for dep in trace.deps(self.blendfiles / blend_fname):
            actual_type = dep.block.dna_type.dna_type_id.decode()
            actual_full_field = self.field_name(dep.path_full_field)
            actual_dirname = self.field_name(dep.path_dir_field)
            actual_basename = self.field_name(dep.path_base_field)

            actual = Expect(
                actual_type,
                actual_full_field,
                actual_dirname,
                actual_basename,
                dep.asset_path,
                dep.is_sequence,
            )

            exp = expects.get(dep.block_name, None)
            if isinstance(exp, (set, list)):
                self.assertIn(actual, exp, msg="for block %s" % dep.block_name)
                exp.remove(actual)
                if not exp:
                    # Don't leave empty sets in expects.
                    del expects[dep.block_name]
            elif exp is None:
                self.assertIsNone(
                    actual, msg="unexpected dependency of block %s" % dep.block_name
                )
                del expects[dep.block_name]
            else:
                self.assertEqual(exp, actual, msg="for block %s" % dep.block_name)
                del expects[dep.block_name]

        # All expected uses should have been seen.
        self.assertEqual(expects, {}, "Expected results were not seen.")

    def test_no_deps(self):
        self.assert_deps("basic_file.blend", {})

    def test_ob_mat_texture(self):
        expects = {
            b"IMbrick_dotted_04-bump": Expect(
                "Image",
                "name[1024]",
                None,
                None,
                b"//textures/Bricks/brick_dotted_04-bump.jpg",
                False,
            ),
            b"IMbrick_dotted_04-color": Expect(
                "Image",
                "name[1024]",
                None,
                None,
                b"//textures/Bricks/brick_dotted_04-color.jpg",
                False,
            ),
            # This data block is in there, but the image is packed, so it
            # shouldn't be in the results.
            # b'IMbrick_dotted_04-specular': Expect(
            #     'Image', 'name[1024]', None, None,
            #     b'//textures/Bricks/brick_dotted_04-specular.jpg', False),
            b"IMbuildings_roof_04-color": Expect(
                "Image",
                "name[1024]",
                None,
                None,
                b"//textures/Textures/Buildings/buildings_roof_04-color.png",
                False,
            ),
        }
        self.assert_deps("material_textures.blend", expects)

    def test_seq_image_sequence(self):
        expects = {
            b"-unnamed-": [
                Expect(
                    "Strip", None, "dir[768]", "name[256]", b"//imgseq/000210.png", True
                ),
                # Video strip reference.
                Expect(
                    "Strip",
                    None,
                    "dir[768]",
                    "name[256]",
                    b"//../../../../cloud/pillar/testfiles/video-tiny.mkv",
                    False,
                ),
                # The sound will be referenced twice, from the sequence strip and an SO data block.
                Expect(
                    "Strip",
                    None,
                    "dir[768]",
                    "name[256]",
                    b"//../../../../cloud/pillar/testfiles/video-tiny.mkv",
                    False,
                ),
            ],
            b"SOvideo-tiny.mkv": Expect(
                "bSound",
                "name[1024]",
                None,
                None,
                b"//../../../../cloud/pillar/testfiles/video-tiny.mkv",
                False,
            ),
        }
        self.assert_deps("image_sequencer.blend", expects)

        # Test the filename expansion.
        expected = [
            self.blendfiles / ("imgseq/%06d.png" % num) for num in range(210, 215)
        ]
        for dep in trace.deps(self.blendfiles / "image_sequencer.blend"):
            if dep.block_name != b"SQ000210.png":
                continue

            actual = list(dep.files())
            self.assertEqual(actual, expected)

    def test_block_cf(self):
        self.assert_deps(
            "alembic-user.blend",
            {
                b"CFclothsim.abc": Expect(
                    "CacheFile", "filepath[1024]", None, None, b"//clothsim.abc", False
                ),
            },
        )

    def test_alembic_sequence(self):
        self.assert_deps(
            "alembic-sequence-user.blend",
            {
                b"CFclothsim_alembic": Expect(
                    "CacheFile",
                    "filepath[1024]",
                    None,
                    None,
                    b"//clothsim.030.abc",
                    True,
                ),
            },
        )

        # Test the filename expansion.
        expected = [
            self.blendfiles / ("clothsim.%03d.abc" % num) for num in range(30, 36)
        ]
        performed_test = False
        for dep in trace.deps(self.blendfiles / "alembic-sequence-user.blend"):
            if dep.block_name != b"CFclothsim_alembic":
                continue

            actual = list(dep.files())
            self.assertEqual(actual, expected)
            performed_test = True
        self.assertTrue(performed_test)

    def test_block_mc(self):
        self.assert_deps(
            "movieclip.blend",
            {
                b"MCvideo.mov": Expect(
                    "MovieClip",
                    "name[1024]",
                    None,
                    None,
                    b"//../../../../cloud/pillar/testfiles/video.mov",
                    False,
                ),
            },
        )

    def test_block_me(self):
        self.assert_deps(
            "multires_external.blend",
            {
                b"MECube": Expect(
                    "Mesh", "filename[1024]", None, None, b"//Cube.btx", False
                ),
            },
        )

    def test_ocean(self):
        self.assert_deps(
            "ocean_modifier.blend",
            {
                b"OBPlane.modifiers[0]": Expect(
                    "OceanModifierData",
                    "cachepath[1024]",
                    None,
                    None,
                    b"//cache_ocean",
                    True,
                ),
            },
        )

    def test_particles(self):
        # This file has an empty name for the cache, which should result in some hex magic
        # to create a name. See ptcache_filename() in pointcache.c.
        self.assert_deps(
            "T55539-particles/particle.blend",
            {
                b"OBCube.modifiers[0]": Expect(
                    "PointCache",
                    "name[64]",
                    None,
                    None,
                    b"//blendcache_particle/43756265_*.bphys",
                    True,
                ),
            },
        )

    def test_smoke(self):
        # This file has an empty name for the cache, which should result in some hex magic
        # to create a name. See ptcache_filename() in pointcache.c.
        self.assert_deps(
            "T55542-smoke/smoke_cache.blend",
            {
                b"OBSmoke Domain.modifiers[0]": Expect(
                    "PointCache",
                    "name[64]",
                    None,
                    None,
                    b"//blendcache_smoke_cache/536D6F6B6520446F6D61696E_*.bphys",
                    True,
                ),
            },
        )
        self.assert_deps(
            "T55542-smoke/smoke_cache_vdb.blend",
            {
                b"OBSmoke Domain.modifiers[0]": Expect(
                    "PointCache",
                    "name[64]",
                    None,
                    None,
                    b"//blendcache_smoke_cache_vdb/536D6F6B6520446F6D61696E_*.vdb",
                    True,
                ),
            },
        )

    def test_mesh_cache(self):
        self.assert_deps(
            "meshcache-user.blend",
            {
                b"OBPlane.modifiers[0]": Expect(
                    "MeshCacheModifierData",
                    "filepath[1024]",
                    None,
                    None,
                    b"//meshcache.mdd",
                    False,
                ),
            },
        )

    def test_block_vf(self):
        self.assert_deps(
            "with_font.blend",
            {
                b"VFHack-Bold": Expect(
                    "VFont",
                    "name[1024]",
                    None,
                    None,
                    b"/usr/share/fonts/truetype/hack/Hack-Bold.ttf",
                    False,
                ),
            },
        )

    def test_block_li(self):
        self.assert_deps(
            "linked_cube.blend",
            {
                b"LILib": Expect(
                    "Library", "name[1024]", None, None, b"//basic_file.blend", False
                ),
            },
        )

    def test_deps_recursive(self):
        self.assert_deps(
            "doubly_linked.blend",
            {
                b"LILib": {
                    # From doubly_linked.blend
                    Expect(
                        "Library",
                        "name[1024]",
                        None,
                        None,
                        b"//linked_cube.blend",
                        False,
                    ),
                    # From linked_cube.blend
                    Expect(
                        "Library",
                        "name[1024]",
                        None,
                        None,
                        b"//basic_file.blend",
                        False,
                    ),
                },
                b"LILib.002": Expect(
                    "Library",
                    "name[1024]",
                    None,
                    None,
                    b"//material_textures.blend",
                    False,
                ),
                # From material_texture.blend
                b"IMbrick_dotted_04-bump": Expect(
                    "Image",
                    "name[1024]",
                    None,
                    None,
                    b"//textures/Bricks/brick_dotted_04-bump.jpg",
                    False,
                ),
                b"IMbrick_dotted_04-color": Expect(
                    "Image",
                    "name[1024]",
                    None,
                    None,
                    b"//textures/Bricks/brick_dotted_04-color.jpg",
                    False,
                ),
                # This data block is in the basic_file.blend file, but not used by
                # any of the objects linked in from linked_cube.blend or
                # doubly_linked.blend, hence it should *not* be reported:
                # b'IMbuildings_roof_04-color': Expect(
                #     'Image', 'name[1024]', None, None,
                #     b'//textures/Textures/Buildings/buildings_roof_04-color.png', False),
            },
        )

    def test_geometry_nodes(self):
        self.assert_deps(
            "geometry-nodes/file_to_pack.blend",
            {
                b"LInode_lib.blend": Expect(
                    type="Library",
                    full_field="name[1024]",
                    dirname_field=None,
                    basename_field=None,
                    asset_path=b"//node_lib.blend",
                    is_sequence=False,
                ),
                b"LIobject_lib.blend": Expect(
                    type="Library",
                    full_field="name[1024]",
                    dirname_field=None,
                    basename_field=None,
                    asset_path=b"//object_lib.blend",
                    is_sequence=False,
                ),
            },
        )

    def test_usage_abspath(self):
        deps = [
            dep
            for dep in trace.deps(self.blendfiles / "doubly_linked.blend")
            if dep.asset_path == b"//material_textures.blend"
        ]
        usage = deps[0]

        expect = self.blendfiles / "material_textures.blend"
        self.assertEqual(expect, usage.abspath)

    def test_sim_data(self):
        self.assert_deps(
            "T53562/bam_pack_bug.blend",
            {
                b"OBEmitter.modifiers[0]": Expect(
                    "PointCache",
                    "name[64]",
                    None,
                    None,
                    b"//blendcache_bam_pack_bug/particles_*.bphys",
                    True,
                ),
            },
        )

    def test_recursion_loop(self):
        infinite_bfile = self.blendfiles / "recursive_dependency_1.blend"

        reclim = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(100)
            # This should finish without hitting the recursion limit.
            for _ in trace.deps(infinite_bfile):
                pass
        finally:
            sys.setrecursionlimit(reclim)

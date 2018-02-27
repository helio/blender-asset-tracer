from blender_asset_tracer import blendfile, bpathlib
from blender_asset_tracer.blendfile import dna


class BlockUsage:
    """Represents the use of an asset by a data block.

    :ivar block_name: an identifying name for this block. Defaults to the ID
        name of the block.
    :ivar block:
    :ivar asset_path:
    :ivar is_sequence: Indicates whether this file is alone (False), the
        first of a sequence (True, and the path points to a file), or a
        directory containing a sequence (True, and path points to a directory).
        In certain cases such files should be reported once (f.e. when
        rewriting the source field to another path), and in other cases the
        sequence should be expanded (f.e. when copying all assets to a BAT
        Pack).
    :ivar path_full_field: field containing the full path of this asset.
    :ivar path_dir_field: field containing the parent path (i.e. the
        directory) of this asset.
    :ivar path_base_field: field containing the basename of this asset.
    """

    def __init__(self,
                 block: blendfile.BlendFileBlock,
                 asset_path: bpathlib.BlendPath,
                 is_sequence: bool = False,
                 path_full_field: dna.Field = None,
                 path_dir_field: dna.Field = None,
                 path_base_field: dna.Field = None,
                 block_name: bytes = '',
                 ):
        if block_name:
            self.block_name = block_name
        else:
            try:
                self.block_name = block[b'id', b'name']
            except KeyError:
                try:
                    self.block_name = block[b'name']
                except KeyError:
                    self.block_name = b'-unnamed-'

        assert isinstance(block, blendfile.BlendFileBlock)
        assert isinstance(asset_path, (bytes, bpathlib.BlendPath)), \
            'asset_path should be BlendPath, not %r' % type(asset_path)

        if path_full_field is None:
            assert isinstance(path_dir_field, dna.Field), \
                'path_dir_field should be dna.Field, not %r' % type(path_dir_field)
            assert isinstance(path_base_field, dna.Field), \
                'path_base_field should be dna.Field, not %r' % type(path_base_field)
        else:
            assert isinstance(path_full_field, dna.Field), \
                'path_full_field should be dna.Field, not %r' % type(path_full_field)

        if isinstance(asset_path, bytes):
            asset_path = bpathlib.BlendPath(asset_path)

        self.block = block
        self.asset_path = asset_path
        self.is_sequence = bool(is_sequence)
        self.path_full_field = path_full_field
        self.path_dir_field = path_dir_field
        self.path_base_field = path_base_field

    def __repr__(self):
        return '<BlockUsage name=%r type=%r field=%r asset=%r%s>' % (
            self.block_name, self.block.dna_type_name,
            self.path_full_field.name.name_full.decode(), self.asset_path,
            ' sequence' if self.is_sequence else ''
        )

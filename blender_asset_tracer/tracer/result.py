

class BlockUsage:
    """Represents the use of an asset by a data block.

    :ivar block:
    :type block: blendfile.BlendFileBlock
    :ivar field:
    :type field: dna.Field
    :ivar asset_path:
    :type asset_path: bpathlib.BlendPath
    """

    def __init__(self, block, field, asset_path):
        self.block_idname = block[b'id', b'name']

        from blender_asset_tracer import blendfile, bpathlib
        from blender_asset_tracer.blendfile import dna

        assert isinstance(block, blendfile.BlendFileBlock)
        assert isinstance(field, dna.Field), 'field should be dna.Field, not %r' % type(field)
        assert isinstance(asset_path, (bytes, bpathlib.BlendPath)), \
            'asset_path should be BlendPath, not %r' % type(asset_path)

        if isinstance(asset_path, bytes):
            asset_path = bpathlib.BlendPath(asset_path)

        self.block = block
        self.field = field
        self.asset_path = asset_path

    def __repr__(self):
        return '<BlockUsage name=%r type=%r field=%r asset=%r>' % (
            self.block_idname, self.block.dna_type_name,
            self.field.name.name_full.decode(), self.asset_path)

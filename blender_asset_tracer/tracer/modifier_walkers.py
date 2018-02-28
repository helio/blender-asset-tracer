"""Modifier handling code used in block_walkers.py

The _modifier_xxx() functions all yield result.BlockUsage objects for external
files used by the modifiers.
"""
import typing

from blender_asset_tracer import blendfile, bpathlib
from . import result, cdefs


def _modifier_filepath(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    """Just yield the 'filepath' field."""
    path, field = modifier.get(b'filepath', return_field=True)
    yield result.BlockUsage(modifier, path, path_full_field=field, block_name=block_name)


def _modifier_ocean(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    if not modifier[b'cached']:
        return

    path, field = modifier.get(b'cachepath', return_field=True)
    # The path indicates the directory containing the cached files.
    yield result.BlockUsage(modifier, path, is_sequence=True, path_full_field=field,
                            block_name=block_name)


def _modifier_particle_system(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    psys = modifier.get_pointer(b'psys')
    if psys is None:
        return

    pointcache = psys.get_pointer(b'pointcache')
    if pointcache is None:
        return

    flag = pointcache[b'flag']

    if flag & cdefs.PTCACHE_DISK_CACHE:
        # See ptcache_path() in pointcache.c
        name, field = pointcache.get(b'name', return_field=True)
        path = b'//%b%b/%b_*%b' % (
            cdefs.PTCACHE_PATH,
            modifier.bfile.filepath.stem.encode(),
            name,
            cdefs.PTCACHE_EXT)
        bpath = bpathlib.BlendPath(path)
        yield result.BlockUsage(pointcache, bpath, path_full_field=field,
                                is_sequence=True, block_name=block_name)

    if flag & cdefs.PTCACHE_EXTERNAL:
        path, field = pointcache.get(b'path', return_field=True)
        yield result.BlockUsage(pointcache, path, path_full_field=field,
                                is_sequence=True, block_name=block_name)


modifier_handlers = {
    cdefs.eModifierType_ParticleSystem: _modifier_particle_system,
    cdefs.eModifierType_Ocean: _modifier_ocean,
    cdefs.eModifierType_MeshCache: _modifier_filepath,
}

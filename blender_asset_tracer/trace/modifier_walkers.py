# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
#
# (c) 2018, Blender Foundation - Sybren A. Stüvel
"""Modifier handling code used in blocks2assets.py

The modifier_xxx() functions all yield result.BlockUsage objects for external
files used by the modifiers.
"""
import typing

from blender_asset_tracer import blendfile, bpathlib, cdefs
from . import result

modifier_handlers = {}  # type: typing.Dict[int, typing.Callable]


def mod_handler(dna_num: int):
    """Decorator, marks decorated func as handler for that modifier number."""

    assert isinstance(dna_num, int)

    def decorator(wrapped):
        modifier_handlers[dna_num] = wrapped
        return wrapped

    return decorator


@mod_handler(cdefs.eModifierType_MeshCache)
def modifier_filepath(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    """Just yield the 'filepath' field."""
    path, field = modifier.get(b'filepath', return_field=True)
    yield result.BlockUsage(modifier, path, path_full_field=field, block_name=block_name)


@mod_handler(cdefs.eModifierType_Ocean)
def modifier_ocean(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    if not modifier[b'cached']:
        return

    path, field = modifier.get(b'cachepath', return_field=True)
    # The path indicates the directory containing the cached files.
    yield result.BlockUsage(modifier, path, is_sequence=True, path_full_field=field,
                            block_name=block_name)


def _get_texture(prop_name: bytes, dblock: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    """Yield block usages from a texture propery.

    Assumes dblock[prop_name] is a texture data block.
    """
    if dblock is None:
        return

    tx = dblock.get_pointer(prop_name)
    yield from _get_image(b'ima', tx, block_name)


def _get_image(prop_name: bytes, dblock: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    """Yield block usages from an image propery.

    Assumes dblock[prop_name] is an image data block.
    """
    if not dblock:
        return
    ima = dblock.get_pointer(prop_name)
    if not ima:
        return

    path, field = ima.get(b'name', return_field=True)
    yield result.BlockUsage(ima, path, path_full_field=field, block_name=block_name)


@mod_handler(cdefs.eModifierType_Displace)
@mod_handler(cdefs.eModifierType_Wave)
def modifier_texture(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    return _get_texture(b'texture', modifier, block_name)


@mod_handler(cdefs.eModifierType_WeightVGEdit)
@mod_handler(cdefs.eModifierType_WeightVGMix)
@mod_handler(cdefs.eModifierType_WeightVGProximity)
def modifier_mask_texture(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    return _get_texture(b'mask_texture', modifier, block_name)


@mod_handler(cdefs.eModifierType_UVProject)
def modifier_image(modifier: blendfile.BlendFileBlock, block_name: bytes) \
        -> typing.Iterator[result.BlockUsage]:
    yield from _get_image(b'image', modifier, block_name)


@mod_handler(cdefs.eModifierType_ParticleSystem)
def modifier_particle_system(modifier: blendfile.BlendFileBlock, block_name: bytes) \
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
        bpath = bpathlib.BlendPath(path)
        yield result.BlockUsage(pointcache, bpath, path_full_field=field,
                                is_sequence=True, block_name=block_name)

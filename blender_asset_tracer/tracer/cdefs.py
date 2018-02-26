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

"""Constants defined in C."""

# DNA_sequence_types.h (Sequence.type)
SEQ_TYPE_IMAGE = 0
SEQ_TYPE_META = 1
SEQ_TYPE_SCENE = 2
SEQ_TYPE_MOVIE = 3
SEQ_TYPE_SOUND_RAM = 4
SEQ_TYPE_SOUND_HD = 5
SEQ_TYPE_MOVIECLIP = 6
SEQ_TYPE_MASK = 7
SEQ_TYPE_EFFECT = 8

IMA_SRC_FILE = 1
IMA_SRC_SEQUENCE = 2
IMA_SRC_MOVIE = 3

# DNA_modifier_types.h
eModifierType_MeshCache = 46

# DNA_particle_types.h
PART_DRAW_OB = 7
PART_DRAW_GR = 8

# DNA_object_types.h
# Object.transflag
OB_DUPLIGROUP = 1 << 8

CACHE_LIBRARY_SOURCE_CACHE = 1

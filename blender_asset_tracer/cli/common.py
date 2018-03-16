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
"""Common functionality for CLI parsers."""
import pathlib


def add_flag(argparser, flag_name: str, **kwargs):
    """Add a CLI argument for the flag.

    The flag defaults to False, and when present on the CLI stores True.
    """

    argparser.add_argument('-%s' % flag_name[0],
                           '--%s' % flag_name,
                           default=False,
                           action='store_true',
                           **kwargs)


def shorten(cwd: pathlib.Path, somepath: pathlib.Path) -> pathlib.Path:
    """Return 'somepath' relative to CWD if possible."""
    try:
        return somepath.relative_to(cwd)
    except ValueError:
        return somepath

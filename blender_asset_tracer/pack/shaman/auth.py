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
# (c) 2019, Blender Foundation - Sybren A. Stüvel
import requests

token = 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiIxMjM0NSIsImV4cCI6MTU1MDI0NDUxMiwiaWF0IjoxNTUwMTU4MTEyLCJzdWIiOiJ1c2VyLUlEIn0.oahZHIVBmULFz0JhOjv4-AEN8vdURjGBiIDdZbvW9A2FQWdi0RyrW2KpcHHpKS8KiG81p9pn2bVytMrRJ8Cjmw'


def session():
    sess = requests.session()
    sess.headers['Authorization'] = 'Bearer ' + token
    return sess

#!/usr/bin/env python3
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
from setuptools import setup, find_packages

import sys

if sys.version_info < (3, 5):
    print("Sorry, Python %s is not supported, minimum is Python 3.5" % (sys.version_info,))
    sys.exit(1)

setup(
    name='blender-asset-tracer',
    version='1.1',
    url='https://gitlab.com/dr.sybren/blender-asset-tracer',
    download_url='https://pypi.python.org/pypi/blender-asset-tracer',
    license='GPLv2+',
    author='Sybren A. Stüvel',
    author_email='sybren@stuvel.eu',
    description='Blender Asset Tracer',
    long_description='BAT parses Blend files and produces dependency information. '
                     'After installation run `bat --help`.',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=find_packages('.'),
    include_package_data=True,
    package_data={
        '': ['*.txt', '*.md'],
    },
    entry_points={
        'console_scripts': [
            'bat = blender_asset_tracer.cli:cli_main',
        ],
    },
    extras_require={
        's3': ['boto3'],
    },
    zip_safe=True,
)

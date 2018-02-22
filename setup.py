from setuptools import setup

import sys
if sys.version_info < (3, 5):
    print("Sorry, Python %s is not supported, minimum is Python 3.5" % (sys.version_info, ))
    sys.exit(1)


setup(
    name='blender-asset-tracer',
    version='0.1-dev',
    url='http://developer.blender.org/',
    download_url='https://pypi.python.org/pypi/blender-ferret',
    license='GPLv2+',
    author='Sybren A. Stüvel, Campbell Barton',
    author_email='sybren@stuvel.eu',
    description='Blender Asset Tracer',
    long_description='BAT🦇 parses Blend files and produces dependency information.',
    classifiers=[
        'Development Status :: 3 - Alpha',
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
    packages=['blender_asset_tracer'],
    include_package_data=True,
    package_data={
        '': ['*.txt', '*.md'],
        },
    entry_points={
        'console_scripts': [
            # 'bf = bam.cli:main',
        ],
    },
    zip_safe=True,
)

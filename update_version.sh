#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 new-version" >&2
    exit 1
fi

poetry version $1
sed "s/version = '[^']*'/version = '$1'/" -i  docs/conf.py
sed "s/release = '[^']*'/release = '$1'/" -i docs/conf.py
sed "s/__version__\s*=\s*\"[^']*\"/__version__ = \"$1\"/" -i blender_asset_tracer/__init__.py
sed --posix "s/\(dist\/blender[_-]asset[_-]tracer-\)\([0-9.betalphdv-]*[0-9]\)/\1$1/g" -i README.md

git diff
echo
echo "Don't forget to commit and tag:"
echo git commit -m \'Bumped version to $1\' pyproject.toml blender_asset_tracer/__init__.py docs/conf.py README.md
echo git tag -a v$1 -m \'Tagged version $1\'
echo
echo "Build the package & upload to PyPi using:"
echo "poetry build"
echo "twine check dist/blender_asset_tracer-$1.tar.gz dist/blender_asset_tracer-$1-*.whl"
echo "twine upload -r bat dist/blender_asset_tracer-$1.tar.gz dist/blender_asset_tracer-$1-*.whl"

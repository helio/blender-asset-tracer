#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 new-version" >&2
    exit 1
fi

sed "s/version='[^']*'/version='$1'/" -i setup.py
sed "s/version = '[^']*'/version = '$1'/" -i  docs/conf.py
sed "s/release = '[^']*'/release = '$1'/" -i docs/conf.py
sed "s/__version__\s*=\s*'[^']*'/__version__ = '$1'/" -i blender_asset_tracer/__init__.py

git diff
echo
echo "Don't forget to commit and tag:"
echo git commit -m \'Bumped version to $1\' setup.py blender_asset_tracer/__init__.py docs/conf.py
echo git tag -a v$1 -m \'Tagged version $1\'
echo
echo "Build the package & upload to PyPi using:"
echo "pipenv run ./setup.py sdist bdist_wheel"
echo "pipenv run twine upload dist/blender*asset*tracer*${VERSION}*"

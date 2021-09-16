#! /bin/bash

pip uninstall baslerpi 
rm -rf  *egg-info
rm -rf build/ dist
python setup.py sdist bdist_wheel
python setup.py install --force

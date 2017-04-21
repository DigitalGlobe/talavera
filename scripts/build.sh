#!/bin/bash
/opt/python/cp27-cp27mu/bin/pip install /app/scripts/GDAL-2.1.1-cp27-cp27mu-manylinux1_x86_64.whl
/opt/python/cp27-cp27mu/bin/pip install -r /app/scripts/requirements.txt
mkdir -p /app/build
cp -r /opt/python/cp27-cp27mu/lib/python2.7/site-packages/* /app/build

import sys
from setuptools import setup, find_packages

setup(name='talavera',
      version='0.0.1',
      description='A vector tiling package for GBDX vector services',
      classifiers=[],
      keywords='',
      author='Chris Helm',
      author_email='chris.helm@digitalglobe.com',
      url='https://github.com/DigitalGlobe/talavera',
      license='MIT',
      packages=['talavera'],
      include_package_data=True,
      zip_safe=False,
      install_requires=['requests==2.12.1',
                        'boto==2.39.0',
                        'boto3',
                        'shapely',
                        'pyproj',
                        'mapbox-vector-tile',
                        'mercantile',
                        'gbdxtools'
                        ]
      )

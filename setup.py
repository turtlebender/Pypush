from setuptools import setup, find_packages

setup(name='pypush',
        version='0.1',
        author='Rafael Turner',
        packages=['.'],
        install_requires=[ 'fabric', 'redis' ],
        )

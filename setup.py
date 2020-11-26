from setuptools import find_packages, setup
from setuptools.command.install import install
import os


class InstallSetup(install):
    def run(self):
        install.run(self)


setup(
    name='windnode_abw',
    version='0.0.1',
    packages=find_packages(),
    url='https://github.com/windnode/WindNODE_ABW',
    license='GNU Affero General Public License v3.0',
    author='nesnoj',
    author_email='',
    description='A regional simulation model',
    install_requires = [
        'oemof',
        'shapely',
        'pandas >=1, <1.1',
        'geopandas',
        'GeoAlchemy2',
        'matplotlib',
        'networkx',
        'psycopg2-binary',
        'keyring',
        'egoio',
        'pyproj',
        'pygraphviz',
        'configobj',
        'descartes',
        'psutil',
        'seaborn',
        'plotly',
        'papermill',
        'Pyomo==5.6.7',
        'PyUtilib==5.7.2',
        'kaleido',
        'notebook'
    ],
    package_data={
        'windnode_abw': [
            os.path.join('config',
                         'config_system'),
            os.path.join('config',
                         '*.cfg')
        ]
        },
    cmdclass={
      'install': InstallSetup}
)

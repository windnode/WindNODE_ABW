from setuptools import find_packages, setup
from setuptools.command.install import install
import os

BASEPATH='.WindNODE_ABW'


class InstallSetup(install):
    def run(self):
        #self.create_edisgo_path()
        install.run(self)

    # @staticmethod
    # def create_edisgo_path():
    #     edisgo_path = os.path.join(os.path.expanduser('~'), BASEPATH)
    #     data_path = os.path.join(edisgo_path, 'data')
    #
    #     if not os.path.isdir(edisgo_path):
    #         os.mkdir(edisgo_path)
    #     if not os.path.isdir(data_path):
    #         os.mkdir(data_path)


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
        'pandas',
        'GeoAlchemy2',
        'matplotlib',
        'networkx',
        'psycopg2-binary',
        'keyring',
        'egoio'
    ],
    # package_data={
    #     'config': [
    #         os.path.join('config',
    #                      'config_system'),
    #         os.path.join('config',
    #                      '*.cfg')
    #     ]
    #     },
    cmdclass={
      'install': InstallSetup}
)

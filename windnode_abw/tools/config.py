"""This module provides a highlevel layer for reading and writing config files.
There must be a file called "config.ini" in the root-folder of the project.
The file has to be of the following structure to be imported correctly.
# this is a comment \n
# the filestructure is like: \n
 \n
[netCDF] \n
RootFolder = c://netCDF \n
FilePrefix = cd2_ \n
 \n
[mySQL] \n
host = localhost \n
user = guest \n
password = root \n
database = znes \n
 \n
[SectionName] \n
OptionName = value \n
Option2 = value2 \n
"""

__copyright__  = "Reiner Lemoine Institut gGmbH"
__license__    = "GNU Affero General Public License Version 3 (AGPL-3.0)"
__url__        = "https://github.com/windnode/WindNODE_ABW/blob/master/LICENSE"
__author__     = "nesnoj"


import os
from glob import glob
import shutil
import windnode_abw
import logging


logger = logging.getLogger('windnode_abw')


try:
    import configparser as cp
except:
    # to be compatible with Python2.7
    import ConfigParser as cp

cfg = cp.RawConfigParser()
_loaded = False

# load config dirs
package_path = windnode_abw.__path__[0]
internal_config_file = os.path.join(package_path, 'config', 'config_system')
try:
    cfg.read(internal_config_file)
except:
    logger.exception('Internal config {} file not found.'.format(internal_config_file))

def load_config(filename):
    config_file = os.path.join(get_data_root_dir(), get('user_dirs', 'config_dir'), filename)

    # config file does not exist -> copy default
    if not os.path.isfile(config_file):
        logger.info('Config file {} not found, I will create a default version'
                    .format(config_file))
        shutil.copy(os.path.join(os.path.join(package_path, 'config'),
                                 filename.replace('.cfg', '_default.cfg')),
                    config_file)

    cfg.read(config_file)
    global _loaded
    _loaded = True


def get(section, key):
    """
    returns the value of a given key of a given section of the main
    config file.
    :param section: the section.
    :type section: str.
    :param key: the key.
    :type key: str.
    :returns: the value which will be casted to float, int or boolean.
    if no cast is successfull, the raw string will be returned.
    """
    if not _loaded:
        pass
    try:
        return cfg.getfloat(section, key)
    except Exception:
        try:
            return cfg.getint(section, key)
        except:
            try:
                return cfg.getboolean(section, key)
            except:
                return cfg.get(section, key)


def get_data_root_dir():
    """Get root dir of data which is located in parent directory of package directory"""
    root_dir = get('user_dirs', 'root_dir')
    root_path = os.path.join(os.path.expanduser('~'), root_dir)

    return root_path


def create_data_dirtree():
    """Create data root path, if necessary"""
    root_path = get_data_root_dir()

    # root dir does not exist
    if not os.path.isdir(root_path):
        # create it
        logger.warning('WindNODE_ABW data root path {} not found, I will create it including subdirectories.'
                       .format(root_path))
        os.mkdir(root_path)

        # create subdirs
        subdirs = ['config_dir', 'log_dir', 'data_dir', 'results_dir']
        for subdir in subdirs:
            path = os.path.join(root_path, get('user_dirs', subdir))
            os.mkdir(path)

        # copy default config files
        config_path = os.path.join(root_path, get('user_dirs', 'config_dir'))
        logger.info('I will create a default set of config files in {}'
                    .format(config_path))
        internal_config_dir = os.path.join(package_path, 'config')
        for file in glob(os.path.join(internal_config_dir, '*.cfg')):
            shutil.copy(file,
                        os.path.join(config_path,
                                     os.path.basename(file)
                                     .replace('_default', '')))

create_data_dirtree()

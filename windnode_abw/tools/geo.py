import logging
logger = logging.getLogger('windnode_abw')
from windnode_abw.tools import config

import pyproj
from functools import partial
from shapely.wkb import loads as wkb_loads
from shapely.wkb import dumps as wkb_dumps


def proj2equidistant():
    """Defines conformal (e.g. WGS84) to ETRS (equidistant) projection
    Source CRS is loaded from Network's config.

    Returns
    -------
    :functools:`partial`
    """
    srid = int(config.get('geo', 'srid'))

    return partial(pyproj.transform,
                   pyproj.Proj(init='epsg:{}'
                               .format(str(srid))),  # source coordinate system
                   pyproj.Proj(init='epsg:3035')  # destination coordinate system
                   )


def proj2conformal():
    """Defines ETRS (equidistant) to conformal (e.g. WGS84) projection.
    Target CRS is loaded from Network's config.

    Returns
    -------
    :functools:`partial`
    """
    srid = int(config.get('geo', 'srid'))

    return partial(pyproj.transform,
                   pyproj.Proj(init='epsg:3035'),  # source coordinate system
                   pyproj.Proj(init='epsg:{}'
                               .format(str(srid)))  # destination coordinate system
                   )


def convert_df_wkb_to_shapely(df, cols=[]):
    """Convert geometry columns of DataFrame from WKB to shapely object columns

    Parameters
    ----------
    df : :pandas:`pandas.DataFrame<dataframe>`
    cols : :obj:`list` of :obj:`str`
        Column names
    Returns
    -------
    :pandas:`pandas.DataFrame<dataframe>`
        DataFrame with converted columns
    """
    for col in cols:
        df[col] = df[col].apply(lambda x: wkb_loads(x, hex=True))

    return df


def convert_df_shapely_to_wkb(df, cols=[]):
    """Convert geometry columns of DataFrame from shapely object columns to WKB

    Parameters
    ----------
    df : :pandas:`pandas.DataFrame<dataframe>`
    cols : :obj:`list` of :obj:`str`
        Column names
    Returns
    -------
    :pandas:`pandas.DataFrame<dataframe>`
        DataFrame with converted columns
    """
    for col in cols:
        df[col] = df[col].apply(lambda x: wkb_dumps(x, hex=True))

    return df
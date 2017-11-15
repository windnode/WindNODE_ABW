import pyproj
from functools import partial
from geopy.distance import vincenty

import logging
logger = logging.getLogger('edisgo')


def proj2equidistant(network):
    """Defines conformal (e.g. WGS84) to ETRS (equidistant) projection
    Source CRS is loaded from Network's config.

    Parameters
    ----------
    network : :class:`~.grid.network.Network`
        The eDisGo container object

    Returns
    -------
    :functools:`partial`
    """
    srid = int(network.config['geo']['srid'])

    return partial(pyproj.transform,
                   pyproj.Proj(init='epsg:{}'
                               .format(str(srid))),  # source coordinate system
                   pyproj.Proj(init='epsg:3035')  # destination coordinate system
                   )


def proj2conformal(network):
    """Defines ETRS (equidistant) to conformal (e.g. WGS84) projection.
    Target CRS is loaded from Network's config.

    Parameters
    ----------
    network : :class:`~.grid.network.Network`
        The eDisGo container object

    Returns
    -------
    :functools:`partial`
    """
    srid = int(network.config['geo']['srid'])

    return partial(pyproj.transform,
                   pyproj.Proj(init='epsg:3035'),  # source coordinate system
                   pyproj.Proj(init='epsg:{}'
                               .format(str(srid)))  # destination coordinate system
                   )

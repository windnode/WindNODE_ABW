import pyproj
from functools import partial
from geopy.distance import vincenty

import os
if not 'READTHEDOCS' in os.environ:
    from shapely.geometry import LineString
    from shapely.ops import transform

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


def calc_geo_dist_vincenty(network, node_source, node_target):
    """Calculates the geodesic distance between node_source and node_target
    incorporating the detour factor in config.

    Parameters
    ----------
    network : :class:`~.grid.network.Network`
        The eDisGo container object
    node_source : :class:`~.grid.components.Component`
        Node to connect (e.g. :class:`~.grid.components.Generator`)
    node_target : :class:`~.grid.components.Component`
        Target node (e.g. :class:`~.grid.components.BranchTee`)

    Returns
    -------
    :obj:`float`
        Distance in m

    Notes
    -----
    Adapted from `Ding0 <https://github.com/openego/ding0/blob/\
        21a52048f84ec341fe54e0204ac62228a9e8a32a/\
        ding0/tools/geo.py#L84>`_.
    """

    branch_detour_factor = network.config['connect']['branch_detour_factor']

    # notice: vincenty takes (lat,lon)
    branch_length = branch_detour_factor * vincenty((node_source.geom.y, node_source.geom.x),
                                                    (node_target.geom.y, node_target.geom.x)).m

    # ========= BUG: LINE LENGTH=0 WHEN CONNECTING GENERATORS ===========
    # When importing generators, the geom_new field is used as position. If it is empty, EnergyMap's geom
    # is used and so there are a couple of generators at the same position => length of interconnecting
    # line is 0. See issue #76
    if branch_length == 0:
        branch_length = 1
        logger.debug('Geo distance is zero, check objects\' positions. '
                     'Distance is set to 1m')
    # ===================================================================

    return branch_length

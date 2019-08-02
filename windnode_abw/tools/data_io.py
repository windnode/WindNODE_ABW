import logging
logger = logging.getLogger('windnode_abw')
from windnode_abw.tools import config

import os
import requests
import pandas as pd
import keyring

from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

from windnode_abw.tools.geo import convert_df_wkt_to_shapely
from egoio.tools.db import connection

from windnode_abw.config.db_models import \
    WnAbwDemandTs, WnAbwFeedinTs, WnAbwGridHvBus, WnAbwGridHvLine,\
    WnAbwGridHvmvSubstation, WnAbwGridMvGriddistrict, WnAbwGridHvTransformer,\
    WnAbwMun, WnAbwMundata, WnAbwPowerplant, WnAbwRelSubstIdAgsId


def db_session(db_section):
    """Create DB session using egoio

    Parameters
    ----------
    db_section : :obj:`str`
      Database section in ego.io db config (usually ~/.egoio/config.ini) which
      holds connection details. Note: keyring entry must exist for the section
      to load the credentials.

    Returns
    -------
    :class:`.sessionmaker`
        SQLAlchemy session
    """
    conn = connection(section=db_section)
    Session = sessionmaker(bind=conn)

    return Session()


def oep_get_token():
    """Read token (password) from system's keyring

    Returns
    -------
    :obj:`str`
        Token
    """
    service = 'OEP'
    user = 'token'

    token = keyring.get_password(service, user)

    if token:
        return token
    else:
        raise ValueError('No token found in keyring!')


def oep_api_get_data(schema, table, columns=[], conditions=[], order=''):
    """Retrieve data from Open Energy Platform (OEP) / Database

    Parameters
    ----------
    schema : :obj:`str`
        Database schema
    table : :obj:`str`
        Database table
    columns : :obj:`list` of :obj:`str`
        Table columns
    conditions : :obj:`list` of :obj:`str`
        Conditions to be applied on query
    order : :obj:`str`
        Column which data is sorted by (ascending)

    Returns
    -------
    :pandas:`pandas.DataFrame`
        Requested data
    """

    oep_url = config.get('data', 'oep_url')

    if not schema or not table:
        raise ValueError('Schema or table not specified.')

    columns = '&'.join('column='+col for col in columns)

    if conditions:
        conditions = '&' + '&'.join('where='+cond for cond in conditions)
    else:
        conditions = ''

    if order:
        order = '&order_by=' + order
    else:
        order = ''

    url = oep_url +\
          '/api/v0/schema/' +\
          schema +\
          '/tables/' +\
          table +\
          '/rows/?' + \
          columns +\
          conditions +\
          order

    result = requests.get(url)
    status = str(result.status_code)

    logger.info('Response from OEP: ' + status + ', elapsed time: ' + str(result.elapsed))
    if status != '200':
        logger.exception('Something went wrong during data retrieval from OEP: ')

    return pd.DataFrame(result.json())


def oep_api_write_data(schema, table, data):
    """Write datasets to a table on the Open Energy Platform (OEP) / Database

    Parameters
    ----------
    schema : :obj:`str`
        Database schema
    table : :obj:`str`
        Database table
    data : :pandas:`pandas.DataFrame`
        Data to be written. Column names of DataFrame have to equal column names of table.
        Note: If data involves geometries, they must follow WKB format.

    Returns
    -------
    :pandas:`pandas.DataFrame`
        Response, such as ids of inserted data
    """

    oep_url = config.get('data', 'oep_url')

    if not schema or not table:
        raise ValueError('Schema or table not specified.')

    url = oep_url +\
          '/api/v0/schema/' +\
          schema +\
          '/tables/' +\
          table +\
          '/rows/new'

    dataset = data.to_dict('records')

    # dataset = []
    # for idx, row in data.iterrows():
    #     dataset.append({'subst_id0': str(row['hvmv_subst_id0']),
    #                     'subst_id1': str(row['hvmv_subst_id1']),
    #                     'capacity': str(row['s_nom'])})
    #
    # dataset = {'id': 1, 'subst_id0': 1,
    #            'subst_id1': 2, 'capacity': 100}

    result = requests.post(url,
                           json={'query': dataset},
                           headers={'Authorization': 'Token %s'%oep_get_token()})
    status = str(result.status_code)

    logger.info('Response from OEP: ' + status + ', elapsed time: ' + str(result.elapsed))
    if status != '200':
        logger.exception('Something went wrong during data retrieval from OEP: ')

    return pd.DataFrame(result.json())


def import_db_data():
    """Import data from DB using SQLA DB models"""

    data = {}

    srid = int(config.get('geo', 'srid'))
    session = db_session('local_kopernikus')

    # import municipalities including stats
    logger.info('Importing municipalities...')

    muns_query = session.query(
        WnAbwMun.ags,
        WnAbwMun.name,
        func.ST_AsText(func.ST_Transform(
            WnAbwMun.geom, srid)).label('geom'),
        WnAbwRelSubstIdAgsId.subst_id,

        WnAbwMundata.pop_2017,
        WnAbwMundata.area,
        WnAbwMundata.gen_capacity_wind,
        WnAbwMundata.gen_capacity_pv_roof_small,
        WnAbwMundata.gen_capacity_pv_roof_large,
        WnAbwMundata.gen_capacity_pv_ground,
        WnAbwMundata.gen_capacity_hydro,
        WnAbwMundata.gen_capacity_bio,
        WnAbwMundata.gen_capacity_sewage_landfill_gas,
        WnAbwMundata.gen_capacity_conventional_large,
        WnAbwMundata.gen_capacity_conventional_small,

        WnAbwMundata.gen_count_wind,
        WnAbwMundata.gen_count_pv_roof_small,
        WnAbwMundata.gen_count_pv_roof_large,
        WnAbwMundata.gen_count_pv_ground,
        WnAbwMundata.gen_count_hydro,
        WnAbwMundata.gen_count_bio,
        WnAbwMundata.gen_count_sewage_landfill_gas,
        WnAbwMundata.gen_count_conventional_large,
        WnAbwMundata.gen_count_conventional_small,

        WnAbwMundata.dem_el_energy_hh,
        WnAbwMundata.dem_el_energy_rca,
        WnAbwMundata.dem_el_energy_ind,

        WnAbwMundata.dem_th_energy_hh,
        WnAbwMundata.dem_th_energy_rca,
        WnAbwMundata.dem_th_energy_dist_heat_share
    ).join(WnAbwMundata, WnAbwRelSubstIdAgsId).order_by(WnAbwMun.ags)

    data['muns'] = pd.read_sql_query(muns_query.statement,
                                     session.bind,
                                     index_col='ags')
    data['muns'] = convert_df_wkt_to_shapely(df=data['muns'],
                                             cols=['geom'])

    # import demand timeseries
    logger.info('Importing demand timeseries...')
    demandts_query = session.query(
        WnAbwDemandTs.ags_id.label('ags'),
        WnAbwDemandTs.el_hh,
        WnAbwDemandTs.el_rca,
        WnAbwDemandTs.el_ind,
        WnAbwDemandTs.th_hh_efh,
        WnAbwDemandTs.th_hh_mfh,
        WnAbwDemandTs.th_rca
    ).order_by(WnAbwDemandTs.timestamp)
    data['demand_ts_init'] = reformat_timeseries(
        pd.read_sql_query(demandts_query.statement,
                          session.bind)
    )

    # import feedin timeseries
    logger.info('Importing feedin timeseries...')
    feedints_query = session.query(
        WnAbwFeedinTs.ags_id.label('ags'),
        WnAbwFeedinTs.wind_sq,
        WnAbwFeedinTs.pv_ground,
        WnAbwFeedinTs.pv_roof,
        WnAbwFeedinTs.hydro,
        WnAbwFeedinTs.bio,
        WnAbwFeedinTs.conventional
    ).order_by(WnAbwFeedinTs.timestamp)
    data['feedin_ts_init'] = reformat_timeseries(
        pd.read_sql_query(feedints_query.statement,
                          session.bind)
    )

    # import HV grid (buses, lines, trafos, substations+grid districts)
    logger.info('Importing HV grid...')
    gridhvbus_query = session.query(
        WnAbwGridHvBus.bus_id,
        WnAbwGridHvBus.v_nom,
        WnAbwGridHvBus.hvmv_subst_id,
        WnAbwGridHvBus.region_bus,
        WnAbwGridHvBus.ags_id.label('ags'),
        func.ST_AsText(func.ST_Transform(
            WnAbwGridHvBus.geom, srid)).label('geom'),
    ).order_by(WnAbwGridHvBus.bus_id)
    data['buses'] = pd.read_sql_query(gridhvbus_query.statement,
                                      session.bind,
                                      index_col='bus_id')
    data['buses'] = convert_df_wkt_to_shapely(df=data['buses'],
                                              cols=['geom'])

    gridhvlines_query = session.query(
        WnAbwGridHvLine.line_id,
        WnAbwGridHvLine.bus0,
        WnAbwGridHvLine.bus1,
        WnAbwGridHvLine.x,
        WnAbwGridHvLine.r,
        WnAbwGridHvLine.g,
        WnAbwGridHvLine.b,
        WnAbwGridHvLine.s_nom,
        WnAbwGridHvLine.length,
        WnAbwGridHvLine.cables,
        func.ST_AsText(func.ST_Transform(
            WnAbwGridHvLine.geom, srid)).label('geom'),
    ).order_by(WnAbwGridHvLine.line_id)
    data['lines'] = pd.read_sql_query(gridhvlines_query.statement,
                                      session.bind)
    data['lines'] = convert_df_wkt_to_shapely(df=data['lines'],
                                              cols=['geom'])

    gridhvtrafo_query = session.query(
        WnAbwGridHvTransformer.trafo_id,
        WnAbwGridHvTransformer.bus0,
        WnAbwGridHvTransformer.bus1,
        WnAbwGridHvTransformer.x,
        WnAbwGridHvTransformer.r,
        WnAbwGridHvTransformer.g,
        WnAbwGridHvTransformer.b,
        WnAbwGridHvTransformer.s_nom,
        WnAbwGridHvTransformer.tap_ratio,
        WnAbwGridHvTransformer.phase_shift,
        WnAbwGridHvTransformer.ags_id.label('ags'),
        func.ST_AsText(func.ST_Transform(
            WnAbwGridHvTransformer.geom_point, srid)).label('geom'),
    ).order_by(WnAbwGridHvTransformer.trafo_id)
    data['trafos'] = pd.read_sql_query(gridhvtrafo_query.statement,
                                       session.bind,
                                       index_col='trafo_id')
    data['trafos'] = convert_df_wkt_to_shapely(df=data['trafos'],
                                               cols=['geom'])

    gridhvmvsubst_query = session.query(
        WnAbwGridHvmvSubstation.subst_id,
        WnAbwGridHvmvSubstation.otg_id.label('bus_id'),
        WnAbwGridHvmvSubstation.voltage,
        func.ST_AsText(func.ST_Transform(
            WnAbwGridHvmvSubstation.geom, srid)).label('geom'),
        func.ST_AsText(func.ST_Transform(
            WnAbwGridMvGriddistrict.geom, srid)).label('geom_mvgd'),
    ).join(
        WnAbwGridMvGriddistrict,
        WnAbwGridHvmvSubstation.subst_id == WnAbwGridMvGriddistrict.subst_id).\
        order_by(WnAbwGridHvmvSubstation.subst_id)
    data['subst'] = pd.read_sql_query(gridhvmvsubst_query.statement,
                                      session.bind,
                                      index_col='subst_id')
    data['subst'] = convert_df_wkt_to_shapely(df=data['subst'],
                                              cols=['geom', 'geom_mvgd'])

    # import generators
    logger.info('Importing generators...')
    generators_query = session.query(
        WnAbwPowerplant.id,
        WnAbwPowerplant.ags_id,
        WnAbwPowerplant.capacity,
        WnAbwPowerplant.chp,
        WnAbwPowerplant.com_month,
        WnAbwPowerplant.com_year,
        WnAbwPowerplant.energy_source_level_1,
        WnAbwPowerplant.energy_source_level_2,
        WnAbwPowerplant.energy_source_level_3,
        WnAbwPowerplant.technology,
        WnAbwPowerplant.thermal_capacity,
        WnAbwPowerplant.capacity_in,
        func.ST_AsText(func.ST_Transform(
            WnAbwPowerplant.geometry, srid)).label('geom')
    )
    data['generators'] = pd.read_sql_query(generators_query.statement,
                                           session.bind,
                                           index_col='id')
    data['generators'] = convert_df_wkt_to_shapely(df=data['generators'],
                                                   cols=['geom'])

    return data


def reformat_timeseries(ts):
    """Reformat timeseries

    Parameters
    ----------
    ts : :pandas:`pandas.DataFrame`
        Normalized timeseries with

    Returns
    -------
    :pandas:`pandas.DataFrame`
        Normalized timeseries with technology & mun MultiIndex on columns
    """

    return ts.pivot(index=ts.index, columns='ags') \
        .apply(lambda _: pd.Series(_.dropna().values)) \
        .fillna(0)


def oemof_nodes_from_excel(filename, header_lines=0):
    """

    Parameters
    ----------
    filename : :obj:`str`
        Path to excel file

    Returns
    -------
    :obj:`dict`
        Imported nodes data
    """
    # excel file does not exist
    if not filename or not os.path.isfile(filename):
        logger.exception('Excel data file {} not found.'
                         .format(filename))

    xls = pd.ExcelFile(filename)

    nodes_data = {'buses': xls.parse('buses', header=header_lines),
                  'chp': xls.parse('chp', header=header_lines),
                  'commodity_sources': xls.parse('commodity_sources', header=header_lines),
                  'transformers': xls.parse('transformers', header=header_lines),
                  'renewables': xls.parse('renewables', header=header_lines),
                  'demand': xls.parse('demand', header=header_lines),
                  'storages': xls.parse('storages', header=header_lines),
                  'powerlines': xls.parse('powerlines', header=header_lines),
                  'timeseries': xls.parse('time_series', header=header_lines)
                  }

    logger.info('Data from Excel file {} imported.'
                .format(filename))

    return nodes_data

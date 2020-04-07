import logging
logger = logging.getLogger('windnode_abw')
from windnode_abw.tools import config
from configobj import ConfigObj

import os
import requests
import pandas as pd
import keyring
import time
import json

from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

from windnode_abw.tools.geo import convert_df_wkt_to_shapely
from egoio.tools.db import connection

from windnode_abw.config.db_models import \
    WnAbwDemandTs, WnAbwFeedinTs, WnAbwGridHvBus, WnAbwGridHvLine,\
    WnAbwGridHvmvSubstation, WnAbwGridMvGriddistrict, WnAbwGridHvTransformer,\
    WnAbwMun, WnAbwMundata, WnAbwPowerplant, WnAbwRelSubstIdAgsId, WnAbwDsmTs,\
    WnAbwTempTs, WnAbwHeatingStructure, WnAbwTechAssumptions,\
    WnAbwPotentialAreasPv, WnAbwPotentialAreasWec


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


def import_db_data(cfg):
    """Import data from DB using SQLA DB models

    Parameters
    ----------
    cfg : :obj:`dict`
        Config to be used to create model

    Returns
    -------
    :obj:`dict`
        Imported data
    """

    data = {}

    srid = int(config.get('geo', 'srid'))
    session = db_session('windnode_abw')

    year = pd.to_datetime(cfg['date_from']).year
    datetime_index_full_year = pd.date_range(start=f'{year}-01-01 00:00:00',
                                             end=f'{year}-12-31 23:00:00',
                                             freq=cfg['freq'])

    ########################################################
    # import municipalities including stats and substation #
    ########################################################
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
        WnAbwMundata.dem_th_energy_rca
    ).join(WnAbwMundata).join(WnAbwRelSubstIdAgsId).order_by(WnAbwMun.ags)

    muns = pd.read_sql_query(muns_query.statement,
                             session.bind,
                             index_col='ags')
    # got one dataset per subst -> muns are duplicated -> create subst list
    muns['subst_id'] = muns.groupby(muns.index)['subst_id'].apply(list)
    # delete duplicates brought by groupby (drop_duplicates do not work here)
    muns = muns[~muns.duplicated(subset='gen')]
    # convert geom to shapely
    data['muns'] = convert_df_wkt_to_shapely(df=muns,
                                             cols=['geom'])

    ############################
    # import demand timeseries #
    ############################
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
    data['demand_ts_init'].index = datetime_index_full_year

    ############################
    # import feedin timeseries #
    ############################
    logger.info('Importing feedin timeseries...')
    feedints_query = session.query(
        WnAbwFeedinTs.ags_id.label('ags'),
        WnAbwFeedinTs.wind_sq,
        WnAbwFeedinTs.wind_fs,
        WnAbwFeedinTs.pv_ground,
        WnAbwFeedinTs.pv_roof,
        WnAbwFeedinTs.hydro,
        WnAbwFeedinTs.bio,
        WnAbwFeedinTs.conventional,
        WnAbwFeedinTs.solar_heat
    ).order_by(WnAbwFeedinTs.timestamp)
    data['feedin_ts_init'] = reformat_timeseries(
        pd.read_sql_query(feedints_query.statement,
                          session.bind)
    )
    data['feedin_ts_init'].index = datetime_index_full_year

    #########################
    # import DSM timeseries #
    #########################
    logger.info('Importing DSM timeseries...')
    dsmts_query = session.query(
        WnAbwDsmTs.ags_id.label('ags'),
        WnAbwDsmTs.Lastprofil,
        WnAbwDsmTs.Flex_Minus,
        WnAbwDsmTs.Flex_Minus_Max,
        WnAbwDsmTs.Flex_Plus,
        WnAbwDsmTs.Flex_Plus_Max,
    ).order_by(WnAbwDsmTs.timestamp)
    data['dsm_ts'] = reformat_timeseries(
        pd.read_sql_query(dsmts_query.statement,
                          session.bind)
    )
    data['dsm_ts'].index = datetime_index_full_year

    #################################
    # import temperature timeseries #
    #################################
    logger.info('Importing temperature timeseries...')
    tempts_query = session.query(
        WnAbwTempTs.ags_id.label('ags'),
        WnAbwTempTs.air_temp,
        WnAbwTempTs.soil_temp
    ).order_by(WnAbwTempTs.timestamp)
    data['temp_ts_init'] = reformat_timeseries(
        pd.read_sql_query(tempts_query.statement,
                          session.bind)
    )
    data['temp_ts_init'].index = datetime_index_full_year

    #####################################################################
    # import HV grid (buses, lines, trafos, substations+grid districts) #
    #####################################################################
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

    #####################
    # import generators #
    #####################
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

    #####################################
    # import heating structure (hh+rca) #
    #####################################
    logger.info('Importing heating structure...')
    heating_structure_query = session.query(
        WnAbwHeatingStructure.ags_id,
        WnAbwHeatingStructure.year,
        WnAbwHeatingStructure.energy_source,
        WnAbwHeatingStructure.tech_share_hh_efh.label('hh_efh'),
        WnAbwHeatingStructure.tech_share_hh_mfh.label('hh_mfh'),
        WnAbwHeatingStructure.tech_share_rca.label('rca')
    )
    data['heating_structure'] = pd.read_sql_query(
        heating_structure_query.statement,
        session.bind,
        index_col=['ags_id', 'energy_source', 'year'])

    #######################################################
    # import technical assumptions (costs, eff, emissions #
    #######################################################
    # convert units to MW/MWh (cf. table "Kosten_Emissionen_Wirkungsgrade")
    logger.info('Importing technical assumptions...')
    tech_assumptions_query = session.query(
        WnAbwTechAssumptions.technology,
        WnAbwTechAssumptions.year,
        (WnAbwTechAssumptions.capex * 1000).label('capex'),
        (WnAbwTechAssumptions.opex_fix * 1000).label('opex_fix'),
        (WnAbwTechAssumptions.opex_var * 1000).label('opex_var'),
        WnAbwTechAssumptions.lifespan,
        WnAbwTechAssumptions.emissions_fix,
        WnAbwTechAssumptions.emissions_var,
        (WnAbwTechAssumptions.sys_eff / 100).label('sys_eff')
    )
    data['tech_assumptions'] = pd.read_sql_query(
        tech_assumptions_query.statement,
        session.bind,
        index_col=['technology', 'year'])

    #####################################
    # import WEC and PV potential areas #
    #####################################
    logger.info('Importing RE potential areas...')
    pot_areas_pv_query = session.query(
        WnAbwPotentialAreasPv.ags_id,
        WnAbwPotentialAreasPv.scenario,
        WnAbwPotentialAreasPv.area_ha,
        func.ST_AsText(func.ST_Transform(
            WnAbwPotentialAreasPv.geom, srid)).label('geom')
    )
    data['pot_areas_pv'] = pd.read_sql_query(
        pot_areas_pv_query.statement,
        session.bind,
        index_col=['ags_id', 'scenario'])

    pot_areas_wec_query = session.query(
        WnAbwPotentialAreasWec.ags_id,
        WnAbwPotentialAreasWec.scenario,
        WnAbwPotentialAreasWec.area_ha,
        func.ST_AsText(func.ST_Transform(
            WnAbwPotentialAreasWec.geom, srid)).label('geom')
    )
    data['pot_areas_wec'] = pd.read_sql_query(
        pot_areas_wec_query.statement,
        session.bind,
        index_col=['ags_id', 'scenario'])

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

    TODO: Not used, remove?
    """
    # excel file does not exist
    if not filename or not os.path.isfile(filename):
        logger.exception(f'Excel data file {filename} not found.')

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

    logger.info(f'Data from Excel file {filename} imported.')

    return nodes_data


def load_scenario_cfg(scn_name=None):
    """Load scenario from ConfigObj file

    Parameters
    ----------
    scn_name : :obj:`str`
        Name of scenario
    """

    def convert2numeric(conf_dict):
        """Convert all string numbers to float values in `conf_dict`"""
        conf_dict2 = {}
        for key, val in conf_dict.items():
            if isinstance(val, dict):
                conf_dict2[key] = convert2numeric(val)
            else:
                try:
                    val = float(val)
                except:
                    pass
                conf_dict2[key] = val
        return conf_dict2

    if scn_name is not None:
        import windnode_abw

        path = os.path.join(windnode_abw.__path__[0],
                            'scenarios',
                            scn_name + '.scn')

        if not os.path.isfile(path):
            msg = f'Scenario file {path} does not exist, aborting'
            logger.info(msg)
            raise ValueError(msg)
        return convert2numeric(dict(ConfigObj(path)))


def export_results(results, meta, scenario_id):
    """Export results to CSV file, meta infos to JSON file

    A new directory is created

    Parameters
    ----------
    results : :obj:`dict`
        Results from optimization
    meta : :obj:
        Meta infos from optimization
    scenario_id : :obj:`str`
        Scenario id from cfg file
    """
    base_path = os.path.join(config.get_data_root_dir(),
                             config.get('user_dirs',
                                        'results_dir')
                             )
    results_subdir = time.strftime('%y%m%d_%H%M%S')
    results_path = os.path.join(base_path, results_subdir, scenario_id)
    os.makedirs(results_path)

    logger.info(f'Exporting results to {results_path} ...')

    for name, df in results.items():
        df.to_csv(os.path.join(results_path, f'{name}.csv'))

    with open(os.path.join(results_path, 'meta.json'), 'w', encoding='utf-8') as file:
        json.dump(meta, file, default=lambda _: '', ensure_ascii=False, indent=2)


def load_results(timestamp, scenario):
    """Load results from CSV and JSON

    Parameters
    ----------
    timestamp : :obj:`str`
        Timestamp of results, format: yymmdd_HHMMSS
    scenario : :obj:`str`
        Scenario id, e.g. "sq"

    Returns
    -------
    :obj:`dict`
        Results, content:
            :pandas:`pandas.DataFrame`
                DataFrame with flows, node pair as columns.
            :pandas:`pandas.DataFrame`
                DataFrame with stationary variables, (node, var) as columns.
                E.g. DSM measures dsm_up and dsm_do of DSM sink nodes.
            :pandas:`pandas.DataFrame`
                DataFrame with flow parameters, node pair as columns,
                params as index
            :pandas:`pandas.Series`
                Series with node parameters, (node, var) as index,
                labels is excluded
    """

    results_path = os.path.join(config.get_data_root_dir(),
                                config.get('user_dirs',
                                            'results_dir'),
                                timestamp,
                                scenario
                                )

    # DataFrames
    df_files = ['flows', 'vars_stat', 'params_flows']
    # Series
    se_files = ['params_stat']

    results = {}
    for file in df_files:
        results[file] = pd.read_csv(os.path.join(results_path, f'{file}.csv'),
                                    index_col=0,
                                    header=[0, 1])
    for file in se_files:
        results[file] = pd.read_csv(os.path.join(results_path, f'{file}.csv'),
                                    index_col=[0, 1],
                                    header=None,
                                    squeeze=True)

    with open(os.path.join(results_path, 'meta.json')) as file:
        results['meta'] = json.load(file)

    return results

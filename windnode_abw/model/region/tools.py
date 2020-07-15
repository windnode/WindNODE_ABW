import logging
logger = logging.getLogger('windnode_abw')

import pandas as pd
from pandas import compat
import networkx as nx
import matplotlib.pyplot as plt
from numpy import nan

import oemof.solph as solph
from oemof.tools.economics import annuity


def remove_isolates():
    raise NotImplementedError
    # logging.info('Removing orphan buses')
    # # get all buses
    # buses = [obj for obj in Regions.entities if isinstance(obj, Bus)]
    # for bus in buses:
    #     if len(bus.inputs) > 0 or len(bus.outputs) > 0:
    #         logging.debug('Bus {0} has connections.'.format(bus.type))
    #     else:
    #         logging.debug('Bus {0} has no connections and will be deleted.'.format(
    #             bus.type))
    #         Regions.entities.remove(bus)
    #
    # for i in esys.nodes[0].inputs.keys():
    #     print(i.label)


def reduce_to_regions(bus_data,
                      line_data):
    """Reduce/sum existing transport capacities to capacities between region pairs

    Parameters
    ----------
    bus_data
    line_data

    Returns
    -------

    """

    def _to_dict_dropna(data):
        return dict((k, v.dropna().to_dict()) for k, v in compat.iteritems(data))

    # convert nominal cap. to numeric
    line_data['s_nom'] = pd.to_numeric(line_data['s_nom'])

    bus_data_nogeom = bus_data[['bus_id', 'hvmv_subst_id']]

    # bus data needs bus_id as index
    bus_data_nogeom.set_index('bus_id', inplace=True)

    # join HV-MV substation ids from buses on lines
    line_data = line_data.join(bus_data_nogeom, on='bus0')
    line_data.rename(columns={'hvmv_subst_id': 'hvmv_subst_id0'}, inplace=True)
    line_data = line_data.join(bus_data_nogeom, on='bus1')
    line_data.rename(columns={'hvmv_subst_id': 'hvmv_subst_id1'}, inplace=True)

    # remove lines which are fully located in one region (MVGD)
    line_data = line_data[line_data['hvmv_subst_id0'] != line_data['hvmv_subst_id1']]

    # swap substation ids if not ascending to allow grouping
    cond = line_data['hvmv_subst_id0'] > line_data['hvmv_subst_id1']
    line_data.loc[cond, ['hvmv_subst_id0',
                         'hvmv_subst_id1']] = \
        line_data.loc[cond, ['hvmv_subst_id1', 'hvmv_subst_id0']].values

    line_data.sort_values(by='hvmv_subst_id0', inplace=True)

    # group by substation ids and sum up capacities
    line_data_grouped = line_data.groupby(
        ['hvmv_subst_id0', 'hvmv_subst_id1']).sum().reset_index()
    line_data_grouped.drop(['bus0', 'bus1', 'line_id'], axis=1, inplace=True)

    line_data_grouped.rename(columns={'s_nom': 'capacity'}, inplace=True)

    # OLD:
    # line_data_grouped = line_data.groupby(
    #     ['hvmv_subst_id0', 'hvmv_subst_id1'])['s_nom'].sum()
    # # flatten and transpose
    # line_data_grouped = line_data_grouped.unstack().transpose()
    # line_data_dict = _to_dict_dropna(line_data_grouped)

    return line_data_grouped


def region_graph(subst_data,
                 line_data,
                 rm_isolates=False,
                 draw=False):
    """Create graph representation of grid from substation and line data

    Parameters
    ----------
    subst_data
    line_data
    rm_isolates
    draw

    Returns
    -------
    networkx.Graph
        Graph representation of grid
    """

    def _find_main_graph(graph):
        """Remove isolated grids (subgraphs) of grid/graph

        Parameters
        ----------
        graph : networkx.Graph

        Returns
        -------
        networkx.Graph
        """

        subgraphs = {len(sg.nodes()): sg for sg in nx.connected_component_subgraphs(graph)}

        if len(subgraphs) > 1:
            logger.warning(f'Region consists of {len(subgraphs)} separate '
                           f'(unconnected) grids with node counts '
                           f'{list(subgraphs.keys())}. The grid with max. '
                           f'node count is used, the others are dropped.')

            # use subgraph with max. count of nodes
            subgraph_used = subgraphs[max(list(subgraphs.keys()))]
            #subgraphs_dropped = [sg for n_cnt, sg in subgraphs.iteritems() if n_cnt != max(list(subgraphs.keys()))]

            return subgraph_used

    # create graph
    graph = nx.Graph()
    npos = {}
    elabels = {}

    for idx, row in line_data.iterrows():
        source = row['hvmv_subst_id0']
        geom = subst_data.loc[source]['geom']
        npos[source] = (geom.x, geom.y)

        target = row['hvmv_subst_id1']
        geom = subst_data.loc[target]['geom']
        npos[target] = (geom.x, geom.y)

        elabels[(source, target)] = str(int(row['capacity']))
        graph.add_edge(source, target)

    # remove isolated grids (graphs)
    if rm_isolates:
        graph = _find_main_graph(graph=graph)

    # draw graph
    if draw:
        plt.figure()
        nx.draw_networkx(graph, pos=npos, with_labels=True, font_size=8)
        nx.draw_networkx_edge_labels(graph, pos=npos, edge_labels=elabels, font_size=8)
        plt.show()

    return graph


def grid_graph(region,
               draw=False):
    """Create graph representation of grid from substation and line data from Region object

    Parameters
    ----------
    region : :class:`~.model.Region`
    draw : :obj:`bool`
        If true, graph is plotted

    Returns
    -------
    networkx.Graph
        Graph representation of grid
    """

    # create graph
    graph = nx.Graph()
    npos = {}
    elabels = {}
    nodes_color = []

    for idx, row in region.lines.iterrows():
        source = row['bus0']
        geom = region.buses.loc[source]['geom']
        npos[source] = (geom.x, geom.y)

        target = row['bus1']
        geom = region.buses.loc[target]['geom']
        npos[target] = (geom.x, geom.y)

        elabels[(source, target)] = str(int(row['s_nom']))
        graph.add_edge(source, target)

    for bus in graph.nodes():
        if bus in list(region.subst['bus_id']):
            color = (0.7, 0.7, 1)
        else:
            color = (0.8, 0.8, 0.8)

        # mark buses which are connected to im- and export
        if (not region.buses.loc[bus]['region_bus'] or
            bus in (list(region.trafos['bus0']) + list(region.trafos['bus1']))
            ):
            color = (1, 0.7, 0.7)

        nodes_color.append(color)

    # draw graph
    if draw:
        plt.figure()
        nx.draw_networkx(graph, pos=npos, node_color=nodes_color, with_labels=True, font_size=6)
        nx.draw_networkx_edge_labels(graph, pos=npos, edge_labels=elabels, font_size=8)
        plt.title('Gridmap')
        plt.xlabel('lon')
        plt.ylabel('lat')
        plt.show()

    return graph


def calc_line_loading(esys, region):
    """Calculates relative loading of esys' lines

    Parameters
    ----------
    esys : oemof.solph.EnergySystem
        Energy system including results

    Returns
    -------
    :obj:`dict`
        Line loading of format (node_from, node_to): relative mean line loading
    :obj:`dict`
        Line loading of format (node_from, node_to): relative max, line loading
    """

    results = esys.results['main']
    om_flows = dict(esys.results['om_flows'])

    line_loading_mean = {
        (from_n, to_n): float(flow['sequences'].mean()) / om_flows[(from_n, to_n)].nominal_value
        for (from_n, to_n), flow in results.items()
        if isinstance(from_n, solph.custom.Link)
    }

    line_loading_mean2 = {}
    for (from_n, to_n), flow in results.items():
        if isinstance(from_n, solph.custom.Link):
            line_loading_mean2[(from_n, to_n)] =\
                float(flow['sequences'].mean()) / om_flows[(from_n, to_n)].nominal_value

            if float(flow['sequences'].mean()) != float(flow['sequences'].max()):
                print((from_n, to_n))

    line_loading_max = {
        (from_n, to_n): float(flow['sequences'].max()) / om_flows[(from_n, to_n)].nominal_value
        for (from_n, to_n), flow in results.items()
        if isinstance(from_n, solph.custom.Link)
    }

    results_lines = region.lines[['line_id', 'bus0', 'bus1']].copy()
    results_lines['loading_mean'] = 0.
    results_lines['loading_max'] = 0.

    # calc max. of 2 loadings (both directions) and save in DF
    for line in results_lines.itertuples():
        link = esys.groups['line_{line_id}_b{b0}_b{b1}'.format(
                    line_id=str(line.line_id),
                    b0=str(line.bus0),
                    b1=str(line.bus1)
                )]
        results_lines.at[line.Index, 'loading_mean'] = max([line_loading_mean[(from_n, to_n)]
                                                     for (from_n, to_n), loading in line_loading_mean.items()
                                                     if from_n == link])
        results_lines.at[line.Index, 'loading_max'] = max([line_loading_max[(from_n, to_n)]
                                                    for (from_n, to_n), loading in line_loading_max.items()
                                                    if from_n == link])
    # region.results_lines = results_lines.sort_values('loading_max')
    region.results_lines = results_lines

    # # Alternative version with oemof objs (working):
    # # create DF with custom cols (node1, node 2, flow) from simulation result dict
    # flows_results = pd.Series(results).rename_axis(['node1', 'node2']).reset_index(name='flow_res')
    # flows_results.set_index(['node1', 'node2'], inplace=True)
    # flows_obj = pd.Series(dict(om_flows)).rename_axis(['node1', 'node2']).reset_index(name='flow_obj')
    # flows_obj.set_index(['node1', 'node2'], inplace=True)
    # flows = pd.concat([flows_obj, flows_results], axis=1).reset_index()
    #
    # # get esys' lines (Link instances)
    # lines = [node for node in esys.nodes if isinstance(node, solph.custom.Link)]
    # # get flows of lines (filtering of column node1 should be sufficient since Link always creates 2 Transformers)
    # flows_links = flows[flows['node1'].isin(lines)]
    #
    # for idx, row in flows_links.iterrows():
    #     obj = row['flow_obj']
    #     seq = row['flow_res']['sequences']
    #     if obj.nominal_value:
    #         flows_links.at[idx, 'loading_mean'] = float(seq.mean()) / obj.nominal_value
    #         flows_links.at[idx, 'loading_max'] = float(seq.max()) / obj.nominal_value
    #     else:
    #         flows_links.at[idx, 'loading_mean'] = 0.
    #         flows_links.at[idx, 'loading_max'] = 0.
    # flows_links.sort_values('loading_max')

    return


def prepare_feedin_timeseries(region):
    """Calculate feedin timeseries per technology for entire region

    Parameters
    ----------
    region : :class:`~.model.Region`

    Returns
    -------
    :obj:`dict` of :pandas:`pandas.DataFrame`
        Absolute feedin timeseries per technology (dict key) and municipality
        (DF column)

    """
    year = int(region.cfg['scn_data']['general']['year'])
    status_quo = True if year == 2017 else False
    region.muns['gen_capacity_solar_heat'] = 1


    # needed columns from scenario's mun data for feedin
    cols = ['gen_capacity_wind',
            'gen_capacity_pv_ground',
            'gen_capacity_pv_roof_small',
            'gen_capacity_pv_roof_large',
            'gen_capacity_hydro',
            'gen_capacity_bio',
            'gen_capacity_sewage_landfill_gas',
            'gen_capacity_conventional_large',
            'gen_capacity_conventional_small',
            'gen_capacity_solar_heat']

    # mapping for capacity columns to timeseries columns
    # if future scenario is present, use wind_fs time series
    tech_mapping = {
        'gen_capacity_wind':
            'wind_sq' if status_quo
                      else 'wind_fs',
        'gen_capacity_pv_ground': 'pv_ground',
        'gen_capacity_pv_roof_small': 'pv_roof_small',
        'gen_capacity_pv_roof_large': 'pv_roof_large',
        'gen_capacity_hydro': 'hydro',
        'gen_capacity_solar_heat': 'solar_heat',
    }

    # prepare capacities (for relative timeseries only)
    cap_per_mun = region.muns[cols].rename(columns=tech_mapping)
    cap_per_mun['bio'] = \
        cap_per_mun['gen_capacity_bio'] + \
        cap_per_mun['gen_capacity_sewage_landfill_gas']
    cap_per_mun['conventional'] = \
        cap_per_mun['gen_capacity_conventional_large'] + \
        cap_per_mun['gen_capacity_conventional_small']
    cap_per_mun.drop(columns=['gen_capacity_bio',
                              'gen_capacity_sewage_landfill_gas',
                              'gen_capacity_conventional_large',
                              'gen_capacity_conventional_small'],
                     inplace=True)

    # adjust feedin ts columns
    region.feedin_ts_init = pd.concat(
        [region.feedin_ts_init,
         region.feedin_ts_init[['pv_roof']].rename(
             columns={'pv_roof': 'pv_roof_small'})],
        axis=1)
    region.feedin_ts_init.rename(columns={'pv_roof': 'pv_roof_large'},
                                 inplace=True)

    region.feedin_ts_init.drop(
        columns=['wind_fs' if status_quo
                 else 'wind_sq'
                 ],
        level=0,
        inplace=True
    )

    # calculate capacity(mun)-weighted aggregated feedin timeseries for entire region:
    # 1) process relative TS
    feedin_agg = {}
    for tech in list(cap_per_mun.loc[:,
                     cap_per_mun.columns != 'conventional'].columns):
        feedin_agg[tech] = region.feedin_ts_init[tech] * cap_per_mun[tech]

    # 2) process absolute TS (conventional plants)
    # do not use capacities as the full load hours of the plants differ - use
    # ratio of currently set power values and those from status quo scenario
    conv_cap_per_mun = \
        cap_per_mun['conventional'] /\
        region.muns[['gen_capacity_conventional_large',
                  'gen_capacity_conventional_small']].sum(axis=1)
    feedin_agg['conventional'] = region.feedin_ts_init['conventional'] * conv_cap_per_mun

    # rename wind column depending on scenario
    if status_quo:
        feedin_agg['wind'] = feedin_agg.pop('wind_sq')
    else:
        feedin_agg['wind'] = feedin_agg.pop('wind_fs')

    return feedin_agg


def prepare_demand_timeseries(region):
    """Calculate demand and reformat demand timeseries
    (from single DF to DF per sector)

    Perform demand calculation using
    * savings from scenario config
    * change in population and employment

    Parameters
    ----------
    region : :class:`~.model.Region`

    Returns
    -------
    :obj:`dict` of :pandas:`pandas.DataFrame`
        Absolute demand timeseries per demand sector (dict key) and
        municipality (DF column)
    """

    # get savings due to efficiency measures
    savings = {**region.cfg['scn_data']['demand']['dem_el_general'],
               **region.cfg['scn_data']['demand']['dem_th_general']}
    for sav in [v for k, v in savings.items() if k[:7] == 'saving_']:
        if sav < 0 or sav > 1:
            msg = 'Saving must be in range [0, 1]'
            logger.error(msg)
            raise ValueError(msg)

    # calc savings for all sectors and carriers
    demand_ts = {}
    demand_types = region.demand_ts_init.columns.get_level_values(0).unique()
    for dt in demand_types:
        col = 'population' if 'hh' in dt else 'employees'

        demand_ts[dt] = (region.demand_ts_init[dt] *
                         (1 - savings.get(f'saving_{dt}'))).T.mul(
            region.demography_change[col], axis=0).T

    # calc savings for DSM
    dsm_ts = (region._dsm_ts * (1 - savings.get('saving_el_hh'))).T.mul(
            region.demography_change['population'], level='ags', axis=0).T

    return demand_ts, dsm_ts


def prepare_temp_timeseries(region):
    """Reformat temperatur timeseries: from single DF to DF per temp type
    (air+soil)

    Parameters
    ----------
    region : :class:`~.model.Region`

    Returns
    -------
    :obj:`dict` of :pandas:`pandas.DataFrame`
        Temperature timeseries per demand sector (dict key) and municipality
        (DF column)
    """
    temp_ts = {}
    temp_types = region.temp_ts_init.columns.get_level_values(0).unique()
    for tt in temp_types:
        temp_ts[tt] = region.temp_ts_init[tt]

    return temp_ts


def calc_heat_pump_cops(t_high, t_low, quality_grade, consider_icing=False,
                        temp_icing=None, factor_icing=None, spf=None, year=2017):
    """Calculate temperature-dependent COP of heat pumps including efficiency
    gain over time.

    COP-Code was adapted from oemof-thermal:
    https://github.com/oemof/oemof-thermal/blob/features/cmpr_heatpumps_and_chillers/src/oemof/thermal/compression_heatpumps_and_chillers.py
    Related issue: https://github.com/oemof/oemof/issues/591

    Efficiency corrections are based upon increase of seasonal performance
    factor (SPF) for scenario year as set in cfg since 2017 (SQ).
    """

    # Expand length of lists with temperatures and convert unit to Kelvin.
    length = max([len(t_high), len(t_low)])
    if len(t_high) == 1:
        list_t_high_K = [t_high[0]+273.15]*length
    elif len(t_high) == length:
        list_t_high_K = [t+273.15 for t in t_high]
    if len(t_low) == 1:
        list_t_low_K = [t_low[0]+273.15]*length
    elif len(t_low) == length:
        list_t_low_K = [t+273.15 for t in t_low]

    # Calculate COPs
    if not consider_icing:
        cops = [quality_grade * t_h/(t_h-t_l) for
                t_h, t_l in zip(list_t_high_K, list_t_low_K)]

    # Temperatures below 2 degC lead to icing at evaporator in
    # heat pumps working with ambient air as heat source.
    elif consider_icing:
        cops = []
        for t_h, t_l in zip(list_t_high_K, list_t_low_K):
            if t_l < temp_icing + 273.15:
                cops = cops + [factor_icing*quality_grade * t_h/(t_h-t_l)]
            if t_l >= temp_icing + 273.15:
                cops = cops + [quality_grade * t_h / (t_h - t_l)]

    # Efficiency gain for scenario year
    if year != 2017 and spf is not None:
        cops = [_ * spf[int(year)]/spf[2017] for _ in cops]

    return cops


def calc_dsm_cap_up(data, ags, mode=None):
    """Calculate the max. positive DSM capacity"""
    demand = data['Lastprofil', ags]

    if mode == 'flex_min':
        flex_plus = data['Flex_Plus', ags]
        capacity_up = flex_plus - demand
    elif mode == 'flex_max':
        flex_plus_max = data['Flex_Plus_Max', ags]
        capacity_up = flex_plus_max - demand
    else:
        msg = 'Invalid SinkDSM mode'
        logger.error(msg)
        raise ValueError(msg)

    return capacity_up


def calc_dsm_cap_down(data, ags, mode=None):
    """Calculate the max. negative DSM capacity"""
    demand = data['Lastprofil', ags]

    if mode == 'flex_min':
        flex_minus = data['Flex_Minus', ags]
        capacity_down = demand - flex_minus
    elif mode == 'flex_max':
        flex_minus_max = data['Flex_Minus_Max', ags]
        capacity_down = demand - flex_minus_max
    else:
        msg = 'Invalid SinkDSM mode'
        logger.error(msg)
        raise ValueError(msg)

    return capacity_down


def preprocess_heating_structure(cfg, heating_structure):
    """Recalculate the sources' share in the heating

    Based upon min. share threshold, energy sources are neglected in heat
    production. Therefore, considered sources are scaled up by weight.
    """
    rescale = False
    sources_cfg = cfg['scn_data']['generation']['gen_th_dec']['general']

    # check sums
    if not (heating_structure.groupby(
            ['ags_id',
             'year']).agg('sum').round(3) == 1).\
                   all().all() == True:
        msg = 'Sums of heating structure shares '\
              'are not 1. Check your data!'
        logger.error(msg)
        raise ValueError(msg)

    # # filter for requested sources in config
    # if sources_cfg['sources'] != '':
    #     heating_structure = heating_structure[
    #         heating_structure.index.get_level_values(
    #             'energy_source').isin(sources_cfg['sources'])]
    #     rescale = True

    # exclude sources with a share below threshold
    if sources_cfg['source_min_share'] > 0:
        # set values below threshold to zero
        heating_structure = heating_structure[
            heating_structure > sources_cfg['source_min_share']
        ].fillna(0)
        rescale = True

    # calculate scale factors
    if rescale:
        source_scale_factor = 1 / heating_structure.groupby(
            ['ags_id', 'year']).agg('sum')
        # apply
        heating_structure = heating_structure * source_scale_factor

    # rescale to relative values exluding distrinct heating
    heating_structure_wo_dist_heating = heating_structure.loc[
        heating_structure.index.get_level_values(1) != 'dist_heating']
    source_scale_factor = 1 / heating_structure_wo_dist_heating.groupby(
        ['ags_id', 'year']).agg('sum')
    heating_structure_dec = heating_structure_wo_dist_heating *\
                            source_scale_factor

    # extract district heating share (use RCA value only as it's the same for
    # all sectors)
    dist_heating_share = heating_structure.xs(
            'dist_heating',
            level='energy_source'
    )['rca']

    return heating_structure_dec, dist_heating_share


def create_maintenance_timeseries(datetime_index, months, duration):
    """Create a list of activation (1) / deactivation (0) times due to
    maintenance

    Parameters
    ----------
    months : :obj:`int` or :obj:`list` of :obj:`int`
        Months where service takes place, e.g. [1]
    duration : :obj:`int`
        Duration of maintenance in days
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index

    Returns
    -------
    :obj:`list` of :obj:`int` (1 or 0)
        List of (de)activation times
    """
    if months in ['', 0]:
        mask = [True] * len(datetime_index)
    else:
        if not isinstance(months, list):
            months = [months]
        if any([not isinstance(_, int) for _ in months]):
            raise ValueError('Supplied BHKW maintenance months are invalid!')
        mask = [True] * len(datetime_index)
        for month in months:
            start = pd.to_datetime(f'{datetime_index[0].year}-'
                                   f'{int(month)}-01 00:00:00')
            end = start + pd.to_timedelta(f'{duration} days')
            mask = mask & ~((datetime_index >= start) & (datetime_index < end))

    return list(map(int, mask))


def calc_annuity(cfg, tech_assumptions):
    """Calculate equivalent annual cost"""

    tech_assumptions['annuity'] = tech_assumptions.replace(0, nan).apply(
        lambda row: annuity(row['capex'],
                            row['lifespan'],
                            row['wacc']),
        axis=1)

    return tech_assumptions


def distribute_large_battery_capacity(region, method='re_cap'):
    """Distribute cumulative capacity of large-scale batteries to
    municipalities, supports 3 different methods:

    * proportional to ratio of installed RE capacity and peak load
      (method='re_cap_peak_load')
    * proportional to maximum of residual load
      (method='residual_peak_load')
    * proportional to installed RE capacity (default)
      (method='re_cap')

    Also, nominal battery power is assigned by calculating c-rates for
    charging and discharging using the power set in scenario config.

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    method : :obj:`str`
        Distribution method (see above)

    Returns
    -------
    :pandas:`pandas.DataFrame`
        Battery capacity, charge and discharge power per municipality
    """
    batt_params = region.cfg['scn_data']['flexopt']['flex_bat_large']
    batt_cap_cum = batt_params['params']['nominal_storage_capacity']

    if batt_cap_cum > 0:
        ee_techs = region.cfg['scn_data']['generation']['gen_el']['technologies']
        dem_el_sectors = ['el_hh', 'el_rca', 'el_ind']

        # get cumulated installed cap. per mun
        ee_cum_cap_per_mun = region.muns[[f'gen_capacity_{tech}'
                                          for tech in ee_techs]].sum(axis=1)

        # calc c-rates
        c_rate_charge = batt_params['inflow']['nominal_value'] / \
                        batt_cap_cum
        c_rate_discharge = batt_params['outflow']['nominal_value'] / \
                           batt_cap_cum

        if method == 're_cap_peak_load':
            re_cap_peak_load_ratio = ee_cum_cap_per_mun /\
                                     region.demand_ts_agg_per_mun(
                                         sectors=dem_el_sectors).max()
            batt_cap = (re_cap_peak_load_ratio /
                        re_cap_peak_load_ratio.sum() *
                        batt_cap_cum)

        elif method == 'residual_peak_load':
            # calc maximum of residual load
            residual_peak_load = (
                    region.demand_ts_agg_per_mun(sectors=dem_el_sectors) -
                    region.feedin_ts_agg_per_mun(techs=ee_techs)
            ).max()
            # set negative residual load to zero
            residual_peak_load[residual_peak_load < 0] = 0

            batt_cap = (residual_peak_load /
                        residual_peak_load.sum() *
                        batt_cap_cum)

        elif method == 're_cap':
            batt_cap = (ee_cum_cap_per_mun /
                        ee_cum_cap_per_mun.sum() *
                        batt_cap_cum)

        else:
            msg = 'Invalid method, cannot allocate large battery capacity.'
            logger.error(msg)
            raise ValueError(msg)

        return pd.DataFrame({
            'capacity': batt_cap,
            'power_charge': batt_cap * c_rate_charge,
            'power_discharge': batt_cap * c_rate_discharge
        })

        # # PLOT: Compare methods
        # results_compare = pd.DataFrame({
        #     're_cap_peak_load': re_cap_peak_load_ratio / re_cap_peak_load_ratio.sum(),
        #     'residual_peak_load': residual_peak_load / residual_peak_load.sum(),
        #     're_cap': ee_cum_cap_per_mun / ee_cum_cap_per_mun.sum(),
        # }
        # )
        # results_compare.plot.bar(title='Ergebnisvergleich verschiedener Verteilungsmethoden für Großbatterien')

    return pd.DataFrame({
        'capacity': 0,
        'power_charge': 0,
        'power_discharge': 0
    }, index=region.muns.index)


def distribute_small_battery_capacity(region):
    """Distribute cumulative capacity of PV batteries to
    municipalities proportional to installed small-scale rooftop PV capacity.

    Also, nominal battery power is assigned by calculating c-rates for
    charging and discharging using the power set in scenario config.

    Parameters
    ----------
    region : :class:`~.model.Region`

    Returns
    -------
    :pandas:`pandas.DataFrame`
        Battery capacity, charge and discharge power per municipality
    """
    batt_params = region.cfg['scn_data']['flexopt']['flex_bat_small']
    batt_cap_cum = batt_params['params']['nominal_storage_capacity']

    if batt_cap_cum > 0:
        # get cumulated installed small PV cap. per mun
        pv_cum_cap_per_mun = region.muns['gen_capacity_pv_roof_small']

        # calc c-rates
        c_rate_charge = batt_params['inflow']['nominal_value'] / \
                        batt_cap_cum
        c_rate_discharge = batt_params['outflow']['nominal_value'] / \
                           batt_cap_cum

        # distribute prop. to installed cap.
        batt_cap = (pv_cum_cap_per_mun /
                    pv_cum_cap_per_mun.sum() *
                    batt_cap_cum)

        return pd.DataFrame({
            'capacity': batt_cap,
            'power_charge': batt_cap * c_rate_charge,
            'power_discharge': batt_cap * c_rate_discharge
        })

    return pd.DataFrame({
        'capacity': 0,
        'power_charge': 0,
        'power_discharge': 0
    }, index=region.muns.index)


def calc_available_pv_capacity(region):
    """Calculate available capacity for ground-mounted PV systems

    Uses land use and land availability from config and PV potential areas.
    Return None if areas are None (applies for scenario 'SQ').

    Possible combinations of config params `pv_installed_power` and
    `pv_land_use_scenario`:
    ================== ==================== =========================================
    pv_installed_power pv_land_use_scenario result
    ================== ==================== =========================================
    SQ                 SQ                   SQ data
    SQ                 H or HS              SQ data
    MAX_AREA           H or HS              max. potential using pv_land_use_scenario
    VALUE              H or HS              VALUE distrib. using pv_land_use_scenario
    ================== ==================== =========================================

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object

    Returns
    -------
    :pandas:`pandas.DataFrame` or None
        Installable PV count (zero) and power, muns as index
    """
    cfg = region.cfg['scn_data']['generation']['re_potentials']

    if region.pot_areas_pv_scn is None:
        if cfg['pv_installed_power'] == 'MAX_AREA':
            msg = 'Cannot calculate PV potential (param pv_installed_power=' \
                  'MAX_AREA but no pv_land_use_scenario selected)'
            logger.error(msg)
            raise ValueError(msg)
        elif isinstance(cfg['pv_installed_power'], float):
            msg = 'Cannot calculate PV potential (param pv_installed_power ' \
                  'is numeric but no pv_land_use_scenario selected to ' \
                  'distribute power)'
            logger.error(msg)
            raise ValueError(msg)
        return None

    areas = region.pot_areas_pv_scn.copy()
    areas_agri = areas[areas.index.get_level_values(level=1).str.startswith(
        'agri_')]

    # limit area on fields and meadows so that it does not exceed 1 % of the
    # total area of fields and meadows in ABW
    if cfg['pv_usable_area_agri_max'] != '':
        if areas_agri.sum() > cfg['pv_usable_area_agri_max']:
            areas_agri *= cfg['pv_usable_area_agri_max'] / areas_agri.sum()
            areas.update(areas_agri)

    areas_agg = areas.groupby('ags_id').agg('sum')

    # use all available areas from DB
    if cfg['pv_installed_power'] == 'MAX_AREA':
        gen_capacity_pv_ground = areas_agg / cfg['pv_land_use']
    # use given power, distribute to muns using available areas from DB
    else:
        gen_capacity_pv_ground = areas_agg / sum(areas_agg) * \
                                 cfg['pv_installed_power']

    return pd.DataFrame({'gen_count_pv_ground': 0,
                         'gen_capacity_pv_ground': gen_capacity_pv_ground}
                        )


def calc_available_pv_roof_capacity(region):
    """Calculate available capacity for roof-mounted PV systems
    (on residential and industrial roofs)

    Uses land use and usable areas from config and PV roof potential
    areas. Return None if areas are None (applies for scenario 'SQ').

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object

    Returns
    -------
    :pandas:`pandas.DataFrame` or None
        Installable PV count (zero) and power, muns as index

    Notes
    -----
    It is assumed, that large PV systems are located on industrial,
    small PV systems on residential roofs which does not necessarily
    reflect the real situation and distorts the distribution of home
    storage systems (small batteries) which take place in the function
    `distribute_small_battery_capacity()`.
    """
    cfg = region.cfg['scn_data']['generation']['re_potentials']

    if cfg['pv_roof_installed_power'] == 'SQ':
        return None
    else:
        areas_agg = pd.DataFrame({
            'area_resid_ha': region.pot_areas_pv_roof['area_resid_ha'] *
                             cfg['pv_roof_resid_usable_area'],
            'area_ind_ha': region.pot_areas_pv_roof['area_ind_ha'] *
                           cfg['pv_roof_ind_usable_area']})

    # use all available areas from DB
    if cfg['pv_roof_installed_power'] == 'MAX_AREA':
        gen_capacity_pv_roof_small = (areas_agg['area_resid_ha'] /
                                      cfg['pv_roof_land_use'])
        gen_capacity_pv_roof_large = (areas_agg['area_ind_ha'] /
                                      cfg['pv_roof_land_use'])

    # use given power, distribute to muns using available areas from DB
    else:
        # distribute power to small (resid) and large (ind) plants prop. to available rooftoparea
        resid_ind_distribution_ratio = areas_agg.sum(axis=0)['area_resid_ha'] / \
                                       areas_agg.sum(axis=0)['area_ind_ha']

        gen_capacity_pv_roof_small = (areas_agg['area_resid_ha'] /
                                      areas_agg['area_resid_ha'].sum() *
                                      resid_ind_distribution_ratio *
                                      cfg['pv_roof_installed_power'])
        gen_capacity_pv_roof_large = (areas_agg['area_ind_ha'] /
                                      areas_agg['area_ind_ha'].sum() *
                                      (1-resid_ind_distribution_ratio) *
                                      cfg['pv_roof_installed_power'])

    return pd.DataFrame({'gen_count_pv_roof_small': 0,
                         'gen_capacity_pv_roof_small':
                             gen_capacity_pv_roof_small,
                         'gen_count_pv_roof_large': 0,
                         'gen_capacity_pv_roof_large':
                             gen_capacity_pv_roof_large}
                        )


def calc_available_wec_capacity(region):
    """Calculate available capacity for wind turbines

    Uses land use and land availability from config and WEC potential areas.
    Return None if areas are None (applies for scenario 'SQ').

    Possible combinations of config params `wec_installed_power` and
    `wec_land_use_scenario`:
    =================== ===================== ==========================================
    wec_installed_power wec_land_use_scenario result
    =================== ===================== ==========================================
    SQ                  SQ                    SQ data
    SQ                  s1000f1/s500f0/s500f1 SQ data
    MAX_AREA            s1000f1/s500f0/s500f1 max. potential using wec_land_use_scenario
    VALUE               s1000f1/s500f0/s500f1 VALUE distrib. using wec_land_use_scenario
    =================== ===================== ==========================================

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object

    Returns
    -------
    :pandas:`pandas.DataFrame` or None
        Installable WEC count (rounded) and power, muns as index

    Notes
    -----
    Installable WEC count is rounded, power is a multiple of the power of the model
    plant set in cfg. Hence, the cumulative power may differ from the power set in
    config (wec_installed_power).
    """
    cfg = region.cfg['scn_data']['generation']['re_potentials']

    if region.pot_areas_wec_scn is None:
        if cfg['wec_installed_power'] == 'MAX_AREA':
            msg = 'Cannot calculate WEC potential (param wec_installed_power=' \
                  'MAX_AREA but no wec_land_use_scenario selected)'
            logger.error(msg)
            raise ValueError(msg)
        elif isinstance(cfg['wec_installed_power'], float):
            msg = 'Cannot calculate WEC potential (param wec_installed_power ' \
                  'is numeric but no wec_land_use_scenario selected to ' \
                  'distribute power)'
            logger.error(msg)
            raise ValueError(msg)
        return None

    areas_agg = region.pot_areas_wec_scn.groupby('ags_id').agg('sum')

    # use all available areas from DB
    if cfg['wec_installed_power'] == 'MAX_AREA':
        gen_count_wind = (areas_agg *
                          cfg['wec_usable_area'] /
                          cfg['wec_land_use']).round().astype(int)
        gen_capacity_wind = gen_count_wind * cfg['wec_nom_power']
    # use given power, distribute to muns using available areas from DB
    else:
        gen_count_wind = (areas_agg / sum(areas_agg) *
                          (cfg['wec_installed_power'] / cfg['wec_nom_power'])
                          ).round().astype(int)
        gen_capacity_wind = gen_count_wind * cfg['wec_nom_power']

    return pd.DataFrame({'gen_count_wind': gen_count_wind,
                         'gen_capacity_wind': gen_capacity_wind}
                        )

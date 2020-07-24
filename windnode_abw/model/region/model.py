import os
import pandas as pd
import oemof.solph as solph
from pyomo.environ import Constraint
from windnode_abw.tools.logger import log_memory_usage
import logging

logger = logging.getLogger('windnode_abw')

from windnode_abw.model.region.tools import calc_heat_pump_cops, \
    calc_dsm_cap_down, calc_dsm_cap_up, create_maintenance_timeseries


def simulate(om, solver='cbc', verbose=True, keepfiles=False):
    """Optimize energy system

    Parameters
    ----------
    om : oemof.solph.OperationalModel
    solver : :obj:`str`
        Solver which is used
    verbose : :obj:`bool`
        If set, be verbose
    keepfiles : :obj:`bool`
        If set, temporary solver files will be kept in /tmp/

    Returns
    -------
    oemof.solph.OperationalModel
    """

    # solve it
    log_memory_usage()
    logger.info('Solve optimization problem...')

    om.solve(solver=solver,
             solve_kwargs={'tee': verbose,
                           'keepfiles': keepfiles})

    return om


def create_oemof_model(region, cfg, save_lp=False):
    """Create oemof model using config and data files. An oemof energy system
    is created, nodes are added and parametrized.

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    cfg : :obj:`dict`
        Config to be used to create model
    save_lp : :obj:`bool`
        Triggers dump of lp file

    Returns
    -------
    oemof.solph.EnergySystem
    oemof.solph.OperationalModel
    """
    logger.info('Create energy system...')

    # create time index
    datetime_index = pd.date_range(start=cfg['date_from'],
                                   end=cfg['date_to'],
                                   freq=cfg['freq'])

    # init energy system
    esys = solph.EnergySystem(timeindex=datetime_index)

    # create and add nodes
    el_nodes = create_el_model(
        region=region,
        datetime_index=datetime_index
    )
    esys.add(*el_nodes)

    th_nodes = create_th_model(
        region=region,
        datetime_index=datetime_index,
        esys_nodes=el_nodes
    )
    esys.add(*th_nodes)

    flex_nodes = create_flexopts(
        region=region,
        datetime_index=datetime_index,
        esys_nodes=th_nodes+el_nodes
    )
    esys.add(*flex_nodes)

    logger.info(f'Energy system created '
                f'({len(el_nodes) + len(th_nodes) + len(flex_nodes)} '
                f'nodes total).')
    # print('The following objects have been created:')
    # for n in esys.nodes:
    #     oobj = str(type(n)).replace("<class 'oemof.solph.", "").replace("'>", "")
    #     print(oobj + ':', n.label)

    # Create problem
    log_memory_usage()
    logger.info('Create optimization problem...')

    om = solph.Model(esys)

    # Add electricity import limit
    el_import_limit = region.cfg['scn_data']['grid']['extgrid'][
        'import']['energy_limit']
    if el_import_limit < 1:
        imported_electricity_limit(om, limit=el_import_limit)

    # Save .lp file
    if save_lp:
        from windnode_abw.tools import config
        om.write(os.path.join(config.get_data_root_dir(),
                              config.get('user_dirs',
                                         'log_dir'),
                              "windnode_abw.lp"),
                 io_options={'symbolic_solver_labels': True})

    return esys, om


def create_el_model(region=None, datetime_index=None):
    """Create electrical model modes (oemof objects) and lines from region such
    as buses, links, sources and sinks.

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index of simulation timerange

    Returns
    -------
    :obj:`list` of :class:`nodes <oemof.network.Node>`
        ESys nodes
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    scn_data = region.cfg['scn_data']

    logger.info("Creating el. system objects...")

    nodes = []

    #########
    # BUSES #
    #########

    # el. grid buses
    buses = {}
    for idx, row in region.buses.iterrows():
        bus = solph.Bus(label='b_el_' + str(idx))
        buses[idx] = bus
        nodes.append(bus)

    ####################
    # ELECTRICAL NODES #
    ####################

    # get el. sectors from cfg
    el_sectors = region.cfg['scn_data']['demand']['dem_el_general']['sectors']

    # get el. demand profile type for households and DSM status from cfg
    hh_profile_type = scn_data['demand']['dem_el_hh']['profile_type']
    hh_dsm_share = scn_data['flexopt']['dsm']['params']['hh_share']

    # create nodes for all municipalities
    for ags, mundata in region.muns.iterrows():
        # get buses for subst in mun
        mun_buses = region.buses.loc[region.subst.loc[mundata.subst_id].bus_id]

        # note: timeseries are distributed equally to all buses of mun
        for bus_id, busdata in mun_buses.iterrows():
            # generators
            for tech, feedin_ts in {t: ts[ags] for t, ts
                                in region.feedin_ts.items()
                                if t in scn_data[
                    'generation']['gen_el']['technologies']}.items():
                outflow_args = {
                    'nominal_value': 1,
                    'fixed':  True,
                    'actual_value': list((feedin_ts /
                                          len(mun_buses))[datetime_index]),
                    'variable_costs': region.tech_assumptions_scn.loc[
                        tech]['opex_var'],
                    'emissions': region.tech_assumptions_scn.loc[
                        tech]['emissions_var']
                    }

                # create node only if feedin sum is >0
                if feedin_ts.sum(axis=0) > 0:
                    nodes.append(
                        solph.Source(
                            label=f'gen_el_{ags}_b{bus_id}_{tech}',
                            outputs={buses[bus_id]: solph.Flow(**outflow_args)})
                    )

            for sector in el_sectors:
                if sector in ['rca', 'ind']:
                    inflow_args = {
                        'nominal_value': 1,
                        'fixed':  True,
                        'actual_value': list(
                            (region.demand_ts[f'el_{sector}'][ags] /
                             len(mun_buses)
                             )[datetime_index]
                        )
                    }
                    nodes.append(
                        solph.Sink(
                            label=f'dem_el_{ags}_b{bus_id}_{sector}',
                            inputs={buses[bus_id]: solph.Flow(
                                **inflow_args)})
                    )
                elif sector == 'hh':
                    # deactivate hh_sinks if DSM is 100% in scenario config,
                    # reduce load otherwise
                    if hh_dsm_share == 1:
                        pass
                    elif 1 > hh_dsm_share >= 0:
                        if hh_profile_type == 'ioew':
                            actual_value = list(
                                (region.dsm_ts['Lastprofil'][ags] /
                                 len(mun_buses)
                                 )[datetime_index] * (1 - hh_dsm_share)
                            )
                        else:
                            actual_value = list(
                                (region.demand_ts[f'el_{sector}'][ags] /
                                 len(mun_buses)
                                 )[datetime_index] * (1 - hh_dsm_share)
                            )

                        inflow_args = {
                            'nominal_value': 1,
                            'fixed': True,
                            'actual_value': actual_value
                        }
                        nodes.append(
                            solph.Sink(
                                label=f'dem_el_{ags}_b{bus_id}_{sector}',
                                inputs={buses[bus_id]: solph.Flow(
                                    **inflow_args)})
                        )
                    else:
                        msg = 'cfg parameter hh_share must be in range 0..1'
                        logger.error(msg)
                        raise ValueError(msg)
                else:
                    msg = 'Invalid power demand sector'
                    logger.error(msg)
                    raise ValueError(msg)

    ################
    # TRANSFORMERS #
    ################

    # add 380/110kV trafos
    for idx, row in region.trafos.iterrows():
        bus0 = buses[row['bus0']]
        bus1 = buses[row['bus1']]
        nodes.append(
            solph.custom.Link(
                label=f'trafo_{idx}_b{row["bus0"]}_b{row["bus1"]}',
                inputs={bus0: solph.Flow(),
                        bus1: solph.Flow()},
                outputs={bus0: solph.Flow(
                    variable_costs=region.tech_assumptions_scn.loc[
                        'trafo']['opex_var'],
                    emissions=region.tech_assumptions_scn.loc[
                        'trafo']['emissions_var'],
                    investment=solph.Investment(
                        ep_costs=region.tech_assumptions_scn.loc[
                            'trafo']['annuity'],
                        existing=row['s_nom'])
                ),
                bus1: solph.Flow(
                    variable_costs=region.tech_assumptions_scn.loc[
                        'trafo']['opex_var'],
                    emissions=region.tech_assumptions_scn.loc[
                        'trafo']['emissions_var'],
                    investment=solph.Investment(
                        ep_costs=region.tech_assumptions_scn.loc[
                            'trafo']['annuity'],
                        existing=row['s_nom'])
                )},
                # TODO: Revise efficiencies
                conversion_factors={
                    (bus0, bus1): region.tech_assumptions_scn.loc[
                        'trafo']['sys_eff'],
                    (bus1, bus0): region.tech_assumptions_scn.loc[
                        'trafo']['sys_eff']
                })
        )

    #################
    # EXTERNAL GRID #
    #################

    # 1. Source (import) and Sink (export) for each non-region bus
    #    (buses which are tagged with region_bus == False)
    # 2. Line from each of those buses to common IMEX bus to reflect power
    #    bypass through external grid

    # create common IMEX bus
    imex_bus = solph.Bus(label='b_el_imex')
    nodes.append(imex_bus)

    # calc costs and emissions
    costs_var = region.tech_assumptions_scn.loc[
        'elenergy']['capex']
    emissions_var = region.tech_assumptions_scn.loc[
        'elenergy']['emissions_var']

    for idx, row in region.buses[~region.buses['region_bus']].iterrows():
        bus = buses[idx]

        # SEPARATE EXCESS+SHORTAGE BUSES
        nodes.append(
            solph.Sink(
                label='excess_el_{v_level}_b{bus_id}'.format(
                    bus_id=idx,
                    v_level='hv' if row['v_nom'] == 110 else 'ehv'
                ),
                inputs={bus: solph.Flow(
                    variable_costs=-costs_var
                )})
        )
        nodes.append(
            solph.Source(
                label='shortage_el_{v_level}_b{bus_id}'.format(
                    bus_id=idx,
                    v_level='hv' if row['v_nom'] == 110 else 'ehv'
                ),
                outputs={bus: solph.Flow(
                    variable_costs=(costs_var + emissions_var *
                                    region.tech_assumptions_scn.loc[
                                        'emission']['capex']),
                    emissions=emissions_var
                )})
        )

        # CONNECTION TO COMMON IMEX BUS
        # get nom. capacity of connected line or trafo
        if not region.lines[region.lines['bus0'] == idx]['s_nom'].empty:
            s_nom = float(region.lines[region.lines['bus0'] == idx]['s_nom'])
        elif not region.lines[region.lines['bus1'] == idx]['s_nom'].empty:
            s_nom = float(region.lines[region.lines['bus1'] == idx]['s_nom'])
        elif not region.trafos[region.trafos['bus0'] == idx]['s_nom'].empty:
            s_nom = float(region.trafos[region.trafos['bus0'] == idx]['s_nom'])
        elif not region.trafos[region.trafos['bus1'] == idx]['s_nom'].empty:
            s_nom = float(region.trafos[region.trafos['bus1'] == idx]['s_nom'])
        else:
            msg = f'Nominal capacity of connected line ' \
                  f'not found for bus {idx}'
            logger.error(msg)
            raise ValueError(msg)

        nodes.append(
            solph.custom.Link(
                label=f'line_b{idx}_b_el_imex',
                inputs={bus: solph.Flow(),
                        imex_bus: solph.Flow()},
                outputs={
                    bus: solph.Flow(
                        nominal_value=s_nom *
                                      scn_data['grid']['extgrid'][
                                          'imex_lines']['power_limit_bypass'],
                        variable_costs=region.tech_assumptions_scn.loc[
                            'line']['opex_var'],
                        emissions=region.tech_assumptions_scn.loc[
                            'line']['emissions_var']
                    ),
                    imex_bus: solph.Flow(
                        nominal_value=s_nom *
                                      scn_data['grid']['extgrid'][
                                          'imex_lines']['power_limit_bypass'],
                        variable_costs=region.tech_assumptions_scn.loc[
                            'line']['opex_var'],
                        emissions=region.tech_assumptions_scn.loc[
                            'line']['emissions_var']
                    )
                },
                # TODO: Revise efficiencies
                conversion_factors={
                    (bus, imex_bus): region.tech_assumptions_scn.loc[
                        'line']['sys_eff'],
                    (imex_bus, bus): region.tech_assumptions_scn.loc[
                        'line']['sys_eff'],
                }
            )
        )

    #################
    # REGION'S GRID #
    #################

    for idx, row in region.lines.iterrows():
        bus0 = buses[row['bus0']]
        bus1 = buses[row['bus1']]

        nodes.append(
            solph.custom.Link(
                label=f'line_{row["line_id"]}_b{row["bus0"]}_b{row["bus1"]}',
                inputs={bus0: solph.Flow(),
                        bus1: solph.Flow()},
                outputs={
                    bus0: solph.Flow(
                        variable_costs=region.tech_assumptions_scn.loc[
                            'line']['opex_var'] * row['length'],
                        emissions=region.tech_assumptions_scn.loc[
                            'line']['emissions_var'] * row['length'],
                        investment=solph.Investment(
                            ep_costs=region.tech_assumptions_scn.loc[
                                         'line']['annuity'] * row['length'],
                            existing=float(row['s_nom'])
                        )
                    ),
                    bus1: solph.Flow(
                        variable_costs=region.tech_assumptions_scn.loc[
                            'line']['opex_var'] * row['length'],
                        emissions=region.tech_assumptions_scn.loc[
                            'line']['emissions_var'] * row['length'],
                        investment=solph.Investment(
                            ep_costs=region.tech_assumptions_scn.loc[
                                         'line']['annuity'] * row['length'],
                            existing=float(row['s_nom'])
                        )
                    )
                },
                # TODO: Revise efficiencies
                conversion_factors={
                    (bus0, bus1): region.tech_assumptions_scn.loc[
                        'line']['sys_eff'],
                    (bus1, bus0): region.tech_assumptions_scn.loc[
                        'line']['sys_eff'],
                }
            )
        )

    return nodes


def create_th_model(region=None, datetime_index=None, esys_nodes=None):
    """Create thermal model modes (oemof objects) and lines from region such
    as buses, sources and sinks.

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index of simulation timerange
    esys_nodes : nodes : :obj:`list` of :class:`nodes <oemof.network.Node>`
        ESys nodes

    Returns
    -------
    :obj:`list` of :class:`nodes <oemof.network.Node>`
        ESys nodes
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    scn_data = region.cfg['scn_data']

    logger.info("Creating th. system objects...")

    esys_nodes = {str(n): n for n in esys_nodes}
    nodes = []

    #########
    # BUSES #
    #########
    buses = {}

    # get th. sectors from cfg
    th_sectors = scn_data['demand']['dem_th_general']['sectors']

    # buses for decentralized heat supply (Dezentrale Wärmeversorgung)
    # (1 per sector and mun)
    for mun in region.muns.itertuples():
        for sector in th_sectors:
            bus = solph.Bus(label=f'b_th_dec_{mun.Index}_{sector}')
            buses[bus.label] = bus
            nodes.append(bus)

    # buses for district heating (Fernwärme)
    # (1 per mun)
    for ags in region.dist_heating_share_scn[region.dist_heating_share_scn > 0].index:
        # heating network bus for feedin (to grid)
        bus = solph.Bus(label=f'b_th_cen_in_{ags}')
        buses[bus.label] = bus
        nodes.append(bus)
        # heating network bus for output (from grid)
        bus = solph.Bus(label=f'b_th_cen_out_{ags}')
        buses[bus.label] = bus
        nodes.append(bus)

    ###############
    # COMMODITIES #
    ###############
    # create a commodity for each energy source in cfg
    # except for el. energy and ambient_heat (el. bus is used)

    methane_share = scn_data['commodities']['methane_share']

    # make sure all sources have data in heating structure
    # (except for methane which is handled separately)
    if not all([_ in region.heating_structure_dec.index.get_level_values('energy_source').unique()
                for _ in scn_data['commodities']['commodities'] if _ != 'methane']):
        msg = 'You have invalid commodities in your config! (at ' \
              'least one is not contained in heating structure)'
        logger.error(msg)
        raise ValueError(msg)

    comm_buses = {}
    for es in scn_data['commodities']['commodities']:
        # do not create methane comm. when share is zero
        if es == 'methane' and methane_share == 0:
            continue
        if es not in ['elenergy', 'dist_heating']:
            bus = solph.Bus(label=f'b_{es}')
            costs_var = region.tech_assumptions_scn.loc[
                'comm_' + es]['capex'] if es != 'solar' else 0
            emissions_var = region.tech_assumptions_scn.loc[
                'comm_' + es]['emissions_var'] if es != 'solar' else 0
            com = solph.Source(
                label=es,
                outputs={bus: solph.Flow(
                    variable_costs=(costs_var + emissions_var *
                                    region.tech_assumptions_scn.loc[
                                        'emission']['capex']),
                    emissions=emissions_var
                )
                }
            )
            comm_buses[bus.label] = bus
            nodes.append(bus)
            nodes.append(com)

    # make buses of natural gas and, if existing, methane feed into general
    # gas bus with predefined ratio
    b_gas = solph.Bus(label=f'b_gas')
    nodes.append(b_gas)

    # adjust gas inputs
    if methane_share == 0:
        inputs = {comm_buses['b_natural_gas']: solph.Flow()}
        conversion_factors = {comm_buses['b_natural_gas']: 1}
    elif methane_share == 1:
        inputs = {comm_buses['b_methane']: solph.Flow()}
        conversion_factors = {comm_buses['b_methane']: 1}
    elif 1 > methane_share > 0:
        inputs = {comm_buses['b_natural_gas']: solph.Flow(),
                  comm_buses['b_methane']: solph.Flow()}
        conversion_factors = {comm_buses['b_natural_gas']: 1 - methane_share,
                              comm_buses['b_methane']: methane_share}
    else:
        msg = 'cfg parameter methane_share must be in range 0..1'
        logger.error(msg)
        raise ValueError(msg)

    nodes.append(
        solph.Transformer(
            label='natural_gas_methane_ratio',
            inputs=inputs,
            outputs={b_gas: solph.Flow()},
            conversion_factors=conversion_factors
        )
    )

    #############################
    # DECENTRALIZED HEAT SUPPLY #
    #############################

    for mun in region.muns.itertuples():
        mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

        # sources for decentralized heat supply (1 per technology, sector, mun)
        for sector in th_sectors:
            bus_th = buses[f'b_th_dec_{mun.Index}_{sector}']

            th_load = region.demand_ts[f'th_{sector}'][mun.Index] *\
                            (1 - region.dist_heating_share_scn.loc[mun.Index])
            solar_feedin = region.feedin_ts['solar_heat'][mun.Index] *\
                           th_load.sum(axis=0) *\
                           region.heating_structure_dec_scn.loc[mun.Index][sector].loc['solar']
            th_residual_load = th_load - solar_feedin

            # Reduce solar feedin at times when th. load < solar feedin
            neg_th_residual_load = th_residual_load[th_residual_load < 0]
            solar_feedin[neg_th_residual_load.index] = (
                    solar_feedin[neg_th_residual_load.index] +
                    neg_th_residual_load
            )
            th_residual_load[th_residual_load < 0] = 0

            del th_load

            for es in region.heating_structure_dec_scn.loc[mun.Index].itertuples():
                if es.Index != 'ambient_heat':
                    if es.Index == 'solar':
                        es_share = 1
                    else:
                        es_share = region.heating_structure_dec_scn_wo_solar.loc[
                            mun.Index, es.Index][sector]

                    if es_share > 0:
                        if es.Index == 'solar':
                            actual_value = solar_feedin
                        else:
                            actual_value = th_residual_load * es_share

                        outflow_args = {
                            'nominal_value': 1,
                            'fixed': True,
                            'actual_value': list(actual_value[datetime_index])
                        }

                        if es.Index != 'elenergy':
                            # use mixed gas bus if energy source is natural gas
                            if es.Index == 'natural_gas':
                                bus_in = b_gas
                            else:
                                bus_in = comm_buses[f'b_{es.Index}']

                            inputs = {bus_in: solph.Flow()}
                            outflow_args['variable_costs'] = region.tech_assumptions_scn.loc[
                                'heating_' + es.Index]['opex_var']
                            outflow_args['emissions'] = region.tech_assumptions_scn.loc[
                                'heating_' + es.Index]['emissions_var']
                            conversion_factors = {
                                bus_th: region.tech_assumptions_scn.loc[
                                    'heating_' + es.Index]['sys_eff']
                                }
                        else:
                            inputs = {
                                esys_nodes[f'b_el_{busdata.Index}']: solph.Flow()
                                for busdata in mun_buses.itertuples()
                            }
                            outflow_args['variable_costs'] = 0
                            outflow_args['emissions'] = 0
                            # TODO: REVISE
                            conversion_factors = {bus_th: 1}

                        nodes.append(
                            solph.Transformer(
                                label=f'gen_th_dec_{mun.Index}_{sector}_{es.Index}',
                                inputs=inputs,
                                outputs={bus_th: solph.Flow(**outflow_args)},
                                conversion_factors=conversion_factors
                            )
                        )

        # demand per sector and mun
        for sector in th_sectors:
            inflow_args = {
                'nominal_value': 1,
                'fixed': True,
                'actual_value': list(
                    (region.demand_ts[f'th_{sector}'][mun.Index] *
                     (1 - region.dist_heating_share_scn.loc[mun.Index])
                     )[datetime_index]
                )
            }

            # ToDo: Include saving using different scn from db table
            nodes.append(
                solph.Sink(
                    label=f'dem_th_dec_{mun.Index}_{sector}',
                    inputs={buses[f'b_th_dec_{mun.Index}_{sector}']:
                                solph.Flow(**inflow_args)
                            }
                )
            )

    ####################
    # DISTRICT HEATING #
    ####################
    # only add if there's district heating in mun
    for ags, dist_heating_share in region.dist_heating_share_scn[
        region.dist_heating_share_scn > 0].iteritems():

        mun_buses = region.buses.loc[region.subst.loc[region.muns.loc[ags].subst_id].bus_id]
        bus_th_net_in = buses[f'b_th_cen_in_{ags}']
        bus_th_net_out = buses[f'b_th_cen_out_{ags}']

        scaling_factor = dist_heating_share / \
                         region.tech_assumptions_scn.loc[
                             'district_heating']['sys_eff']

        # get annual thermal peak load (consider network losses)
        th_cen_peak_load = sum(
            [region.demand_ts[f'th_{sector}'][ags]
             for sector in th_sectors]
        ).max() * scaling_factor
        # get sum of thermal demand for time period
        th_cen_demand = sum(
            [region.demand_ts[f'th_{sector}'][ags][datetime_index]
             for sector in th_sectors]
        ).sum() * scaling_factor

        # get gas boiler config
        gas_boiler_cfg = scn_data['generation']['gen_th_cen']['gas_boiler']

        # heating network
        nodes.append(
            solph.Transformer(
                label=f'network_th_cen_{ags}',
                inputs={bus_th_net_in: solph.Flow()},
                outputs={bus_th_net_out: solph.Flow(
                    variable_costs=region.tech_assumptions_scn.loc[
                        'district_heating']['opex_var']
                )
                },
                conversion_factors={
                    bus_th_net_out: region.tech_assumptions_scn.loc[
                        'district_heating']['sys_eff']
                }
            )
        )

        # Dessau
        if ags == 15001000:
            # Extraction turbine docs:
            # https://oemof.readthedocs.io/en/stable/oemof_solph.html#extractionturbinechp-component

            # load GuD params
            gud_cfg = scn_data['generation']['gen_th_cen']['gud_dessau']
            cb_coeff = gud_cfg['cb_coeff']
            cv_coeff = gud_cfg['cv_coeff']
            el_eff_full_cond = gud_cfg['efficiency_full_cond']
            nom_th_power = gud_cfg['nom_th_power']
            # max. th. efficiency at max. heat extraction
            th_eff_max_ex = el_eff_full_cond / (cb_coeff + cv_coeff)
            # max. el. efficiency at max. heat extraction
            el_eff_max_ex = cb_coeff * th_eff_max_ex

            bus_el = esys_nodes['b_el_27977']

            # GuD Dessau
            nodes.append(
                solph.components.ExtractionTurbineCHP(
                    label=f'gen_th_cen_{ags}_gud',
                    inputs={b_gas: solph.Flow(
                        # nom. power gas derived from nom. th. power and
                        # max. th. efficiency
                        nominal_value=nom_th_power / th_eff_max_ex
                    )},
                    outputs={
                        bus_th_net_in: solph.Flow(
                            nominal_value=nom_th_power,
                            # provide at least X% of the th. energy demand
                            summed_min=th_cen_demand / nom_th_power *
                                       gud_cfg['min_th_energy_share']
                        ),
                        bus_el: solph.Flow(
                            variable_costs=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_cc']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_cc']['emissions_var']
                        )
                    },
                    conversion_factors={
                        bus_th_net_in: th_eff_max_ex,
                        bus_el: el_eff_max_ex
                    },
                    conversion_factor_full_condensation={
                        bus_el: el_eff_full_cond
                    }
                )
            )

            # gas boiler
            chp_th_power = round(th_cen_peak_load *
                                 gas_boiler_cfg['nom_th_power_rel_to_pl'])
            nodes.append(
                solph.Transformer(
                    label=f'gen_th_cen_{ags}_gas_boiler',
                    inputs={b_gas: solph.Flow()},
                    outputs={
                        bus_th_net_in: solph.Flow(
                            nominal_value=chp_th_power,
                            variable_costs=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['emissions_var']
                        )
                    },
                    conversion_factors={
                        bus_th_net_in: region.tech_assumptions_scn.loc[
                        'pp_natural_gas_boiler']['sys_eff']
                    }
                )
            )

            # storage
            if scn_data['storage']['th_cen_storage_dessau'][
                    'enabled']['enabled'] == 1:
                nodes.append(
                    solph.components.GenericStorage(
                        label=f'stor_th_cen_{ags}',
                        inputs={bus_th_net_in: solph.Flow(
                            **scn_data['storage']['th_cen_storage_dessau'][
                                'inflow'],
                            variable_costs=region.tech_assumptions_scn.loc[
                                'stor_th_large']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'stor_th_large']['emissions_var'],
                        )},
                        outputs={bus_th_net_in: solph.Flow(
                            **scn_data['storage']['th_cen_storage_dessau'][
                                'outflow']
                        )},
                        **scn_data['storage']['th_cen_storage_dessau'][
                            'params']
                    )
                )

        # Power plants Bitterfeld-Wolfen
        # Only el. power output is considered
        if ags == 15082015:
            # load GuD params
            gud_cfg = scn_data['generation']['gen_th_cen']['gud_bw']
            # max. th. efficiency at max. heat extraction
            th_eff_max_ex = gud_cfg['efficiency_full_cond'] /\
                            (gud_cfg['cb_coeff'] + gud_cfg['cv_coeff'])
            # max. el. efficiency at max. heat extraction
            el_eff_max_ex = gud_cfg['cb_coeff'] * th_eff_max_ex

            # el. demand is determined using normalized el. load (step)
            # profile and given el. production of GuD
            el_ind_demand = region.demand_ts['el_ind'][ags] / \
                            region.demand_ts['el_ind'][ags].sum() * \
                            gud_cfg['annual_el_prod']

            # GuD Bitterfeld-Wolfen
            # (as linear relationship between el. and th. is assumed, a simple
            # Transformer with constant eff. (at max. heat extraction) is
            # sufficient)
            bus_el = esys_nodes['b_el_26081']
            nodes.append(
                solph.Transformer(
                    label=f'gen_th_cen_{ags}_gud',
                    inputs={b_gas: solph.Flow()},
                    outputs={bus_el: solph.Flow(
                        nominal_value=gud_cfg['nom_el_power'],
                        fixed=True,
                        actual_value=list(el_ind_demand[datetime_index] /
                                          gud_cfg['nom_el_power']),
                        variable_costs=region.tech_assumptions_scn.loc[
                            'pp_natural_gas_cc']['opex_var'],
                        emissions=region.tech_assumptions_scn.loc[
                            'pp_natural_gas_cc']['emissions_var']
                    )
                    },
                    conversion_factors={
                        bus_el: el_eff_max_ex
                    }
                )
            )

            # Simple cycle (peak power) gas plant Wolfen
            gas_cfg = scn_data['generation']['gas_bw']
            bus_el = esys_nodes['b_el_27910']
            nodes.append(
                solph.Transformer(
                    label=f'gen_el_{ags}_gas',
                    inputs={b_gas: solph.Flow()},
                    outputs={bus_el: solph.Flow(
                        nominal_value=gas_cfg['nom_el_power'],
                        summed_min=(len(datetime_index)/8760) *
                                   gas_cfg['annual_flh'],
                        summed_max=(len(datetime_index)/8760) *
                                   gas_cfg['annual_flh'],
                        variable_costs=region.tech_assumptions_scn.loc[
                            'pp_natural_gas_sc']['opex_var'],
                        emissions=region.tech_assumptions_scn.loc[
                            'pp_natural_gas_sc']['emissions_var']
                    )
                    },
                    conversion_factors={
                        bus_el: region.tech_assumptions_scn.loc[
                            'pp_natural_gas_sc']['sys_eff']
                    }
                )
            )

        # Bitterfeld-Wolfen, Köthen, Wittenberg
        # Units: CHP (BHKW) (base) + gas boiler (peak)
        if ags in [15082015, 15091375, 15082180]:

            # CHP (BHKW)
            # TODO. Replace efficiency by data from db table?
            bhkw_cfg = scn_data['generation']['gen_th_cen']['bhkw']
            uptimes = create_maintenance_timeseries(
                datetime_index,
                bhkw_cfg['maint_months'],
                bhkw_cfg['maint_duration']
            )
            el_eff = region.tech_assumptions_scn.loc[
                'pp_bhkw']['sys_eff']
            th_eff = el_eff / bhkw_cfg['pq_coeff']
            chp_th_power = round(th_cen_peak_load * bhkw_cfg['nom_th_power_rel_to_pl'])
            chp_el_power = chp_th_power * bhkw_cfg['pq_coeff']

            outputs_el = {
                esys_nodes[f'b_el_{busdata.Index}']: solph.Flow(
                    nominal_value=chp_el_power / len(mun_buses),
                    variable_costs=region.tech_assumptions_scn.loc[
                        'pp_bhkw']['opex_var'] / len(mun_buses),
                    emissions=region.tech_assumptions_scn.loc[
                        'pp_bhkw']['emissions_var'] / len(mun_buses)
                )
                for busdata in mun_buses.itertuples()
            }

            nodes.append(
                solph.Transformer(
                    label=f'gen_th_cen_{ags}_bhkw',
                    inputs={b_gas: solph.Flow()},
                    outputs={
                        bus_th_net_in: solph.Flow(
                            nominal_value=chp_th_power,
                            # min=list(map(lambda _:
                            #              _ * bhkw_cfg['min_power'],
                            #              uptimes)),
                            max=uptimes,
                        ),
                        **outputs_el
                    },
                    conversion_factors={
                        bus_th_net_in: th_eff,
                        **{b_el: el_eff / len(mun_buses)
                           for b_el in outputs_el.keys()}
                    }
                )
            )

            # gas boiler
            chp_th_power = round(th_cen_peak_load *
                                 gas_boiler_cfg['nom_th_power_rel_to_pl'])
            nodes.append(
                solph.Transformer(
                    label=f'gen_th_cen_{ags}_gas_boiler',
                    inputs={b_gas: solph.Flow()},
                    outputs={
                        bus_th_net_in: solph.Flow(
                            nominal_value=chp_th_power,
                            variable_costs=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['emissions_var']
                        )
                    },
                    conversion_factors={
                        bus_th_net_in: region.tech_assumptions_scn.loc[
                        'pp_natural_gas_boiler']['sys_eff']
                    }
                )
            )

            # storage
            pth_storage_cfg = scn_data['storage']['th_cen_storage']
            stor_capacity = th_cen_peak_load * pth_storage_cfg[
                'general']['capacity_spec']

            if scn_data['storage']['th_cen_storage'][
                    'enabled']['enabled'] == 1:
                nodes.append(
                    solph.components.GenericStorage(
                        label=f'stor_th_cen_{ags}',
                        inputs={bus_th_net_in: solph.Flow(
                            nominal_value=stor_capacity * pth_storage_cfg[
                                'general']['c_rate_charge'],
                            variable_costs=region.tech_assumptions_scn.loc[
                                'stor_th_large']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'stor_th_large']['emissions_var'],
                        )},
                        outputs={bus_th_net_in: solph.Flow(
                            nominal_value=stor_capacity * pth_storage_cfg[
                                'general']['c_rate_discharge'],
                        )},
                        **pth_storage_cfg['params'],
                        nominal_storage_capacity=stor_capacity
                    )
                )

        # demand per sector and mun
        # TODO: Include efficiencies (also in sources above)
        for sector in th_sectors:
            inflow_args = {
                'nominal_value': 1,
                'fixed': True,
                'actual_value': list(
                    (region.demand_ts[f'th_{sector}'][ags] *
                     dist_heating_share
                     )[datetime_index]
                )
            }

            nodes.append(
                solph.Sink(label=f'dem_th_cen_{ags}_{sector}',
                    inputs={buses[f'b_th_cen_out_{ags}']:
                                solph.Flow(**inflow_args)})
            )

    return nodes


def create_flexopts(region=None, datetime_index=None, esys_nodes=[]):
    """Create model nodes for flexibility options such as batteries, PtH and
    DSM

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index of simulation timerange
    esys_nodes : nodes : :obj:`list` of :class:`nodes <oemof.network.Node>`
        ESys nodes

    Returns
    -------
    :obj:`list` of :class:`nodes <oemof.network.Node>`
        Nodes
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    scn_data = region.cfg['scn_data']

    logger.info("Creating flexopt objects...")

    esys_nodes = {str(n): n for n in esys_nodes}
    nodes = []

    # get th. sectors from cfg
    th_sectors = scn_data['demand']['dem_th_general']['sectors']

    #############
    # BATTERIES #
    #############
    # large scale batteries
    if scn_data['flexopt']['flex_bat_large']['enabled']['enabled'] == 1:
        batt_params = scn_data['flexopt']['flex_bat_large']

        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            batt_subst = region.batteries_large.loc[mun.Index] / len(mun_buses)

            if batt_subst['capacity'] > 0:
                batt_params['params'][
                    'nominal_storage_capacity'] = batt_subst['capacity']

                for busdata in mun_buses.itertuples():
                    bus = esys_nodes[f'b_el_{busdata.Index}']

                    nodes.append(
                        solph.components.GenericStorage(
                            label=f'flex_bat_large_{mun.Index}_b{busdata.Index}',
                            inputs={bus: solph.Flow(
                                nominal_value=batt_subst['power_charge'],
                                variable_costs=region.tech_assumptions_scn.loc[
                                    'stor_battery_large']['opex_var']
                            )},
                            outputs={bus: solph.Flow(
                                nominal_value=batt_subst['power_discharge']
                            )},
                            **batt_params['params']
                            # Note: efficiencies are read from cfg, not tech table
                        )
                    )

    # PV batteries in small rooftop solar home systems
    if scn_data['flexopt']['flex_bat_small']['enabled']['enabled'] == 1:
        batt_params = scn_data['flexopt']['flex_bat_small']

        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            batt_subst = region.batteries_small.loc[mun.Index] / len(mun_buses)

            if batt_subst['capacity'] > 0:
                batt_params['params'][
                    'nominal_storage_capacity'] = batt_subst['capacity']

                for busdata in mun_buses.itertuples():
                    bus = esys_nodes[f'b_el_{busdata.Index}']

                    nodes.append(
                        solph.components.GenericStorage(
                            label=f'flex_bat_small_{mun.Index}_b{busdata.Index}',
                            inputs={bus: solph.Flow(
                                nominal_value=batt_subst['power_charge'],
                                variable_costs=region.tech_assumptions_scn.loc[
                                    'stor_battery_small']['opex_var']
                            )},
                            outputs={bus: solph.Flow(
                                nominal_value=batt_subst['power_discharge']
                            )},
                            **batt_params['params']
                            # Note: efficiencies are read from cfg, not tech table
                        )
                    )


    ##################################################
    # PTH for decentralized heat supply (heat pumps) #
    ##################################################
    if scn_data['flexopt']['flex_dec_pth']['enabled']['enabled'] == 1:
        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            params = scn_data['flexopt']['flex_dec_pth']['params']
            share_ashp = scn_data['flexopt']['flex_dec_pth'][
                'technology']['share_ASHP']
            share_gshp = scn_data['flexopt']['flex_dec_pth'][
                'technology']['share_GSHP']

            # calc temperature-dependent coefficient of performance (COP)
            cops_ASHP = calc_heat_pump_cops(
                t_high=[params['heating_temp']],
                t_low=list(
                    (region.temp_ts['air_temp'][mun.Index]
                    )[datetime_index]
                ),
                quality_grade=params['quality_grade_ASHP'],
                consider_icing=True,
                temp_icing=params['icing_temp'],
                factor_icing=params['icing_factor'],
                spf=region.tech_assumptions.loc['heating_ashp']['sys_eff'],
                year=scn_data['general']['year']
            )
            cops_GSHP = calc_heat_pump_cops(
                t_high=[params['heating_temp']],
                t_low=list(
                    (region.temp_ts['soil_temp'][mun.Index]
                    )[datetime_index]
                ),
                quality_grade=params['quality_grade_GSHP'],
                spf=region.tech_assumptions.loc['heating_gshp']['sys_eff'],
                year=scn_data['general']['year']
            )

            for sector in th_sectors:
                th_load = region.demand_ts[f'th_{sector}'][mun.Index] * \
                          (1 - region.dist_heating_share_scn.loc[mun.Index])
                solar_feedin = region.feedin_ts['solar_heat'][mun.Index] * \
                               th_load.sum(axis=0) * \
                               region.heating_structure_dec_scn.loc[
                                   mun.Index][sector].loc['solar']
                th_residual_load = (
                        (th_load - solar_feedin) *
                        region.heating_structure_dec_scn_wo_solar.loc[
                            mun.Index, 'ambient_heat'][sector]
                )[datetime_index]

                # Set residual load = 0 at times when th. load < solar feedin
                th_residual_load[th_residual_load < 0] = 0

                th_residual_load_sum, th_residual_load_max =\
                    th_residual_load.agg(['sum', 'max'])

                del th_load, solar_feedin

                if th_residual_load_sum > 0:
                    bus_th_dec = esys_nodes[f'b_th_dec_{mun.Index}_{sector}']

                    # calc cum. th demand, th peak load and el peak load
                    # for ASHP+GSHP
                    th_dec_demand_pth_mun_sec_ashp = th_residual_load_sum * \
                                                     share_ashp
                    th_dec_th_peak_pth_mun_sec_ashp = th_residual_load_max * \
                                                      share_ashp
                    th_dec_el_peak_pth_mun_sec_ashp = (th_residual_load /
                                                       cops_ASHP).max() * \
                                                      share_ashp
                    th_dec_demand_pth_mun_sec_gshp = th_residual_load_sum * \
                                                     share_gshp
                    th_dec_th_peak_pth_mun_sec_gshp = th_residual_load_max * \
                                                      share_gshp
                    th_dec_el_peak_pth_mun_sec_gshp = (th_residual_load /
                                                       cops_GSHP).max() * \
                                                      share_gshp

                    ################################
                    # HP systems with heat storage #
                    ################################
                    pth_storage_cfg = scn_data['storage']['th_dec_pth_storage']
                    if (pth_storage_cfg['enabled']['enabled'] == 1 and
                            0 <
                            pth_storage_cfg['general']['pth_storage_share']
                            <= 1):

                        # create additional PTH heat bus
                        bus_th_dec_pth = solph.Bus(
                            label=f'b_th_dec_pth_{mun.Index}_{sector}'
                        )
                        nodes.append(bus_th_dec_pth)

                        # calc nominal capacity depending on
                        # HP peak load (nom. el. power):
                        # capacity [MWh] = P_hp [MW] * capacity_spec [m^3/MW] *
                        #                  1000 [kg/m^3] * 4,2 [kJ/(kg*K)] *
                        #                  delta_temp [K] / 3600 / 1000
                        stor_capacity = (
                                ((th_dec_el_peak_pth_mun_sec_ashp +
                                  th_dec_el_peak_pth_mun_sec_gshp) *
                                 pth_storage_cfg['general'][
                                     'pth_storage_share']
                                 ) *
                                pth_storage_cfg['general']['capacity_spec'] *
                                1000 * 4.2 *
                                pth_storage_cfg['general']['delta_temp'] /
                                3600 / 1000
                        )

                        # create storage
                        nodes.append(
                            solph.components.GenericStorage(
                                label=f'stor_th_dec_pth_{mun.Index}_{sector}',
                                inputs={bus_th_dec_pth: solph.Flow(
                                    nominal_value=(
                                        stor_capacity * pth_storage_cfg[
                                            'general']['c_rate_charge']
                                    ),
                                    variable_costs=region.tech_assumptions_scn.loc[
                                        'stor_th_small']['opex_var'],
                                    emissions=region.tech_assumptions_scn.loc[
                                        'stor_th_small']['emissions_var'],
                                )},
                                outputs={bus_th_dec_pth: solph.Flow(
                                    nominal_value=(
                                        stor_capacity * pth_storage_cfg[
                                            'general']['c_rate_discharge']
                                    )
                                )},
                                nominal_storage_capacity=stor_capacity,
                                **pth_storage_cfg['params']
                                # Note: efficiencies are read from cfg, not tech table
                            )
                        )

                        # create ASHP
                        nodes.append(
                            solph.Transformer(
                                label=f'flex_dec_pth_ASHP_stor_{mun.Index}_{sector}',
                                inputs={
                                    esys_nodes[f'b_el_{busdata.Index}']: solph.Flow()
                                    for busdata in mun_buses.itertuples()
                                },
                                outputs={bus_th_dec_pth: solph.Flow(
                                    nominal_value=(th_dec_th_peak_pth_mun_sec_ashp *
                                                   pth_storage_cfg['general'][
                                                       'pth_storage_share']),
                                    variable_costs=region.tech_assumptions_scn.loc[
                                        'heating_ashp']['opex_var'],
                                    emissions=region.tech_assumptions_scn.loc[
                                        'heating_ashp']['emissions_var'],
                                )},
                                conversion_factors={
                                    esys_nodes[f'b_el_{busdata.Index}']:
                                        [1 / len(mun_buses) / cop
                                         for cop in cops_ASHP]
                                    for busdata in mun_buses.itertuples()
                                }
                            )
                        )

                        # create GSHP
                        nodes.append(
                            solph.Transformer(
                                label=f'flex_dec_pth_GSHP_stor_{mun.Index}_{sector}',
                                inputs={
                                    esys_nodes[f'b_el_{busdata.Index}']: solph.Flow()
                                    for busdata in mun_buses.itertuples()
                                },
                                outputs={bus_th_dec_pth: solph.Flow(
                                    nominal_value=(th_dec_th_peak_pth_mun_sec_gshp *
                                                   pth_storage_cfg['general'][
                                                       'pth_storage_share']),
                                    variable_costs=region.tech_assumptions_scn.loc[
                                        'heating_gshp']['opex_var'],
                                    emissions=region.tech_assumptions_scn.loc[
                                        'heating_gshp']['emissions_var'],
                                )},
                                conversion_factors={
                                    esys_nodes[f'b_el_{busdata.Index}']:
                                        [1 / len(mun_buses) / cop
                                         for cop in cops_ASHP]
                                    for busdata in mun_buses.itertuples()
                                }
                            )
                        )

                        # create transformer to dec heat bus
                        nodes.append(
                            solph.Transformer(
                                label=f'trans_dummy_th_dec_pth_{mun.Index}_{sector}',
                                inputs={bus_th_dec_pth: solph.Flow()},
                                outputs={bus_th_dec: solph.Flow(
                                    nominal_value=(
                                            (th_dec_th_peak_pth_mun_sec_ashp +
                                             th_dec_th_peak_pth_mun_sec_gshp) *
                                            pth_storage_cfg['general'][
                                                'pth_storage_share']
                                    ),
                                    summed_min=(
                                        (th_dec_demand_pth_mun_sec_ashp /
                                         th_dec_th_peak_pth_mun_sec_ashp) +
                                        (th_dec_demand_pth_mun_sec_gshp /
                                         th_dec_th_peak_pth_mun_sec_gshp)
                                    )/2,
                                    summed_max=(
                                        (th_dec_demand_pth_mun_sec_ashp /
                                         th_dec_th_peak_pth_mun_sec_ashp) +
                                        (th_dec_demand_pth_mun_sec_gshp /
                                         th_dec_th_peak_pth_mun_sec_gshp)
                                    )/2,
                                )},
                                conversion_factors={bus_th_dec: 1}
                            )
                        )
                    else:
                        pth_storage_cfg['general']['pth_storage_share'] = 0

                    ###################################
                    # HP systems without heat storage #
                    ###################################
                    if pth_storage_cfg['general']['pth_storage_share'] != 1:
                        # create ASHP
                        nodes.append(
                            solph.Transformer(
                                label=f'flex_dec_pth_ASHP_nostor_'
                                      f'{mun.Index}_{sector}',
                                inputs={
                                    esys_nodes[f'b_el_{busdata.Index}']:
                                        solph.Flow()
                                    for busdata in mun_buses.itertuples()
                                },
                                outputs={bus_th_dec: solph.Flow(
                                    nominal_value=(
                                            th_dec_th_peak_pth_mun_sec_ashp *
                                            (1 - pth_storage_cfg['general'][
                                                'pth_storage_share'])
                                    ),
                                    summed_min=(
                                            th_dec_demand_pth_mun_sec_ashp /
                                            th_dec_th_peak_pth_mun_sec_ashp
                                    ),
                                    summed_max=(
                                            th_dec_demand_pth_mun_sec_ashp /
                                            th_dec_th_peak_pth_mun_sec_ashp
                                    ),
                                    variable_costs=region.tech_assumptions_scn.loc[
                                        'heating_ashp']['opex_var'],
                                    emissions=region.tech_assumptions_scn.loc[
                                        'heating_ashp']['emissions_var'],
                                )},
                                conversion_factors={
                                    esys_nodes[f'b_el_{busdata.Index}']:
                                        [1/len(mun_buses)/cop
                                         for cop in cops_ASHP]
                                    for busdata in mun_buses.itertuples()
                                }
                            )
                        )

                        # create GSHP
                        nodes.append(
                            solph.Transformer(
                                label=f'flex_dec_pth_GSHP_nostor_'
                                      f'{mun.Index}_{sector}',
                                inputs={
                                    esys_nodes[f'b_el_{busdata.Index}']:
                                        solph.Flow()
                                    for busdata in mun_buses.itertuples()
                                },
                                outputs={bus_th_dec: solph.Flow(
                                    nominal_value=(
                                            th_dec_th_peak_pth_mun_sec_gshp *
                                            (1 - pth_storage_cfg['general'][
                                                'pth_storage_share'])
                                    ),
                                    summed_min=(
                                            th_dec_demand_pth_mun_sec_gshp /
                                            th_dec_th_peak_pth_mun_sec_gshp
                                    ),
                                    summed_max=(
                                            th_dec_demand_pth_mun_sec_gshp /
                                            th_dec_th_peak_pth_mun_sec_gshp
                                    ),
                                    variable_costs=region.tech_assumptions_scn.loc[
                                        'heating_gshp']['opex_var'],
                                    emissions=region.tech_assumptions_scn.loc[
                                        'heating_gshp']['emissions_var'],
                                )},
                                conversion_factors={
                                    esys_nodes[f'b_el_{busdata.Index}']:
                                        [1/len(mun_buses)/cop
                                         for cop in cops_GSHP]
                                    for busdata in mun_buses.itertuples()
                                }
                            )
                        )

    #################################################
    # PTH for district heating (boiler/heating rod) #
    #################################################
    if scn_data['flexopt']['flex_cen_pth']['enabled']['enabled'] == 1:
        for mun in region.muns.itertuples():

            if region.dist_heating_share_scn[mun.Index] > 0:
                scaling_factor = region.dist_heating_share_scn.loc[mun.Index] / \
                                 region.tech_assumptions_scn.loc[
                                     'district_heating']['sys_eff']

                # get annual thermal peak load (consider network losses)
                th_cen_peak_load = sum(
                    [region.demand_ts[f'th_{sector}'][mun.Index]
                     for sector in th_sectors]
                ).max() * scaling_factor

                mun_buses = region.buses.loc[region.subst.loc[
                    mun.subst_id].bus_id]
                bus_out = esys_nodes[f'b_th_cen_in_{mun.Index}']

                nodes.append(
                    solph.Transformer(
                        label=f'flex_cen_pth_{str(mun.Index)}',
                        inputs={
                            esys_nodes[f'b_el_{busdata.Index}']: solph.Flow()
                            for busdata in mun_buses.itertuples()
                        },
                        outputs={bus_out: solph.Flow(
                            nominal_value=round(
                                th_cen_peak_load * scn_data['flexopt'][
                                    'flex_cen_pth']['params'][
                                    'nom_th_power_rel_to_pl']),
                            variable_costs=region.tech_assumptions_scn.loc[
                                'heating_rod']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'heating_rod']['emissions_var']
                        )},
                        conversion_factors={
                            esys_nodes[f'b_el_{busdata.Index}']:
                                1 / len(mun_buses) *
                                region.tech_assumptions_scn.loc[
                                    'heating_rod']['sys_eff']
                            for busdata in mun_buses.itertuples()
                        }
                    )
                )

    ####################
    # DSM (households) #
    ####################
    dsm_cfg = scn_data['flexopt']['dsm']

    # if DSM is enabled (>0), load of HH Sinks in l.191 ff. will be reduced
    if dsm_cfg['params']['hh_share'] > 0:

        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            for busdata in mun_buses.itertuples():
                bus_in = esys_nodes[f'b_el_{busdata.Index}']
                dsm_mode = dsm_cfg['params']['mode']

                nodes.append(
                    solph.custom.SinkDSM(
                        label=f'flex_dsm_{mun.Index}_b{busdata.Index}',
                        inputs={bus_in: solph.Flow()},
                        demand=list(
                            (region.dsm_ts['Lastprofil']
                             [mun.Index] / len(mun_buses)
                             )[datetime_index] * dsm_cfg['params']['hh_share']
                        ),
                        capacity_up=list(
                            (calc_dsm_cap_up(
                                region.dsm_ts,
                                mun.Index,
                                mode=dsm_mode) / len(mun_buses)
                             )[datetime_index] * dsm_cfg['params']['hh_share']
                        ),
                        capacity_down=list(
                            (calc_dsm_cap_down(
                                region.dsm_ts,
                                mun.Index,
                                mode=dsm_mode) / len(mun_buses)
                             )[datetime_index] * dsm_cfg['params']['hh_share']
                        ),
                        method=dsm_cfg['params']['method'],
                        shift_interval=int(dsm_cfg['params']['shift_interval']),
                        delay_time=int(dsm_cfg['params']['delay_time'])
                    )
                )

    return nodes


def imported_electricity_limit(om, limit):
    """
    Limit the annual imported electricity from national system

    Adds a constraint to the optimization problem that limits imported electricity
    from the national system to a certain share of total consumed electricity.

    .. math::

        \sum_{tr \in Trafos_{HV/EHV} } \sum_t P_{tr} \left( t \right)
        \leq limit
        \cdot \sum_t \left( \sum_{d \in demand_{el}} P_d(t)
        + \sum_{s \in storages_{el}} P_{loss,s}(t)
        + \sum_{l \in lines} P_{loss,l}(t)
        + \sum_{hp \in heat\_pump_{el}} P_{el,hp}(t) \right)

    Parameters
    ----------

    om : :class:`OperationalModel <oemof.solph.Model>`
        Instance of oemof.solph operational model
    limit : float
        Electricity imports limit from external grid (0..1)
    """
    el_demand_labels = ("dem_el", "flex_dsm", "flex_dec_pth", "flex_cen_pth")

    import_flows = [(i, o)
                    for (i, o) in om.FLOWS
                    if i.label.startswith("shortage_el")]
    el_demand_flows = [(i, o)
                       for (i, o) in om.FLOWS
                       if o.label.startswith(el_demand_labels)]
    battery_storage_charge_flows = [(i, o)
                                    for (i, o) in om.FLOWS
                                    if o.label.startswith("flex_bat")]
    battery_storage_discharge_flows = [(i, o)
                                       for (i, o) in om.FLOWS
                                       if i.label.startswith("flex_bat")]
    grid_flows_to_grid = [(i, o)
                          for (i, o) in om.FLOWS
                          if isinstance(o, solph.custom.Link)]
    grid_flows_to_bus = [(i, o)
                         for (i, o) in om.FLOWS
                         if isinstance(i, solph.custom.Link)]

    def _import_limit_rule(om):
        lhs = sum(om.flow[i, o, t]
                  for (i, o) in import_flows
                  for t in om.TIMESTEPS)
        rhs = limit * (sum(om.flow[i, o, t]
                           for (i, o) in el_demand_flows
                           for t in om.TIMESTEPS) +
                       sum(om.flow[i, o, t]
                           for (i, o) in battery_storage_charge_flows
                           for t in om.TIMESTEPS) -
                       sum(om.flow[i, o, t]
                           for (i, o) in battery_storage_discharge_flows
                           for t in om.TIMESTEPS) +
                       sum(om.flow[i, o, t]
                           for (i, o) in grid_flows_to_grid
                           for t in om.TIMESTEPS) -
                       sum(om.flow[i, o, t]
                           for (i, o) in grid_flows_to_bus
                           for t in om.TIMESTEPS)
                       )

        return lhs <= rhs

    el_import_lim = Constraint(rule=_import_limit_rule)

    setattr(om, "el_import_constraint", el_import_lim)

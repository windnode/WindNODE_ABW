import pandas as pd
import oemof.solph as solph
import logging
logger = logging.getLogger('windnode_abw')

from windnode_abw.model.region.tools import calc_heat_pump_cops,\
    calc_dsm_cap_down, calc_dsm_cap_up, create_maintenance_timeseries


def simulate(esys, solver='cbc', verbose=True):
    """Optimize energy system

    Parameters
    ----------
    esys : oemof.solph.EnergySystem
    solver : `obj`:str
        Solver which is used

    Returns
    -------
    oemof.solph.OperationalModel
    """

    # Create problem
    logger.info('Create optimization problem...')
    om = solph.Model(esys)

    # solve it
    logger.info('Solve optimization problem...')
    om.solve(solver=solver,
             solve_kwargs={'tee': verbose,
                           'keepfiles': True})

    return om


def create_oemof_model(cfg, region):
    """Create oemof model using config and data files. An oemof energy system
    is created, nodes are added and parametrized.

    Parameters
    ----------
    cfg : :obj:`dict`
        Config to be used to create model
    region : :class:`~.model.Region`
        Region object

    Returns
    -------
    oemof.solph.EnergySystem
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

    print('Number of nodes created:', len(el_nodes) + len(th_nodes) + len(flex_nodes))
    # print('The following objects have been created:')
    # for n in esys.nodes:
    #     oobj = str(type(n)).replace("<class 'oemof.solph.", "").replace("'>", "")
    #     print(oobj + ':', n.label)

    return esys


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
    hh_dsm = scn_data['flexopt']['dsm']['enabled']['enabled']

    # create nodes for all municipalities
    for ags, mundata in region.muns.iterrows():
        # get buses for subst in mun
        mun_buses = region.buses.loc[region.subst.loc[mundata.subst_id].bus_id]

        # note: timeseries are distributed equally to all buses of mun
        for bus_id, busdata in mun_buses.iterrows():
            # generators
            for tech, ts_df in {t: ts for t, ts
                                in region.feedin_ts.items()
                                if t in scn_data[
                    'generation']['gen_el']['technologies']}.items():
                outflow_args = {
                    'nominal_value': 1,
                    'fixed':  True,
                    'actual_value': list((ts_df[ags] /
                                          len(mun_buses))[datetime_index]),
                    'variable_costs': region.tech_assumptions_scn.loc[
                        tech]['opex_var'],
                    'emissions': region.tech_assumptions_scn.loc[
                        tech]['emissions']
                }

                # create node only if feedin sum is >0
                if ts_df[ags].sum(axis=0) > 0:
                    nodes.append(
                        solph.Source(
                            label='gen_el_{ags_id}_b{bus_id}_{tech}'.format(
                                ags_id=ags,
                                bus_id=str(bus_id),
                                tech=tech
                            ),
                            outputs={buses[bus_id]: solph.Flow(**outflow_args)})
                    )

            for sector in el_sectors:
                # deactivate hh_sinks if DSM is enabled in scenario config
                if sector == 'hh' and hh_dsm == 1:
                    pass
                else:
                    inflow_args = {
                        'nominal_value': 1,
                        'fixed':  True,
                        'actual_value': list(
                            (region.demand_ts['el_{sector}'.format(
                                sector=sector)][ags] / len(mun_buses)
                             )[datetime_index]
                        )
                    }

                    # use IÖW load profile if set in scenario config
                    if sector == 'hh' and hh_profile_type == 'ioew':
                        inflow_args['actual_value'] = \
                            list(
                                (region.dsm_ts['Lastprofil'][ags] /
                                 len(mun_buses)
                                 )[datetime_index]
                            )

                    nodes.append(
                        solph.Sink(
                            label='dem_el_{ags_id}_b{bus_id}_{sector}'.format(
                                ags_id=ags,
                                bus_id=str(bus_id),
                                sector=sector
                            ),
                            inputs={buses[bus_id]: solph.Flow(
                                **inflow_args)})
                    )

    ################
    # TRANSFORMERS #
    ################

    # add 380/110kV trafos
    for idx, row in region.trafos.iterrows():
        bus0 = buses[row['bus0']]
        bus1 = buses[row['bus1']]
        nodes.append(
            solph.custom.Link(
                label='trafo_{trafo_id}_b{b0}_b{b1}'.format(
                    trafo_id=str(idx),
                    b0=str(row['bus0']),
                    b1=str(row['bus1'])
                ),
                inputs={bus0: solph.Flow(),
                        bus1: solph.Flow()},
                outputs={bus0: solph.Flow(nominal_value=row['s_nom']),
                         bus1: solph.Flow(nominal_value=row['s_nom'])},
                # TODO: Revise efficiencies
                conversion_factors={
                    (bus0, bus1): scn_data['grid']['trafos']['params']['conversion_factor'],
                    (bus1, bus0): scn_data['grid']['trafos']['params']['conversion_factor']})
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
                    variable_costs=region.tech_assumptions_scn.loc[
                        'el_energy']['capex']
                )})
        )
        nodes.append(
            solph.Source(
                label='shortage_el_{v_level}_b{bus_id}'.format(
                    bus_id=idx,
                    v_level='hv' if row['v_nom'] == 110 else 'ehv'
                ),
                outputs={bus: solph.Flow(
                    variable_costs=region.tech_assumptions_scn.loc[
                        'el_energy']['capex'],
                    emissions=region.tech_assumptions_scn.loc[
                        'el_energy']['emissions']
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
            msg = 'Nominal capacity of connected line '
            'not found for bus {bus_id}'.format(bus_id=idx)
            logger.error(msg)
            raise ValueError(msg)

        nodes.append(
            solph.custom.Link(
                label='line_b{bus_id}_b_el_imex'.format(
                    bus_id=str(idx)
                ),
                inputs={bus: solph.Flow(),
                        imex_bus: solph.Flow()},
                outputs={
                    bus: solph.Flow(
                        nominal_value=s_nom *
                                      scn_data['grid']['extgrid']['imex_lines']['params']['max_usable_capacity'],
                        **scn_data['grid']['extgrid']['imex_lines']['outflow']
                    ),
                    imex_bus: solph.Flow(
                        nominal_value=s_nom *
                                      scn_data['grid']['extgrid']['imex_lines']['params']['max_usable_capacity'],
                        **scn_data['grid']['extgrid']['imex_lines']['outflow']
                    )
                },
                # TODO: Revise efficiencies
                conversion_factors={
                    (bus, imex_bus): scn_data['grid']['extgrid']['imex_lines']['params']['conversion_factor'],
                    (imex_bus, bus): scn_data['grid']['extgrid']['imex_lines']['params']['conversion_factor']
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
                label='line_{line_id}_b{b0}_b{b1}'.format(
                    line_id=str(row['line_id']),
                    b0=str(row['bus0']),
                    b1=str(row['bus1'])
                ),
                inputs={bus0: solph.Flow(),
                        bus1: solph.Flow()},
                outputs={
                    bus0: solph.Flow(
                        nominal_value=float(row['s_nom']),
                        **scn_data['grid']['lines']['outflow']
                    ),
                    bus1: solph.Flow(
                        nominal_value=float(row['s_nom']),
                        **scn_data['grid']['lines']['outflow']
                    )
                },
                # TODO: Revise efficiencies
                conversion_factors={
                    (bus0, bus1): scn_data['grid']['lines']['params']['conversion_factor'],
                    (bus1, bus0): scn_data['grid']['lines']['params']['conversion_factor']
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
            bus = solph.Bus(label='b_th_dec_{ags_id}_{sector}'.format(
                ags_id=str(mun.Index),
                sector=sector)
            )
            buses[bus.label] = bus
            nodes.append(bus)

    # buses for district heating (Fernwärme)
    # (1 per mun)
    for ags, _ in region.dist_heating_share_scn[region.dist_heating_share_scn > 0].\
            iteritems():
        # heating network bus for feedin (to grid)
        bus = solph.Bus(label='b_th_cen_in_{ags_id}'.format(
            ags_id=str(ags))
        )
        buses[bus.label] = bus
        nodes.append(bus)
        # heating network bus for output (from grid)
        bus = solph.Bus(label='b_th_cen_out_{ags_id}'.format(
            ags_id=str(ags))
        )
        buses[bus.label] = bus
        nodes.append(bus)

    ###############
    # COMMODITIES #
    ###############
    # create a commodity for each energy source in cfg
    # except for el. energy and ambient_heat (el. bus is used)

    # make sure all sources have data in heating structure
    if not all([_ in region.heating_structure_dec.index.get_level_values('energy_source').unique()
                for _ in scn_data['commodities']['commodities']]):
        msg = 'You have invalid commodities in your config! (at ' \
              'least one is not contained in heating structure)'
        logger.error(msg)
        raise ValueError(msg)

    commodities = {}
    for es in scn_data['commodities']['commodities']:
        if es not in ['el_energy', 'dist_heating']:
            bus = solph.Bus(label='b_{es}'.format(es=es))
            com = solph.Source(
                label='{es}'.format(es=str(es)),
                outputs={bus: solph.Flow(
                    variable_costs=region.tech_assumptions_scn.loc[
                        'comm_' + es]['capex'] if es != 'solar' else 0,
                    emissions=region.tech_assumptions_scn.loc[
                        'comm_' + es]['emissions']  if es != 'solar' else 0
                )
                }
            )
            commodities[com.label] = com
            nodes.append(com)

    #############################
    # DECENTRALIZED HEAT SUPPLY #
    #############################

    for mun in region.muns.itertuples():
        dec_sources = scn_data['generation']['gen_th_dec']['general']['sources']
        # load heating structure for current scenario
        heating_structure_dec = region.heating_structure_dec_scn.loc[
            mun.Index].filter(items=dec_sources, axis=0)
        mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

        # sources for decentralized heat supply (1 per technology, sector, mun)
        for sector in th_sectors:
            bus_th = buses['b_th_dec_{ags_id}_{sector}'.format(
                ags_id=str(mun.Index),
                sector=sector)]

            for es in heating_structure_dec.itertuples():
                es_share = heating_structure_dec[sector].loc[es.Index]

                if es_share > 0:
                    outflow_args = {
                        'nominal_value': 1,
                        'fixed': True,
                        'actual_value': list(
                            (region.demand_ts['th_{sector}'.format(
                                sector=sector)][mun.Index] *
                             (1 - region.dist_heating_share_scn.loc[mun.Index]) * es_share
                             )[datetime_index]
                        )
                    }

                    # TODO: Revise solar
                    if es.Index != 'el_energy':
                        inputs = {commodities[es.Index]: solph.Flow()}
                        outflow_args['variable_costs'] = region.tech_assumptions_scn.loc[
                            'heating_' + es.Index]['opex_var']
                        outflow_args['emissions'] = region.tech_assumptions_scn.loc[
                            'heating_' + es.Index]['emissions']
                        conversion_factors = {
                            bus_th: region.tech_assumptions_scn.loc[
                                'heating_' + es.Index]['sys_eff']
                            }
                    else:
                        inputs = {
                            esys_nodes['b_el_{bus_id}'.format(
                                bus_id=busdata.Index)]: solph.Flow()
                            for busdata in mun_buses.itertuples()
                        }
                        outflow_args['variable_costs'] = 0
                        outflow_args['emissions'] = 0
                        # TODO: REVISE
                        conversion_factors = {bus_th: 1}

                    nodes.append(
                        solph.Transformer(
                            label='gen_th_dec_{ags_id}_{sector}_{src}'.format(
                                ags_id=str(mun.Index),
                                sector=sector,
                                src=str(es.Index)
                            ),
                            inputs=inputs,
                            outputs={bus_th: solph.Flow(**outflow_args)},
                            conversion_factors=conversion_factors
                        )
                    )

            # general common heat storage
            if scn_data['storage']['th_dec_storage']['enabled']['enabled'] == 1:
                nodes.append(
                    solph.components.GenericStorage(
                        label='stor_th_dec_{ags_id}_{sector}'.format(
                            ags_id=str(mun.Index),
                            sector=sector
                        ),
                        inputs={bus_th: solph.Flow(
                            **scn_data['storage']['th_dec_storage']['inflow']
                        )},
                        outputs={bus_th: solph.Flow(
                            **scn_data['storage']['th_dec_storage']['outflow']
                        )},
                        **scn_data['storage']['th_dec_storage']['params']
                    )
                )

        # demand per sector and mun
        for sector in th_sectors:
            inflow_args = {
                'nominal_value': 1,
                'fixed': True,
                'actual_value': list(
                    (region.demand_ts['th_{sector}'.format(
                        sector=sector)][mun.Index] *
                     (1 - region.dist_heating_share_scn.loc[mun.Index])
                     )[datetime_index]
                )
            }

            # ToDo: Include saving using different scn from db table
            nodes.append(
                solph.Sink(
                    label='dem_th_dec_{ags_id}_{sector}'.format(
                        ags_id=str(mun.Index),
                        sector=sector
                ),
                    inputs={buses['b_th_dec_{ags_id}_{sector}'.format(
                        ags_id=str(mun.Index),
                        sector=sector)]: solph.Flow(**inflow_args)
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
        bus_th_net_in = buses['b_th_cen_in_{ags_id}'.format(ags_id=str(ags))]
        bus_th_net_out = buses['b_th_cen_out_{ags_id}'.format(ags_id=str(ags))]

        #
        scaling_factor = dist_heating_share / \
                         region.tech_assumptions_scn.loc[
                             'district_heating']['sys_eff']

        # get annual thermal peak load (consider network losses)
        th_cen_peak_load = sum(
            [region.demand_ts['th_{sector}'.format(
                sector=sector)][ags]
             for sector in th_sectors]
        ).max() * scaling_factor
        # get sum of thermal demand for time period
        th_cen_demand = sum(
            [region.demand_ts['th_{sector}'.format(
                sector=sector)][ags][datetime_index]
             for sector in th_sectors]
        ).sum() * scaling_factor

        # get gas boiler config
        gas_boiler_cfg = scn_data['generation']['gen_th_cen']['gas_boiler']

        # heating network
        nodes.append(
            solph.Transformer(
                label='network_th_cen_{ags_id}'.format(
                    ags_id=str(ags)
                ),
                inputs={bus_th_net_in: solph.Flow()},
                outputs={bus_th_net_out: solph.Flow(
                    variable_costs=1
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

            gud_cfg = scn_data['generation']['gen_th_cen']['gud']
            cb_coeff = gud_cfg['cb_coeff']
            cv_coeff = gud_cfg['cv_coeff']
            el_eff_full_cond = gud_cfg['efficiency_full_cond']
            nom_th_power = gud_cfg['nom_th_power']
            # max. th. efficiency at max. heat extraction
            th_eff_max_ex = el_eff_full_cond / (cb_coeff + cv_coeff)
            # max. el. efficiency at max. heat extraction
            el_eff_max_ex = cb_coeff * th_eff_max_ex
            bus_el = esys_nodes['b_el_27977']

            # GuD
            nodes.append(
                solph.components.ExtractionTurbineCHP(
                    label='gen_th_cen_{ags_id}_gud'.format(
                        ags_id=str(ags)
                    ),
                    inputs={commodities['natural_gas']: solph.Flow(
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
                                'pp_natural_gas_gud']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_gud']['emissions']
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
                    label='gen_th_cen_{ags_id}_gas_boiler'.format(
                        ags_id=str(ags)
                    ),
                    inputs={commodities['natural_gas']: solph.Flow()},
                    outputs={
                        bus_th_net_in: solph.Flow(
                            nominal_value=chp_th_power,
                            variable_costs=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['emissions']
                        )
                    },
                    conversion_factors={
                        bus_th_net_in: region.tech_assumptions_scn.loc[
                        'pp_natural_gas_boiler']['sys_eff']
                    }
                )
            )

            # storage
            if scn_data['storage']['th_cen_storage']['enabled']['enabled'] == 1:
                nodes.append(
                    solph.components.GenericStorage(
                        label='stor_th_cen_{ags_id}'.format(
                            ags_id=str(ags),
                        ),
                        inputs={bus_th_net_in: solph.Flow(
                            **scn_data['storage']['th_cen_storage']['inflow']
                        )},
                        outputs={bus_th_net_in: solph.Flow(
                            **scn_data['storage']['th_cen_storage']['outflow']
                        )},
                        **scn_data['storage']['th_cen_storage']['params']
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

            # chp_eff = bhkw_cfg['efficiency']
            # chp_pq_coeff = bhkw_cfg['pq_coeff']
            # chp_el_power = chp_th_power * chp_pq_coeff
            # chp_th_conv_fac = chp_eff * 1 / (1 + chp_pq_coeff)
            # chp_el_conv_fac = chp_eff * chp_pq_coeff / (1 + chp_pq_coeff) /\
            #                   len(mun_buses)

            outputs_el = {
                esys_nodes['b_el_{bus_id}'.format(bus_id=busdata.Index)]: solph.Flow(
                    nominal_value=chp_el_power / len(mun_buses),
                    variable_costs=region.tech_assumptions_scn.loc[
                        'pp_bhkw']['opex_var'] / len(mun_buses),
                    emissions=region.tech_assumptions_scn.loc[
                        'pp_bhkw']['emissions'] / len(mun_buses)
                )
                for busdata in mun_buses.itertuples()
            }

            nodes.append(
                solph.Transformer(
                    label='gen_th_cen_{ags_id}_bhkw'.format(
                        ags_id=str(ags)
                    ),
                    inputs={commodities['natural_gas']: solph.Flow()},
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
                    label='gen_th_cen_{ags_id}_gas_boiler'.format(
                        ags_id=str(ags)
                    ),
                    inputs={commodities['natural_gas']: solph.Flow()},
                    outputs={
                        bus_th_net_in: solph.Flow(
                            nominal_value=chp_th_power,
                            variable_costs=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['opex_var'],
                            emissions=region.tech_assumptions_scn.loc[
                                'pp_natural_gas_boiler']['emissions']
                        )
                    },
                    conversion_factors={
                        bus_th_net_in: region.tech_assumptions_scn.loc[
                        'pp_natural_gas_boiler']['sys_eff']
                    }
                )
            )

        # demand per sector and mun
        # TODO: Include efficiencies (also in sources above)
        for sector in th_sectors:
            inflow_args = {
                'nominal_value': 1,
                'fixed': True,
                'actual_value': list(
                    (region.demand_ts['th_{sector}'.format(
                        sector=sector)][ags] *
                     dist_heating_share
                     )[datetime_index]
                )
            }

            nodes.append(
                solph.Sink(label='dem_th_cen_{ags_id}_{sector}'.format(
                    ags_id=str(ags),
                    sector=sector
                ),
                    inputs={buses['b_th_cen_out_{ags_id}'.format(
                        ags_id=str(ags))]: solph.Flow(**inflow_args)})
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
    if scn_data['flexopt']['flex_bat']['enabled']['enabled'] == 1:
        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            for busdata in mun_buses.itertuples():
                bus = esys_nodes['b_el_{bus_id}'.format(bus_id=busdata.Index)]

                nodes.append(
                    solph.components.GenericStorage(
                        label='flex_bat_{ags_id}_b{bus_id}'.format(
                            ags_id=str(mun.Index),
                            bus_id=busdata.Index
                        ),
                        inputs={bus: solph.Flow(
                            variable_costs=region.tech_assumptions_scn.loc[
                                'stor_battery_large']['opex_var']
                        )},
                        outputs={bus: solph.Flow()},
                        **scn_data['flexopt']['flex_bat']['params']
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
                factor_icing=params['icing_factor']
            )
            cops_GSHP = calc_heat_pump_cops(
                t_high=[params['heating_temp']],
                t_low=list(
                    (region.temp_ts['soil_temp'][mun.Index]
                    )[datetime_index]
                ),
                quality_grade=params['quality_grade_GSHP']
            )

            # calc dec th. demand to be met by pth
            # (share of 'ambient_heat' in heating structure)
            # and use it as min. feedin
            th_dec_demand_pth_mun = pd.DataFrame(
                {sector:
                     region.demand_ts['th_{sector}'.format(
                         sector=sector)][mun.Index][datetime_index] *
                     (1 - region.dist_heating_share_scn.loc[mun.Index])
                 for sector in th_sectors}
            ) * region.heating_structure_dec_scn.loc[mun.Index,
                                                     'ambient_heat']

            for sector in th_sectors:
                if th_dec_demand_pth_mun.sum()[sector] > 0:
                    bus_out = esys_nodes['b_th_dec_{ags_id}_{sector}'.format(
                        ags_id=mun.Index,
                        sector=sector
                    )]

                    #####################
                    # Heat pump storage #
                    #####################
                    if scn_data['storage']['th_dec_pth_storage']['enabled']['enabled'] == 1:
                        # create additional PTH heat bus
                        bus_th_dec_pth = solph.Bus(
                            label=f'b_th_dec_pth_{mun.Index}_{sector}'
                        )
                        nodes.append(bus_th_dec_pth)

                        # create storage
                        nodes.append(
                            solph.components.GenericStorage(
                                label=f'stor_th_dec_pth_{mun.Index}_{sector}',
                                inputs={bus_th_dec_pth: solph.Flow(
                                    **scn_data['storage']['th_dec_pth_storage']['inflow']
                                )},
                                outputs={bus_th_dec_pth: solph.Flow(
                                    **scn_data['storage']['th_dec_pth_storage']['outflow']
                                )},
                                **scn_data['storage']['th_dec_pth_storage']['params']
                            )
                        )

                        # create transformer to dec heat bus
                        nodes.append(
                            solph.Transformer(
                                label=f'trans_dummy_th_dec_pth_{mun.Index}_{sector}',
                                inputs={bus_th_dec_pth: solph.Flow()},
                                outputs={bus_out: solph.Flow()},
                                conversion_factors={bus_out: 1}
                            )
                        )

                        # use PTH hat bus as output for HP
                        bus_out = bus_th_dec_pth

                    #########################
                    # Air Source Heat Pumps #
                    #########################
                    th_dec_demand_pth_mun_sec = th_dec_demand_pth_mun.sum()\
                                                    [sector] * share_ashp
                    th_dec_peak_pth_mun_sec = th_dec_demand_pth_mun.max()\
                                                  [sector] * share_ashp
                    nodes.append(
                        solph.Transformer(
                            label='flex_dec_pth_ASHP_{ags_id}_{sector}'.format(
                                ags_id=str(mun.Index),
                                sector=sector
                            ),
                            inputs={
                                esys_nodes[f'b_el_{busdata.Index}']: solph.Flow()
                                for busdata in mun_buses.itertuples()
                            },
                            outputs={bus_out: solph.Flow(
                                nominal_value=th_dec_peak_pth_mun_sec,
                                summed_min=th_dec_demand_pth_mun_sec / th_dec_peak_pth_mun_sec,
                                summed_max=th_dec_demand_pth_mun_sec / th_dec_peak_pth_mun_sec,
                                variable_costs=region.tech_assumptions_scn.loc[
                                    'heating_ashp']['opex_var'],
                                emissions=region.tech_assumptions_scn.loc[
                                    'heating_ashp']['emissions'],
                            )},
                            conversion_factors={
                                esys_nodes[f'b_el_{busdata.Index}']:
                                    [1/len(mun_buses)/cop for cop in cops_ASHP]
                                for busdata in mun_buses.itertuples()
                            }
                        )
                    )

                    ############################
                    # Ground Source Heat Pumps #
                    ############################
                    th_dec_demand_pth_mun_sec = th_dec_demand_pth_mun.sum()\
                                                    [sector] * share_gshp
                    th_dec_peak_pth_mun_sec = th_dec_demand_pth_mun.max()\
                                                  [sector] * share_gshp
                    nodes.append(
                        solph.Transformer(
                            label='flex_dec_pth_GSHP_{ags_id}_{sector}'.format(
                                ags_id=str(mun.Index),
                                sector=sector
                            ),
                            inputs={
                                esys_nodes[f'b_el_{busdata.Index}']: solph.Flow()
                                for busdata in mun_buses.itertuples()
                            },
                            outputs={bus_out: solph.Flow(
                                nominal_value=th_dec_peak_pth_mun_sec,
                                summed_min=th_dec_demand_pth_mun_sec / th_dec_peak_pth_mun_sec,
                                summed_max=th_dec_demand_pth_mun_sec / th_dec_peak_pth_mun_sec,
                                variable_costs=region.tech_assumptions_scn.loc[
                                    'heating_gshp']['opex_var'],
                                emissions=region.tech_assumptions_scn.loc[
                                    'heating_gshp']['emissions'],
                            )},
                            conversion_factors={
                                esys_nodes[f'b_el_{busdata.Index}']:
                                    [1/len(mun_buses)/cop for cop in cops_GSHP]
                                for busdata in mun_buses.itertuples()
                            }
                        )
                    )

    #################################################
    # PTH for district heating (boiler/heating rod) #
    #################################################
    if scn_data['flexopt']['flex_cen_pth']['enabled']['enabled'] == 1:
        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            for busdata in mun_buses.itertuples():
                bus_in = esys_nodes['b_el_{bus_id}'.format(bus_id=busdata.Index)]

                if 'b_th_cen_in_{ags_id}'.format(ags_id=mun.Index) in esys_nodes.keys():
                    bus_out = esys_nodes['b_th_cen_in_{ags_id}'.format(
                        ags_id=mun.Index
                    )]

                    nodes.append(
                        solph.Transformer(
                            label='flex_cen_pth_{ags_id}_b{bus_id}'.format(
                                ags_id=str(mun.Index),
                                bus_id=busdata.Index
                            ),
                            inputs={bus_in: solph.Flow()},
                            outputs={bus_out: solph.Flow(
                                # TODO: get from DB table?
                                nominal_value=scn_data['flexopt'][
                                    'flex_cen_pth']['outflow']['nominal_value'],
                                variable_costs=region.tech_assumptions_scn.loc[
                                    'heating_rod']['opex_var'],
                                emissions = region.tech_assumptions_scn.loc[
                                    'heating_rod']['emissions']
                            )},
                            conversion_factors={
                                bus_out: region.tech_assumptions_scn.loc[
                                    'heating_rod']['sys_eff']
                            }
                        )
                    )

    ####################
    # DSM (households) #
    ####################
    # if DSM is enabled hh Sinks in l.170 ff. will be deactivated
    if scn_data['flexopt']['dsm']['enabled']['enabled'] == 1:
        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            for busdata in mun_buses.itertuples():
                bus_in = esys_nodes['b_el_{bus_id}'.format(bus_id=busdata.Index)]
                dsm_mode = scn_data['flexopt']['dsm']['params']['mode']

                nodes.append(
                    solph.custom.SinkDSM(
                        label='flex_dsm_{ags_id}_b{bus_id}'.format(
                            ags_id=str(mun.Index),
                            bus_id=busdata.Index
                        ),
                        inputs={bus_in: solph.Flow()},
                        demand=list(
                            (region.dsm_ts['Lastprofil']
                             [mun.Index] / len(mun_buses)
                             )[datetime_index]
                        ),
                        capacity_up=list(
                            (calc_dsm_cap_up(
                                region.dsm_ts,
                                mun.Index,
                                mode=dsm_mode) / len(mun_buses)
                             )[datetime_index]
                        ),
                        capacity_down=list(
                            (calc_dsm_cap_down(
                                region.dsm_ts,
                                mun.Index,
                                mode=dsm_mode) / len(mun_buses)
                             )[datetime_index]
                        ),
                        method=scn_data['flexopt']['dsm']['params']['method'],
                        shift_interval=int(scn_data['flexopt']['dsm']['params']['shift_interval']),
                        delay_time=int(scn_data['flexopt']['dsm']['params']['delay_time'])
                    )
                )

    return nodes

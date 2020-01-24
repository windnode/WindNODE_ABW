import pandas as pd
import oemof.solph as solph
import logging
logger = logging.getLogger('windnode_abw')

from windnode_abw.model.region.tools import calc_heat_pump_cops
from windnode_abw.model.region.tools import calc_dsm_cap_down
from windnode_abw.model.region.tools import calc_dsm_cap_up


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
    th_nodes = create_th_model(
        region=region,
        datetime_index=datetime_index,
        scn_data=cfg['scn_data']
    )
    esys.add(*th_nodes)

    el_nodes = create_el_model(
        region=region,
        datetime_index=datetime_index,
        scn_data=cfg['scn_data']
    )
    esys.add(*el_nodes)

    flex_nodes = create_flexopts(
        region=region,
        datetime_index=datetime_index,
        nodes_in=th_nodes+el_nodes,
        scn_data=cfg['scn_data']
    )
    esys.add(*flex_nodes)

    print('The following objects have been created:')
    for n in esys.nodes:
        oobj = str(type(n)).replace("<class 'oemof.solph.", "").replace("'>", "")
        print(oobj + ':', n.label)

    return esys


def create_el_model(region=None, datetime_index=None, scn_data={}):
    """Create electrical model modes (oemof objects) and lines from region such
    as buses, links, sources and sinks.

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index

    Returns
    -------
    :obj:`list` of :class:`nodes <oemof.network.Node>`
        ESys nodes
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Creating el. system objects...")

    timesteps_cnt = len(datetime_index)

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

    # create nodes for all municipalities
    for ags, mundata in region.muns.iterrows():
        # get buses for subst in mun
        mun_buses = region.buses.loc[region.subst.loc[mundata.subst_id].bus_id]

        # note: timeseries are distributed equally to all buses of mun
        for bus_id, busdata in mun_buses.iterrows():
            # generators
            for tech, ts_df in region.feedin_ts.items():
                outflow_args = {
                    'nominal_value': 1,
                    'fixed':  True,
                    'actual_value': list(ts_df[ags] /
                                         len(mun_buses))[:timesteps_cnt]
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

            hh_profile_type = scn_data['demand']['dem_el_hh']['profile_type']
            hh_dsm = scn_data['flexopt']['dsm']['enabled']['enabled']

            for sector, ts_df in region.demand_ts.items():
                if sector[:3] == 'el_':
                    # deactivate hh_sinks if DSM is enabled in scenario config
                    if sector == 'el_hh' and hh_dsm == 1:
                        pass
                    else:
                        inflow_args = {
                            'nominal_value': 1,
                            'fixed':  True,
                            'actual_value': list(
                                ts_df[ags] / len(mun_buses)
                            )[:timesteps_cnt]
                        }

                        # use IÖW load profile if set in scenario config
                        if sector == 'el_hh' and hh_profile_type == 'ioew':
                            inflow_args['actual_value'] = \
                                list(region.dsm_ts['Lastprofil'][ags] /
                                     len(mun_buses))[:timesteps_cnt]

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
        if row['v_nom'] == 110:
            v_level = 'hv'
            sink_inflow_args = scn_data['grid']['extgrid']['excess_el_hv']['inflow']
            source_outflow_args = scn_data['grid']['extgrid']['shortage_el_hv']['outflow']
        elif row['v_nom'] == 380:
            v_level = 'ehv'
            sink_inflow_args = scn_data['grid']['extgrid']['excess_el_ehv']['inflow']
            source_outflow_args = scn_data['grid']['extgrid']['shortage_el_ehv']['outflow']
        nodes.append(
            solph.Sink(label='excess_el_{v_level}_b{bus_id}'.format(
                bus_id=idx,
                v_level=v_level
            ),
                       inputs={bus: solph.Flow(
                           **sink_inflow_args
                       )})
        )
        nodes.append(
            solph.Source(label='shortage_el_{v_level}_b{bus_id}'.format(
                bus_id=idx,
                v_level=v_level
            ),
                         outputs={bus: solph.Flow(
                             **source_outflow_args
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
                conversion_factors={
                    (bus0, bus1): scn_data['grid']['lines']['params']['conversion_factor'],
                    (bus1, bus0): scn_data['grid']['lines']['params']['conversion_factor']
                }
            )
        )

    return nodes


def create_th_model(region=None, datetime_index=None, scn_data={}):
    """Create thermal model modes (oemof objects) and lines from region such
    as buses, sources and sinks.

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index

    Returns
    -------
    :obj:`list` of :class:`nodes <oemof.network.Node>`
        ESys nodes
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Creating th. system objects...")

    timesteps_cnt = len(datetime_index)

    nodes = []

    #########
    # BUSES #
    #########
    buses = {}

    # get th. sectors from demand TS
    th_sectors = [sec[3:] for sec in region.demand_ts.keys() if sec[:3] == 'th_']

    # buses for decentralized heat supply (Dezentrale Wärmeversorgung)
    # (1 per sector and mun)
    for mun in region.muns.itertuples():
        for sector in th_sectors:
            bus = solph.Bus(label='b_th_dec_{ags_id}_{sector}'.format(
                ags_id=str(mun.Index),
                sector=sector[11:])
            )
            buses[bus.label] = bus
            nodes.append(bus)

    # buses for district heating (Fernwärme)
    # (1 per sector and mun)
    # TODO: Replace dist heat share by new param table
    for mun in region.muns[region.muns.dem_th_energy_dist_heat_share > 0].\
            itertuples():
        bus = solph.Bus(label='b_th_cen_{ags_id}'.format(
            ags_id=str(mun.Index))
        )
        buses[bus.label] = bus
        nodes.append(bus)

    #############################
    # DECENTRALIZED HEAT SUPPLY #
    #############################
    for mun in region.muns.itertuples():

        # sources for decentralized heat supply (1 per mun)
        # Todo: Currently just a simple shortage source, update later?
        nodes.append(
            solph.Source(
                label='gen_th_dec_{ags_id}'.format(
                    ags_id=str(mun.Index)
                ),
                outputs={buses['b_th_dec_{ags_id}'.format(
                    ags_id=str(mun.Index))]: solph.Flow(
                    **scn_data['generation']['gen_th_dec']['outflow']
                )})
        )

        # demand per sector and mun
        for sector, ts_df in region.demand_ts.items():
            if sector[:3] == 'th_':
                inflow_args = {
                    'nominal_value': 1,
                    'fixed': True,
                    'actual_value': list(
                        ts_df[mun.Index] *
                        (1 - mun.dem_th_energy_dist_heat_share)
                    )[:timesteps_cnt]
                }

                # ToDo: Include saving using different scn from db table

                nodes.append(
                    solph.Sink(
                        label='dem_th_dec_{ags_id}_{sector}'.format(
                            ags_id=str(mun.Index),
                            sector=sector[3:]
                    ),
                        inputs={buses['b_th_dec_{ags_id}'.format(
                            ags_id=str(mun.Index))]: solph.Flow(**inflow_args)})
                )

    ####################
    # DISTRICT HEATING #
    ####################
    for mun in region.muns.itertuples():

        # only add if there's district heating in mun
        if mun.dem_th_energy_dist_heat_share > 0:

            # sources for district heating (1 per mun)
            # Todo: Currently just a simple shortage source, update later?
            nodes.append(
                solph.Source(
                    label='gen_th_cen_{ags_id}'.format(
                        ags_id=str(mun.Index)
                    ),
                    outputs={buses['b_th_cen_{ags_id}'.format(
                        ags_id=str(mun.Index))]: solph.Flow(
                        **scn_data['generation']['gen_th_cen']['outflow']
                    )})
            )

            # demand per sector and mun
            for sector, ts_df in region.demand_ts.items():
                if sector[:3] == 'th_':
                    inflow_args = {
                        'nominal_value': 1,
                        'fixed': True,
                        'actual_value': list(
                            ts_df[mun.Index] *
                            mun.dem_th_energy_dist_heat_share
                        )[:timesteps_cnt]
                    }

                    nodes.append(
                        solph.Sink(label='dem_th_cen_{ags_id}_{sector}'.format(
                            ags_id=str(mun.Index),
                            sector=sector
                        ),
                            inputs={buses['b_th_cen_{ags_id}'.format(
                                ags_id=str(mun.Index))]: solph.Flow(**inflow_args)})
                    )

    return nodes


def create_flexopts(region=None, datetime_index=None, nodes_in=[], scn_data={}):
    """Create model nodes for flexibility options such as batteries, PtH and
    DSM

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index
    nodes_in : nodes : :obj:`list` of :class:`nodes <oemof.network.Node>`
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

    logger.info("Creating flexopt objects...")

    timesteps_cnt = len(datetime_index)

    nodes_in = {str(n): n for n in nodes_in}
    nodes = []

    #############
    # BATTERIES #
    #############
    # ToDo: Develop location strategy

    if scn_data['flexopt']['flex_bat']['enabled']['enabled'] == 1:
        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            for busdata in mun_buses.itertuples():
                bus = nodes_in['b_el_{bus_id}'.format(bus_id=busdata.Index)]

                nodes.append(
                    solph.components.GenericStorage(
                        label='flex_bat_{ags_id}_b{bus_id}'.format(
                            ags_id=str(mun.Index),
                            bus_id=busdata.Index
                        ),
                        inputs={bus: solph.Flow(
                            **scn_data['flexopt']['flex_bat']['inflow']
                        )},
                        outputs={bus: solph.Flow()},
                        **scn_data['flexopt']['flex_bat']['params']
                    )
                )

    #################
    # POWER-TO-HEAT #
    #################
    flex_dec_pth_enabled = True if scn_data['flexopt']['flex_dec_pth']['enabled']['enabled'] == 1 else False
    flex_cen_pth_enabled = True if scn_data['flexopt']['flex_cen_pth']['enabled']['enabled'] == 1 else False
    flex_hh_dsm_enabled = True if scn_data['flexopt']['dsm']['enabled']['enabled'] == 1 else False

    if flex_dec_pth_enabled or flex_cen_pth_enabled or flex_hh_dsm_enabled:
        for mun in region.muns.itertuples():
            mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

            for busdata in mun_buses.itertuples():
                bus_in = nodes_in['b_el_{bus_id}'.format(bus_id=busdata.Index)]

                ##################################################
                # PTH for decentralized heat supply (heat pumps) #
                ##################################################
                if flex_dec_pth_enabled:
                    bus_out = nodes_in['b_th_dec_{ags_id}'.format(ags_id=mun.Index)]

                    #########################
                    # Air Source Heat Pumps #
                    #########################
                    # calc temperature-dependent coefficient of performance (COP)
                    params = scn_data['flexopt']['flex_dec_pth']['params']
                    cops_ASHP = calc_heat_pump_cops(
                        t_high=[params['heating_temp']],
                        t_low=list(
                            region.temp_ts['air_temp'][mun.Index]
                        )[:timesteps_cnt],
                        quality_grade=params['quality_grade'],
                        consider_icing=True,
                        factor_icing=params['ASHP_factor_icing']
                    )
                    # DEBUG ONLY:
                    # print('COP: ', max(cops_hp), min(cops_hp))
                    # xxx = {'heat_demand_mfh': region.demand_ts['th_hh_mfh'][mun.Index],
                    #        'temp': list(region.temp_ts[mun.Index]),
                    #        'cop': cops_hp}
                    # x = pd.DataFrame.from_dict(xxx)
                    # x.plot()
                    outflow_args = {
                        'nominal_value': scn_data['flexopt']['flex_dec_pth']
                                         ['outflow']['nominal_value_total'] *
                                         scn_data['flexopt']['flex_dec_pth']
                                         ['technology']['share_ASHP'] /
                                         len(mun_buses),
                        'variable_costs': scn_data['flexopt']['flex_dec_pth']
                                          ['outflow']['variable_costs_ASHP']
                    }
                    nodes.append(
                        solph.Transformer(
                            label='flex_dec_pth_ASHP_{ags_id}_b{bus_id}'.format(
                                ags_id=str(mun.Index),
                                bus_id=busdata.Index
                            ),
                            inputs={bus_in: solph.Flow()},
                            outputs={bus_out: solph.Flow(
                                **outflow_args
                            )},
                            conversion_factors={bus_out: cops_ASHP}
                        )
                    )

                    ############################
                    # Ground Source Heat Pumps #
                    ############################
                    cops_GSHP = calc_heat_pump_cops(
                        t_high=[params['heating_temp']],
                        t_low=list(
                            region.temp_ts['soil_temp'][mun.Index]
                        )[:timesteps_cnt],
                        quality_grade=params['quality_grade'],
                        consider_icing=False
                    )
                    outflow_args = {
                        'nominal_value': scn_data['flexopt']['flex_dec_pth']
                                         ['outflow']['nominal_value_total'] *
                                         scn_data['flexopt']['flex_dec_pth']
                                         ['technology']['share_GSHP'] /
                                         len(mun_buses),
                        'variable_costs': scn_data['flexopt']['flex_dec_pth']
                                          ['outflow']['variable_costs_GSHP']
                    }
                    nodes.append(
                        solph.Transformer(
                            label='flex_dec_pth_GSHP_{ags_id}_b{bus_id}'.format(
                                ags_id=str(mun.Index),
                                bus_id=busdata.Index
                            ),
                            inputs={bus_in: solph.Flow()},
                            outputs={bus_out: solph.Flow(
                                **outflow_args
                            )},
                            conversion_factors={bus_out: cops_GSHP}
                        )
                    )

                #####################################
                # PTH for district heating (boiler) #
                #####################################
                if flex_cen_pth_enabled:
                    if 'b_th_cen_{ags_id}'.format(ags_id=mun.Index) in nodes_in.keys():
                        bus_out = nodes_in['b_th_cen_{ags_id}'.format(
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
                                    **scn_data['flexopt']['flex_cen_pth']['outflow']
                                )},
                                conversion_factors={
                                    bus_out: scn_data['flexopt']['flex_cen_pth']
                                                     ['params']['conversion_factor']
                                }
                            )
                        )

                ####################
                # DSM (households) #
                ####################
                if flex_hh_dsm_enabled:
                    # if DSM is enabled hh Sinks in l.170 ff. will be deactivated

                    dsm_mode = scn_data['flexopt']['dsm']['params']['mode']

                    nodes.append(
                        solph.custom.SinkDSM(
                            label='flex_dsm_{ags_id}_b{bus_id}'.format(
                                ags_id=str(mun.Index),
                                bus_id=busdata.Index
                            ),
                            inputs={bus_in: solph.Flow()},
                            demand=(region.dsm_ts['Lastprofil']
                                    [mun.Index] / len(mun_buses))[:timesteps_cnt],
                            capacity_up=(
                                calc_dsm_cap_up(
                                    region.dsm_ts,
                                    mun.Index,
                                    mode=dsm_mode
                                ) / len(mun_buses)
                                        )[:timesteps_cnt],
                            capacity_down=(
                                calc_dsm_cap_down(
                                    region.dsm_ts,
                                    mun.Index,
                                    mode=dsm_mode
                                ) / len(mun_buses)
                                          )[:timesteps_cnt],
                            method=scn_data['flexopt']['dsm']['params']['method'],
                            shift_interval=int(scn_data['flexopt']['dsm']['params']['shift_interval']),
                            delay_time=int(scn_data['flexopt']['dsm']['params']['delay_time'])
                        )
                    )

    return nodes

import pandas as pd
import oemof.solph as solph
import logging
logger = logging.getLogger('windnode_abw')


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
        datetime_index=datetime_index
    )
    esys.add(*th_nodes.values())

    el_nodes = create_el_model(
        region=region,
        datetime_index=datetime_index
    )
    esys.add(*el_nodes.values())

    flex_nodes = create_flexopts(
        region=region,
        datetime_index=datetime_index,
        nodes_in=dict(el_nodes, **th_nodes)
    )
    esys.add(*flex_nodes.values())

    print('The following objects have been created:')
    for n in esys.nodes:
        oobj = str(type(n)).replace("<class 'oemof.solph.", "").replace("'>", "")
        print(oobj + ':', n.label)

    return esys


def create_el_model(region=None, datetime_index=None):
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
    :obj:`dict` of :class:`nodes <oemof.network.Node>`
        Node label as key, object as val
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

    #################
    # EXTERNAL GRID #
    #################

    # common bus for el. power import and export (110 kV level)
    imex_hv_bus = solph.Bus(label='b_el_imex_hv')
    nodes.append(imex_hv_bus)
    # common bus for el. power import and export (380 kV level)
    imex_ehv_bus = solph.Bus(label='b_el_imex_ehv')
    nodes.append(imex_ehv_bus)

    # add sink and source for common import/export bus to represent external
    # grid (110 kV level)
    nodes.append(
        solph.Sink(label='excess_el_hv',
                   inputs={imex_hv_bus: solph.Flow(variable_costs=-50)})
    )
    nodes.append(
        solph.Source(label='shortage_el_hv',
                     outputs={imex_hv_bus: solph.Flow(variable_costs=200)})
    )

    # add sink and source for common import/export bus to represent external
    # grid (380 kV level)
    nodes.append(
        solph.Sink(label='excess_el_ehv',
                   inputs={imex_ehv_bus: solph.Flow(variable_costs=-50)})
    )
    nodes.append(
        solph.Source(label='shortage_el_ehv',
                     outputs={imex_ehv_bus: solph.Flow(variable_costs=200)})
    )

    ####################
    # ELECTRICAL NODES #
    ####################

    # create nodes for all municipalities
    for ags, mundata in region.muns.iterrows():
        # get buses for subst in mun
        mun_buses = region.buses.loc[region.subst.loc[mundata.subst_id].bus_id]

        # note: timeseries are distributed equally to all buses of mun
        for bus_id, busdata in mun_buses.iterrows():
            # create generators
            # ToDo: Use normalized ts and cap instead?
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
                            label='gen_el_b{bus_id}_{tech}'.format(
                                bus_id=str(bus_id),
                                tech=tech
                            ),
                            outputs={buses[bus_id]: solph.Flow(**outflow_args)})
                    )
            # create el. demands
            # ToDo: Use normalized ts and cap instead?
            for sector, ts_df in region.demand_ts.items():
                if sector[:3] == 'el_':
                    inflow_args = {
                        'nominal_value': 1,
                        'fixed':  True,
                        'actual_value': list(ts_df[ags] /
                                             len(mun_buses))[:timesteps_cnt]
                    }
                    nodes.append(
                        solph.Sink(
                            label='dem_el_b{bus_id}_{sector}'.format(
                                bus_id=str(bus_id),
                                sector=sector
                        ),
                            inputs={buses[bus_id]: solph.Flow(**inflow_args)})
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
                conversion_factors={(bus0, bus1): 0.98, (bus1, bus0): 0.98})
        )

    # create lines for import and export
    # (buses which are tagged with region_bus == False)
    for idx, row in region.buses[~region.buses['region_bus']].iterrows():
        bus = buses[idx]

        # SEPARATE EXCESS+SHORTAGE BUSES
        # # add sink and source for import/export
        # nodes.append(
        #     solph.Sink(label='excess_el_b{bus_id}'.format(bus_id=idx),
        #                inputs={bus: solph.Flow(variable_costs=-50)})
        # )
        # nodes.append(
        #     solph.Source(label='shortage_el_b{bus_id}'.format(bus_id=idx),
        #                  outputs={bus: solph.Flow(variable_costs=100)})
        # )

        # CONNECTION TO COMMON IMEX BUS
        if row['v_nom'] == 110:
            imex_bus = imex_hv_bus
        elif row['v_nom'] == 380:
            imex_bus = imex_ehv_bus

        nodes.append(
            solph.custom.Link(
                label='line_b{b0}_b_el_imex'.format(
                    b0=str(idx)
                ),
                inputs={bus: solph.Flow(),
                        imex_bus: solph.Flow()},
                outputs={bus: solph.Flow(nominal_value=10e6,
                                         variable_costs=1),
                         imex_bus: solph.Flow(nominal_value=10e6,
                                              variable_costs=1)
                         },
                conversion_factors={(bus, imex_bus): 0.98,
                                    (imex_bus, bus): 0.98})
        )

    # create regular lines
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
                outputs={bus0: solph.Flow(nominal_value=float(row['s_nom']),
                                          variable_costs=0.0001
                                          ),
                         bus1: solph.Flow(nominal_value=float(row['s_nom']),
                                          variable_costs=0.0001
                                          )
                         },
                conversion_factors={(bus0, bus1): 0.98, (bus1, bus0): 0.98})
        )

    return {str(n): n for n in nodes}


def create_th_model(region=None, datetime_index=None):
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
    :obj:`dict` of :class:`nodes <oemof.network.Node>`
        Node label as key, object as val
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

    # buses for decentralized heat supply (Dezentrale Wärmeversorgung)
    for mun in region.muns.itertuples():
        bus = solph.Bus(label='b_th_dec_{ags_id}'.format(
            ags_id=str(mun.Index))
        )
        buses[bus.label] = bus
        nodes.append(bus)

    # buses for district heating (Fernwärme)
    for mun in region.muns[region.muns.dem_th_energy_dist_heat_share > 0].\
            itertuples():
        bus = solph.Bus(label='b_th_cen_{ags_id}'.format(
            ags_id=str(mun.Index))
        )
        buses[bus.label] = bus
        nodes.append(bus)

    ################################
    # HEAT DEMAND AND FEEDIN NODES #
    ################################
    inflow_args = {
        'nominal_value': 1,
        'fixed': True
    }

    for mun in region.muns.itertuples():
        for sector, ts_df in region.demand_ts.items():
            if sector[:3] == 'th_':
                #############################
                # decentralized heat supply #
                #############################
                # demand
                inflow_args['actual_value'] = list(
                        ts_df[mun.Index] *
                        (1 - mun.dem_th_energy_dist_heat_share)
                    )[:timesteps_cnt]

                nodes.append(
                    solph.Sink(
                        label='dem_th_dec_{ags_id}_{sector}'.format(
                            ags_id=str(mun.Index),
                            sector=sector
                    ),
                        inputs={buses['b_th_dec_{ags_id}'.format(
                            ags_id=str(mun.Index))]: solph.Flow(**inflow_args)})
                )

                # feedin
                # Todo: Currently just a simple shortage source, update later?
                nodes.append(
                    solph.Source(
                        label='gen_th_dec_{ags_id}'.format(
                            ags_id=str(mun.Index)
                        ),
                        outputs={buses['b_th_dec_{ags_id}'.format(
                            ags_id=str(mun.Index))]: solph.Flow(variable_costs=100)})
                )

                ####################
                # district heating #
                ####################
                if mun.dem_th_energy_dist_heat_share > 0:
                    # demand
                    inflow_args['actual_value'] = list(
                            ts_df[mun.Index] *
                            mun.dem_th_energy_dist_heat_share
                        )[:timesteps_cnt]

                    nodes.append(
                        solph.Sink(label='dem_th_cen_{ags_id}_{sector}'.format(
                            ags_id=str(mun.Index),
                            sector=sector
                        ),
                            inputs={buses['b_th_cen_{ags_id}'.format(
                                ags_id=str(mun.Index))]: solph.Flow(**inflow_args)})
                    )

                    # feedin
                    # Todo: Currently just a simple shortage source, update later?
                    nodes.append(
                        solph.Source(
                            label='gen_th_cen_{ags_id}'.format(
                                ags_id=str(mun.Index)
                            ),
                            outputs={buses['b_th_cen_{ags_id}'.format(
                                ags_id=str(mun.Index))]: solph.Flow(variable_costs=100)})
                    )

    return {str(n): n for n in nodes}


def create_flexopts(region=None, datetime_index=None, nodes_in={}):
    """Create model nodes for flexibility options such as batteries, PtH and
    DSM

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index
    nodes_in : nodes : :obj:`dict` of :class:`nodes <oemof.network.Node>`
        esys nodes - node label as key, object as val

    Returns
    -------
    :obj:`dict` of :class:`nodes <oemof.network.Node>`
        Node label as key, object as val
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Creating flexopt objects...")

    timesteps_cnt = len(datetime_index)

    nodes = []

    #############
    # BATTERIES #
    #############
    # ToDo: Develop location strategy, implement

    #################
    # POWER-TO-HEAT #
    #################
    for mun in region.muns.itertuples():

        mun_buses = region.buses.loc[region.subst.loc[mun.subst_id].bus_id]

        for busdata in mun_buses.itertuples():
            bus_in = nodes_in['b_el_{bus_id}'.format(bus_id=busdata.Index)]

            ##################################################
            # PTH for decentralized heat supply (heat pumps) #
            ##################################################
            bus_out = nodes_in['b_th_dec_{ags_id}'.format(ags_id=mun.Index)]

            outflow_args = {'nominal_value': 1000,
                            'fixed': False,
                            'variable_costs': 500}
            nodes.append(
                solph.Transformer(
                    label='flex_dec_pth_{ags_id}'.format(
                        ags_id=str(mun.Index)
                    ),
                    inputs={bus_in: solph.Flow()},
                    outputs={bus_out: solph.Flow(**outflow_args)}
                )
            )

            #####################################
            # PTH for district heating (boiler) #
            #####################################
            if 'b_th_cen_{ags_id}'.format(ags_id=mun.Index) in nodes_in.keys():
                bus_out = nodes_in['b_th_cen_{ags_id}'.format(ags_id=mun.Index)]

                outflow_args = {'nominal_value': 1000,
                                'fixed': False,
                                'variable_costs': 500}
                nodes.append(
                    solph.Transformer(
                        label='flex_cen_pth_{ags_id}'.format(
                            ags_id=str(mun.Index)
                        ),
                        inputs={bus_in: solph.Flow()},
                        outputs={bus_out: solph.Flow(**outflow_args)}
                    )
                )

    return {str(n): n for n in nodes}

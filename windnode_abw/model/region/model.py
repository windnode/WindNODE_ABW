import logging
logger = logging.getLogger('windnode_abw')

from windnode_abw.model import Region
from windnode_abw.model.region.tools import grid_graph

import pandas as pd
import numpy as np
import numpy.random as random

import oemof.solph as solph


def create_nodes(region=None, datetime_index = list()):
    """Create nodes (oemof objects) from node dict

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index :
        Datetime index

    Returns
    -------
    nodes : `obj`:dict of :class:`nodes <oemof.network.Node>`
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Creating objects")

    # create buses
    buses = {}
    nodes = []
    for idx, row in region.buses.iterrows():
        bus = solph.Bus(label='b_el_' + str(idx))
        buses[idx] = bus
        nodes.append(bus)

    # # add bus for power import and export
    # imex_bus = solph.Bus(label='b_el_imex')
    # nodes.append(imex_bus)

    # create sources: RES power plants
    for idx, row in region.geno_res_grouped.iterrows():
        # get bus
        bus = buses[region.subst.loc[idx[0]]['otg_id']]
        # get timeseries datasets (there could be multiple)
        ts_ds = region.geno_res_ts.loc[idx]
        #outflow_args = {'nominal_value': row['sum']}
        outflow_args = {'nominal_value': row['sum']}

        # if source is renewable (fixed source with timeseries)
        #if (ts_ds['dispatch'] == 'variable').all():
        # calc relative feedin sum from all timeseries
        if 'wind' in idx:
            fac = 1
        elif 'solar' in idx:
            fac = 0.85
        elif 'biomass' in idx:
            fac = 0.85
        elif 'run_of_river' in idx:
            fac = 0.85
        else:
            fac = 1
        #ts = np.sum(list(ts_ds['p_set']), 0) / row['sum']
        ts = [fac, fac, fac]
        # add ts and fix it for renewables
        outflow_args['actual_value'] = ts
        outflow_args['fixed'] = True

        # create node
        nodes.append(
            solph.Source(label=idx[1] + '_' + str(idx[0]),
                         outputs={bus: solph.Flow(**outflow_args)})
        )

    # create sources: conventional power plants
    for idx, row in region.geno_conv_grouped.iterrows():
        # get bus
        bus = buses[region.subst.loc[idx[0]]['otg_id']]

        # do we have a timeseries for this geno?
        if idx in region.geno_res_ts.index:
            ts_ds = region.geno_res_ts.loc[idx]
        else:
            logger.error('No timeseries for HV generator {} found! '
                         '(capacity={} MW), skipped'
                         .format(str(idx),
                                 str(row['sum'])))
            continue
        outflow_args = {'nominal_value': row['sum']}

        # calc relative feedin sum from all timeseries
        ts = [1, 1, 1]
        #ts = np.array(list(ts_ds['p_set'])[0] / row['sum'])
        # add ts and fix it for renewables
        outflow_args['actual_value'] = ts
        outflow_args['fixed'] = True

        # create node
        nodes.append(
            solph.Source(label=idx[1] + '_' + str(idx[0]),
                         outputs={bus: solph.Flow(**outflow_args)})
        )


    # create demands (electricity/heat)
    for idx, row in region.demand_el.iterrows():
        bus = buses[region.subst.loc[idx]['otg_id']]
        # calc nominal power
        #p_nom = row.drop(['population'], axis=0).sum()
        p_nom = max(np.array(region.demand_el_ts.loc[idx]['p_set']))
        # calc relative power
        ts = [0.01, 0.01, 0.01]
        #ts = np.array(region.demand_el_ts.loc[idx]['p_set']) / p_nom
        nodes.append(
            solph.Sink(label="demand_el_" + str(idx),
                       inputs={bus: solph.Flow(nominal_value=p_nom,
                                               actual_value=ts,
                                               fixed=True)})
        )

    # add 380/110kV trafos
    for idx, row in region.trafos.iterrows():
        bus0 = buses[row['bus0']]
        bus1 = buses[row['bus1']]
        nodes.append(
            solph.custom.Link(label='trafo'
                                    + '_' + str(row['trafo_id'])
                                    + '_b' + str(row['bus0'])
                                    + '_b' + str(row['bus1']),
                              inputs={bus0: solph.Flow(),
                                      bus1: solph.Flow()},
                              outputs={bus0: solph.Flow(nominal_value=row['s_nom']),
                                       bus1: solph.Flow(nominal_value=row['s_nom'])},
                              conversion_factors={(bus0, bus1): 0.98, (bus1, bus0): 0.98})
        )

    # # add sink and source for import/export
    # nodes.append(
    #     solph.Sink(label='excess_el',
    #                inputs={imex_bus: solph.Flow()})
    # )
    # nodes.append(
    #     solph.Source(label='shortage_el',
    #                  outputs={imex_bus: solph.Flow(variable_costs=200)})
    # )

    # create lines for import and export (buses which are tagged with region_bus == False)
    for idx, row in region.buses[~region.buses['region_bus']].iterrows():
        bus = buses[idx]

        # add sink and source for import/export
        nodes.append(
            solph.Sink(label='excess_el' + '_b' + str(idx),
                       inputs={bus: solph.Flow(variable_costs=-50)})
        )
        nodes.append(
            solph.Source(label='shortage_el' + '_b' + str(idx),
                         outputs={bus: solph.Flow(variable_costs=100)})
        )

        # nodes.append(
        #     solph.custom.Link(label='line'
        #                             + '_b' + str(idx)
        #                             + '_b_el_imex',
        #                       inputs={bus: solph.Flow(),
        #                               imex_bus: solph.Flow()},
        #                       outputs={bus: solph.Flow(nominal_value=10e6,
        #                                                variable_costs=1),
        #                                imex_bus: solph.Flow(nominal_value=10e6,
        #                                                     variable_costs=1)
        #                                },
        #                       conversion_factors={(bus, imex_bus): 0.98,
        #                                           (imex_bus, bus): 0.98})
        # )

    # create regular lines
    for idx, row in region.lines.iterrows():
        bus0 = buses[row['bus0']]
        bus1 = buses[row['bus1']]

        nodes.append(
            solph.custom.Link(label='line'
                                    + '_' + str(row['line_id']),
                                    #+ '_b' + str(row['bus0'])
                                    #+ '_b' + str(row['bus1']),
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

    return nodes


def create_model(cfg, region):
    """Create oemof model using config and data files. An oemof energy system is created,
    nodes are added and parametrized.

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

    logger.info('Create energy system')
    # Create time index
    datetime_index = pd.date_range(start=cfg['date_from'],
                                   end=cfg['date_to'],
                                   freq=cfg['freq'])

    # Set up energy system
    esys = solph.EnergySystem(timeindex=datetime_index)

    # # read nodes data
    # if cfg['load_data_from_file']:
    #     region = Region.load_from_pkl('data.pkl')
    # else:
    #     region = Region.import_data()
    #     region.dump_to_pkl('data.pkl')

    graph = grid_graph(region=region,
                       draw=False)

    nodes = create_nodes(
        region=region,
        datetime_index=datetime_index
    )

    esys.add(*nodes)

    print('The following objects have been created:')
    for n in esys.nodes:
        oobj = str(type(n)).replace("<class 'oemof.solph.", "").replace("'>", "")
        print(oobj + ':', n.label)

    return esys


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
    logger.info('Create optimization problem')
    om = solph.Model(esys)

    # solve it
    logger.info('Solve optimization problem')
    om.solve(solver=solver,
             solve_kwargs={'tee': verbose,
                           'keepfiles': True})

    return om



    # if filename is None:
    #     filename = os.path.join(os.path.dirname(__file__), 'input_data.csv')
    #
    # data = pd.read_csv(filename, sep=",")


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
    nodes = create_nodes2(
        region=region,
        datetime_index=datetime_index
    )

    esys.add(*nodes)

    print('The following objects have been created:')
    for n in esys.nodes:
        oobj = str(type(n)).replace("<class 'oemof.solph.", "").replace("'>", "")
        print(oobj + ':', n.label)

    return esys


def create_nodes2(region=None, datetime_index=None):
    """Create nodes (oemof objects) and lines from region such as buses, links,
    sources and sinks.

    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    datetime_index : :pandas:`pandas.DatetimeIndex`
        Datetime index

    Returns
    -------
    nodes : `obj`:dict of :class:`nodes <oemof.network.Node>`
    """

    if not region:
        msg = 'No region class provided.'
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Creating objects...")

    timesteps = len(datetime_index)

    #########
    # BUSES #
    #########

    # grid buses
    buses = {}
    nodes = []
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
        # get all subst in mun
        mun_subst = region.subst[region.subst.ags == ags]
        # get buses for subst
        mun_buses = region.buses.loc[mun_subst.bus_id]

        # note: ts are distributed equally to all buses of mun
        for bus_id, busdata in mun_buses.iterrows():
            # create generators
            # ToDo: Use normalized ts and cap instead?
            for tech, ts_df in region.feedin_ts.items():
                outflow_args = {
                    'nominal_value': 1,
                    'fixed':  True,
                    'actual_value': list(ts_df[ags] /
                                         len(mun_buses))[:timesteps]
                }

                # create node only if feedin sum is >0
                if ts_df[ags].sum(axis=0) > 0:
                    nodes.append(
                        solph.Source(
                            label='gen_b{bus_id}_{tech}'.format(
                                bus_id=str(bus_id),
                                tech=tech
                            ),
                            outputs={buses[bus_id]: solph.Flow(**outflow_args)})
                    )
            # create el. demands
            # ToDo: Use normalized ts and cap instead?
            for sector, ts_df in region.demand_ts.items():
                # ToDo: include thermal demand
                if sector[:3] == 'el_':
                    inflow_args = {
                        'nominal_value': 1,
                        'fixed':  True,
                        'actual_value': list(ts_df[ags] /
                                             len(mun_buses))[:timesteps]
                    }
                    nodes.append(
                        solph.Sink(label='dem_el_b{bus_id}_{sector}'.format(
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

    return nodes

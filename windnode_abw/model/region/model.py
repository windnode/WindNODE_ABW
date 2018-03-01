import logging
logger = logging.getLogger('windnode_abw')

from windnode_abw.model import Region
from windnode_abw.model.region.tools import grid_graph

import pandas as pd
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

    # add bus for power import and export
    imex_bus = solph.Bus(label='b_el_imex')
    nodes.append(imex_bus)

    # create sources
    for idx, row in region.geno_res_grouped.iterrows():
        bus = buses[region.subst.loc[idx[0]]['otg_id']]
        nodes.append(
            solph.Source(label=idx[1] + '_' + str(idx[0]),
                         outputs={bus: solph.Flow(actual_value=random.rand(len(datetime_index)), #data['wind'],
                                                  nominal_value=row['sum'],
                                                  fixed=True)})
        )

        # nodes.append(
        #     solph.Source(label="pv_" + str(idx),
        #                  outputs={buses[idx]: solph.Flow(actual_value=data['pv'],
        #                                                  nominal_value=10,
        #                                                  fixed=True)})
        # )

    # create demands (electricity/heat)
    for idx, row in region.subst.iterrows():
        bus = buses[region.subst.loc[idx]['otg_id']]
        nodes.append(
            solph.Sink(label="demand_el_" + str(idx),
                       inputs={bus: solph.Flow(nominal_value=10,
                                               actual_value=random.rand(len(datetime_index)), #data['demand_el'],
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

    # add sink and source for import/export
    nodes.append(
        solph.Sink(label='excess_el',
                   inputs={imex_bus: solph.Flow()})
    )
    nodes.append(
        solph.Source(label='shortage_el',
                     outputs={imex_bus: solph.Flow(variable_costs=200)})
    )

    # create lines for import and export (buses which are tagged with region_bus == False)
    for idx, row in region.buses[~region.buses['region_bus']].iterrows():
        bus = buses[idx]
        nodes.append(
            solph.custom.Link(label='line'
                                    + '_b' + str(idx)
                                    + '_b_el_imex',
                              inputs={bus: solph.Flow(),
                                      imex_bus: solph.Flow()},
                              outputs={bus: solph.Flow(nominal_value=1e6),
                                       imex_bus: solph.Flow(nominal_value=1e6)},
                              conversion_factors={(bus, imex_bus): 1.0,
                                                  (imex_bus, bus): 1.0})
        )

    # create regular lines
    for idx, row in region.lines.iterrows():
        bus0 = buses[row['bus0']]
        bus1 = buses[row['bus1']]

        nodes.append(
            solph.custom.Link(label='line'
                                    + '_' + str(row['line_id'])
                                    + '_b' + str(row['bus0'])
                                    + '_b' + str(row['bus1']),
                              inputs={bus0: solph.Flow(),
                                      bus1: solph.Flow()},
                              outputs={bus0: solph.Flow(nominal_value=float(row['s_nom'])),
                                       bus1: solph.Flow(nominal_value=float(row['s_nom']))},
                              conversion_factors={(bus0, bus1): 0.98, (bus1, bus0): 0.98})
        )

    return nodes


def create_model(cfg):
    """Create oemof model using config and data files. An oemof energy system is created,
    nodes are added and parametrized.

    Parameters
    ----------
    cfg : :obj:`dict`
        Config to be used to create model

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

    # read nodes data
    if cfg['load_data_from_file']:
        region = Region.load_from_pkl('data.pkl')
    else:
        region = Region.import_data()
        region.dump_to_pkl('data.pkl')

    graph = grid_graph(region=region,
                       draw=True)

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
    Dict with results
    """

    # Create problem
    logger.info('Create optimization problem')
    om = solph.Model(esys)

    # solve it
    logger.info('Solve optimization problem')
    om.solve(solver=solver,
             solve_kwargs={'tee': verbose,
                           'keepfiles': True})

    return om.results()



    # if filename is None:
    #     filename = os.path.join(os.path.dirname(__file__), 'input_data.csv')
    #
    # data = pd.read_csv(filename, sep=",")

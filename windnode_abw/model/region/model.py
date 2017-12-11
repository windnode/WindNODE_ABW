import logging
logger = logging.getLogger('windnode_abw')

import os
import pandas as pd
import numpy.random as random

import oemof.solph as solph
from oemof import outputlib
from oemof.outputlib.graph_tools import graph
import matplotlib.pyplot as plt


def build_oemof_model(subst_data,
                      transport_data,
                      filename=None,
                      solver='cbc',
                      tee_switch=True,
                      keep=True):

    datetimeindex = pd.date_range('1/1/2012', periods=10, freq='H')

    esys = solph.EnergySystem(timeindex=datetimeindex)

    if filename is None:
        filename = os.path.join(os.path.dirname(__file__), 'input_data.csv')

    data = pd.read_csv(filename, sep=",")

    ### CREATE OBJECTS ###
    logging.info("Creating objects")

    # create buses, sources and sinks
    buses = {}
    nodes = []
    for idx, row in subst_data.iterrows():
        bus = solph.Bus(label="b_el_" + str(idx))
        buses[idx] = bus
        nodes.append(bus)

        # Sources
        nodes.append(
            solph.Source(label="wind_" + str(idx),
                         outputs={buses[idx]: solph.Flow(actual_value=random.rand(len(datetimeindex)), #data['wind'],
                                                         nominal_value=10,
                                                         fixed=True)})
        )

        nodes.append(
            solph.Source(label="pv_" + str(idx),
                         outputs={buses[idx]: solph.Flow(actual_value=data['pv'],
                                                         nominal_value=10,
                                                         fixed=True)})
        )

        # Demands (electricity/heat)
        nodes.append(
            solph.Sink(label="demand_el_" + str(idx),
                       inputs={buses[idx]: solph.Flow(nominal_value=1,
                                                      actual_value=data['demand_el'],
                                                      fixed=True)})
        )

    slack_bus = buses[2431]

    # adding an excess variable can help to avoid infeasible problems
    nodes.append(
        solph.Sink(label="excess", inputs={slack_bus: solph.Flow()})
    )
    nodes.append(
        solph.Source(label="shortage", outputs={slack_bus: solph.Flow(variable_costs=200)})
    )

    # create lines
    for idx, row in transport_data.iterrows():
        bus0 = buses[row['hvmv_subst_id0']]
        bus1 = buses[row['hvmv_subst_id1']]
        nodes.append(
            solph.Transformer(label='line_'
                                    + '_b' + str(row['hvmv_subst_id0'])
                                    + '_b' + str(row['hvmv_subst_id1']),
                              inputs={bus0: solph.Flow()},
                              outputs={bus1: solph.Flow(nominal_value=row['capacity'])},
                              conversion_factors={bus1: 0.98})
        )
        nodes.append(
            solph.Transformer(label='line_'
                                    + '_b' + str(row['hvmv_subst_id1'])
                                    + '_b' + str(row['hvmv_subst_id0']),
                              inputs={bus1: solph.Flow()},
                              outputs={bus0: solph.Flow(nominal_value=row['capacity'])},
                              conversion_factors={bus0: 0.98})
        )

    esys.add(*nodes)

    graph(energy_system=esys,
          node_size=100)

    ### OPTIMIZATION ###
    # create Optimization model based on energy_system
    logging.info("Create optimization problem")
    om = solph.Model(es=esys)

    # solve with specific optimization options (passed to pyomo)
    logging.info("Solve optimization problem")
    om.solve(solver=solver,
             solve_kwargs={'tee': tee_switch, 'keepfiles': keep})

    # write back results from optimization object to energysystem
    results = om.results()

    # PLOT #
    logging.info("Plot results")

    slack_bus_results = outputlib.views.node(results, 'b_el_2431')
    slack_bus_results['sequences'].plot(kind='line', drawstyle='steps-post')
    plt.show()
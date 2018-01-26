import logging
logger = logging.getLogger('windnode_abw')

import os
import pandas as pd
import numpy.random as random

import oemof.solph as solph
from oemof.outputlib import views
from oemof.graph import create_nx_graph
import matplotlib.pyplot as plt

from windnode_abw.tools.draw import draw_graph


def build_oemof_model(subst_data,
                      transport_data,
                      filename=None,
                      solver='cbc',
                      tee_switch=True,
                      keep=True):

    datetimeindex = pd.date_range(start='2016-01-01 00:00:00',
                                  end='2016-01-02 00:00:00',
                                  freq='H')

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

    slack_bus = buses[2433]

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
            solph.Transformer(label='line'
                                    + '_b' + str(row['hvmv_subst_id0'])
                                    + '_b' + str(row['hvmv_subst_id1']),
                              inputs={bus0: solph.Flow()},
                              outputs={bus1: solph.Flow(nominal_value=row['capacity'])},
                              conversion_factors={bus1: 0.98})
        )
        nodes.append(
            solph.Transformer(label='line'
                                    + '_b' + str(row['hvmv_subst_id1'])
                                    + '_b' + str(row['hvmv_subst_id0']),
                              inputs={bus1: solph.Flow()},
                              outputs={bus0: solph.Flow(nominal_value=row['capacity'])},
                              conversion_factors={bus0: 0.98})
        )

    esys.add(*nodes)

    graph = create_nx_graph(esys)
    draw_graph(grph=graph, plot=True, layout='neato', node_size=100, font_size=8,
               node_color={
                   'bus_el': '#cd3333',
                   'bus_gas': '#7EC0EE',
                   'bus_th': '#eeac7e'})

    ### OPTIMIZATION ###
    # create Optimization model based on energy_system
    logging.info("Create optimization problem")
    om = solph.Model(esys)

    # solve with specific optimization options (passed to pyomo)
    logging.info("Solve optimization problem")
    om.solve(solver=solver,
             solve_kwargs={'tee': tee_switch, 'keepfiles': keep})

    # write back results from optimization object to energysystem
    results = om.results()

    # PLOT #
    logging.info("Plot results")

    slack_bus_results = views.node(results, 'b_el_2433')
    slack_bus_results_flows = slack_bus_results['sequences']

    # print some sums for slack bus
    print(slack_bus_results_flows.sum())
    print(slack_bus_results_flows.info())

    ax = slack_bus_results_flows.plot(kind='bar', stacked=True, linewidth=0, width=1)
    ax.set_title('Sums for optimization period')
    ax.legend(loc='upper right', bbox_to_anchor=(1, 1))
    ax.set_xlabel('Energy (MWh)')
    ax.set_ylabel('Flow')
    plt.tight_layout()

    dates = slack_bus_results_flows.index
    tick_distance = int(len(dates) / 7) - 1
    ax.set_xticks(range(0, len(dates), tick_distance), minor=False)
    ax.set_xticklabels(
        [item.strftime('%d-%m-%Y') for item in dates.tolist()[0::tick_distance]],
        rotation=90, minor=False)
    plt.show()
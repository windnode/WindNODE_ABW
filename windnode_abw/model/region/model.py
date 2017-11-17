import os
import logging
import pandas as pd

from oemof.solph import EnergySystem, Bus, Sink, Flow, Source, OperationalModel
import oemof.outputlib as output
import matplotlib.pyplot as plt


def build_oemof_model(buses,
                      lines,
                      filename=None,
                      solver='cbc',
                      tee_switch=True,
                      keep=True):

    datetimeindex = pd.date_range('1/1/2012', periods=2000, freq='H')

    energysystem = EnergySystem(timeindex=datetimeindex)

    if filename is None:
        filename = os.path.join(os.path.dirname(__file__), 'input_data.csv')

    data = pd.read_csv(filename, sep=",")

    ### CREATE OBJECTS ###
    logging.info("Creating objects")

    # electricity and heat
    b_el = Bus(label="b_el")

    # adding an excess variable can help to avoid infeasible problems
    Sink(label="excess", inputs={b_el: Flow()})
    Source(label="shortage", outputs={b_el: Flow(variable_costs=200)})

    # Sources
    Source(label="wind",
           outputs={b_el: Flow(actual_value=data['wind'],
                               nominal_value=66.3,
                               fixed=True)})

    Source(label="pv",
           outputs={b_el: Flow(actual_value=data['pv'],
                               nominal_value=65.3,
                               fixed=True)})

    # Demands (electricity/heat)
    Sink(label="demand_el",
         inputs={b_el: Flow(nominal_value=85,
                            actual_value=data['demand_el'],
                            fixed=True)})

    ### OPTIMIZATION ###
    # create Optimization model based on energy_system
    logging.info("Create optimization problem")
    om = OperationalModel(es=energysystem)

    # solve with specific optimization options (passed to pyomo)
    logging.info("Solve optimization problem")
    om.solve(solver=solver,
             solve_kwargs={'tee': tee_switch, 'keepfiles': keep})

    # write back results from optimization object to energysystem
    om.results()

    # PLOT #
    logging.info("Plot results")
    # define colors
    cdict = {'wind': '#00bfff', 'pv': '#ffd700', 'demand_el': '#fff8dc'}

    # create multiindex dataframe with result values
    esplot = output.DataFramePlot(energy_system=energysystem)

    # select input results of electrical bus (i.e. power delivered by plants)
    esplot.slice_unstacked(bus_label="b_el", type="to_bus",
                           date_from='2012-01-01 00:00:00',
                           date_to='2012-01-07 00:00:00')

    # set colorlist for esplot
    colorlist = esplot.color_from_dict(cdict)

    esplot.plot(color=colorlist, title="January 2016", stacked=True, width=1,
                lw=0.1, kind='bar')
    esplot.ax.set_ylabel('Power in MW')
    esplot.ax.set_xlabel('Date')
    esplot.set_datetime_ticks(tick_distance=24, date_format='%d-%m')
    esplot.outside_legend(reverse=True)
    plt.show()
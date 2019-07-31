# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

from windnode_abw.model import Region
from windnode_abw.model.region.model import simulate, create_oemof_model
from windnode_abw.model.region.tools import calc_line_loading
from windnode_abw.model.region.tools import grid_graph

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.draw import draw_graph

# import oemof modules
import oemof.solph as solph
import oemof.outputlib as outputlib
from oemof.outputlib import views
from oemof.graph import create_nx_graph

import os
import matplotlib.pyplot as plt


def run_scenario(cfg):
    """Run scenario

    Parameters
    ----------
    cfg : :obj:`dict`
        Config to be used to create model

    Returns
    -------
    oemof.solph.EnergySystem
        Energy system including results
    :class:`~.model.Region`
    """

    # define paths
    path = os.path.join(config.get_data_root_dir(),
                        config.get('user_dirs',
                                   'results_dir')
                        )
    file_esys = os.path.splitext(
        os.path.basename(__file__))[0] + '_esys.oemof'
    file_region = os.path.splitext(
        os.path.basename(__file__))[0] + '_region.oemof'

    # load esys from file
    if cfg['load_esys']:
        # load esys
        esys = solph.EnergySystem()
        esys.restore(dpath=path,
                     filename=file_esys)
        logger.info('The energy system was loaded from {}.'
                    .format(path + '/' + file_esys))

        # load region
        region = Region.load_from_pkl(filename=file_region)

        return esys, region

    region = Region.import_data()
    region.prepare_timeseries()

    esys = create_oemof_model(cfg=cfg,
                              region=region)

    # plot grid (not oemof model)
    graph = grid_graph(region=region,
                       draw=True)

    om = simulate(esys=esys,
                  solver=cfg['solver'])

    # dump esys to file
    if cfg['dump_esys']:
        # add results to the energy system to make it possible to store them.
        esys.results['main'] = outputlib.processing.results(om)
        esys.results['meta'] = outputlib.processing.meta_results(om)
        # add om flows to allow access to Flow objects
        esys.results['om_flows'] = list(om.flows.items())

        # dump esys
        esys.dump(dpath=path,
                  filename=file_esys)
        logger.info('The energy system was dumped to {}.'
                    .format(path + '/' + file_esys))

        # dump region
        region.dump_to_pkl(filename=file_region)

    return esys, region


def plot_results(esys, region):
    """Plots results of simulation

    Parameters
    ----------
    esys : oemof.solph.EnergySystem
        Energy system including results
    region : :class:`~.model.Region`
        Region object
    """

    logger.info('Plot results')

    results = esys.results['main']
    om_flows = esys.results['om_flows']

    # create and plot graph of energy system
    graph = create_nx_graph(esys)
    draw_graph(grph=graph, plot=True, layout='neato', node_size=100, font_size=8,
               node_color={
                   'bus_el': '#cd3333',
                   'bus_gas': '#7EC0EE',
                   'bus_th': '#eeac7e'})

    imex_bus_results = views.node(results, 'b_el_27144')
    imex_bus_results_flows = imex_bus_results['sequences']

    # print some sums for import/export bus
    print(imex_bus_results_flows.sum())
    print(imex_bus_results_flows.info())

    # some example plots for bus_el
    ax = imex_bus_results_flows.sum(axis=0).plot(kind='barh')
    ax.set_title('Sums for optimization period')
    ax.set_xlabel('Energy (MWh)')
    ax.set_ylabel('Flow')
    plt.tight_layout()
    plt.show()

    imex_bus_results_flows.plot(kind='line', drawstyle='steps-post')
    plt.show()

    ax = imex_bus_results_flows.plot(kind='bar', stacked=True, linewidth=0, width=1)
    ax.set_title('Sums for optimization period')
    ax.legend(loc='upper right', bbox_to_anchor=(1, 1))
    ax.set_xlabel('Energy (MWh)')
    ax.set_ylabel('Flow')
    plt.tight_layout()

    dates = imex_bus_results_flows.index
    tick_distance = int(len(dates) / 7) - 1
    ax.set_xticks(range(0, len(dates), tick_distance), minor=False)
    ax.set_xticklabels(
        [item.strftime('%d-%m-%Y') for item in dates.tolist()[0::tick_distance]],
        rotation=90, minor=False)
    plt.show()


if __name__ == "__main__":

    # configuration
    cfg = {
        'data_path': os.path.join(os.path.dirname(__file__), 'data'),
        'date_from': '2015-01-01 00:00:00',
        'date_to': '2015-01-01 02:00:00',
        'freq': '60min',
        'results_path': os.path.join(config.get_data_root_dir(),
                                     config.get('user_dirs',
                                                'results_dir')),
        'solver': 'cbc',
        'verbose': True,
        'dump_esys': True,
        'load_esys': False
    }

    esys, region = run_scenario(cfg=cfg)

    calc_line_loading(esys=esys,
                      region=region)

    plot_results(esys=esys,
                 region=region)

    logger.info('Done!')

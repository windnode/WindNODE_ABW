# define and setup logger
from windnode_abw.tools.logger import setup_logger, log_memory_usage
logger = setup_logger()

import os

from windnode_abw.model import Region
from windnode_abw.model.region.model import simulate, create_oemof_model
from windnode_abw.model.region.tools import calc_line_loading
from windnode_abw.model.region.tools import grid_graph
from windnode_abw.analysis.tools import results_to_dataframes

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.draw import draw_graph, set_node_colors, plot_results
from windnode_abw.tools.data_io import load_scenario_cfg, export_results

# import oemof modules
import oemof.solph as solph
import oemof.outputlib as outputlib
from oemof.graph import create_nx_graph


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
        logger.info(f'The energy system was loaded from {path}/{file_esys}.')

        # load region
        region = Region.load_from_pkl(filename=file_region)

        return esys, region

    log_memory_usage()
    region = Region.import_data(cfg)

    # Vergleich el load IÖW+SLP
    # import pandas as pd
    # x = pd.concat([region.dsm_ts['Lastprofil'][15001000].rename(columns={15001000: 'IÖW'}),
    #                region.demand_ts['el_hh'][15001000].rename(columns={15001000: 'SLP'})],
    #               axis=1)
    # x.plot()

    log_memory_usage()
    esys = create_oemof_model(cfg=cfg,
                              region=region)

    # create and plot graph of energy system
    graph = create_nx_graph(esys)
    draw_graph(grph=graph, plot=True, layout='neato', node_size=100, font_size=8,
               node_color=set_node_colors(graph))
    #
    # # plot grid (not oemof model)
    # graph = grid_graph(region=region,
    #                    draw=True)

    om = simulate(esys=esys,
                  solver=cfg['solver'])

    log_memory_usage()
    logger.info('Processing results...')
    # add results to energy system
    esys.results['main'] = outputlib.processing.results(om)
    # add meta infos
    esys.results['meta'] = outputlib.processing.meta_results(om)
    # add initial params to energy system
    esys.results['params'] = outputlib.processing.parameter_as_dict(esys)
    # add om flows to allow access Flow objects
    #esys.results['om_flows'] = list(om.flows.items())

    log_memory_usage()

    results = results_to_dataframes(esys)
    logger.info('Dumping results...')

    # dump esys to file
    if cfg['dump_esys']:
        # dump esys
        esys.dump(dpath=path,
                  filename=file_esys)
        logger.info(f'The energy system was dumped to {path}/{file_esys}.')

        # dump region
        region.dump_to_pkl(filename=file_region)

    if cfg['dump_results']:
        export_results(results=results,
                       meta=esys.results['meta'],
                       scenario_id=region.cfg['scn_data']['general']['id'])

    return esys, region


if __name__ == "__main__":

    # configuration
    cfg = {
        'scenario': 'status_quo',
        'data_path': os.path.join(os.path.dirname(__file__), 'data'),
        'date_from': '2015-01-01 00:00:00',
        'date_to': '2015-01-04 23:00:00',
        'freq': '60min',
        'results_path': os.path.join(config.get_data_root_dir(),
                                     config.get('user_dirs',
                                                'results_dir')),
        'solver': 'gurobi',
        'verbose': True,
        'dump_esys': False,
        'load_esys': False,
        'dump_results': True
    }

    cfg['scn_data'] = load_scenario_cfg(cfg['scenario'])

    esys, region = run_scenario(cfg=cfg)

    # calc_line_loading(esys=esys,
    #                   region=region)

    plot_results(esys=esys,
                 region=region)

    logger.info('Done!')

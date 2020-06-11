# define and setup logger
from windnode_abw.tools.logger import setup_logger, log_memory_usage
logger = setup_logger()

import os
import argparse
import time
import multiprocessing

from windnode_abw import __path__ as wn_path
from windnode_abw.model import Region
from windnode_abw.model.region.model import simulate, create_oemof_model
from windnode_abw.model.region.tools import calc_line_loading
from windnode_abw.model.region.tools import grid_graph
from windnode_abw.analysis.tools import results_to_dataframes

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.draw import draw_graph, set_node_colors, debug_plot_results
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

    cfg['scn_data'] = load_scenario_cfg(cfg['scenario'])

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
    esys, om = create_oemof_model(region=region,
                                  cfg=cfg,
                                  save_lp=cfg['save_lp'])

    # # create and plot graph of energy system
    # graph = create_nx_graph(esys)
    # # entire system
    # draw_graph(grph=graph, plot=True, layout='neato',
    #            node_size=100, font_size=10,
    #            node_color=set_node_colors(graph))
    # # single municipality only
    # draw_graph(grph=graph, mun_ags=15001000, plot=True, layout='neato',
    #            node_size=100, font_size=10,
    #            node_color=set_node_colors(graph))

    # # plot grid (not oemof model)
    # graph = grid_graph(region=region,
    #                    draw=True)

    om = simulate(om=om,
                  solver=cfg['solver'],
                  verbose=cfg['verbose'])

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
                       cfg=cfg,
                       solver_meta=esys.results['meta'])

    logger.info(f'===== Scenario {scn_id} done! =====')

    return esys, region


if __name__ == "__main__":
    # get list of available scenarios
    avail_scenarios = [file.split('.')[0]
                       for file in os.listdir(os.path.join(wn_path[0],
                                                           'scenarios'))
                       if file.endswith(".scn")]
    avail_scenarios_str = ''.join(
        [(s+',\n  ' if (n%5 == 0 and n > 0) else s+', ')
         for n, s in enumerate(avail_scenarios)])

    parser = argparse.ArgumentParser(
        description='WindNODE ABW energy system.',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('scn', metavar='SCENARIO', type=str, nargs='*',
                        default=['dev/future'],
                        help='ID of scenario to be run, e.g. \'ISE2050\'. '
                             'You may pass multiple, e.g. \'dev/sq ISE2050\'. '
                             'Use \'all\' for all scenarios. '
                             'If nothing is provided, it defaults to scenario '
                             'dev/future.\n\n'
                             f'Available scenarios:\n  {avail_scenarios_str}')
    parser.add_argument('--mp', metavar='NUMBER', type=int, nargs='?',
                        dest='proc_count', default=1,
                        help='Number of processes to be used by '
                             'multiprocessing. If values is 1 or not '
                             'provided, program is executed without MP. '
                             'If value exceeds number of scenarios, number of '
                             'scenarios is used.')
    args = parser.parse_args()

    # check if sufficient CPU cores
    if args.proc_count > multiprocessing.cpu_count():
        msg = 'Number of processes exceeds number of installed CPU cores.'
        logger.error(msg)
        raise ValueError(msg)

    # create scenario list
    if args.scn == ['all']:
        scenarios = avail_scenarios
    else:
        scenarios = args.scn

    # check if MP process count exceeds scenario count
    if args.proc_count > len(scenarios):
        logger.info('Number of processes exceeds number of scenarios. '
                    'I will use the number of scenarios '
                    f'({len(scenarios)}) as process count.')
        args.proc_count = len(scenarios)

    logger.info(f'Running scenarios: {str(scenarios)} in {args.proc_count} '
                f'processes.')
    run_timestamp = time.strftime('%Y-%m-%d_%H%M%S')
    logger.info(f'Run timestamp: {run_timestamp}')

    # configuration for all calculated scenarios
    cfg = {
        # note: dev scenarios have been moved to dev/,
        # use them 'scenario': 'dev/future'
        'run_timestamp': run_timestamp,
        'date_from': '2015-01-01 00:00:00',
        'date_to': '2015-12-31 23:00:00',
        'freq': '60min',
        'solver': 'gurobi',
        'verbose': True,
        'save_lp': False,
        'dump_esys': False,
        'load_esys': False,
        'dump_results': True
    }

    # use MP
    if args.proc_count > 1:
        pool = multiprocessing.Pool(args.proc_count)
        cfgs = [dict(**c, **{'scenario': s})
                for c, s in zip([cfg] * len(scenarios), scenarios)]
        pool.map(run_scenario, cfgs)

    # do not use MP
    else:
        for scn_id in scenarios:
            cfg['scenario'] = scn_id
            esys, region = run_scenario(cfg=cfg)

            # debug_plot_results(esys=esys,
            #                    region=region)

    logger.info('===== All done! =====')

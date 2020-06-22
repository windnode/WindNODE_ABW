# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

import os

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')
from windnode_abw.tools.data_io import load_results
from windnode_abw.analysis.tools import aggregate_flows, aggregate_parameters, flows_timexagsxtech, \
    results_agsxlevelxtech, highlevel_results, results_tech
from windnode_abw.model import Region
from windnode_abw.tools.draw import sample_plots


if __name__ == "__main__":
    # TODO: Nice-to-have: argparse

    # specify what to import (in path ~/.windnode_abw/)
    run_timestamp = '2020-06-17_125728_1month'

    # select multiple scenarios manually or use ['ALL'] to analyze all
    # scenarios found in directory
    #scenarios = ['future', 'sq']
    scenarios = ['ALL']

    # read available scenarios if 'ALL' requested
    if scenarios == ['ALL']:
        scenarios = [
            file.split('.')[0]
            for file in os.listdir(os.path.join(
                config.get_data_root_dir(),
                config.get('user_dirs',
                           'results_dir'),
                run_timestamp
            ))]

    logger.info(f'Analyzing {len(scenarios)} scenarios...')

    results_scns = {}
    timerange = None

    for scn_id in scenarios:
        logger.info(f'Analyzing scenario: {scn_id}...')

        # load raw results
        results_raw = load_results(timestamp=run_timestamp,
                                   scenario=scn_id)

        if results_raw is None:
            logger.warning(f'Scenario {scn_id} not found, skipping...')
        else:
            results_scns[scn_id] = {}
            # import region using cfg from results meta
            cfg = results_raw['meta']['config']

            # extract timerange and check consistency across multiple scenarios
            if timerange is None:
                timerange = [cfg.get('date_from'), cfg.get('date_to')]
            else:
                if timerange != [cfg.get('date_from'), cfg.get('date_to')]:
                    msg = 'Simulation timeranges of different scenarios do ' \
                          'not match!'
                    logger.error(msg)
                    raise ValueError(msg)

            region = Region.import_data(cfg)

            # Aggregate flow results along different dimensions (outdated, see #29)
            #results = aggregate_flows(results_raw)

            # Retrieve parameters from database and config file
            parameters = aggregate_parameters(region, results_raw)
            results_scns[scn_id]['parameters'] = parameters

            # Flows extracted to dimension time, ags code, technology (and sometimes more dimensions)
            flows_txaxt = flows_timexagsxtech(results_raw["flows"], region)
            results_scns[scn_id]['flows_txaxt'] = flows_txaxt

            # Aggregation of results to region level (dimensions: ags code (region) x technology)
            results_axlxt = results_agsxlevelxtech(flows_txaxt, parameters, region)
            results_scns[scn_id]['results_axlxt'] = results_axlxt

            # Further aggregation and post-analysis calculations
            results_t = results_tech(results_axlxt)
            results_scns[scn_id]['results_t'] = results_t

            # Aggregation to scalar result values
            highlevel_results = highlevel_results(results_axlxt, results_t, flows_txaxt)
            results_scns[scn_id]['highlevel_results'] = highlevel_results

            # sample_plots(region=region,
            #              results=results)

    logger.info('===== All done! =====')

    # DO STUFF WITH RESULTS (dict results_scns) HERE

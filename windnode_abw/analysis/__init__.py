import os
import pandas as pd

import logging
logger = logging.getLogger('windnode_abw')

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.data_io import load_results, export_processed_results,\
    load_processed_results
from windnode_abw.model import Region

from windnode_abw.analysis.tools import aggregate_flows, aggregate_parameters,\
    flows_timexagsxtech, results_agsxlevelxtech, create_highlevel_results,\
    results_tech, additional_results_txaxt


def analysis(run_timestamp, scenarios='ALL',
             force_new_results=False, dump_results=True):
    """Start analysis for single or multiple scenarios

    If pickle of processed results is available, it is loaded except
    `force_new_results` is True.

    Parameters
    ----------
    run_timestamp : :obj:`str`
        Timestamp of run, e.g. '2020-06-17_125728_1month' (folder in
        ~/.windnode_abw/results/ the scenarios are imported from.
    scenarios : (:obj:`str`) OR (:obj:`list` of :obj:`str`)
        Scenarios - select single or multiple scenarios manually (e.g.
        'sq' or ['future', 'sq']) or use 'ALL' to analyze all scenarios
        found in directory. Default: 'ALL'
    dump_results : :obj:`bool`
        Dump results of analysis to folder
        ~/.windnode_abw/results/<run_timestamp>/<scenario>/processed/
        Only triggered when analysis was performed (results not loaded).
        Default: True
    force_new_results : :obj:`bool`
        Process results even if pickled results are available.
        Default: False

    Returns
    -------
    :obj:`dict` of :obj:`dict` of :pandas:`pandas.DataFrame`
        Dict with scenario names. Each entry holds a dict with a DataFrame
        with converted columns.
    """
    if isinstance(scenarios, str):
        scenarios = [scenarios]

    # read available scenarios if 'ALL' requested
    if scenarios == ['ALL']:
        scenarios = [
            file.split('.')[0]
            for file in os.listdir(os.path.join(
                config.get_data_root_dir(),
                config.get('user_dirs',
                           'results_dir'),
                run_timestamp
            )) if not file.startswith('.')
        ]

    logger.info(f'Analyzing {len(scenarios)} scenarios...')

    results_scns = {}
    regions_scns = {}
    
    timerange = None

    for scn_id in scenarios:
        # check for processed results
        loaded_results = None
        if not force_new_results:
            loaded_region, loaded_results = load_processed_results(
                run_id=run_timestamp,
                scn_id=scn_id
            )

        if loaded_results is None:
            logger.info(f'-> Analyzing scenario: {scn_id}...')
            # load raw results
            results_raw = load_results(timestamp=run_timestamp,
                                       scenario=scn_id)

            if results_raw is None:
                logger.warning(f'Scenario {scn_id} not found or file(s) malformed, skipping...')
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

                regions_scns[scn_id] = Region.import_data(cfg)
                results_scns[scn_id]['results_raw'] = results_raw

                logger.info(f'Analyzing...')

                # Flows extracted to dimension time, ags code, technology (and sometimes more dimensions)
                flows_txaxt = flows_timexagsxtech(results_raw["flows"], regions_scns[scn_id])
                results_scns[scn_id]['flows_txaxt'] = flows_txaxt

                # Retrieve parameters from database and config file
                parameters = aggregate_parameters(regions_scns[scn_id], results_raw, flows_txaxt)
                results_scns[scn_id]['parameters'] = parameters

                # Add more parameters derived from flows + parameters
                results_scns[scn_id]['flows_txaxt'] = additional_results_txaxt(results_scns[scn_id]['flows_txaxt'],
                    results_scns[scn_id]['parameters'])

                # Aggregate flow results along different dimensions (outdated, see #29)
                # only used to access DSM demand increase/decrease
                aggregated_results = aggregate_flows(results_raw)
                results_scns[scn_id]['flows_txaxt']["DSM activation"] = pd.concat(
                    [aggregated_results['Lasterhöhung DSM Haushalte nach Gemeinde'].stack().rename("Demand increase"),
                     aggregated_results['Lastreduktion DSM Haushalte nach Gemeinde'].stack().rename(
                         "Demand decrease")], axis=1)
                results_scns[scn_id]['flows_txaxt']["DSM activation"].index = results_scns[scn_id]['flows_txaxt']["DSM activation"].index.set_names(["timestamp", "ags"])

                # Aggregation of results to region level (dimensions: ags code (region) x technology)
                results_axlxt = results_agsxlevelxtech(flows_txaxt, parameters, regions_scns[scn_id])
                results_scns[scn_id]['results_axlxt'] = results_axlxt

                # Further aggregation and post-analysis calculations
                results_t = results_tech(results_axlxt)
                results_scns[scn_id]['results_t'] = results_t

                # Aggregation to scalar result values
                highlevel_results = create_highlevel_results(results_axlxt, results_t, flows_txaxt, regions_scns[scn_id])
                results_scns[scn_id]['highlevel_results'] = highlevel_results

                # Export results of analysis
                if dump_results:
                    export_processed_results(run_id=run_timestamp,
                                             scn_id=scn_id,
                                             results=results_scns[scn_id],
                                             region=regions_scns[scn_id])
        else:
            regions_scns[scn_id] = loaded_region
            results_scns[scn_id] = loaded_results

    return regions_scns, results_scns

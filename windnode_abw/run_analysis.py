# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

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
    # specify what to import (in path ~/.windnode_abw/)
    timestamp = '200604_144728'
    scenario = 'NEP'

    # load raw results
    results_raw = load_results(timestamp=timestamp,
                               scenario=scenario)

    # import region using cfg from results meta
    cfg = results_raw['meta']['config']
    region = Region.import_data(cfg)

    # Aggregate flow results along different dimensions (outdated, see #29)
    results = aggregate_flows(results_raw)

    # Retrieve parameters from database and config file
    parameters = aggregate_parameters(region, results_raw)

    # Flows extracted to dimension time, ags code, technology (and sometimes more dimensions)
    flows_timexagsxtech = flows_timexagsxtech(results_raw["flows"], region)

    # Aggregation of results to region level (dimensions: ags code (region) x technology)
    results_axlxt = results_agsxlevelxtech(flows_timexagsxtech, parameters, region)

    # Further aggregation and post-analysis calculations
    results_t = results_tech(results_axlxt)

    # Aggregation to scalar result values
    highlevel_results = highlevel_results(results_axlxt, results_t, flows_timexagsxtech)

    sample_plots(region=region,
                 results=results)


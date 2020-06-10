# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.data_io import load_results
from windnode_abw.analysis.tools import aggregate_flows
from windnode_abw.model import Region
from windnode_abw.tools.draw import sample_plots


if __name__ == "__main__":
    # specify what to import (in path ~/.windnode_abw/)
    timestamp = '200528_141225'
    scenario = 'future'

    # load raw results
    results_raw = load_results(timestamp=timestamp,
                               scenario=scenario)

    # import region using cfg from results meta
    cfg = results_raw['meta']['config']
    region = Region.import_data(cfg)

    # do stuff!
    results = aggregate_flows(results_raw)

    sample_plots(region=region,
                 results=results)


# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

import os

from windnode_abw.tools.data_io import load_results
from windnode_abw.analysis.tools import aggregate_flows


if __name__ == "__main__":
    timestamp = '200320_110701'
    scenario = 'sq'

    results_raw = load_results(timestamp=timestamp,
                               scenario=scenario)

    aggregate_flows(results_raw)

# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

import os

from windnode_abw.tools.data_io import load_results
from windnode_abw.analysis.tools import aggregate_flows
from windnode_abw.model import Region
from windnode_abw.tools.data_io import load_scenario_cfg
from windnode_abw.tools.draw import sample_plots


if __name__ == "__main__":
    timestamp = '200324_223510'
    scenario = 'sq'

    results_raw = load_results(timestamp=timestamp,
                               scenario=scenario)

    results = aggregate_flows(results_raw)

    # configuration
    cfg = {
        'scenario': 'status_quo',
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

    region = Region.import_data(cfg)

    sample_plots(region=region,
                 results=results)


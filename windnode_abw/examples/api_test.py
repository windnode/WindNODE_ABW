import logging
logging.basicConfig(filename='example.log',
                    format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)
logger = logging.getLogger('windnode_abw')
logger.setLevel(logging.DEBUG)

from windnode_abw.tools import config
config.load_config('config_data.cfg')

from windnode_abw.tools.data import oep_get_data

# ==========================================


data = oep_get_data(schema='grid',
                    table='ego_dp_mv_griddistrict',
                    columns=['subst_id', 'zensus_sum'],
                    conditions=['subst_id<=5', 'version=v0.3.0pre1'],
                    order='zensus_sum')

print(data)
import logging
logging.basicConfig(filename='example.log',
                    format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)
logger = logging.getLogger('windnode_abw')
logger.setLevel(logging.DEBUG)

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.data import oep_get_data
from windnode_abw.model.region.model import build_oemof_model

# OEMOF
# 1. Landkreise
# 2. EHV/HV Busse+Branches
# 3. EE (OEP, PTH-Studie)
# 4. Kosten
# 5. Weitere Parameter

# DINGO/EDISGO
# 1. HV/MV substations
# 2. Dingo-Grids
# 3.

# get Kreise
# krs = oep_get_data(schema='model_draft',
#                    table='wn_abw_bkg_vg250_4_krs',
#                    columns=['id', 'geom'],
#                    conditions=[])
#
# get HV grid
buses = oep_get_data(schema='model_draft',
                     table='wn_abw_ego_pf_hv_bus',
                     columns=['bus_id'])
lines = oep_get_data(schema='model_draft',
                     table='wn_abw_ego_pf_hv_line',
                     columns=['line_id', 'bus0', 'bus1', 's_nom'])

# # get grid districts
# districts = oep_get_data(schema='model_draft',
#                          table='wn_abw_ego_dp_mv_griddistrict',
#                          columns=['subst_id', 'geom'])

# determine exchange capacities between districts

build_oemof_model(bus_data=buses,
                  line_data=lines)
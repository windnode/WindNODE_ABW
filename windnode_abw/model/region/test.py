# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.data import oep_get_data, oep_write_data
from windnode_abw.tools.geo import convert_df_wkb_to_shapely, convert_df_shapely_to_wkb
from windnode_abw.model.region.model import build_oemof_model
from windnode_abw.model.region.tools import reduce_to_regions, draw_region_graph

import pandas as pd
from shapely.geometry import LineString

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

# # get Kreise
# krs = oep_get_data(schema='model_draft',
#                    table='wn_abw_bkg_vg250_4_krs',
#                    columns=['id', 'geom'])

# get HV grid
buses = oep_get_data(schema='model_draft',
                     table='wn_abw_ego_pf_hv_bus',
                     columns=['bus_id', 'hvmv_subst_id'])

lines = oep_get_data(schema='model_draft',
                     table='wn_abw_ego_pf_hv_line',
                     columns=['line_id', 'bus0', 'bus1', 's_nom'])

# get grid districts
substations = oep_get_data(schema='model_draft',
                           table='wn_abw_ego_dp_hvmv_substation',
                           columns=['subst_id', 'geom'])
substations = convert_df_wkb_to_shapely(df=substations,
                                        cols=['geom'])
substations.set_index('subst_id', inplace=True)

# determine exchange capacities between districts
transport_data = reduce_to_regions(bus_data=buses,
                                   line_data=lines)

# prepare transport data for writig to OEP
# join HV-MV substation ids drom buses on lines
geoms = pd.concat([transport_data.join(substations,
                                       on='hvmv_subst_id0')['geom'].rename('geom0'),
                   transport_data.join(substations,
                                       on='hvmv_subst_id1')['geom'].rename('geom1')],
                  axis=1)
def to_linestring(df):
    return LineString([df['geom0'], df['geom1']])
transport_data.loc[:,'geom'] = geoms.apply(to_linestring, axis=1)


oep_write_data(schema='model_draft',
               table='wn_abw_region_transport',
               data=convert_df_shapely_to_wkb(df=transport_data,
                                              cols=['geom']))

draw_region_graph(subst_data=substations,
                  line_data=transport_data)

build_oemof_model(bus_data=buses,
                  line_data=lines)
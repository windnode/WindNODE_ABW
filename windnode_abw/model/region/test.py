# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.tools.data import oep_api_get_data, oep_api_write_data
from windnode_abw.tools.geo import convert_df_wkb_to_shapely, convert_df_shapely_to_wkb
from windnode_abw.model.region.model import build_oemof_model
from windnode_abw.model.region.tools import reduce_to_regions, region_graph, grid_graph

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
# krs = oep_api_get_data(schema='model_draft',
#                    table='wn_abw_bkg_vg250_4_krs',
#                    columns=['id', 'geom'])

# get HV grid
buses = oep_api_get_data(schema='model_draft',
                         table='wn_abw_ego_pf_hv_bus',
                         columns=['bus_id', 'hvmv_subst_id', 'region_bus', 'geom'])
buses = convert_df_wkb_to_shapely(df=buses,
                                  cols=['geom'])

lines = oep_api_get_data(schema='model_draft',
                         table='wn_abw_ego_pf_hv_line',
                         columns=['line_id', 'bus0', 'bus1', 's_nom'])

trafos = oep_api_get_data(schema='model_draft',
                          table='wn_abw_ego_pf_hv_transformer',
                          columns=['trafo_id', 'bus0', 'bus1', 's_nom', 'geom'])

# get grid districts
substations = oep_api_get_data(schema='model_draft',
                               table='wn_abw_ego_dp_hvmv_substation',
                               columns=['subst_id', 'otg_id', 'geom'])
substations = convert_df_wkb_to_shapely(df=substations,
                                        cols=['geom'])
substations.set_index('subst_id', inplace=True)

# determine exchange capacities between districts
transport = reduce_to_regions(bus_data=buses,
                              line_data=lines)

# ==== works only if substations are included in db table ====
# # prepare transport data for writig to OEP
# # join HV-MV substation ids drom buses on lines
# geoms = pd.concat([transport.join(substations,
#                                   on='hvmv_subst_id0')['geom'].rename('geom0'),
#                    transport.join(substations,
#                                   on='hvmv_subst_id1')['geom'].rename('geom1')],
#                   axis=1)
# def to_linestring(df):
#     return LineString([df['geom0'], df['geom1']])
# transport.loc[:,'geom'] = geoms.apply(to_linestring, axis=1)


# oep_api_write_data(schema='model_draft',
#                table='wn_abw_region_transport',
#                data=convert_df_shapely_to_wkb(df=transport_data,
#                                               cols=['geom']))

graph = grid_graph(bus_data=buses,
                   line_data=lines,
                   subst_data=substations,
                   trafo_data=trafos,
                   draw=True)

graph = region_graph(subst_data=substations,
                     line_data=transport,
                     rm_isolates=True,
                     draw=True)

# remove isolated grids (substations and lines)
nodes = list(graph.nodes())
substations = substations.loc[nodes]
transport = transport[transport['hvmv_subst_id0'].isin(nodes) &
                      transport['hvmv_subst_id1'].isin(nodes)]

build_oemof_model(subst_data=substations,
                  transport_data=transport)

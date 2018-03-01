# define and setup logger
from windnode_abw.tools.logger import setup_logger
logger = setup_logger()

# load configs
from windnode_abw.tools import config
config.load_config('config_data.cfg')
config.load_config('config_misc.cfg')

from windnode_abw.model import Region
from windnode_abw.tools.data_io import oep_api_get_data, oep_api_write_data
from windnode_abw.tools.geo import convert_df_wkb_to_shapely, convert_df_shapely_to_wkb
from windnode_abw.model.region.model import build_oemof_model
from windnode_abw.model.region.tools import reduce_to_regions, region_graph, grid_graph

from oemof.outputlib import views
from oemof.graph import create_nx_graph
import matplotlib.pyplot as plt

from windnode_abw.tools.draw import draw_graph

import pandas as pd
from shapely.geometry import LineString


def plot_results(esys, results):
    """Plots results of simulation

    Parameters
    ----------
    esys : oemof.solph.EnergySystem
    results : :obj:`dict`
        Results of simulation
    """
    logger.info("Plot results")

    # create and plot graph of energy system
    graph = create_nx_graph(esys)
    draw_graph(grph=graph, plot=True, layout='neato', node_size=100, font_size=8,
               node_color={
                   'bus_el': '#cd3333',
                   'bus_gas': '#7EC0EE',
                   'bus_th': '#eeac7e'})

    imex_bus_results = views.node(results, 'b_el_imex')
    imex_bus_results_flows = imex_bus_results['sequences']

    # print some sums for import/export bus
    print(imex_bus_results_flows.sum())
    print(imex_bus_results_flows.info())

    # some example plots for bus_el
    ax = imex_bus_results_flows.sum(axis=0).plot(kind='barh')
    ax.set_title('Sums for optimization period')
    ax.set_xlabel('Energy (MWh)')
    ax.set_ylabel('Flow')
    plt.tight_layout()
    plt.show()

    imex_bus_results_flows.plot(kind='line', drawstyle='steps-post')
    plt.show()

    ax = imex_bus_results_flows.plot(kind='bar', stacked=True, linewidth=0, width=1)
    ax.set_title('Sums for optimization period')
    ax.legend(loc='upper right', bbox_to_anchor=(1, 1))
    ax.set_xlabel('Energy (MWh)')
    ax.set_ylabel('Flow')
    plt.tight_layout()

    dates = imex_bus_results_flows.index
    tick_distance = int(len(dates) / 7) - 1
    ax.set_xticks(range(0, len(dates), tick_distance), minor=False)
    ax.set_xticklabels(
        [item.strftime('%d-%m-%Y') for item in dates.tolist()[0::tick_distance]],
        rotation=90, minor=False)
    plt.show()

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

load_from_pkl = True

if not load_from_pkl:
    region = Region.import_data()
    region.dump_to_pkl('test.pkl')
else:
    region = Region.load_from_pkl('test.pkl')

# # determine exchange capacities between districts
# transport = reduce_to_regions(bus_data=buses,
#                               line_data=lines)

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
#group_params = ['subst_id', 'generation_type']
graph = grid_graph(region=region,
                   draw=False)

# graph = region_graph(subst_data=substations,
#                      line_data=transport,
#                      rm_isolates=True,
#                      draw=True)

# # remove isolated grids (substations and lines)
# nodes = list(graph.nodes())
# substations = substations.loc[nodes]
# transport = transport[transport['hvmv_subst_id0'].isin(nodes) &
#                       transport['hvmv_subst_id1'].isin(nodes)]

# build_oemof_model(subst_data=substations,
#                   transport_data=transport)
esys, results = build_oemof_model(region=region)

plot_results(esys=esys,
             results=results)

logger.info('Done!')
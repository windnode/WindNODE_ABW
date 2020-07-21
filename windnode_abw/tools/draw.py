import networkx as nx

from matplotlib import rcParams
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = 'Roboto'
rcParams['font.weight'] = 'normal'
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.ticker import ScalarFormatter
import matplotlib.gridspec as gridspec


import pandas as pd
import geopandas as gpd
import os

import seaborn as sns
# set seaborn style
sns.set()

import plotly.express as px
import plotly.io as pio
import plotly.graph_objs as go
import plotly.offline as pltly

from oemof.outputlib import views
from oemof.graph import create_nx_graph

import logging
logger = logging.getLogger('windnode_abw')

PRINT_NAMES = {
    'bhkw': "Large-scale CHP",
    'bio': "Biogas",
    'gas': "Open-cycle gas turbine",
    'gud': "Combined-cycle gas turbine",
    'bhkw': 'CHP',
    'hydro': "Hydro",
    'pv_ground': "PV ground-mounted",
    'pv_roof_large': "PV roof top (large)",
    'pv_roof_small': "PV roof top (small)",
    'wind': "Wind",
    'import': "Electricity imports (national grid)",
    "elenergy": "Direct electric heating",
    "fuel_oil": "Oil heating",
    "gas_boiler": "Gas (district heating)",
    "natural_gas": "Gas heating",
    "solar": "Solar thermal heating",
    "solar_heat": "Solar heating",
    "elenergy" : "electrical energy",
    "wood": "Wood heating",
    "coal": "Coal heating",
    "pth": "Power-to-heat (district heating)",
    "pth_ASHP" : "Air source heat pump",
    "pth_ASHP_nostor" : "Air source heat pump, no storage",
    "pth_ASHP_stor" : "Air source heat pump, storage",
    "pth_GSHP" : "Ground source heat pump",
    "pth_GSHP_nostor" :"Ground source heat pump, no storage",
    "pth_GSHP_stor" : "Ground source heat pump, storage",
    "stor_th_large" : "Thermal storage (district heating)",
    "stor_th_small" : "Thermal storage",
    "flex_bat_large" : "Large-scale battery storage",
    "flex_bat_small" : "PV system battery storage",
    "hh" : "Households",
    "ind" : "Industry",
    "rca" : "Agri-comerce",
    "export" : "Export",
    "conventional" : "Conventional",
    "el_hh" : "Electricity households",
    "el_rca" : "Electricity agri-comerce",
    "el_ind" : "Electricity industry",
    "th_hh_efh" : "thermal single household",
    "th_hh_mfh" : "thermal multi household",
    "th_rca": "thermal agri-comerce",
    "hh_efh" : "singe households",
    "hh_mfh" : "multi households",
    "ABW-export": "ABW-export",
    "ABW-import": "ABW-import"



}

# https://developer.mozilla.org/en-US/docs/Web/CSS/color_value
# https://plotly.com/python/builtin-colorscales/
COLORS = {'bio': 'green',
          'hydro': 'royalblue',
          'pv_ground' : 'goldenrod',
          'pv_roof_large' : 'gold',
          'pv_roof_small' : 'darkorange',
          'wind': 'skyblue',
          'conventional':'grey',
          'solar_heat': 'peru',
          'gud':'teal',
          'bhkw' : 'seagreen',
          'gas' : 'lightgrey',
          'import' : 'maroon',
          'export' : 'olive',
          'demand' : 'darkgray',
          'rca': 'gray',
          'hh': 'darkmagenta',
          'ind': 'darkslategray',
          'el_rca': 'gray',
          'el_hh': 'darkmagenta',
          'el_ind': 'darkslategray',
          'th_hh_efh': 'plum',
          'th_hh_mfh': 'fuchsia',
          'th_rca' : 'crimson',
          'ABW-export': 'mediumpurple',
          'ABW-import': 'mediumorchid',

         }


def draw_graph(grph, mun_ags=None,
               edge_labels=True, node_color='#AFAFAF',
               edge_color='#CFCFCF', plot=True, node_size=2000,
               with_labels=True, arrows=True, layout='neato',
               node_pos = None, font_size=10):
    """
    Draw a graph (from oemof examples)

    Parameters
    ----------
    grph : networkxGraph
        A graph to draw.
    mun_ags : int
        Municipality's AGS. If provided, the graph will contain only nodes from
        this municipality.
    edge_labels : boolean
        Use nominal values of flow as edge label
    node_color : dict or string
        Hex color code oder matplotlib color for each node. If string, all
        colors are the same.

    edge_color : string
        Hex color code oder matplotlib color for edge color.

    plot : boolean
        Show matplotlib plot.

    node_size : integer
        Size of nodes.

    with_labels : boolean
        Draw node labels.

    arrows : boolean
        Draw arrows on directed edges. Works only if an optimization_model has
        been passed.
    layout : string
        networkx graph layout, one of: neato, dot, twopi, circo, fdp, sfdp.
    """
    if type(node_color) is dict:
        node_color = [node_color.get(g, '#AFAFAF') for g in grph.nodes()]

    # set drawing options
    options = {
        'prog': 'dot',
        'with_labels': with_labels,
        'node_color': node_color,
        'edge_color': edge_color,
        'node_size': node_size,
        'arrows': arrows,
        'font_size': font_size
    }

    if mun_ags is not None:
        nodes = [n for n in grph.nodes if str(mun_ags) in n]
        nodes_neighbors = [list(nx.all_neighbors(grph, n))
                           for n in nodes]
        nodes = set(nodes + list(set([n for nlist in nodes_neighbors
                                      for n in nlist])))
        grph = grph.subgraph(nodes)
        grph = nx.relabel_nodes(grph,
                                lambda x: x.replace('_' + str(mun_ags), ''))
        options['node_color'] = [set_node_colors(grph).get(n, '#AFAFAF')
                                 for n in grph.nodes()]
        options['node_size'] = 200
        options['arrowsize'] = 15
        options['with_labels'] = False
        options['font_size'] = 10
        pos = nx.drawing.nx_agraph.graphviz_layout(grph,
                                                   prog='neato',
                                                   args='-Gepsilon=0.0001')
        nx.draw(grph, pos=pos, **options)
        pos = {k: (v[0], v[1] + 10) for k, v in pos.items()}
        nx.draw_networkx_labels(grph, pos=pos, **options)

    else:
        if node_pos is None:
            pos = nx.drawing.nx_agraph.graphviz_layout(grph, prog=layout)
        else:
            pos = node_pos

        nx.draw(grph, pos=pos, **options)
        labels = nx.get_edge_attributes(grph, 'weight')
        nx.draw_networkx_edge_labels(grph, pos=pos, edge_labels=labels)

    # show output
    if plot is True:
        plt.show()


def set_node_colors(grph):
    """Define node colors

    Parameters
    ----------
    grph : networkxGraph
        A graph to draw.

    Returns
    -------
    :obj:`dict`
        Node colors: graph node as key, hex color as val

    Notes
    -----
    Colors made with color brewer (http://colorbrewer2.org)
    """
    colors = {}
    for node in grph.nodes():
        if node[:4] == 'b_el':
            colors[node] = '#bdc9e1'
        elif node[:6] == 'gen_el':
            colors[node] = '#016c59'
        elif node[:6] == 'dem_el':
            colors[node] = '#67a9cf'
        elif node[:9] == 'excess_el':
            colors[node] = '#cccccc'
        elif node[:11] == 'shortage_el':
            colors[node] = '#cccccc'
        elif node[:4] == 'line':
            colors[node] = '#f7f7f7'

        elif node[:8] == 'b_th_dec':
            colors[node] = '#fecc5c'
        elif node[:10] == 'gen_th_dec':
            colors[node] = '#bd0026'
        elif node[:10] == 'dem_th_dec':
            colors[node] = '#fd8d3c'
        elif node[:8] == 'b_th_cen':
            colors[node] = '#d7b5d8'
        elif node[:10] == 'gen_th_cen':
            colors[node] = '#980043'
        elif node[:10] == 'dem_th_cen':
            colors[node] = '#df65b0'

        elif node[:14] == 'flex_bat_large':
            colors[node] = '#08519c'
        elif node[:14] == 'flex_bat_small':
            colors[node] = '#08519c'
        elif node[:12] == 'flex_dec_pth':
            colors[node] = '#ffffb2'
        elif node[:12] == 'flex_cen_pth':
            colors[node] = '#ffffb2'
        elif node[:8] == 'flex_dsm':
            colors[node] = '#3c6ecf'

    return colors


def debug_plot_results(esys, region):
    """Plots results of simulation

    Parameters
    ----------
    esys : oemof.solph.EnergySystem
        Energy system including results
    region : :class:`~.model.Region`
        Region object
    """

    logger.info('Plotting results...')

    results = esys.results['main']
    #om_flows = esys.results['om_flows']

    imex_bus_results = views.node(results, 'b_th_dec_15001000_hh_efh')
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


def sample_plots(region, results):

    ##############
    # PLOT: Grid #
    ##############
    fig, axs = plt.subplots(1, 2)
    de = gpd.read_file(os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'data',
        'DEU_adm0.shp')).to_crs("EPSG:3035")
    de.plot(ax=axs[0], color='white', edgecolor='#aaaaaa')

    gdf_region = gpd.GeoDataFrame(region.muns, geometry='geom')
    gdf_region['centroid'] = gdf_region['geom'].centroid

    gdf_region.plot(ax=axs[0])

    gdf_region.plot(ax=axs[1], color='white', edgecolor='#aaaaaa')
    for idx, row in gdf_region.iterrows():
        axs[1].annotate(s=row['gen'],
                        xy=(row['geom'].centroid.x, row['geom'].centroid.y),
                        ha='center',
                        va='center',
                        color='#555555',
                        size=8)
    gdf_lines = gpd.GeoDataFrame(region.lines, geometry='geom')
    gdf_lines.plot(ax=axs[1], color='#88aaaa', linewidth=1.5, alpha=1)
    gdf_buses = gpd.GeoDataFrame(region.buses, geometry='geom')
    gdf_buses.plot(ax=axs[1], color='#338888', markersize=6, alpha=1)

    for p in [0, 1]:
        axs[p].set_yticklabels([])
        axs[p].set_xticklabels([])

    axs[0].set_title('Region ABW in Deutschland',
                     fontsize=16,
                     fontweight='normal')
    axs[1].set_title('Region ABW mit Hochspannungsnetz',
                     fontsize=16,
                     fontweight='normal')

    plt.show()

    #######################
    # PLOT: RE capacities #
    #######################
    fig, axs = plt.subplots(2, 2)
    gdf_region = gpd.GeoDataFrame(region.muns, geometry='geom')
    gdf_region['gen_capacity_pv_roof'] = gdf_region['gen_capacity_pv_roof_small'] + \
                                         gdf_region['gen_capacity_pv_roof_large']
    gdf_region.plot(column='gen_capacity_wind', ax=axs[0, 0], legend=True, cmap='viridis')

    axs[0, 0].set_title('Wind')
    gdf_region.plot(column='gen_capacity_pv_ground', ax=axs[0, 1], legend=True, cmap='viridis')
    axs[0, 1].set_title('Photovoltaik FF-Anlagen')
    gdf_region.plot(column='gen_capacity_pv_roof', ax=axs[1, 0], legend=True, cmap='viridis')
    axs[1, 0].set_title('Photovoltaik Aufdachanlagen')
    gdf_region.plot(column='gen_capacity_bio', ax=axs[1, 1], legend=True, cmap='viridis')
    axs[1, 1].set_title('Bioenergie')
    # plt.axis('off')
    for x, y in zip([0, 0, 1, 1], [0, 1, 0, 1]):
        axs[x, y].set_yticklabels([])
        axs[x, y].set_xticklabels([])
        # for idx, row in gdf_region.iterrows():
        #     axs[x, y].annotate(s=row['gen'],
        #                        xy=(row['geom'].centroid.x, row['geom'].centroid.y),
        #                        ha='center',
        #                        va='center',
        #                        color='#ffffff',
        #                        size=8)
    fig.suptitle('Installierte Leistung Erneuerbare Energie in Megawatt',
                 fontsize=16,
                 fontweight='normal')
    plt.show()

    ###########################
    # PLOT: RE feedin stacked #
    ###########################
    time_start = 2000
    timesteps = 240
    techs = {'hydro': 'Laufwasser',
             'bio': 'Bioenergie',
             'wind': 'Windenergie',
             'pv_ground': 'Photovoltaik (Freifläche)',
             'pv_roof_small': 'Photovoltaik (Aufdach <30 kW)',
             'pv_roof_large': 'Photovoltaik (Aufdach >30 kW)',
             }
    sectors = {'el_ind': 'Industrie',
               'el_rca': 'GHD',
               'el_hh': 'Haushalte'
               }
    fig, ax = plt.subplots()
    feedin = pd.DataFrame({v: region.feedin_ts[k].sum(axis=1)
                           for k, v in techs.items()}).iloc[
             time_start:time_start + timesteps]
    demand = pd.DataFrame({v: region.demand_ts[k].sum(axis=1)
                           for k, v in sectors.items()}).iloc[
             time_start:time_start + timesteps]

    residual_load = demand.sum(axis=1) - feedin.sum(axis=1)

    (-feedin).plot.area(ax=ax, cmap='viridis')
    demand.plot.area(ax=ax, cmap='copper')
    residual_load.plot(ax=ax, style='r--', label='Residuallast')
    ax.set_title('Strom: Last- und EE-Erzeugungszeitreihen, Residuallast',
                 fontsize=16,
                 fontweight='normal')
    ax.set_xlabel('Zeit', fontsize=12)
    ax.set_ylabel('MW', fontsize=12)
    ax.set_ylim(round(min(-feedin.sum(axis=1)) / 100 - 1) * 100,
                round(max(demand.sum(axis=1)) / 100 + 1) * 100)
    plt.legend()
    plt.show()
    
    #############################
    # PLOT: Dec. th. generation #
    #############################
    timesteps = 96
    fig, ax = plt.subplots()
    th_generation = results['Wärmeerzeugung dezentral nach Technologie'].merge(
        results['Wärmeerzeugung Wärmepumpen nach Technologie'], left_index=True, right_index=True).iloc[0:0 + timesteps]

    th_generation.plot.area(ax=ax, cmap='viridis')  # BrBG
    ax.set_title('Wärmeerzeugung dezentral nach Technologie',
                 fontsize=16,
                 fontweight='normal')
    ax.set_xlabel('Zeit', fontsize=12)
    ax.set_ylabel('MW', fontsize=12)
    ax.set_ylim(0)
    plt.legend()
    plt.show()



# one geoplot to fit in subplots
def plot_geoplot(name, data, region, ax, cmap='viridis'):
    """plot geoplot from pd.Series
    Parameters
    ----------
    name : str
        title of plot
    data : pd.Series
        data to plot
    region : :class:`~.model.Region`
        Region object
    ax : matplotlib.axes
        coordinate system
    cmap: str
        colormap
    """
    gdf_region = gpd.GeoDataFrame(region.muns.loc[:,['gen', 'geom']],
                                  geometry='geom')
    gdf_region = gdf_region.join(data,
                                 how='inner')

    # size the colorbar to plot
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)

    #
    gdf_region.plot(column=data.values,
                    ax=ax,
                    legend=True,
                    cmap=cmap,
                    cax=cax,
                   )

    # Set title, remove ticks/grid
    ax.set_title(name)
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)



def plot_snd_total(region, df_supply, df_demand):
    """plot barplot of yearly total supply and demand per ags
    Parameters
    ----------
    region : :class:`~.model.Region`
        Region object
    df_supply : pd.DataFrame
        yearly total per ags
    df_demand : pd.DataFrame
        yearly total per ags
    """    
    fig = go.Figure()
    for tech, data in df_supply.iteritems():
        fig.add_trace(go.Bar(x=region.muns['gen'],
                             y=data,
                             name=PRINT_NAMES[tech],
                             marker_color=COLORS[tech]))



    for tech, data in df_demand.iteritems():
        fig.add_trace(go.Bar(x=region.muns['gen'],
                             y=-data,
                             name=PRINT_NAMES[tech],
                             marker_color=COLORS[tech],
                            visible='legendonly'))


    fig.update_layout(
        title='Power Generation and Demand',
        barmode='relative',
        xaxis={'categoryorder':'category ascending'},
        xaxis_tickfont_size=14,
        yaxis=dict(title='MWh',
            titlefont_size=16,
            tickfont_size=14),
            autosize=True)
    fig.show()

def plot_rel_autarky(df_data, limit, ax):
    """"""
    
    df_data = df_data.sort_values()
    # split data
    df_data = df_data.mul(100)
    df_data_left = df_data[df_data < limit]
    df_data_right = df_data[df_data >= limit]

    # split subplot
    inner = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=ax, wspace=0.35, hspace=0.2)
    
    # left plot
    ax1 = plt.subplot(inner[0])
    df_data_left.plot(kind='barh', ax=ax1)#, color=colors_hight(df_data_left.values, 'winter'))
    ax1.set_ylabel('AGS')
    ax1.set_xlabel('%')
    ax1.set_xlim([0,limit])

    # right plot
    ax2 = plt.subplot(inner[1])
    df_data_right.plot(kind='barh', ax=ax2)# color=colors_hight(df_data_right.values, 'winter'))
    ax2.set_ylabel(None)
    ax2.set_xlabel('%')

    fig = plt.gcf()
    fig.suptitle('rel. autarky',
             fontsize=16,
             fontweight='normal')

def plot_timeseries(results_scn, kind='el', **kwargs):
    """"""
    #start = kwargs.get('start', region.cfg['date_from'])
    #end = kwargs.get('end', region.cfg['date_to'])
    ags = kwargs.get('ags', 'ABW')
    
    # remove if ags in multiindex is converted to int
    ags = str(ags)
    
    if kind =='el':
        df_feedin = results_scn['flows_txaxt']['Stromerzeugung']
        df_demand = results_scn['flows_txaxt']['Stromnachfrage']
    elif kind == 'th':
        df_feedin = results_scn['flows_txaxt']['Wärmeerzeugung']
        df_demand = results_scn['flows_txaxt']['Wärmenachfrage']
    #else:
    #    raise ValueError("Enter either 'el' or 'th'") 
   
    if ags=='ABW':
        df_feedin = df_feedin.sum(level=0)#.loc[start:end,:]
        df_demand = df_demand.sum(level=0)#.loc[start:end,:]
    else:  
        df_feedin = df_feedin.loc[(slice(None),ags),:].sum(level=0)#.loc[start:end,:]
        df_demand = df_demand.loc[(slice(None),ags),:].sum(level=0)

    # what is conventional
    #df_residual_load = df_demand.sum(axis=1) - df_feedin.drop(columns=['conventional']).sum(axis=1)

    fig = go.Figure()

    for tech, data in df_feedin.iteritems():
        fig.add_trace(go.Scatter(x=data.index,
                                 y=data.values,
                                 name=PRINT_NAMES[tech],
                                 fill='tonexty',
                                 mode='none',
                                 #fillcolor=COLORS[tech],
                                stackgroup='one'))

    for tech, data in df_demand.iteritems():
        fig.add_trace(go.Scatter(x=data.index,
                                 y=(-data.values),
                                 name=PRINT_NAMES[tech],
                                 fill='tonexty',
                                 mode='none',
                                 #fillcolor=COLORS[tech],
                                stackgroup='two'))


    fig.update_xaxes(
        title='Zoom',
        rangeslider_visible=True,
        rangeselector=dict(
            buttons=list([
                dict(count=6, label="6m", step="month", stepmode="backward"),
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(count=14, label="2w", step="day", stepmode="backward"),
                dict(count=7, label="1w", step="day", stepmode="backward"),
                dict(count=3, label="3d", step="day", stepmode="backward"),
                #dict(step="all")
            ])
        )
    )

    fig.update_layout(
        title='Power Generation and Demand of %s'% ags,
        #xaxis={'categoryorder':'category ascending'},
        xaxis_tickfont_size=14,
        yaxis=dict(
        title='MW',
        titlefont_size=16,
        tickfont_size=14),
        autosize=True)
    fig.show()

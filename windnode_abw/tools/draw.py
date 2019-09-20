import networkx as nx
import matplotlib.pyplot as plt

from oemof.outputlib import views
from oemof.graph import create_nx_graph

import logging
logger = logging.getLogger('windnode_abw')


def draw_graph(grph, edge_labels=True, node_color='#AFAFAF',
               edge_color='#CFCFCF', plot=True, node_size=2000,
               with_labels=True, arrows=True, layout='neato',
               node_pos = None, font_size=10):
    """
    Draw a graph (from oemof examples)

    Parameters
    ----------
    grph : networkxGraph
        A graph to draw.
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

    # draw graph
    if node_pos is None:
        pos = nx.drawing.nx_agraph.graphviz_layout(grph, prog=layout)
    else:
        pos = node_pos

    nx.draw(grph, pos=pos, **options)

    # add edge labels for all edges
    if edge_labels is True and plt:
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

        elif node[:8] == 'flex_bat':
            colors[node] = '#08519c'
        elif node[:12] == 'flex_dec_pth':
            colors[node] = '#ffffb2'
        elif node[:12] == 'flex_cen_pth':
            colors[node] = '#ffffb2'

    return colors


def plot_results(esys, region):
    """Plots results of simulation

    Parameters
    ----------
    esys : oemof.solph.EnergySystem
        Energy system including results
    region : :class:`~.model.Region`
        Region object
    """

    logger.info('Plot results')

    results = esys.results['main']
    om_flows = esys.results['om_flows']

    imex_bus_results = views.node(results, 'b_th_dec_15001000')
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

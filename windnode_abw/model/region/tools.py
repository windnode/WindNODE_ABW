import logging
logger = logging.getLogger('windnode_abw')

import pandas as pd
from pandas import compat
import networkx as nx
import matplotlib.pyplot as plt


def remove_isolates():
    raise NotImplementedError
    # logging.info('Removing orphan buses')
    # # get all buses
    # buses = [obj for obj in Regions.entities if isinstance(obj, Bus)]
    # for bus in buses:
    #     if len(bus.inputs) > 0 or len(bus.outputs) > 0:
    #         logging.debug('Bus {0} has connections.'.format(bus.type))
    #     else:
    #         logging.debug('Bus {0} has no connections and will be deleted.'.format(
    #             bus.type))
    #         Regions.entities.remove(bus)
    #
    # for i in esys.nodes[0].inputs.keys():
    #     print(i.label)


def reduce_to_regions(bus_data,
                      line_data):
    """Reduce/sum existing transport capacities to capacities between region pairs

    Parameters
    ----------
    bus_data
    line_data

    Returns
    -------

    """

    def _to_dict_dropna(data):
        return dict((k, v.dropna().to_dict()) for k, v in compat.iteritems(data))

    # convert nominal cap. to numeric
    line_data['s_nom'] = pd.to_numeric(line_data['s_nom'])

    bus_data_nogeom = bus_data[['bus_id', 'hvmv_subst_id']]

    # bus data needs bus_id as index
    bus_data_nogeom.set_index('bus_id', inplace=True)

    # join HV-MV substation ids from buses on lines
    line_data = line_data.join(bus_data_nogeom, on='bus0')
    line_data.rename(columns={'hvmv_subst_id': 'hvmv_subst_id0'}, inplace=True)
    line_data = line_data.join(bus_data_nogeom, on='bus1')
    line_data.rename(columns={'hvmv_subst_id': 'hvmv_subst_id1'}, inplace=True)

    # remove lines which are fully located in one region (MVGD)
    line_data = line_data[line_data['hvmv_subst_id0'] != line_data['hvmv_subst_id1']]

    # swap substation ids if not ascending to allow grouping
    cond = line_data['hvmv_subst_id0'] > line_data['hvmv_subst_id1']
    line_data.loc[cond, ['hvmv_subst_id0',
                         'hvmv_subst_id1']] = \
        line_data.loc[cond, ['hvmv_subst_id1', 'hvmv_subst_id0']].values

    line_data.sort_values(by='hvmv_subst_id0', inplace=True)

    # group by substation ids and sum up capacities
    line_data_grouped = line_data.groupby(
        ['hvmv_subst_id0', 'hvmv_subst_id1']).sum().reset_index()
    line_data_grouped.drop(['bus0', 'bus1', 'line_id'], axis=1, inplace=True)

    line_data_grouped.rename(columns={'s_nom': 'capacity'}, inplace=True)

    # OLD:
    # line_data_grouped = line_data.groupby(
    #     ['hvmv_subst_id0', 'hvmv_subst_id1'])['s_nom'].sum()
    # # flatten and transpose
    # line_data_grouped = line_data_grouped.unstack().transpose()
    # line_data_dict = _to_dict_dropna(line_data_grouped)

    return line_data_grouped


def region_graph(subst_data,
                 line_data,
                 rm_isolates=False,
                 draw=False):
    """Create graph representation of grid from substation and line data

    Parameters
    ----------
    subst_data
    line_data
    rm_isolates
    draw

    Returns
    -------
    networkx.Graph
        Graph representation of grid
    """

    def _find_main_graph(graph):
        """Remove isolated grids (subgraphs) of grid/graph

        Parameters
        ----------
        graph : networkx.Graph

        Returns
        -------
        networkx.Graph
        """

        subgraphs = {len(sg.nodes()): sg for sg in nx.connected_component_subgraphs(graph)}

        if len(subgraphs) > 1:
            logger.warning('Region consists of {g_cnt} separate (unconnected) grids with node counts '
                           '{n_cnt}. The grid with max. node count is used, the others are dropped.'
                           .format(g_cnt=str(len(subgraphs)),
                                   n_cnt=str(list(subgraphs.keys()))
                                   )
                           )

            # use subgraph with max. count of nodes
            subgraph_used = subgraphs[max(list(subgraphs.keys()))]
            #subgraphs_dropped = [sg for n_cnt, sg in subgraphs.iteritems() if n_cnt != max(list(subgraphs.keys()))]

            return subgraph_used

    # create graph
    graph = nx.Graph()
    npos = {}
    elabels = {}

    for idx, row in line_data.iterrows():
        source = row['hvmv_subst_id0']
        geom = subst_data.loc[source]['geom']
        npos[source] = (geom.x, geom.y)

        target = row['hvmv_subst_id1']
        geom = subst_data.loc[target]['geom']
        npos[target] = (geom.x, geom.y)

        elabels[(source, target)] = str(int(row['capacity']))
        graph.add_edge(source, target)

    # remove isolated grids (graphs)
    if rm_isolates:
        graph = _find_main_graph(graph=graph)

    # draw graph
    if draw:
        plt.figure()
        nx.draw_networkx(graph, pos=npos, with_labels=True, font_size=8)
        nx.draw_networkx_edge_labels(graph, pos=npos, edge_labels=elabels, font_size=8)
        plt.show()

    return graph


def grid_graph(bus_data,
               line_data,
               subst_data,
               trafo_data,
               draw=False):
    """Create graph representation of grid from substation and line data

    Parameters
    ----------
    bus_data
    line_data
    draw

    Returns
    -------
    networkx.Graph
        Graph representation of grid
    """

    # create graph
    graph = nx.Graph()
    npos = {}
    elabels = {}
    nodes_color = []

    bus_data.set_index('bus_id', inplace=True)

    for idx, row in line_data.iterrows():
        source = row['bus0']
        geom = bus_data.loc[source]['geom']
        npos[source] = (geom.x, geom.y)

        target = row['bus1']
        geom = bus_data.loc[target]['geom']
        npos[target] = (geom.x, geom.y)

        elabels[(source, target)] = str(int(row['s_nom']))
        graph.add_edge(source, target)

    for bus in graph.nodes():
        if bus in list(subst_data['otg_id']):
            color = (0.7, 0.7, 1)
        else:
            color = (0.8, 0.8, 0.8)

        # mark buses which are connected to im- and export
        if (not bus_data.loc[bus]['region_bus'] or
            bus in (list(trafo_data['bus0']) + list(trafo_data['bus1']))
            ):
            color = (1, 0.7, 0.7)

        nodes_color.append(color)

    # draw graph
    if draw:
        plt.figure()
        nx.draw_networkx(graph, pos=npos, node_color=nodes_color, with_labels=True, font_size=6)
        nx.draw_networkx_edge_labels(graph, pos=npos, edge_labels=elabels, font_size=8)
        plt.title('Gridmap')
        plt.xlabel('lon')
        plt.ylabel('lat')
        plt.show()

    return graph

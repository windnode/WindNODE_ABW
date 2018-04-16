import logging
logger = logging.getLogger('windnode_abw')

import pandas as pd
from pandas import compat
import networkx as nx
import matplotlib.pyplot as plt

import oemof.solph as solph


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


def grid_graph(region,
               draw=False):
    """Create graph representation of grid from substation and line data from Region object

    Parameters
    ----------
    region : :class:`~.model.Region`
    draw : :obj:`bool`
        If true, graph is plotted

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

    for idx, row in region.lines.iterrows():
        source = row['bus0']
        geom = region.buses.loc[source]['geom']
        npos[source] = (geom.x, geom.y)

        target = row['bus1']
        geom = region.buses.loc[target]['geom']
        npos[target] = (geom.x, geom.y)

        elabels[(source, target)] = str(int(row['s_nom']))
        graph.add_edge(source, target)

    for bus in graph.nodes():
        if bus in list(region.subst['otg_id']):
            color = (0.7, 0.7, 1)
        else:
            color = (0.8, 0.8, 0.8)

        # mark buses which are connected to im- and export
        if (not region.buses.loc[bus]['region_bus'] or
            bus in (list(region.trafos['bus0']) + list(region.trafos['bus1']))
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


def calc_line_loading(esys, region):
    """Calculates relative loading of esys' lines

    Parameters
    ----------
    esys : oemof.solph.EnergySystem
        Energy system including results

    Returns
    -------
    :obj:`dict`
        Line loading of format (node_from, node_to): relative mean line loading
    :obj:`dict`
        Line loading of format (node_from, node_to): relative max, line loading
    """

    results = esys.results['main']
    om_flows = dict(esys.results['om_flows'])

    line_loading_mean = {
        (from_n, to_n): float(flow['sequences'].mean()) / om_flows[(from_n, to_n)].nominal_value
        #from_n: float(flow['sequences'].mean()) / om_flows[(from_n, to_n)].nominal_value
        for (from_n, to_n), flow in results.items()
        if isinstance(from_n, solph.custom.Link)
    }

    line_loading_max = {
        (from_n, to_n): float(flow['sequences'].max()) / om_flows[(from_n, to_n)].nominal_value
        #from_n: float(flow['sequences'].max()) / om_flows[(from_n, to_n)].nominal_value
        for (from_n, to_n), flow in results.items()
        if isinstance(from_n, solph.custom.Link)
    }

    # x = {}
    # for k1, k2 in line_loading_max2.keys():
    #     x[k1] = max([v for k, v in line_loading_max2.items() if k1 in k])

    results_lines = region.lines[['line_id']].copy()
    results_lines['loading_mean'] = 0.
    results_lines['loading_max'] = 0.

    for idx, row in results_lines.iterrows():
        #results_lines.at[idx, 'loading_mean'] = line_loading_mean[esys.groups['line_' + str(int(row['line_id']))]]
        line = esys.groups['line_' + str(int(row['line_id']))]
        results_lines.at[idx, 'loading_mean'] = max([line_loading_mean[(from_n, to_n)]
                                                     for (from_n, to_n), loading in line_loading_mean.items()
                                                     if from_n == line])

        #results_lines.at[idx, 'loading_max'] = line_loading_max[esys.groups['line_' + str(int(row['line_id']))]]
        results_lines.at[idx, 'loading_max'] = max([line_loading_max[(from_n, to_n)]
                                                    for (from_n, to_n), loading in line_loading_max.items()
                                                    if from_n == line])

    region.results_lines = results_lines

    # # create DF with custom cols (node1, node 2, flow) from simulation result dict
    # flows_results = pd.Series(results).rename_axis(['node1', 'node2']).reset_index(name='flow_res')
    # flows_results.set_index(['node1', 'node2'], inplace=True)
    # flows_obj = pd.Series(dict(om_flows)).rename_axis(['node1', 'node2']).reset_index(name='flow_obj')
    # flows_obj.set_index(['node1', 'node2'], inplace=True)
    # flows = pd.concat([flows_obj, flows_results], axis=1).reset_index()
    #
    # # get esys' lines (Link instances)
    # lines = [node for node in esys.nodes if isinstance(node, solph.custom.Link)]
    # # get flows of lines (filtering of column node1 should be sufficient since Link always creates 2 Transformers)
    # flows_links = flows[flows['node1'].isin(lines)]
    #
    # for idx, row in flows_links.iterrows():
    #     obj = row['flow_obj']
    #     seq = row['flow_res']['sequences']
    #     if obj.nominal_value:
    #         flows_links.at[idx, 'loading_mean'] = float(seq.mean()) / obj.nominal_value
    #         flows_links.at[idx, 'loading_max'] = float(seq.max()) / obj.nominal_value
    #     else:
    #         flows_links.at[idx, 'loading_mean'] = 0.
    #         flows_links.at[idx, 'loading_max'] = 0.
    # # flows_links.sort_values('loading_max')

    return

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

    def _to_dict_dropna(data):
        return dict((k, v.dropna().to_dict()) for k, v in compat.iteritems(data))

    # convert nominal cap. to numeric
    line_data['s_nom'] = pd.to_numeric(line_data['s_nom'])

    bus_data_nogeom = bus_data[['bus_id', 'hvmv_subst_id']]

    # bus data needs bus_id as index
    bus_data_nogeom.set_index('bus_id', inplace=True)

    # join HV-MV substation ids drom buses on lines
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


def draw_region_graph(subst_data,
                      line_data):

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

    plt.figure()
    #nx.draw_networkx(graph, pos=npos, node_size=30, font_size=8)
    nx.draw(graph, pos=npos)
    nx.draw_networkx_edge_labels(graph, pos=npos, edge_labels=elabels)
    plt.show()

    list(nx.connected_component_subgraphs(graph))

import pandas as pd
from re import match


def result_seqs_to_dataframe(esys):
    """Convert result dict to DataFrame with Flow tuple as columns

    Returns
    -------
    :pandas:`pandas.DataFrame`
        DataFrame with unidirectional flows, node pair as columns.
        Includes the resulting flow into the DSM sink.
    :pandas:`pandas.DataFrame`
        DataFrame with bidirectional flows, (node, param) as columns.
        E.g. DSM measures dsm_up and dsm_do of DSM sink nodes.
    """
    bidirectional_nodes_prefixes = ['flex_dsm']
    bidirectional_nodes_pattern = '(?:' + '|'.join(
        p for p in bidirectional_nodes_prefixes) + r')_\w+'

    return pd.DataFrame(
        {(str(from_n), str(to_n)): flow['sequences']['flow']
         for (from_n, to_n), flow in esys.results['main'].items()
         if not match(bidirectional_nodes_pattern, str(from_n))}
    ), pd.DataFrame(
        {(str(from_n), col): flow['sequences'][col]
        for (from_n, to_n), flow in esys.results['main'].items()
        if match(bidirectional_nodes_pattern, str(from_n))
        for col in flow['sequences'].columns}
    )


def aggregate_flows(region, esys):
    """Calculate total emissions of energy system"""

    nodes = {
        'Stromerzeugung nach Technologie': {
            'pattern': 'gen_el_\d+_b\d+_(\w+)',
            'level': 0
        },
        'Strombedarf nach Sektor': {
            'pattern': 'dem_el_\d+_b\d+_(\w+)',
            'level': 1
        },
        'Wärmeerzeugung dezentral nach Technologie': {
            'pattern': 'gen_th_dec_\d+_\w+_(\w+)',
            'level': 0
        },
        'Wärmeerzeugung dezentral nach Sektor': {
            'pattern': 'gen_th_dec_\d+_((?:hh_efh|hh_mfh|rca))_\w+',
            'level': 0
        },
        'Wärmebedarf nach Sektor': {
            'pattern': 'dem_th_(?:dec|cen)_\d+_(\w+)',
            'level': 1
        },
        'Wärmeerzeugung Wärmepumpen nach Technologie': {
            'pattern': 'flex_dec_pth_((?:A|G)SHP)_\d+_\w+',
            'level': 0
        },
        'DSM Haushalte nach Gemeinde': {
            'pattern': 'flex_dsm_(\d+)_b\d+',
            'level': 1
        },
        'Großbatterien nach Gemeinde': {
            'pattern': 'flex_bat_(\d+)_b\d+',
            'level': 1
        },
    }

    datetime_index = pd.date_range(start=region.cfg['date_from'],
                                   end=region.cfg['date_to'],
                                   freq=region.cfg['freq'])
    df = pd.DataFrame(columns=nodes.keys(), index=datetime_index)

    flows_uni, flows_bi = result_seqs_to_dataframe(esys)

    # aggragation of unidirectional flows
    for name, node in nodes.items():
        df[name] = flows_uni.groupby(
            flows_uni.columns.get_level_values(level=node['level']).str.extract(
                node['pattern'],
                expand=False),
            axis=1).agg('sum')

    # TODO: Insert aggregation of bidirectional flows here

    pass

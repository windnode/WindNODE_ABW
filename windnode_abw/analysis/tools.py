import pandas as pd
from re import match


def result_seqs_to_dataframe(esys):
    """Convert result dict to DataFrames for flows and stationary variables.

    Returns
    -------
    :pandas:`pandas.DataFrame`
        DataFrame with flows, node pair as columns.
    :pandas:`pandas.DataFrame`
        DataFrame with stationary variables, (node, var) as columns.
        E.g. DSM measures dsm_up and dsm_do of DSM sink nodes.
    """
    # bidirectional_nodes_prefixes = ['flex_dsm', 'flex_bat']
    # bidirectional_nodes_pattern = '(?:' + '|'.join(
    #     p for p in bidirectional_nodes_prefixes) + r')_\w+'

    return pd.DataFrame(
        {(str(from_n), str(to_n)): flow['sequences']['flow']
         for (from_n, to_n), flow in esys.results['main'].items()
         if to_n is not None}
    ), pd.DataFrame(
        {(str(from_n), col): flow['sequences'][col]
        for (from_n, to_n), flow in esys.results['main'].items()
        if to_n is None
        for col in flow['sequences'].columns}
    )

    # pd.DataFrame(
    #     {(str(from_n), str(to_n)): flow['sequences']['flow']
    #      for (from_n, to_n), flow in esys.results['main'].items()
    #      if not match(bidirectional_nodes_pattern, str(from_n))}
    # )
    # pd.DataFrame(
    #     {(str(from_n), col) if match(bidirectional_nodes_pattern, str(from_n))
    #                         else (col, str(to_n)): flow['sequences'][col]
    #     for (from_n, to_n), flow in esys.results['main'].items()
    #     if match(bidirectional_nodes_pattern, str(from_n)) or
    #        match(bidirectional_nodes_pattern, str(to_n))
    #     for col in flow['sequences'].columns}
    # )



def aggregate_flows(esys):
    """Aggregate result flows and create result dictionary"""

    # aggregations, format:
    # {<TITLE>: {'pattern': <REGEX PATTERN OF NODE NAME>,
    #            'level': 0 for flow input, 1 for flow output}
    # }
    aggregations_flows = {
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
        'Wärmeerzeugung Heizstäbe nach Gemeinde': {
            'pattern': 'flex_cen_pth_(\d+)',
            'level': 0
        },
        'Strombedarf Haushalte mit DSM nach Gemeinde': {
            'pattern': 'flex_dsm_(\d+)_b\d+',
            'level': 1
        },
        'Großbatterien nach Gemeinde': {
            'pattern': 'flex_bat_(\d+)_b\d+',
            'level': 1
        },
        'Stromexport nach Spannungsebene': {
            'pattern': 'excess_el_(\w+)_b\d+',
            'level': 1
        },
        'Stromimport nach Spannungsebene': {
            'pattern': 'shortage_el_(\w+)_b\d+',
            'level': 0
        },
    }

    aggregations_vars = {
        'Lasterhöhung DSM Haushalte nach Gemeinde': {
            'pattern': 'flex_dsm_(\d+)_b\d+',
            'variable': 'dsm_up'
        },
        'Lastreduktion DSM Haushalte nach Gemeinde': {
            'pattern': 'flex_dsm_(\d+)_b\d+',
            'variable': 'dsm_do'
        },
        'Speicherfüllstand Großbatterien nach Gemeinde': {
            'pattern': 'flex_bat_(\d+)_b\d+',
            'variable': 'capacity'
        },
        'Speicherfüllstand dezentrale Wärmespeicher nach Sektor': {
            'pattern': 'stor_th_dec_\d+_((?:hh_efh|hh_mfh|rca))',
            'variable': 'capacity'
        },
        'Speicherfüllstand dezentrale Wärmespeicher nach Gemeinde': {
            'pattern': 'stor_th_dec_(\d+)_(?:hh_efh|hh_mfh|rca)',
            'variable': 'capacity'
        },
        'Speicherfüllstand dezentrale Wärmespeicher (Wärmepumpen) nach Sektor': {
            'pattern': 'stor_th_dec_pth_\d+_((?:hh_efh|hh_mfh|rca))',
            'variable': 'capacity'
        },
        'Speicherfüllstand dezentrale Wärmespeicher (Wärmepumpen) nach Gemeinde': {
            'pattern': 'stor_th_dec_pth_(\d+)_(?:hh_efh|hh_mfh|rca)',
            'variable': 'capacity'
        },
        'Speicherfüllstand zentrale Wärmespeicher nach Gemeinde': {
            'pattern': 'stor_th_cen_(\d+)',
            'variable': 'capacity'
        },
    }

    flows_df, vars_df = result_seqs_to_dataframe(esys)

    results = {}

    # aggregation of flows
    for name, params in aggregations_flows.items():
        results[name] = flows_df.groupby(
            flows_df.columns.get_level_values(level=params['level']).str.extract(
                params['pattern'],
                expand=False),
            axis=1).agg('sum')

    # aggregation of stationary vars
    for name, params in aggregations_vars.items():
        vars_df_filtered = vars_df.xs(params['variable'], level=1, axis=1)
        results[name] = vars_df_filtered.groupby(
            vars_df_filtered.columns.get_level_values(level=0).str.extract(
                params['pattern'],
                expand=False),
            axis=1).agg('sum')

    print('xxx')

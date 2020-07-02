# Convert CSV file with scenarios to scenario files (.scn)
# (in folder windnode_abw/scenarios/)

import os
import ast
from configobj import ConfigObj
import pandas as pd
import windnode_abw


def merge_dicts(a, b, path=None):
    """merges b into a"""
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dicts(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass # same leaf value
            else:
                raise Exception(f'Conflict at {".".join(path + [str(key)])}')
        else:
            a[key] = b[key]
    return a


if __name__ == "__main__":
    # ===================================================
    # CSV file holding scenarios
    # (exported from scenario document, separated by ";")
    csv_file = 'scenarios.csv'
    # header lines (check in CSV or tool will break!)
    header_lines = 4
    # ===================================================

    # import scenario table
    scn_df = pd.read_csv(os.path.join(windnode_abw.__path__[0],
                                      'scenarios',
                                      csv_file),
                         sep=';',
                         header=None)
    
    for scn_no in range(len(scn_df) - header_lines):
        # extract params from scn DF
        scn_data = scn_df.iloc[
            list(range(header_lines)) + [scn_no + header_lines]
        ].to_dict()

        # build dict
        scn_config = {}
        sec = {}
        for _, subsec in scn_data.items():
            sec = {}
            vals = [v for v in subsec.values() if not pd.isnull(v)]
            for v in reversed(vals):
                if vals[-1] == v:
                    try:
                        sec = ast.literal_eval(v)
                    except:
                        sec = v
                else:
                    sec = {v: sec}
            y = merge_dicts(scn_config, sec)

        # build ConfigObj
        scn_configobj = ConfigObj(scn_config)
        scn_id = scn_configobj['general']['id']

        # write file
        scn_configobj.filename = os.path.join(windnode_abw.__path__[0],
                                              'scenarios',
                                              f'{scn_id}.scn')
        scn_configobj.write()

        print(f'Scenario converted: "{scn_id}"')

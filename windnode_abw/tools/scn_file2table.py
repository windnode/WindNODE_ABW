# Convert parameter structure from scenario file (.scn) to CSV file
# (used to avoid manual creation of export sheet in scenario table)

import os
import pandas as pd
from pandas.io.json._normalize import nested_to_record
import windnode_abw
from windnode_abw.tools.data_io import load_scenario_cfg


if __name__ == "__main__":
    # =========================================
    scn_name = 'sq'
    # out file
    csv_file = 'scenario_header.csv'
    # number of value rows to be created (=number of scenarios)
    # (all filled with identical data from scenario above)
    row_count = 39
    # =========================================

    scn = load_scenario_cfg(scn_name)

    # flatten dict
    scn_flat = nested_to_record(scn, sep='#')

    # create DF with multiindex by split
    scn_df = pd.DataFrame.from_dict(scn_flat,
                                    orient='index').T
    idx = scn_df.columns.str.split('#', expand=True)

    # extract param values
    values = scn_df.iloc[0].reset_index(drop=True)

    # extract header
    scn_df.columns = idx
    scn_df_header = idx.to_frame(index=False).T

    # merge header and param values
    scn_df_header = scn_df_header.append([values] * row_count,
                                         ignore_index=True)

    # export
    scn_df_header.to_csv(os.path.join(windnode_abw.__path__[0],
                                      'scenarios',
                                      csv_file),
                         sep=';',
                         decimal=',',
                         header=False,
                         index=False)

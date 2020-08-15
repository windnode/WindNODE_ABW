import pandas as pd
import os
from tabulate import tabulate
import windnode_abw


def extract_and_format():
    """Prepare scenario data for docs table"""

    header_lines = [0,1,2,3]

    # import scenario table
    scn_df = pd.read_csv(os.path.join(windnode_abw.__path__[0],
                                      'scenarios',
                                      'scenarios.csv'),
                         sep=';',
                         header=header_lines,
                         )

    # set scenario name as index
    df_idx = pd.Index([_[0] for _ in scn_df.xs(("general", "id"), axis=1).values])
    df = scn_df.set_index(df_idx, "Scenario")

    mapping_dict = {
        ("Generation capacity", "PV", "MW"): ("generation", "re_potentials", "pv_installed_power"),
        ("Generation capacity", "Wind", "MW"): ("generation", "re_potentials", "wec_installed_power"),
        ("Autarky level", "minimum", "%-demand"): ("grid", "extgrid", "import"),
        ("Demand-Side Management", "market penetration", "% of households"): ("flexopt", "dsm", "params"),
        ("Battery storage", "large-scale", "MWh"): ("flexopt", "flex_bat_large", "params"),
        ("Battery storage", "PV storage", "MWh"): ("flexopt", "flex_bat_small", "params"),
        ("Thermal storage", "Decentralized heating", "MWh"): ("storage", "th_dec_pth_storage", "general"),
        ("Thermal storage", "District heating", "MWh"): ("storage", "th_cen_storage", "general"),

    }

    scn_dict = {
        new_cols: [_[0] for _ in df.xs(old_cols, axis=1).values] for new_cols, old_cols in mapping_dict.items()
    }

    extracted_df = pd.DataFrame.from_dict(scn_dict).set_index(df_idx)

    # hack some data
    extracted_df[("Autarky level", "minimum", "%-demand")] = (1 - extracted_df[
        ("Autarky level", "minimum", "%-demand")]) * 100
    extracted_df[("Demand-Side Management", "market penetration", "% of households")] = extracted_df[
        ("Demand-Side Management", "market penetration", "% of households")] * 100

    return extracted_df

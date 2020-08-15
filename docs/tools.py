import pandas as pd
import os
import windnode_abw


def create_scn_table_docs():
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
        "PV capacity [MW]": ("generation", "re_potentials", "pv_installed_power"),
        "Wind capacity [MW]": ("generation", "re_potentials", "wec_installed_power"),
        "Autarky level [minimum % of demand]": ("grid", "extgrid", "import"),
        "Demand-Side Management [% of households]": ("flexopt", "dsm", "params"),
        "Battery storage (large) [MWh]": ("flexopt", "flex_bat_large", "params"),
        "Battery storage (PV storage) [MWh]": ("flexopt", "flex_bat_small", "params"),
        "Thermal storage (dec. heating) [MWh]": ("storage", "th_dec_pth_storage", "general"),
        "Thermal storage (district heating) [MWh]": ("storage", "th_cen_storage", "general"),

    }

    scn_dict = {
        new_cols: [_[0] for _ in df.xs(old_cols, axis=1).values] for new_cols, old_cols in mapping_dict.items()
    }

    extracted_df = pd.DataFrame.from_dict(scn_dict).set_index(df_idx)

    # hack some data
    extracted_df["Autarky level [minimum % of demand]"] = (1 - extracted_df[
        "Autarky level [minimum % of demand]"]) * 100
    extracted_df["Demand-Side Management [% of households]"] = extracted_df[
        "Demand-Side Management [% of households]"] * 100

    # save to docs subfolder
    scn_table_path = os.path.join(windnode_abw.__path__[0],
                                  '..',
                                  'docs',
                                  '_static',
                                  'scenario_overview.rst')

    # headers = [" ".join(col) for col in extracted_df.columns]
    headers = extracted_df.columns

    with open(scn_table_path, "w") as fh:
        extracted_df.to_markdown(buf=fh, tablefmt="grid", headers=headers)

    return extracted_df


if __name__== "__main__":

    df = create_scn_table_docs()

    # headers = ["\n".join(col) for col in df.columns]
    # print(df.to_markdown(tablefmt="grid", headers=headers))

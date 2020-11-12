# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

import sphinx_material
import pandas as pd
import os
import windnode_abw
import pathlib


PARENTDIR = pathlib.Path(__file__).parent.absolute()


def _df2rst(df, filepath):
    headers = df.columns

    with open(filepath, "w") as fh:
        df.to_markdown(buf=fh, tablefmt="grid", headers=headers)


def create_tech_scn_table_docs():
    tab_names = [
        "re_scenarios_nep",
        "re_scenarios_ise",
        "dsm_scenarios_nep",
        "dsm_scenarios_ise",
        "battery_storage_scenarios",
        "pth_scenarios",
        "autarky_scenarios"
    ]

    for tab in tab_names:
        df = pd.read_csv(os.path.join(PARENTDIR,
                                      "_data",
                                      "{}.csv".format(tab)),
                         index_col="Unnamed: 0")

        _df2rst(df, os.path.join(PARENTDIR, "{}.rst".format(tab)))


def create_scn_table_docs():
    """Prepare scenario data for docs table"""

    header_lines = [0,1,2,3]

    # import scenario and RES installed capacity tables
    scn_df = pd.read_csv(os.path.join(windnode_abw.__path__[0],
                                      'scenarios',
                                      'scenarios.csv'),
                         sep=';',
                         header=header_lines,
                         )
    res_capacity = pd.read_csv(os.path.join(windnode_abw.__path__[0],
                                      'scenarios',
                                      'scenarios_installed_power.csv'),
                         sep=';',
                         ).set_index(["base_scenario", "landuse_scenario"])

    # set scenario name as index
    df_idx = pd.Index([_[0] for _ in scn_df.xs(("general", "id"), axis=1).values])
    df = scn_df.set_index(df_idx, "Scenario")

    mapping_dict = {
        "PV capacity (ground) [MW]": ("generation", "re_potentials", "pv_installed_power"),
        "PV capacity (rooftop) [MW]": ("generation", "re_potentials", "pv_roof_installed_power"),
        "Wind capacity [MW]": ("generation", "re_potentials", "wec_installed_power"),
        "Autarky level [minimum % of demand]": ("grid", "extgrid", "import"),
        "Demand-Side Management [% of households]": ("flexopt", "dsm", "params"),
        "Battery storage (large) [MWh]": ("flexopt", "flex_bat_large", "params"),
        "Battery storage (PV storage) [MWh]": ("flexopt", "flex_bat_small", "params"),
        "Dec. heating systems with storage [%]": ("storage", "th_dec_pth_storage", "general"),
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

    # Add correct RES installation numbers
    scenario_args = extracted_df.index.str.extract(
        "(?P<base_scenario>StatusQuo|NEP|ISE)_?(?P<landuse_scenario>RE-|PV\+|WIND\+|RE\+\+)?")
    scenario_args.index = extracted_df.index

    for idx, row in scenario_args.iterrows():
        res_tmp = res_capacity.loc[[(row["base_scenario"], row["landuse_scenario"])]]

        extracted_df.loc[idx, 'PV capacity (ground) [MW]'] = int(res_tmp["pv_installed_power"])
        extracted_df.loc[idx, 'PV capacity (rooftop) [MW]'] = int(res_tmp["pv_roof_installed_power"])
        extracted_df.loc[idx, 'Wind capacity [MW]'] = int(res_tmp["wec_installed_power"])


    # save to docs subfolder
    scn_table_path = os.path.join(PARENTDIR, 'scenario_overview.rst')
    print(scn_table_path)

    headers = extracted_df.columns

    with open(scn_table_path, "w") as fh:
        extracted_df.to_markdown(buf=fh, tablefmt="grid", headers=headers)

    return extracted_df


# Create required data and tables
create_scn_table_docs()
create_tech_scn_table_docs()


# -- Project information -----------------------------------------------------

project = 'WindNODE ABW'
copyright = '2020, @nesnoj,@gplssm,@nailend'
author = '@nesnoj,@gplssm,@nailend'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'nbsphinx',
    'sphinx.ext.mathjax',
    'sphinxcontrib.bibtex',
    'sphinx.ext.intersphinx',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', "_data"]

master_doc = 'index'


# -- Options for HTML output -------------------------------------------------
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_show_sourcelink = False
html_sidebars = {
    "**": [
        # "logo-text.html",
        "globaltoc.html",
        # "localtoc.html",
        # "searchbox.html"
    ]
}

extensions.append("sphinx_material")
html_theme_path = sphinx_material.html_theme_path()
html_context = sphinx_material.get_html_context()
html_theme = "sphinx_material"
html_logo = "images/Windnode.png"

# material theme options (see theme.conf for more information)
html_theme_options = {
    "repo_url": "https://github.com/windnode/windnode_abw/",
    "repo_name": "See source code on GitHub",
    "html_minify": False,
    "html_prettify": True,
    "css_minify": True,
    # "logo_icon": "&#xe869",
    "repo_type": "github",
    "color_primary": "blue",
    "color_accent": "cyan",
    "globaltoc_depth": 3,
    # "touch_icon": "images/apple-icon-152x152.png",
    "theme_color": "#2196f3",
    "master_doc": False,
    "nav_links": [
        {"href": "index", "internal": True, "title": "WindNODE ABW"},
        {
            "href": "scenarios",
            "internal": True,
            "title": "Scenarios",
        },
        {
            "href": "energy_system_model",
            "internal": True,
            "title": "Energy system model",
        },
        {
            "href": "data",
            "internal": True,
            "title": "Data",
        },
        {
            "href": "results",
            "internal": True,
            "title": "Results",
        },
        {
            "href": "zbibliography",
            "internal": True,
            "title": "Bibliography",
        },
        {
            "href": "development",
            "internal": True,
            "title": "Development",
        },
    ],
    "heroes": {
        "index": "A regional energy system model for Anhalt-Bitterfeld-Wittenberg",
        "scenarios": "Scenario-based exploration of energy supply and flexibility options",
        "energy_system_model": "Modelling regional aspects of future electricity and heat supply",
        "data": "Where the data comes from",
        "results": "Explore results in detail",
        "development": "Some notes for developers"
    },
    "version_dropdown": True,
    "version_json": "_static/versions.json",
    "version_info": {
        "Release": "https://bashtage.github.io/sphinx-material/",
        "Development": "https://bashtage.github.io/sphinx-material/devel/",
        "Release (rel)": "/sphinx-material/",
        "Development (rel)": "/sphinx-material/devel/",
    },
    "table_classes": ["plain"],
}
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
import pynodo
import logging
import re


PARENTDIR = pathlib.Path(__file__).parent.absolute()
ZENODO_DEPOSIT_ID = 4896569

def _df2rst(df, filepath):
    headers = df.columns

    with open(filepath, "w") as fh:
        df.to_markdown(buf=fh, tablefmt="grid", headers=headers)


def create_tech_scn_table_docs():
    tab_names_scenario = [
        "re_scenarios_nep",
        "re_scenarios_ise",
        "dsm_scenarios_nep",
        "dsm_scenarios_ise",
        "battery_storage_scenarios",
        "pth_scenarios",
        "autarky_scenarios"
    ]
    tab_names_esm = [
        "electricty_heat_demand",
        "heating_structure",
        "model_components",
        "database_tables"
    ]

    for tab in tab_names_scenario:
        df = pd.read_csv(os.path.join(PARENTDIR,
                                      "_data",
                                      "{}.csv".format(tab)),
                         index_col="Unnamed: 0")

        _df2rst(df, os.path.join(PARENTDIR, "{}.rst".format(tab)))
    for tab in tab_names_esm:
        df = pd.read_csv(os.path.join(PARENTDIR,
                                      "_data",
                                      "{}.csv".format(tab)),
                         index_col=0)
        df.index = df.index.fillna("")

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
        "Thermal storage (district heating) [MWh/MW]": ("storage", "th_cen_storage", "general"),
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
    extracted_df["Dec. heating systems with storage [%]"] = extracted_df[
        "Dec. heating systems with storage [%]"] * 100

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


def download_from_zenodo(deposit_id):

    notebooks_path = "notebooks"
    os.makedirs(notebooks_path, exist_ok=True)

    # Make sure the directory 'notebooks/' is empty, otherwise skip download
    if not os.listdir(notebooks_path):

        if 'ZENODO_ACCESS_TOKEN' in os.environ:
            zen_files = pynodo.DepositionFiles(deposition=deposit_id,
                                               access_token=os.environ["ZENODO_ACCESS_TOKEN"],
                                               sandbox=False)

            for file in zen_files.files.keys():
                print("Downloading {}...".format(file))
                zen_files.download(file, notebooks_path)
        else:
            raise EnvironmentError("Variable `ZENODO_ACCESS_TOKEN` is missing.")
    else:
        logging.warning(f"Notebooks {notebooks_path} directory is not empty. I won't download anything. "
                        f"Docs are built with present *.ipynb files.")


def single_scenario_nb_toctree(target_file="_include/single_scenario_results.rst", scenario_names=None):

    os.makedirs("_include", exist_ok=True)

    prolog = "Results for each scenario are presented on a separate page. Please click on one of the links below.\n\n"

    if scenario_names:
        files = ["scenario_analysis_" + s + ".ipynb" for s in scenario_names]
    else:
        files = [f for f in os.listdir("notebooks") if re.match("scenario_analysis_(NEP|ISE|StatusQuo)", f)]
    basenames = [os.path.splitext(file)[0] for file in files]
    names = [file.replace("scenario_analysis_", "") for file in basenames]

    toctree_links = ""

    for file in names:
        link = "   {name} <notebooks/scenario_analysis_{name}>\n".format(name=file)
        toctree_links += link
    header = ".. toctree::\n   :maxdepth: 1\n\n"

    with open(target_file, "w") as text_file:
        text_file.write("{0}".format(prolog + header + toctree_links))

# Create required data and tables
scenario_names = create_scn_table_docs()
create_tech_scn_table_docs()

# Download results .ipynb and hook into documentation
download_from_zenodo(ZENODO_DEPOSIT_ID)
single_scenario_nb_toctree(scenario_names=scenario_names.index.to_list())



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
html_logo = "images/rli_windnode_logo.png"

# enable numeric references for figures
numfig = True

# material theme options (see theme.conf for more information)
html_theme_options = {
    "repo_url": "https://github.com/windnode/windnode_abw/",
    "repo_name": "See source code on GitHub",
    "html_minify": False,
    "html_prettify": True,
    "css_minify": True,
    # "logo_icon": "&#xe869",
    "repo_type": "github",
    "color_primary": "indigo",
    "color_accent": "orange",
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
            "href": "land_eligibility",
            "internal": True,
            "title": "Land eligibility for RE",
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
            "href": "usage_notes",
            "internal": True,
            "title": "Usage notes",
        },
        {
            "href": "zbibliography",
            "internal": True,
            "title": "References",
        }
    ],
    "heroes": {
        "index": "A regional energy system model for Anhalt-Bitterfeld-Wittenberg",
        "scenarios": "Scenario-based exploration of energy supply and flexibility options",
        "energy_system_model": "Modelling regional aspects of future electricity and heat supply",
        "land_eligibility": "Analysis of regional land eligibility for wind energy and photovoltaics",
        "data": "How to obtain model input and results data",
        "results": "Explore results in detail",
        "usage_notes": "How to install and use the model",
        "zbibliography": "References"
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


# NBSphinx config
# nbsphinx_prolog = """
# {% set docname =  env.doc2path(env.docname, base=None)|replace("notebooks/scenario_analysis_", "")|replace(".ipynb", "") %}
# {% set scenariodocname = "Scenario: " ~ docname %}
#
# .. raw:: html
#
#    <h3 id={{ docname }}>
#         {{ scenariodocname }}
#         <a class="headerlink" href="#{{ docname }}" title="Permalink to this headline">
#         ¶
#         </a>
#    </h3>
# """

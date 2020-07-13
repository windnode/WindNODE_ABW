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
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

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
        "localtoc.html",
        # "searchbox.html"
    ]
}

extensions.append("sphinx_material")
html_theme_path = sphinx_material.html_theme_path()
html_context = sphinx_material.get_html_context()
html_theme = "sphinx_material"

# material theme options (see theme.conf for more information)
html_theme_options = {
    "repo_url": "https://github.com/windnode/windnode_abw/",
    "repo_name": "See source code on GitHub",
    "html_minify": False,
    "html_prettify": True,
    "css_minify": True,
    "logo_icon": "&#xe869",
    "repo_type": "github",
    "globaltoc_depth": 2,
    "color_primary": "blue",
    "color_accent": "cyan",
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
        "index": "A regional energy system model for Anhalt-Bitterfeld-Wolfen",
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
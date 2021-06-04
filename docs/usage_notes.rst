.. _usage_notes:

Usage notes
===========

Installation
------------

Clone and install via

.. code-block:: bash

    git clone https://github.com/windnode/WindNODE_ABW.git # or by SSH: git@github.com:windnode/WindNODE_ABW.git
    pip install -e /path/to/cloned/repo/

(a virtualenv is recommended).

**Notice:** The recent package **psycopg2-binary** in `setup.py` conflicts with the **psycopg2** required by **egoio**.
If the install breaks, use the following temporary workaround:

Install requirements manually in your venv, **egoio** should be the last. Install it without dependencies by using

.. code-block:: bash

    pip install --no-dependencies egoio

To run the model, you also need a solver to be installed such as CBC or Gurobi. On Linux, you can install CBC with
`apt install coinor-cbc`. Make sure the solver is set in the run configuration dict in `run_scenario.py`.

Trouble shooting
^^^^^^^^^^^^^^^^

Installation of ``psutils``
"""""""""""""""""""""""""""

During the installtion of ``windnode_abw``, the package ``psutils``
might fail. Install the system package ``python3-dev`` with

.. code:: bash

   sudo apt install python3-dev

Installation of ``pygraphviz``
""""""""""""""""""""""""""""""

During the installtion of ``windnode_abw``, the package ``pygraphviz``
might fail. Install additional system packages with

.. code:: bash

   sudo apt install python3-dev graphviz libgraphviz-dev pkg-config

Setup postgres database with docker (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Note** You don't have to necessarily use docker to create a PostgreSQL database. Using a native installation works as
well.

Inside the repo's root directory (where docker-compose.yml lives) execute

.. code-block:: bash

    docker-compose up -d --build

Afterwards you can access the database via

+---------------+---------------+
| Field         | Value         |
+===============+===============+
| host          | localhost     |
+---------------+---------------+
| port          | 54321         |
+---------------+---------------+
| Maintance DB  | windnode_abw  |
+---------------+---------------+
| User          | windnode      |
+---------------+---------------+
| Password      | windnode      |
+---------------+---------------+


Import scenario data
^^^^^^^^^^^^^^^^^^^^

Scenario data is contained in the database dump available [here](https://zenodo.org/record/4898349/).
Do the following steps to import the scenario data to your database:

1. Download the above scenario data file
2. Import tables, data, and constraints by
   ```
   pg_restore -U windnode -d windnode_abw -h localhost -p 54321 -W --no-owner --no-privileges --no-tablespace -1  </path/to/windnode_db_200817.backup>
   ```
   To overwrite existing tables, you may use the `--clean` argument.

Setup database connection config file
-------------------------------------

When you try to run `windnode_abw/run_scenario.py`, it will search for  the file `$HOME/.egoio/config.ini`. More
specifically, in the file `config.ini` it searches for a section `[windnode_abw]`. It won't be found whe you run it for
the first time. Subsequently, a command-line dialog opens that asks you for database connection details.

When you use a local database, the section in the config looks like

```
[windnode_abw]
dialect = psycopg2
username = windnode
host = localhost
port = 54321
database = windnode_abw
```

Run Optimization
----------------

To start the optimization, you can use the command line interface: run script
`run_scenario.py` from the shell:

.. code-block:: bash

   python run_scenario.py [-h] [--mp [NUMBER]] [SCENARIO [SCENARIO ...]]

where `NUMBER` is the number of threads and `SCENARIOS` the scenarios to be executed. For example,
to run all scenarios in 4 processes, use

.. code-block:: bash

   python run_scenario.py --mp 4 all

To get help on parameters and available scenarios you can use

.. code-block:: bash

   python run_scenario.py -h

Depending on the system settings, the optimization takes about 1-2 hours for each scenario.

By default, raw results are written to `~/.windnode_abw/results/`, a subdirectory with a timestamp
(run id) is created (e.g. `~/.windnode_abw/results/2020-08-05_024335/`).

Post-processing results
-----------------------

The results, aggregated on different temporal and spatial levels, are calculated by post-processing
the raw results from above. These post-processed data is stored as pickle file in subdirectory
`./processed` of the run id folder and can be quickly loaded, e.g. from the jupyter notebooks.

By default, this step is automatically performed after the optimization run but can be manually
triggered by passing `force_new_results=True` to the notebook creation functions (see below).

Analyzing results
-----------------

A single notebook for each scenario can be produced best by using papermill. Either for one scenario

.. code-block:: python

   create_scenario_notebook("NEP2035",
                            '2020-07-24_104145_1month',
                            template="scenario_analysis_template.ipynb")

or for multiple scenarios using multiprocessing (in this case all)

.. code-block:: python

   create_multiple_scenario_notebooks(
        "all",
        '2020-07-24_104145_1month',
        template="scenario_analysis_template.ipynb",
        num_processes=None
   )

You can then further convert to the executed notebook to HTML by

.. code-block:: bash

   jupyter nbconvert scenario_analysis_NEP2035.ipynb

.. note::

    * Some plots (those generated with plotly) in the generated notebooks may won't show up initially.
      This can be solved by clicking `File -> Trust Notebook`. To trust all notebooks in the notebook
      directory, you can use

      .. code-block:: bash

        jupyter trust *.ipynb

      before you start the jupyter notebook server.

    * If parameter `output_path` is not passed, the standard path `/path/to/windnode/repo/windnode_abw/jupy/`
      is used.

    * If you get an error like `WARNING: No such kernel named ...` try to open the template notebook and
      save it manually to set your current kernel name.

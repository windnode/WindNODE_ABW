Energy system model
===================

The region Anhalt-Bitterfeld-Wittenberg
---------------------------------------


Rationale and model focus
-------------------------


Objective and constraints
-------------------------

Energy sectors and technologies
-------------------------------

Model details
-------------

Usage notes
-----------

Run Optimization
^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^

The results, aggregated on different temporal and spatial levels, are calculated by post-processing
the raw results from above. These post-processed data is stored as pickle file in subdirectory
`./processed` of the run id folder and can be quickly loaded, e.g. from the jupyter notebooks.

By default, this step is automatically performed after the optimization run but can be manually
triggered by passing `force_new_results=True` to the notebook creation functions (see below).

Analyzing results
^^^^^^^^^^^^^^^^^

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

.. code-block:: python

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

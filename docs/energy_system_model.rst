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

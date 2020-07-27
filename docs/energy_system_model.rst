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
                            "windnode_abw/jupy/scenario_analysis_template.ipynb")

or for multiple scenarios using multiprocessing (in this case all)

.. code-block:: python

   create_multiple_scenario_notebooks(
        "all",
        '2020-07-24_104145_1month',
        template="windnode_abw/jupy/scenario_analysis_template.ipynb",
        num_processes=None
   )


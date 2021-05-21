Energy system model
===================

The region Anhalt-Bitterfeld-Wittenberg (ABW)
---------------------------------------------

The Anhalt-Bitterfeld-Wittenberg (ABW) region modelled in this tool is located in the east of Saxony-Anhalt comprising
the three districts Anhalt-Bitterfeld, Wittenberg, and the city of Dessau-Roßlau (:numref:`map_de_abw`). It has a total
area of 3,629 km² and a population of 366,931 in 2018.

.. _map_de_abw:
.. figure:: images/map_de_abw.png
   :width: 40 %
   :align: center

   Region ABW in Germany

.. _map_abw_esys1:
.. figure:: images/map_abw_esys1.png
   :width: 75 %
   :align: center

   Region ABW with municipalities

Substantial amounts of \ac{RES} are installed in the region. In 2017, 717 MW of wind power and 445 MW of ground-mounted
PV covered 63 % of the regional electricty demand of 20 municipalities.

..
  COMMENTED OUT
 .. image:: images/map_de_abw.png
    :width: 50 %
 .. image:: images/map_abw_esys1.png
    :width: 40 %


Rationale and model focus
-------------------------

The employed energy system model (ESM) is based on the energy system modeling framework *oemof-solph* :cite:`Krien2020`.
The model comprises the electricity and heat sector of ABW at municipal-level at a temporal resolution of 1 hour.
It is formulated as a linear optimization problem with the objective of minimizing the cost for operation, CO2 emission
allowances and grid extension.

Grid model
----------

The transmission capacities between the municipalities are given by the extra high voltage (380 kV) and high voltage
grid (110 kV) as shown in :numref:`map_abw_grid`; its topology and parameters were taken from :cite:`Mueller2018`. This
allows for a realistic assessment of the intra-regional exchange and grid load as well as the identification of
potential congestions on those voltage levels.

Subsequently, the electrical generation and demand of the municipalities are allocated to high voltage (HV) / medium
voltage (MV) transformer stations. The allocation is done as follows:

* Municipality contains no HV/MS station: electric components are connected to the closest station available
* Municipality contains 1 HV/MS station: electric components are connected to this station
* Municipality contains >1 HV/MS stations: all electric components are evenly distributed to stations

Although the national grid is not explicitly modeled, it is used for power exchange by municipalities without direct
connection to the regional grid. Imports and exports are facilitated by using virtual sources and sinks located at 9
cross-regional links to the national grid.

.. _map_abw_grid:
.. figure:: images/map_abw_grid.png
   :width: 75 %
   :align: center

   Extra high voltage and high voltage grid of ABW with cross-regional links to the national grid

Medium and low voltage distribution grids are not part of the grid model. District heating networks are not explicitly
modelled but the heat demand of connected consumers is taken into account.

Energy sectors and technologies
-------------------------------

On the electrical generation side, wind turbines, ground-mounted PV, roof-mounted PV, biogas plants, run-of-river
plants, Combined-cycle gas turbines (CCGT), and simple-cycle gas turbines (SCGT) have been integrated as the most
important technologies in the region. The heat generation includes decentralized conventional heating systems primarily
based on natural gas, wood, and fuel oil. Four large district heating networks are located in the region which are fed
by CCGT, CHP units, and gas boilers. The electrical and heat demand incorporates the residential, commercial, trade,
services (CTS) and agricultural sector; for the industrial sector, only the electricity side is included. On the
flexiblity side, the model integrates households with demand-side management, battery storages, and power-to-heat (heat
pumps and electrical boilers). :numref:`map_abw_esys6` shows the model's components.

.. _map_abw_esys6:
.. figure:: images/map_abw_esys6.png
   :width: 75 %
   :align: center

   Components of regional energy system model

Fluctuating renewables
^^^^^^^^^^^^^^^^^^^^^^

The model includes georeferenced data on wind turbines, ground-mounted PV, roof-mounted PV, biogas plants, and
run-of-river plant data of 2017 from the *OPSD* project :cite:`OPSDre2018`.

Wind turbines
"""""""""""""

* Installed nominal power (2017): 717 MW
* Wind turbine models for the status quo (2017) are chosen according to the largest manufacturers in Germany in terms of
  market share :cite:`FraunhoferIEE2015`. Typical turbines of the two market leaders Enercon (40 %) and Vestas (24 %)
  that have been used are E-82 (85 m and 98 m hub height), E-115 (122 m hub height), V90 (80 m and 100 m hub height),
  and  V112 (119 m hub height). The individual turbine types were sorted into 2 classes <2.5 MW (87 %) and >2.5 MW
  (13 %) based on the installed types as of today (cf. above). The 6 types were weighted by market share.
* For both future scenarios, a single turbine model (Enercon E-141, hub height of 159 m)
* Feedin timeseries are generated by *reegis* :cite:`Krien2019` which uses *Coastdat-2* weather data
  :cite:`Coastdat2014` (weather year 2013).
* To account for annual variations, the data is scaled to match the mean annual full load hours in Saxony-Anhalt for
  2011-2015 of 1630 h given by :cite:`SAWindenergie2015`.

Photovoltaics
"""""""""""""

* In the *OPSD* dataset :cite:`OPSDre2018` there's no information of the type of PV system (roof or ground-mounted).
  Based upon typical values :cite:`dena2012` plants with a nominal power of <=300 kWp area treated as rooftop systems,
  larger plants as ground-mounted systems.
* Installed nominal power of ground-mounted systems (2017): 445 MW
* Feedin timeseries are generated by *renewables.ninja* :cite:`Pfenninger2016` which uses generic PV models and
  *CM-SAF SARAH* irradiation data :cite:`cmsaf2015` (weather year 2015).
* To account for annual variations, the data is scaled to match the mean annual full load hours in Saxony-Anhalt for
  2011-2015 of 998 h given by :cite:`SApv2015`.

Biomass and biogas plants
"""""""""""""""""""""""""

* In the absence of sufficient information on which plants are used for heat generation, it is assumed that all biomass
  and biogas plants are used exclusively for electricity generation.
* A constant feedin is assumed with 6000 annual full load hours :cite:`ISE2018`, :cite:`SABioenergie2015`.

Run-of-river plants
"""""""""""""""""""

* A constant feedin is assumed with 3833 annual full load hours (2012-2017 mean from :cite:`STALA2018`)

Electricity and heat demand
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Calculation of total demand
"""""""""""""""""""""""""""

The annual electricity demand for each sector (residential, commercial, trade, services, agricultural and industrial)
and municipality is taken from :cite:`OEP2018` and allocated to the HV/MV stations. The hourly profiles are calculated
in different ways:

* Households: data from :cite:`gaehrs2020`
* Commercial, trade, services (CTS) and agricultural: standard load profiles (SLP G0) using the *demandlib*
  :cite:`demandlib2019`
* Industrial sector: band-like profile using the *demandlib* :cite:`demandlib2019`

The annual heat demand for each sector and municipality is determined as follows:

* Households: based on the number of buildings and living spaces from :cite:`StatistischesBundesamt2018` and
  :cite:`Zensus2017`, heat demands are calculated per municipality using building-specific consumptions from
  :cite:`IWU2015` and :cite:`BDEW2019`. The year of construction, unoccupancy rates and type of building (single or
  multi-family house) are taken into account. Time series are created with the *demandlib* :cite:`demandlib2019` using
  standard gas load profiles *HEF* and *HMF*. Furthermore, historical ambient temperature profiles from the closest DWD
  survey station :cite:`DWD2020` are incorporated.
* Commercial, trade, services (CTS) and agricultural: for these sectors, only the energy required for space heating is
  taken into account. The definition of economic brnaches conform to the classification WZ2008 by the German Federal
  Statistical Office :cite:`StatistischesBundesamt2007` is used. For each branch, specific consumption values (mostly
  per employee, data from :cite:`StatistischeAemter2018`) are used from :cite:`BMWi2015` to calculate annual demands per
  municipality. As for households, time series are created with the *demandlib* :cite:`demandlib2019` but based upon the
  standard gas load profile *GHD* for CTS.

The final results for electricity and heat demand are shown below.

.. include:: electricty_heat_demand.rst

Centralized and decentralized heat systems
""""""""""""""""""""""""""""""""""""""""""

The total heat demand described above is split into centralized (district heating systems) and decentralized systems.
The four largest district heating networks are located in Dessau-Roßlau, Bitterfeld-Wolfen, Köthen and Wittenberg. The
municipal energy suppliers provided load profiles for different years :cite:`StadtwerkeABW2013` which were
temperature-corrected to profiles valid for 2017. This results in the following district heating shares: Dessau-Roßlau
42 %, Bitterfeld-Wolfen 15 %, Köthen 9 % and Wittenberg 20 %. Subsequently, the remaining heat demand is allocated to
decentralized consumers.

Electricity and heat generation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The The allocation of heat demand to the technologies for decentralized systems are  :cite:`ISE2020`

Note: energy generation by solar thermal systems is calculated using the normalized PV feedin timeseries.

Model details
-------------



.. _abw_esys_graph_mun1:
.. figure:: images/abw_esys_graph_mun1.png
   :width: 100 %
   :align: center

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

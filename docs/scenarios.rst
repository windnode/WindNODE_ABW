Scenarios
=========

The scenarios are build along to main dimensions: generation capacity of RES and diffusion of flexibility options.
We look at the years 2035 and 2050. Aside from expected generation capacity the pillars also define the characteristics
of the demand side.

.. image:: images/WindNODE_ABW_scenario-dimensions-generation_inkscape.png
   :width: 75 %
   :align: center

The generation capacity fundamentally derives from two studies. For the year 2035 we follow the assumptions by the
Netzentwicklungsplan 2035 (2021) :cite:`NEP2021`. For the climate neutral scenario, which might be in 2050, the
scenarios base on a Studie by Fraunhofer ISE :cite:`ISE2020`.

The second main dimension that describe how much flexibility is deployed to the system, splits into four sub-dimensions.

.. image:: images/WindNODE_ABW_scenario-dimensions-flexibility_inkscape.png
   :width: 75 %
   :align: center

Based on these dimensions 39 computable scenarios are defined which are described in detail in :ref:`scenario-details`.


.. _research-questions:

Research questions
------------------

Time horizon
------------

The study of :cite:`ISE2020` frames the assumptions made for climate neutral scenarios in 2050.


.. _scenario-details:

Scenarios data in detail
------------------------

.. include:: scenario_overview.rst


Battery storage capacity
^^^^^^^^^^^^^^^^^^^^^^^^

The battery storage capacity is determined by scaling with installed RES capacity. The ratio between battery storage capacity
and RES generation capacity is taken from :cite:`NEP2021`. This is also applied to ISE-scenarios using the same ratio,
but RES generation capacity from :cite:`ISE2020`.
Spatial allocation of battery storage capacity follows the same idea down to municipality level.

.. include:: battery_storage_scenarios.rst


Power-to-heat
^^^^^^^^^^^^^

The inherent thermal storage capacity induced by pipes in decentral heating systems is assumed with 20 l/kW of
installed heat pump power according to suggestions by the manufacturer Viessmann :cite:`viessmann2011`.

.. include:: pth_scenarios.rst


Autarky
^^^^^^^

With the scenario dimension autarkic supply, it is investigated how region's energy demand can be supplied under
constrained imports of electricity.
Autarky on annual balance of 80 % and 90 % is analyzed based in the in-depth investigation of regional autarky in RES
based electricity supply by :cite:`moeller2020`.

.. include:: autarky_scenarios.rst
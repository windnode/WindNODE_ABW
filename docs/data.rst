Data and license
================

Model input data
----------------

You can obtain the complete input dataset (PostgreSQL database dump) from
`Zenodo <https://zenodo.org/record/4898349/>`_. See :ref:`usage_notes` on how to get the model running with the data.

The database contains the following tables:

.. include:: database_tables.rst

The database table `wn_abw_tech_assumptions` includes costs, emissions, efficiencies, and lifetimes based upon data from
:cite:`Schroder2013`, :cite:`ISE2018`, :cite:`IPCC_Annex3`, :cite:`Hao2017`, :cite:`Prueggler2019`, :cite:`Scharte2016`,
:cite:`UBA2011`, :cite:`Fluri2018`, :cite:`IEA2019`, :cite:`Jorge2012a`, :cite:`Jorge2012b`, :cite:`acatech2018`,
:cite:`oeko2016`, :cite:`RWTH2019`, :cite:`Transnet2050`, :cite:`carmen2018`, :cite:`BWP2017`, :cite:`BWP2015`,
:cite:`dena2050`, :cite:`Agora2017`, :cite:`ISE2015`, :cite:`Bloomberg2019`, :cite:`UBA2019`, :cite:`Wirth2021`,
:cite:`HTW2020`, :cite:`STALA2020`.

Result data
-----------

The raw results can be either produced by running the optimization or obtained from Zenodo
`here <https://zenodo.org/record/4288943/>`__.

The detailed results as shown in chapter :ref:`results` show only static graphics, for full functionality the
interactive Jupyter notebooks for all scenarios can be generated as described in :ref:`usage_notes` or downloaded as
executed version from Zenodo `here <https://zenodo.org/record/4896569/>`__.

License
-------

This tool uses mostly open or at least freely available data.
All data are licenced under Creative Commons `CC-BY-4.0 <https://creativecommons.org/licenses/by/4.0/>`_.

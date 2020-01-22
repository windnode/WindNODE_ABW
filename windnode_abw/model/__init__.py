import pickle
import os

import logging
logger = logging.getLogger('windnode_abw')

from windnode_abw.tools import config
from windnode_abw.tools.data_io import import_db_data
from windnode_abw.model.region.tools import \
    prepare_feedin_timeseries, prepare_demand_timeseries,\
    prepare_temp_timeseries, rescale_heating_structure


class Region:
    """Defines the model for ABW region

    Attributes
    ----------
    _name : :obj:`str`
        Name of network
    _cfg : :obj:`dict`
        Run configuration such as timerange, solver, scenario, ...
    _buses : :pandas:`pandas.DataFrame`
        Region's buses
    _lines : :pandas:`pandas.DataFrame`
        Region's lines
    _trafos : :pandas:`pandas.DataFrame`
        Region's transformers
    _subst : :pandas:`pandas.DataFrame`
        Region's substations
    _generators : :pandas:`pandas.DataFrame`
        Region's renewable and conventional generators

    _results_lines : :pandas:`pandas.DataFrame`
        Line loading results

    _demand_ts_init : :pandas:`pandas.DataFrame`
        Original absolute demand (electrical+thermal) timeseries per
        municipality and sector
    _demand_ts : :obj:`dict` of :pandas:`pandas.DataFrame`
        Absolute demand timeseries per demand sector (dict key) and
        municipality (DF column)
    _feedin_ts_init : :pandas:`pandas.DataFrame`
        Original normalized feedin timeseries of renewable and conventional
        generators per municipality and technology/type
    _feedin_ts : :obj:`dict` of :pandas:`pandas.DataFrame`
        Absolute feedin timeseries per technology/type (dict key) and
        municipality (DF column)
    _dsm_ts : :pandas:`pandas.DataFrame`
        DSM timeseries per load band and municipality (MultiIndex columns)
    _temp_ts : :obj:`dict` of :pandas:`pandas.DataFrame`
        Temperature timeseries (air and soil -> dict key) per municipality in
        degree Celsius
    _heating_structure : :pandas:`pandas.DataFrame`
        Heating structure of thermal loads per municpality, sector and
        energy source
    """
    def __init__(self, **kwargs):
        self._name = 'ABW region'
        self._cfg = kwargs.get('cfg', None)

        self._muns = kwargs.get('muns', None)
        self._buses = kwargs.get('buses', None)
        self._lines = kwargs.get('lines', None)
        self._trafos = kwargs.get('trafos', None)
        self._subst = kwargs.get('subst', None)
        self._generators = kwargs.get('generators', None)

        self._results_lines = kwargs.get('_results_lines', None)

        self._demand_ts_init = kwargs.get('demand_ts_init', None)
        self._demand_ts = prepare_demand_timeseries(self)
        self._feedin_ts_init = kwargs.get('feedin_ts_init', None)
        self._feedin_ts = prepare_feedin_timeseries(self)
        self._dsm_ts = kwargs.get('dsm_ts', None)
        self._temp_ts_init = kwargs.get('temp_ts_init', None)
        self._temp_ts = prepare_temp_timeseries(self)

        self._heating_structure = rescale_heating_structure(
            cfg=self._cfg,
            heating_structure=kwargs.get('heating_structure', None)
        )

    @property
    def muns(self):
        """Returns region's municipalities"""
        return self._muns

    @property
    def cfg(self):
        """Returns run config"""
        return self._cfg

    @property
    def buses(self):
        """Returns region's buses"""
        return self._buses

    @property
    def lines(self):
        """Returns region's lines"""
        return self._lines

    @property
    def trafos(self):
        """Returns region's transformers"""
        return self._trafos

    @property
    def subst(self):
        """Returns region's substations"""
        return self._subst

    @property
    def generators(self):
        """Returns region's generators (renewable and conventional)"""
        return self._generators

    @property
    def geno_res_grouped(self):
        """Returns grouped region's RES generators

        Data is grouped by HV-MV-substation id and generation type,
        count of generators and sum of nom. capacity is returned.

        Returns
        -------
        :pandas:`pandas.DataFrame`
            Grouped RES generators with MultiIndex
        """
        # access: e.g. df.loc[2303, 'gas']
        # consider to reset index to convert index cols to regular cols
        # ToDo: Revise this method

        return self.geno_res.groupby(['subst_id', 'generation_type'])[
            'capacity'].agg(['sum', 'count'])#.reset_index()

    @property
    def results_lines(self):
        return self._results_lines

    @results_lines.setter
    def results_lines(self, results_lines):
        self._results_lines = results_lines

    @property
    def demand_ts_init(self):
        return self._demand_ts_init

    @property
    def demand_ts(self):
        return self._demand_ts

    @property
    def feedin_ts_init(self):
        return self._feedin_ts_init

    @property
    def feedin_ts(self):
        return self._feedin_ts

    @property
    def dsm_ts(self):
        return self._dsm_ts

    @property
    def temp_ts_init(self):
        return self._temp_ts_init

    @property
    def temp_ts(self):
        return self._temp_ts

    @property
    def heating_structure(self):
        return self._heating_structure

    @classmethod
    def import_data(cls, cfg=None):
        """Import data to Region object"""

        if cfg is None:
            raise ValueError('Please provide config')

        # create the region instance
        region = cls(**{**import_db_data(), 'cfg': cfg})

        return region

    def dump_to_pkl(self, filename):
        """Dump Region to pickle"""
        filepath = os.path.join(config.get_data_root_dir(),
                                config.get('user_dirs', 'results_dir'))
        pickle.dump(self, open(os.path.join(filepath,
                                            filename), 'wb'))
        logger.info('The region was dumped to {}.'
                    .format(filepath + '/' + filename))

    @classmethod
    def load_from_pkl(self, filename):
        """Load Region from pickle"""
        filepath = os.path.join(config.get_data_root_dir(),
                                config.get('user_dirs', 'results_dir'))
        logger.info('The region was loaded from {}.'
                    .format(filepath + '/' + filename))

        return pickle.load(open(os.path.join(filepath,
                                             filename), 'rb'))

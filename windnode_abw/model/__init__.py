from windnode_abw.tools import config
from windnode_abw.tools.data_io import oep_import_data

import pickle
import os


class Region:
    """Defines the model for ABW region

    Attributes
    ----------
    _name : :obj:`str`
        Name of network
    _buses : :pandas:`pandas.DataFrame<dataframe>`
        Region's buses
    _lines : :pandas:`pandas.DataFrame<dataframe>`
        Region's lines
    _trafos : :pandas:`pandas.DataFrame<dataframe>`
        Region's transformers
    _substations : :pandas:`pandas.DataFrame<dataframe>`
        Region's substations
    _geno_res : :pandas:`pandas.DataFrame<dataframe>`
        Region's renewable (RES) generators
    _geno_conv : :pandas:`pandas.DataFrame<dataframe>`
        Region's conventional generators
    _demand_el : :pandas:`pandas.DataFrame<dataframe>`
        Region's power demand per Grid District and sector
    """
    def __init__(self, **kwargs):
        self._name = 'ABW region'

        self._buses = kwargs.get('buses', None)
        self._lines = kwargs.get('lines', None)
        self._trafos = kwargs.get('trafos', None)
        self._subst = kwargs.get('subst', None)
        self._geno_res = kwargs.get('geno_res', None)
        self._geno_conv = kwargs.get('geno_conv', None)
        self._geno_res_ts = kwargs.get('geno_res_ts', None)
        self._demand_el = kwargs.get('demand_el', None)
        self._demand_el_ts = kwargs.get('demand_el_ts', None)

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
    def geno_res(self, scenario='Status Quo'):
        """Returns region's RES generators"""

        return self._geno_res[self._geno_res['scenario'] == scenario]

    @property
    def geno_conv(self, scenario='Status Quo'):
        """Returns region's conventional generators"""
        return self._geno_conv[self._geno_conv['scenario'] == scenario]

    @property
    def geno_res_ts(self):
        """Returns timeseries of region's RES generators"""

        return self._geno_res_ts

    @property
    def geno_res_grouped(self):
        """Returns grouped region's RES generators

        Data is grouped by HV-MV-substation id and generation type,
        count of generators and sum of nom. capacity is returned.

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Grouped RES generators with MultiIndex
        """
        # access: e.g. df.loc[2303, 'gas']
        # consider to reset index to convert index cols to regular cols

        return self.geno_res.groupby(['subst_id', 'generation_type'])[
            'capacity'].agg(['sum', 'count'])#.reset_index()

    @property
    def geno_conv_grouped(self):
        """Returns grouped region's conventional generators

        Data is grouped by HV-MV-substation/Grid District id and fuel,
        count of generators and sum of nom. capacity is returned.

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Grouped conventional generators with MultiIndex
        """

        return self.geno_conv.groupby(['subst_id', 'fuel'])[
            'capacity'].agg(['sum', 'count'])

    @property
    def demand_el(self):
        """Returns region's power demand per Grid District"""
        return self._demand_el

    @property
    def demand_el_ts(self):
        """Returns timeseries of region's demand"""

        return self._demand_el_ts

    @classmethod
    def import_data(cls, **kwargs):
        """Import data to Region object"""

        # import
        kwargs = oep_import_data()

        # create the region instance
        region = cls(**kwargs)

        return region

    def dump_to_pkl(self, filename):
        """Dump Region to pickle"""
        filepath = os.path.join(config.get_data_root_dir(),
                                config.get('user_dirs', 'data_dir'))
        pickle.dump(self, open(os.path.join(filepath,
                                            filename), 'wb'))

    @classmethod
    def load_from_pkl(self, filename):
        """Load Region from pickle"""
        filepath = os.path.join(config.get_data_root_dir(),
                                config.get('user_dirs', 'data_dir'))
        return pickle.load(open(os.path.join(filepath,
                                             filename), 'rb'))

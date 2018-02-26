from windnode_abw.tools.data_io import oep_import_data


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
    """
    def __init__(self, **kwargs):
        self._name = 'ABW region'

        self._buses = kwargs.get('buses', None)
        self._lines = kwargs.get('lines', None)
        self._trafos = kwargs.get('trafos', None)
        self._subst = kwargs.get('subst', None)
        self._geno_res = kwargs.get('geno_res', None)
        self._geno_conv = kwargs.get('geno_conv', None)

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
    def geno_res(self):
        """Returns region's RES generators"""
        return self._geno_res

    @property
    def geno_conv(self):
        """Returns region's conventional generators"""
        return self._geno_conv

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

        return self._geno_res.groupby(['subst_id', 'generation_type'])[
            'capacity'].agg(['sum', 'count'])#.reset_index()

    @property
    def geno_conv_grouped(self):
        """Returns grouped region's conventional generators

        Data is grouped by HV-MV-substation id and fuel,
        count of generators and sum of nom. capacity is returned.

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Grouped conventional generators with MultiIndex
        """

        return self._geno_conv.groupby(['subst_id', 'fuel'])[
            'capacity'].agg(['sum', 'count'])

    @classmethod
    def import_data(cls, **kwargs):

        # import
        kwargs = oep_import_data()

        # create the region instance
        region = cls(**kwargs)

        return region


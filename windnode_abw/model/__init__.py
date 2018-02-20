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
    """
    def __init__(self, **kwargs):
        self._name = 'ABW region'

        self._buses = kwargs.get('buses', None)
        self._lines = kwargs.get('lines', None)
        self._trafos = kwargs.get('trafos', None)
        self._subst = kwargs.get('subst', None)

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

    @classmethod
    def import_data(cls, **kwargs):

        # import
        kwargs = oep_import_data()

        # create the region instance
        region = cls(**kwargs)

        return region


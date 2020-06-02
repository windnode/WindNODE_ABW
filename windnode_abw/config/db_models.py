# coding: utf-8
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float,\
    ForeignKey, Integer, Numeric, SmallInteger, String, Text, text
from sqlalchemy.orm import relationship
from geoalchemy2.types import Geometry
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()
metadata = Base.metadata

# ToDo: Add docstrings (many can be copied from StEmp ABW)

class WnAbwDemandTs(Base):
    __tablename__ = 'wn_abw_demandts'
    __table_args__ = {'schema': 'windnode'}

    id = Column(BigInteger, primary_key=True, server_default=text("nextval('windnode.stemp_abw_demandts_id_seq'::regclass)"))
    timestamp = Column(DateTime(True), nullable=False, index=True)
    el_ind = Column(Float(53))
    el_rca = Column(Float(53))
    el_hh = Column(Float(53))
    th_ind = Column(Float(53))
    th_hh_efh = Column(Float(53))
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), nullable=False, index=True)
    th_rca = Column(Float(53))
    th_hh_mfh = Column(Float(53))
    th_hh_efh_spec = Column(Float(53))
    th_hh_mfh_spec = Column(Float(53))

    mun = relationship('WnAbwMun', back_populates='demand_ts')


class WnAbwFeedinTs(Base):
    __tablename__ = 'wn_abw_feedints'
    __table_args__ = {'schema': 'windnode'}

    id = Column(BigInteger, primary_key=True, server_default=text("nextval('windnode.stemp_abw_feedints_id_seq'::regclass)"))
    timestamp = Column(DateTime(True), nullable=False, index=True)
    pv_ground = Column(Float(53))
    pv_roof = Column(Float(53))
    hydro = Column(Float(53))
    wind_sq = Column(Float(53))
    wind_fs = Column(Float(53))
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), nullable=False, index=True)
    conventional = Column(Float(53))
    bio = Column(Float(53))
    solar_heat = Column(Float(53))

    mun = relationship('WnAbwMun', back_populates='feedin_ts')


class WnAbwDsmTs(Base):
    __tablename__ = 'wn_abw_dsmts'
    __table_args__ = {'schema': 'windnode'}

    timestamp = Column(DateTime, primary_key=True, nullable=False, index=True)
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), primary_key=True, nullable=False, index=True)
    Flex_Minus = Column(Float(53))
    Flex_Minus_Max = Column(Float(53))
    Flex_Plus = Column(Float(53))
    Flex_Plus_Max = Column(Float(53))
    Lastprofil = Column(Float(53))

    ags = relationship('WnAbwMun', back_populates='dsm_ts')


class WnAbwDsmTsNorm(Base):
    __tablename__ = 'wn_abw_dsmts_norm'
    __table_args__ = {'schema': 'windnode'}

    timestamp = Column(DateTime, primary_key=True, nullable=False, index=True)
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), primary_key=True, nullable=False, index=True)
    Flex_Minus = Column(Float(53))
    Flex_Minus_Max = Column(Float(53))
    Flex_Plus = Column(Float(53))
    Flex_Plus_Max = Column(Float(53))
    Lastprofil = Column(Float(53))

    ags = relationship('WnAbwMun', back_populates='dsm_ts_norm')


class WnAbwTempTs(Base):
    __tablename__ = 'wn_abw_tempts'
    __table_args__ = {'schema': 'windnode'}

    timestamp = Column(DateTime, primary_key=True, nullable=False, index=True)
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), primary_key=True, nullable=False, index=True)
    air_temp = Column(Float(53))
    soil_temp = Column(Float(53))

    ags = relationship('WnAbwMun', back_populates='temp_ts')


class WnAbwGridHvBus(Base):
    __tablename__ = 'wn_abw_grid_hv_bus'
    __table_args__ = {'schema': 'windnode'}

    version = Column(Text, primary_key=True, nullable=False)
    scn_name = Column(String, primary_key=True, nullable=False, server_default=text("'Status Quo'::character varying"))
    bus_id = Column(BigInteger, primary_key=True, nullable=False)
    v_nom = Column(Float(53))
    current_type = Column(Text, server_default=text("'AC'::text"))
    v_mag_pu_min = Column(Float(53), server_default=text("0"))
    v_mag_pu_max = Column(Float(53))
    geom = Column(Geometry('POINT', 4326), index=True)
    hvmv_subst_id = Column(Integer)
    region_bus = Column(Boolean, server_default=text("false"))
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'))

    mun = relationship('WnAbwMun', back_populates='grid_hv_bus')


class WnAbwGridHvLine(Base):
    __tablename__ = 'wn_abw_grid_hv_line'
    __table_args__ = {'schema': 'windnode'}

    version = Column(Text, primary_key=True, nullable=False)
    scn_name = Column(String, primary_key=True, nullable=False, server_default=text("'Status Quo'::character varying"))
    line_id = Column(BigInteger, primary_key=True, nullable=False)
    bus0 = Column(BigInteger)
    bus1 = Column(BigInteger)
    x = Column(Numeric, server_default=text("0"))
    r = Column(Numeric, server_default=text("0"))
    g = Column(Numeric, server_default=text("0"))
    b = Column(Numeric, server_default=text("0"))
    s_nom = Column(Numeric, server_default=text("0"))
    s_nom_extendable = Column(Boolean, server_default=text("false"))
    s_nom_min = Column(Float(53), server_default=text("0"))
    s_nom_max = Column(Float(53))
    capital_cost = Column(Float(53))
    length = Column(Float(53))
    cables = Column(Integer)
    frequency = Column(Numeric)
    terrain_factor = Column(Float(53), server_default=text("1"))
    geom = Column(Geometry('MULTILINESTRING', 4326))
    topo = Column(Geometry('LINESTRING', 4326))


class WnAbwGridHvTransformer(Base):
    __tablename__ = 'wn_abw_grid_hv_transformer'
    __table_args__ = {'schema': 'windnode'}

    version = Column(Text, primary_key=True, nullable=False)
    scn_name = Column(String, primary_key=True, nullable=False, server_default=text("'Status Quo'::character varying"))
    trafo_id = Column(BigInteger, primary_key=True, nullable=False)
    bus0 = Column(BigInteger)
    bus1 = Column(BigInteger)
    x = Column(Numeric, server_default=text("0"))
    r = Column(Numeric, server_default=text("0"))
    g = Column(Numeric, server_default=text("0"))
    b = Column(Numeric, server_default=text("0"))
    s_nom = Column(Float(53), server_default=text("0"))
    s_nom_extendable = Column(Boolean, server_default=text("false"))
    s_nom_min = Column(Float(53), server_default=text("0"))
    s_nom_max = Column(Float(53))
    tap_ratio = Column(Float(53))
    phase_shift = Column(Float(53))
    capital_cost = Column(Float(53), server_default=text("0"))
    geom = Column(Geometry('MULTILINESTRING', 4326))
    topo = Column(Geometry('LINESTRING', 4326))
    geom_point = Column(Geometry('POINT', 4326))
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'))

    mun = relationship('WnAbwMun', back_populates='grid_hv_transformer')


class WnAbwGridHvmvSubstation(Base):
    __tablename__ = 'wn_abw_grid_hvmv_substation'
    __table_args__ = {'schema': 'windnode'}

    version = Column(Text, nullable=False)
    subst_id = Column(Integer, primary_key=True)
    lon = Column(Float(53))
    lat = Column(Float(53))
    point = Column(Geometry('POINT', 4326))
    polygon = Column(Geometry)
    voltage = Column(Text)
    power_type = Column(Text)
    substation = Column(Text)
    osm_id = Column(Text)
    osm_www = Column(Text)
    frequency = Column(Text)
    subst_name = Column(Text)
    ref = Column(Text)
    operator = Column(Text)
    dbahn = Column(Text)
    status = Column(SmallInteger)
    otg_id = Column(BigInteger)
    geom = Column(Geometry('POINT', 3035), index=True)

    mun = relationship('WnAbwMun', back_populates='grid_hvmv_substation')


class WnAbwGridMvGriddistrict(Base):
    __tablename__ = 'wn_abw_grid_mv_griddistrict'
    __table_args__ = {'schema': 'windnode'}

    version = Column(Text, nullable=False)
    subst_id = Column(Integer, primary_key=True)
    subst_sum = Column(Integer)
    type1 = Column(Integer)
    type1_cnt = Column(Integer)
    type2 = Column(Integer)
    type2_cnt = Column(Integer)
    type3 = Column(Integer)
    type3_cnt = Column(Integer)
    group = Column(String(1))
    gem = Column(Integer)
    gem_clean = Column(Integer)
    zensus_sum = Column(Integer)
    zensus_count = Column(Integer)
    zensus_density = Column(Numeric)
    population_density = Column(Numeric)
    la_count = Column(Integer)
    area_ha = Column(Numeric)
    la_area = Column(Numeric(10, 1))
    free_area = Column(Numeric(10, 1))
    area_share = Column(Numeric(4, 1))
    consumption = Column(Numeric)
    consumption_per_area = Column(Numeric)
    dea_cnt = Column(Integer)
    dea_capacity = Column(Numeric)
    lv_dea_cnt = Column(Integer)
    lv_dea_capacity = Column(Numeric)
    mv_dea_cnt = Column(Integer)
    mv_dea_capacity = Column(Numeric)
    geom_type = Column(Text)
    geom = Column(Geometry('MULTIPOLYGON', 3035), index=True)
    consumption_total = Column(Integer)


class WnAbwMun(Base):
    __tablename__ = 'wn_abw_mun'
    __table_args__ = {'schema': 'windnode'}

    geom = Column(Geometry('MULTIPOLYGON', 3035), nullable=False, index=True)
    ags = Column(Integer, primary_key=True)
    name = Column('gen', String(254), nullable=False)
    geom_centroid = Column(Geometry('POINT', 3035), index=True)

    demand_ts = relationship('WnAbwDemandTs', back_populates='mun')
    feedin_ts = relationship('WnAbwFeedinTs', back_populates='mun')
    temp_ts = relationship('WnAbwTempTs', back_populates='mun')
    grid_hv_bus = relationship('WnAbwGridHvBus', back_populates='mun')
    grid_hv_transformer = relationship('WnAbwGridHvTransformer', back_populates='mun')
    grid_hvmv_substation = relationship('WnAbwGridHvmvSubstation', back_populates='mun')
    mundata = relationship('WnAbwMundata', back_populates='mun', uselist=False)
    powerplant = relationship('WnAbwPowerplant', back_populates='mun')


class WnAbwMundata(Base):
    __tablename__ = 'wn_abw_mundata'
    __table_args__ = {'schema': 'windnode'}

    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), primary_key=True, nullable=False)
    area = Column(Float(53))
    gen_count_wind = Column(Float(53))
    gen_capacity_pv_roof_small = Column(Float(53))
    gen_count_pv_ground = Column(Float(53))
    gen_count_hydro = Column(Float(53))
    gen_count_bio = Column(Float(53))
    gen_count_sewage_landfill_gas = Column(Float(53))
    gen_capacity_wind = Column(Float(53))
    gen_capacity_pv_roof_large = Column(Float(53))
    gen_capacity_pv_ground = Column(Float(53))
    gen_capacity_hydro = Column(Float(53))
    gen_capacity_bio = Column(Float(53))
    gen_capacity_sewage_landfill_gas = Column(Float(53))
    gen_el_energy_wind = Column(Float(53))
    gen_el_energy_pv_roof = Column(Float(53))
    gen_el_energy_pv_ground = Column(Float(53))
    gen_el_energy_hydro = Column(Float(53))
    dem_el_energy_hh = Column(Float(53))
    dem_el_energy_rca = Column(Float(53))
    dem_el_energy_ind = Column(Float(53))
    dem_th_energy_hh = Column(Float(53))
    dem_th_energy_rca = Column(Float(53))
    dem_th_energy_ind = Column(Float(53))
    gen_count_pv_roof_large = Column(Float(53))
    gen_count_pv_roof_small = Column(Float(53))
    gen_capacity_storage = Column(Float(53))
    gen_count_storage = Column(Float(53))
    dem_el_peak_load_hh = Column(Float(53))
    dem_el_peak_load_ind = Column(Float(53))
    dem_el_peak_load_rca = Column(Float(53))
    dem_th_peak_load_hh = Column(Float(53))
    dem_th_peak_load_ind = Column(Float(53))
    dem_th_peak_load_rca = Column(Float(53))
    dem_th_energy_hh_efh = Column(Float(53))
    dem_th_energy_hh_efh_spec = Column(Float(53))
    dem_th_energy_hh_mfh = Column(Float(53))
    dem_th_energy_hh_mfh_spec = Column(Float(53))
    dem_th_energy_hh_per_capita = Column(Float(53))
    dem_th_energy_total_per_capita = Column(Float(53))
    total_living_space = Column(Float(53))
    reg_prio_area_wec_area = Column(Float(53))
    reg_prio_area_wec_count = Column(Integer)
    gen_el_energy_bio = Column(Float(53))
    gen_el_energy_conventional = Column(Float(53))
    gen_capacity_conventional_large = Column(Float(53))
    gen_capacity_conventional_small = Column(Float(53))
    gen_count_conventional_large = Column(Float(53))
    gen_count_conventional_small = Column(Float(53))

    mun = relationship('WnAbwMun', back_populates='mundata')


class WnAbwPowerplant(Base):
    __tablename__ = 'wn_abw_powerplant'
    __table_args__ = {'schema': 'windnode'}

    id = Column(BigInteger, primary_key=True)
    capacity = Column(Float(53))
    chp = Column(Text)
    com_month = Column(Float(53))
    com_year = Column(Float(53))
    comment = Column(Text)
    decom_month = Column(BigInteger)
    decom_year = Column(BigInteger)
    efficiency = Column(Float(53))
    energy_source_level_1 = Column(Text)
    energy_source_level_2 = Column(Text)
    energy_source_level_3 = Column(Text)
    geometry = Column(Geometry('POINT', 4326), index=True)
    state = Column(Text)
    technology = Column(Text)
    thermal_capacity = Column(Float(53))
    coastdat2 = Column(Float(53))
    capacity_in = Column(Float(53))
    federal_state = Column(Text)
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), nullable=False, index=True)

    mun = relationship('WnAbwMun', back_populates='powerplant')


class WnAbwRelSubstIdAgsId(Base):
    __tablename__ = 'wn_abw_rel_subst_id_ags_id'
    __table_args__ = {'schema': 'windnode'}

    id = Column(Integer, primary_key=True, server_default=text("nextval('windnode.wn_abw_rel_subst_id_ags_id_id_seq'::regclass)"))
    subst_id = Column(ForeignKey('windnode.wn_abw_grid_hvmv_substation.subst_id'))
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'))

    ags = relationship('WnAbwMun')
    subst = relationship('WnAbwGridHvmvSubstation')


class WnAbwHeatingStructure(Base):
    __tablename__ = 'wn_abw_heating_structure'
    __table_args__ = {'schema': 'windnode'}

    year = Column(BigInteger, primary_key=True, nullable=False, index=True)
    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), primary_key=True, nullable=False, index=True)
    energy_source = Column(Text, primary_key=True, nullable=False, index=True)
    tech_share_hh_efh = Column(Float(53))
    tech_share_hh_mfh = Column(Float(53))
    tech_share_rca = Column(Float(53))

    ags = relationship('WnAbwMun', back_populates='heating_structure')


class WnAbwTechAssumptions(Base):
    """Technical assumptions: costs, emissions, efficiency

    Units see column type below.

    Attributes
    ----------
    technology : :class:`sqlalchemy.sql.schema.Column`
        Id of technology
    technology_name : :class:`sqlalchemy.sql.schema.Column`
        Full German name of technology
    year : :class:`sqlalchemy.sql.schema.Column`
        Year
    capex : :class:`sqlalchemy.sql.schema.Column`
        CAPEX in EUR/kw
    opex_fix : :class:`sqlalchemy.sql.schema.Column`
        Fixed OPEX in EUR/(kWh*a), apples to systems only
    opex_var : :class:`sqlalchemy.sql.schema.Column`
        Variable OPEX in EUR/kWh, apples to systems only
    lifespan : :class:`sqlalchemy.sql.schema.Column`
        Expected lifespan in years, apples to systems only
    emissions_var : :class:`sqlalchemy.sql.schema.Column`
        Variable (energy-specific) supply chain emissions in kg/MWh
    emissions_fix : :class:`sqlalchemy.sql.schema.Column`
        Fixed (power-specific) supply chain emissions in kg/MW
    sys_eff : :class:`sqlalchemy.sql.schema.Column`
        Annual system efficiency, apples to systems only
    """
    __tablename__ = 'wn_abw_tech_assumptions'
    __table_args__ = {'schema': 'windnode'}

    technology = Column(Text, primary_key=True, nullable=False, index=True)
    year = Column(BigInteger, primary_key=True, nullable=False, index=True)
    technology_name = Column(Text)
    capex = Column(Float(53))
    opex_fix = Column(Float(53))
    opex_var = Column(Float(53))
    lifespan = Column(BigInteger)
    emissions_var = Column(Float(53))
    emissions_fix = Column(Float(53))
    sys_eff = Column(Float(53))


class WnAbwPotentialAreasPv(Base):
    """Potential areas for ground-mounted PV plants

    Attributes
    ----------
    ags_id : :class:`sqlalchemy.sql.schema.Column`
        AGS of municipality
    scenario : :class:`sqlalchemy.sql.schema.Column`
        Scenario (e.g. 'bab_hs' for areas around highways including
        areas being subject to hard and light restrictions)
    area_ha : :class:`sqlalchemy.sql.schema.Column`
        Potential area in ha
    geom : :class:`sqlalchemy.sql.schema.Column`
        Geometry (polygons, EPSG:3035)
    """
    __tablename__ = 'wn_abw_potential_areas_pv'
    __table_args__ = {'schema': 'windnode'}

    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), primary_key=True, nullable=False)
    scenario = Column(String, primary_key=True, nullable=False)
    area_ha = Column(BigInteger)
    geom = Column(Geometry('MULTIPOLYGON', 3035), index=True)

    ags = relationship('WnAbwMun')


class WnAbwPotentialAreasPvRoof(Base):
    __tablename__ = 'wn_abw_potential_areas_pv_roof'
    __table_args__ = {'schema': 'windnode'}

    ags_id = Column(Integer, primary_key=True)
    area_resid_ha = Column(Float(53))
    area_ind_ha = Column(Float(53))

    ags = relationship('WnAbwMun')

class WnAbwPotentialAreasWec(Base):
    """Potential areas for wind turbines

    Attributes
    ----------
    ags_id : :class:`sqlalchemy.sql.schema.Column`
        AGS of municipality
    scenario : :class:`sqlalchemy.sql.schema.Column`
        Scenario
        (e.g. 's500f0' for 500m distance to settlements, do not use forests)
    area_ha : :class:`sqlalchemy.sql.schema.Column`
        Potential area in ha
    geom : :class:`sqlalchemy.sql.schema.Column`
        Geometry (polygons, EPSG:3035)
    """
    __tablename__ = 'wn_abw_potential_areas_wec'
    __table_args__ = {'schema': 'windnode'}

    ags_id = Column(ForeignKey('windnode.wn_abw_mun.ags'), primary_key=True, nullable=False)
    scenario = Column(String, primary_key=True, nullable=False)
    area_ha = Column(BigInteger)
    geom = Column(Geometry('MULTIPOLYGON', 3035), index=True)

    ags = relationship('WnAbwMun')


class WnAbwDemography(Base):
    __tablename__ = 'wn_abw_demography'
    __table_args__ = {'schema': 'windnode'}

    ags_id = Column(Integer, primary_key=True, nullable=False)
    year = Column(Integer, primary_key=True, nullable=False)
    population = Column(Integer)
    employees = Column(Integer)

    ags = relationship('WnAbwMun')

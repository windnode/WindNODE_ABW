import logging
logger = logging.getLogger('windnode_abw')
from windnode_abw.tools import config

import os
import requests
import pandas as pd
import keyring


def oep_get_token():
    """Read token (password) from system's keyring

    Returns
    -------
    :obj:`str`
        Token
    """
    service = 'OEP'
    user = 'token'

    token = keyring.get_password(service, user)

    if token:
        return token
    else:
        raise ValueError('No token found in keyring!')


def oep_api_get_data(schema, table, columns=[], conditions=[], order=''):
    """Retrieve data from Open Energy Platform (OEP) / Database

    Parameters
    ----------
    schema : :obj:`str`
        Database schema
    table : :obj:`str`
        Database table
    columns : :obj:`list` of :obj:`str`
        Table columns
    conditions : :obj:`list` of :obj:`str`
        Conditions to be applied on query
    order : :obj:`str`
        Column which data is sorted by (ascending)

    Returns
    -------
    :pandas:`pandas.DataFrame<dataframe>`
        Requested data
    """

    oep_url = config.get('data', 'oep_url')

    if not schema or not table:
        raise ValueError('Schema or table not specified.')

    columns = '&'.join('column='+col for col in columns)

    if conditions:
        conditions = '&' + '&'.join('where='+cond for cond in conditions)
    else:
        conditions = ''

    if order:
        order = '&order_by=' + order
    else:
        order = ''

    url = oep_url +\
          '/api/v0/schema/' +\
          schema +\
          '/tables/' +\
          table +\
          '/rows/?' + \
          columns +\
          conditions +\
          order

    result = requests.get(url)
    status = str(result.status_code)

    logger.info('Response from OEP: ' + status + ', elapsed time: ' + str(result.elapsed))
    if status != '200':
        logger.exception('Something went wrong during data retrieval from OEP: ')

    return pd.DataFrame(result.json())


def oep_api_write_data(schema, table, data):
    """Write datasets to a table on the Open Energy Platform (OEP) / Database

    Parameters
    ----------
    schema : :obj:`str`
        Database schema
    table : :obj:`str`
        Database table
    data : :pandas:`pandas.DataFrame<dataframe>`
        Data to be written. Column names of DataFrame have to equal column names of table.
        Note: If data involves geometries, they must follow WKB format.

    Returns
    -------
    :pandas:`pandas.DataFrame<dataframe>`
        Response, such as ids of inserted data
    """

    oep_url = config.get('data', 'oep_url')

    if not schema or not table:
        raise ValueError('Schema or table not specified.')

    url = oep_url +\
          '/api/v0/schema/' +\
          schema +\
          '/tables/' +\
          table +\
          '/rows/new'

    dataset = data.to_dict('records')

    # dataset = []
    # for idx, row in data.iterrows():
    #     dataset.append({'subst_id0': str(row['hvmv_subst_id0']),
    #                     'subst_id1': str(row['hvmv_subst_id1']),
    #                     'capacity': str(row['s_nom'])})
    #
    # dataset = {'id': 1, 'subst_id0': 1,
    #            'subst_id1': 2, 'capacity': 100}

    result = requests.post(url,
                           json={'query': dataset},
                           headers={'Authorization': 'Token %s'%oep_get_token()})
    status = str(result.status_code)

    logger.info('Response from OEP: ' + status + ', elapsed time: ' + str(result.elapsed))
    if status != '200':
        logger.exception('Something went wrong during data retrieval from OEP: ')

    return pd.DataFrame(result.json())


def 


def oemof_nodes_from_excel(filename, header_lines=0):
    """

    Parameters
    ----------
    filename : :obj:`str`
        Path to excel file

    Returns
    -------
    :obj:`dict`
        Imported nodes data
    """
    # excel file does not exist
    if not filename or not os.path.isfile(filename):
        logger.exception('Excel data file {} not found.'
                         .format(filename))

    xls = pd.ExcelFile(filename)

    nodes_data = {'buses': xls.parse('buses', header=header_lines),
                  'chp': xls.parse('chp', header=header_lines),
                  'commodity_sources': xls.parse('commodity_sources', header=header_lines),
                  'transformers': xls.parse('transformers', header=header_lines),
                  'renewables': xls.parse('renewables', header=header_lines),
                  'demand': xls.parse('demand', header=header_lines),
                  'storages': xls.parse('storages', header=header_lines),
                  'powerlines': xls.parse('powerlines', header=header_lines),
                  'timeseries': xls.parse('time_series', header=header_lines)
                  }

    logger.info('Data from Excel file {} imported.'
                .format(filename))

    return nodes_data

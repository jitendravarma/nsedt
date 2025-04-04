""" 
get data for Equity
"""
import concurrent
import datetime
import logging
import urllib
from concurrent.futures import ALL_COMPLETED

import pandas as pd

from nsedt import utils
from nsedt.resources import constants as cns

from nsedt.utils import data_format

log = logging.getLogger("root")


def get_companyinfo(
    symbol: str,
    response_type: str = "panda_df",
):
    """get_companyinfo

    Args:\n
        symbol (str): stock name\n
        response_type (str, Optional): define the response type panda_df | json. Default panda_df\n
    Returns:\n
        Pandas DataFrame: df containing company info\n
      or\n
        Json: json containing company info\n
    """

    params = {}
    cookies = utils.get_cookies()
    base_url = cns.BASE_URL
    event_api = cns.EQUITY_INFO

    params["symbol"] = symbol

    url = base_url + event_api + urllib.parse.urlencode(params)
    data = utils.fetch_url(
        url,
        cookies,
        key=None,
        response_type=response_type,
    )

    return data


def get_marketstatus(
    response_type: str = "panda_df",
):
    """
    Args:\n
        response_type (str, Optional): define the response type panda_df | json. Default panda_df\n
    Returns:\n
        Pandas DataFrame: df containing market status\n
        Json : Json containing market status\n
    """

    cookies = utils.get_cookies()
    base_url = cns.BASE_URL
    event_api = cns.MARKETSTATUS

    url = base_url + event_api
    data = utils.fetch_url(
        url,
        cookies,
        key="marketState",
        response_type=response_type,
    )

    return data


def get_price(
    start_date,
    end_date,
    symbol=None,
    input_type="stock",
    series="EQ",
):
    """
    Create threads for different requests, parses data, combines them and returns dataframe\n
    Args:\n
        start_date (datetime.datetime): start date\n
        end_date (datetime.datetime): end date\n
        input_type (str): Either 'stock' or 'index'\n
        symbol (str, optional): stock symbol. Defaults to None. TODO: implement for index`\n
    Returns:\n
        Pandas DataFrame: df containing data for symbol of provided date range\n
    """
    cookies = utils.get_cookies()
    base_url = cns.BASE_URL
    price_api = cns.EQUITY_PRICE_HISTORY
    url_list = []

    # set the window size to one year
    window_size = datetime.timedelta(days=cns.WINDOW_SIZE)

    start_date, end_date = utils.check_nd_convert(start_date, end_date)

    current_window_start = start_date
    while current_window_start < end_date:
        current_window_end = current_window_start + window_size

        # check if the current window extends beyond the end_date
        current_window_end = min(current_window_end, end_date)

        if input_type == "stock":
            params = {
                "from": current_window_start.strftime("%d-%m-%Y"),
                "to": current_window_end.strftime("%d-%m-%Y"),
                "symbol": symbol,
                "dataType": "priceVolumeDeliverable",
                "series": series,
            }
            url = base_url + price_api + urllib.parse.urlencode(params)
            url_list.append(url)

        # move the window start to the next day after the current window end
        current_window_start = current_window_end + datetime.timedelta(days=1)

    result = pd.DataFrame()
    with concurrent.futures.ThreadPoolExecutor(max_workers=cns.MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(utils.fetch_url, url, cookies, "data"): url
            for url in url_list
        }
        concurrent.futures.wait(future_to_url, return_when=ALL_COMPLETED)
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                dataframe = future.result()
                result = pd.concat([result, dataframe])
            except Exception as exc:
                logging.error("%s got exception: %s. Please try again later.", url, exc)
                raise exc
    return data_format.price(result)


def get_corpinfo(
    start_date,
    end_date,
    symbol=None,
    response_type="panda_df",
):
    """
    Create threads for different requests, parses data, combines them and returns dataframe\n
    Args:\n
        start_date (datetime.datetime): start date\n
        end_date (datetime.datetime): end date\n
        symbol (str, optional): stock symbol. Defaults to None.\n
    Returns:\n
        Pandas DataFrame: df containing data for symbol of provided date range\n
      or\n
        Json: json containing data for symbol of provided date range\n
    """
    cookies = utils.get_cookies()
    params = {
        "symbol": symbol,
        "from_date": start_date,
        "to_date": end_date,
        "index": "equities",
    }
    base_url = cns.BASE_URL
    price_api = cns.EQUITY_CORPINFO
    url = base_url + price_api + urllib.parse.urlencode(params)

    data = utils.fetch_url(
        url,
        cookies,
        key=None,
        response_type=response_type,
    )

    return data


def get_event(
    start_date=None,
    end_date=None,
    index="equities",
):
    """
    Args:\n
        start_date (datetime.datetime,optional): start date\n
        end_date (datetime.datetime,optional): end date\n
    Returns:\n
        Pandas DataFrame: df containing event of provided date range\n
    """
    params = {}
    cookies = utils.get_cookies()
    base_url = cns.BASE_URL
    event_api = cns.EQUITY_EVENT

    params["index"] = index
    if start_date is not None:
        params["from_date"] = start_date
    if end_date is not None:
        params["to_date"] = end_date

    url = base_url + event_api + urllib.parse.urlencode(params)
    return utils.fetch_url(url, cookies)


def get_chartdata(
    symbol,
    preopen=False,
    response_type="panda_df",
):
    """
    Args:\n
        symbol (str): stock symbol.\n
    Returns:\n
        Pandas DataFrame: df containing chart data of provided date\n
    """
    params = {}
    cookies = utils.get_cookies()
    base_url = cns.BASE_URL
    event_api = cns.EQUITY_CHART
    try:
        identifier = get_companyinfo(
            symbol,
            response_type="json",
        )[
            "info"
        ]["identifier"]

    except KeyError:
        return f"Invalid symbol name: {symbol}"

    params["index"] = identifier
    if preopen:
        params["preopen"] = "true"

    url = base_url + event_api + urllib.parse.urlencode(params)

    data = utils.fetch_url(
        url,
        cookies,
        key="grapthData",
        response_type=response_type,
    )
    if response_type == "panda_df":
        data_frame = data.rename(
            columns={
                0: "timestamp_milliseconds",
                1: "price",
            }
        )
        data_frame["datetime"] = pd.to_datetime(
            data_frame["timestamp_milliseconds"], unit="ms"
        )
        return data_frame
    return data


def get_symbols_list():
    """
    Args:\n
        No arguments needed\n
    Returns:\n
        List of stock or equity symbols\n
    """
    cookies = utils.get_cookies()
    base_url = cns.BASE_URL
    event_api = cns.EQUITY_LIST

    url = base_url + event_api
    data = utils.fetch_url(url, cookies)
    f_dict = data.to_dict()
    eq_list = []
    for i in range(len(f_dict["data"])):
        eq_list.append(f_dict["data"][i]["metadata"]["symbol"])

    return eq_list


def get_asm_list(asm_type="both") -> list:
    """
        Args:\n
            asm_type (str): ASM type, possible values: both,longterm,shortterm\n
        Returns:\n
            List of stocks under ASM\n
    """
    cookies = utils.get_cookies()
    base_url = cns.BASE_URL
    event_api = cns.ASM_LIST

    url = base_url + event_api
    data = utils.fetch_url(url, cookies)
    _data = data.to_dict()

    if asm_type ==  "both":
        return _data
    if asm_type == "longterm":
        return _data.get("longterm").get("data")
    if asm_type == "shortterm":
        return _data.get("shortterm").get("data")
    return ["possible values are both,longterm,shortterm"]

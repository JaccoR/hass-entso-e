from __future__ import annotations

import enum
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Union

import pytz
import requests

_LOGGER = logging.getLogger(__name__)
URL = "https://web-api.tp.entsoe.eu/api"
DATETIMEFORMAT = "%Y%m%d%H00"


class EntsoeClient:

    def __init__(self, api_key: str):
        if api_key == "":
            raise TypeError("API key cannot be empty")
        self.api_key = api_key

    def _base_request(
        self, params: Dict, start: datetime, end: datetime
    ) -> requests.Response:

        base_params = {
            "securityToken": self.api_key,
            "periodStart": start.strftime(DATETIMEFORMAT),
            "periodEnd": end.strftime(DATETIMEFORMAT),
        }
        params.update(base_params)

        _LOGGER.debug(f"Performing request to {URL} with params {params}")
        response = requests.get(url=URL, params=params)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        return response

    def _remove_namespace(self, tree):
        """Remove namespaces in the passed XML tree for easier tag searching."""
        for elem in tree.iter():
            # Remove the namespace if present
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]
        return tree

    def query_day_ahead_prices(
        self, country_code: Union[Area, str], start: datetime, end: datetime
    ) -> str:
        """
        Parameters
        ----------
        country_code : Area|str
        start : datetime
        end : datetime

        Returns
        -------
        str
        """
        area = Area[country_code.upper()]
        params = {
            "documentType": "A44",
            "in_Domain": area.code,
            "out_Domain": area.code,
        }
        response = self._base_request(params=params, start=start, end=end)

        if response.status_code == 200:
            try:
                series = self.parse_price_document(response.content)
                return dict(sorted(series.items()))

            except Exception as exc:
                _LOGGER.debug(f"Failed to parse response content:{response.content}")
                raise exc
        else:
            print(f"Failed to retrieve data: {response.status_code}")
            return None

    # lets process the received document
    def parse_price_document(self, document: str) -> str:

        root = self._remove_namespace(ET.fromstring(document))
        _LOGGER.debug(f"content: {root}")
        series = {}

        # for all given timeseries in this response
        # There may be overlapping times in the repsonse. For now we skip timeseries which we already processed
        for timeseries in root.findall(".//TimeSeries"):

            # for all periods in this timeseries.....-> we still asume the time intervals do not overlap, and are in sequence
            for period in timeseries.findall(".//Period"):
                # there can be different resolutions for each period (BE casus in which historical is quarterly and future is hourly)
                resolution = period.find(".//resolution").text

                # for now supporting 60 and 15 minutes resolutions (ISO8601 defined)
                if resolution == "PT60M" or resolution == "PT1H":
                    resolution = "PT60M"
                elif resolution != "PT15M":
                    continue

                response_start = period.find(".//timeInterval/start").text
                start_time = (
                    datetime.strptime(response_start, "%Y-%m-%dT%H:%MZ")
                    .replace(tzinfo=pytz.UTC)
                    .astimezone()
                )
                start_time.replace(minute=0)  # ensure we start from the whole hour

                response_end = period.find(".//timeInterval/end").text
                end_time = (
                    datetime.strptime(response_end, "%Y-%m-%dT%H:%MZ")
                    .replace(tzinfo=pytz.UTC)
                    .astimezone()
                )
                _LOGGER.debug(
                    f"Period found is from {start_time} till {end_time} with resolution {resolution}"
                )
                if start_time in series:
                    _LOGGER.debug(
                        "We found a duplicate period in the response, possibly with another resolution. We skip this period"
                    )
                    continue

                if resolution == "PT60M":
                    series.update(self.process_PT60M_points(period, start_time))
                else:
                    series.update(self.process_PT15M_points(period, start_time))

                # Now fill in any missing hours
                current_time = start_time
                last_price = series[current_time]

                while current_time < end_time:  # upto excluding! the endtime
                    if current_time in series:
                        last_price = series[current_time]  # Update to the current price
                    else:
                        _LOGGER.debug(
                            f"Extending the price {last_price} of the previous hour to {current_time}"
                        )
                        series[current_time] = (
                            last_price  # Fill with the last known price
                        )
                    current_time += timedelta(hours=1)

        return series

    # processing hourly prices info -> thats easy
    def process_PT60M_points(self, period: Element, start_time: datetime):
        data = {}
        for point in period.findall(".//Point"):
            position = point.find(".//position").text
            price = point.find(".//price.amount").text
            hour = int(position) - 1
            time = start_time + timedelta(hours=hour)
            data[time] = float(price)
        return data

    # processing quarterly prices -> this is more complex
    def process_PT15M_points(self, period: Element, start_time: datetime):
        positions = {}

        # first store all positions
        for point in period.findall(".//Point"):
            position = point.find(".//position").text
            price = point.find(".//price.amount").text
            positions[int(position)] = float(price)

        # now calculate hourly averages based on available points
        data = {}
        last_hour = (max(positions.keys()) + 3) // 4
        last_price = 0

        for hour in range(last_hour):
            sum_prices = 0
            for idx in range(hour * 4 + 1, hour * 4 + 5):
                last_price = positions.get(idx, last_price)
                sum_prices += last_price

            time = start_time + timedelta(hours=hour)
            data[time] = round(sum_prices / 4, 2)

        return data


class Area(enum.Enum):
    """
    ENUM containing 3 things about an Area: CODE, Meaning, Timezone
    """

    def __new__(cls, *args, **kwds):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    # ignore the first param since it's already set by __new__
    def __init__(self, _: str, meaning: str, tz: str):
        self._meaning = meaning
        self._tz = tz

    def __str__(self):
        return self.value

    @property
    def meaning(self):
        return self._meaning

    @property
    def tz(self):
        return self._tz

    @property
    def code(self):
        return self.value

    @classmethod
    def has_code(cls, code: str) -> bool:
        return code in cls.__members__

    # List taken directly from the API Docs
    DE_50HZ = (
        "10YDE-VE-------2",
        "50Hertz CA, DE(50HzT) BZA",
        "Europe/Berlin",
    )
    AL = (
        "10YAL-KESH-----5",
        "Albania, OST BZ / CA / MBA",
        "Europe/Tirane",
    )
    DE_AMPRION = (
        "10YDE-RWENET---I",
        "Amprion CA",
        "Europe/Berlin",
    )
    AT = (
        "10YAT-APG------L",
        "Austria, APG BZ / CA / MBA",
        "Europe/Vienna",
    )
    BY = (
        "10Y1001A1001A51S",
        "Belarus BZ / CA / MBA",
        "Europe/Minsk",
    )
    BE = (
        "10YBE----------2",
        "Belgium, Elia BZ / CA / MBA",
        "Europe/Brussels",
    )
    BA = (
        "10YBA-JPCC-----D",
        "Bosnia Herzegovina, NOS BiH BZ / CA / MBA",
        "Europe/Sarajevo",
    )
    BG = (
        "10YCA-BULGARIA-R",
        "Bulgaria, ESO BZ / CA / MBA",
        "Europe/Sofia",
    )
    CZ_DE_SK = (
        "10YDOM-CZ-DE-SKK",
        "BZ CZ+DE+SK BZ / BZA",
        "Europe/Prague",
    )
    HR = (
        "10YHR-HEP------M",
        "Croatia, HOPS BZ / CA / MBA",
        "Europe/Zagreb",
    )
    CWE = (
        "10YDOM-REGION-1V",
        "CWE Region",
        "Europe/Brussels",
    )
    CY = (
        "10YCY-1001A0003J",
        "Cyprus, Cyprus TSO BZ / CA / MBA",
        "Asia/Nicosia",
    )
    CZ = (
        "10YCZ-CEPS-----N",
        "Czech Republic, CEPS BZ / CA/ MBA",
        "Europe/Prague",
    )
    DE_AT_LU = (
        "10Y1001A1001A63L",
        "DE-AT-LU BZ",
        "Europe/Berlin",
    )
    DE_LU = (
        "10Y1001A1001A82H",
        "DE-LU BZ / MBA",
        "Europe/Berlin",
    )
    DK = (
        "10Y1001A1001A65H",
        "Denmark",
        "Europe/Copenhagen",
    )
    DK_1 = (
        "10YDK-1--------W",
        "DK1 BZ / MBA",
        "Europe/Copenhagen",
    )
    DK_1_NO_1 = (
        "46Y000000000007M",
        "DK1 NO1 BZ",
        "Europe/Copenhagen",
    )
    DK_2 = (
        "10YDK-2--------M",
        "DK2 BZ / MBA",
        "Europe/Copenhagen",
    )
    DK_CA = (
        "10Y1001A1001A796",
        "Denmark, Energinet CA",
        "Europe/Copenhagen",
    )
    EE = (
        "10Y1001A1001A39I",
        "Estonia, Elering BZ / CA / MBA",
        "Europe/Tallinn",
    )
    FI = (
        "10YFI-1--------U",
        "Finland, Fingrid BZ / CA / MBA",
        "Europe/Helsinki",
    )
    MK = (
        "10YMK-MEPSO----8",
        "Former Yugoslav Republic of Macedonia, MEPSO BZ / CA / MBA",
        "Europe/Skopje",
    )
    FR = (
        "10YFR-RTE------C",
        "France, RTE BZ / CA / MBA",
        "Europe/Paris",
    )
    DE = "10Y1001A1001A83F", "Germany", "Europe/Berlin"
    GR = (
        "10YGR-HTSO-----Y",
        "Greece, IPTO BZ / CA/ MBA",
        "Europe/Athens",
    )
    HU = (
        "10YHU-MAVIR----U",
        "Hungary, MAVIR CA / BZ / MBA",
        "Europe/Budapest",
    )
    IS = (
        "IS",
        "Iceland",
        "Atlantic/Reykjavik",
    )
    IE_SEM = (
        "10Y1001A1001A59C",
        "Ireland (SEM) BZ / MBA",
        "Europe/Dublin",
    )
    IE = (
        "10YIE-1001A00010",
        "Ireland, EirGrid CA",
        "Europe/Dublin",
    )
    IT = (
        "10YIT-GRTN-----B",
        "Italy, IT CA / MBA",
        "Europe/Rome",
    )
    IT_SACO_AC = (
        "10Y1001A1001A885",
        "Italy_Saco_AC",
        "Europe/Rome",
    )
    IT_CALA = (
        "10Y1001C--00096J",
        "IT-Calabria BZ",
        "Europe/Rome",
    )
    IT_SACO_DC = (
        "10Y1001A1001A893",
        "Italy_Saco_DC",
        "Europe/Rome",
    )
    IT_BRNN = (
        "10Y1001A1001A699",
        "IT-Brindisi BZ",
        "Europe/Rome",
    )
    IT_CNOR = (
        "10Y1001A1001A70O",
        "IT-Centre-North BZ",
        "Europe/Rome",
    )
    IT_CSUD = (
        "10Y1001A1001A71M",
        "IT-Centre-South BZ",
        "Europe/Rome",
    )
    IT_FOGN = (
        "10Y1001A1001A72K",
        "IT-Foggia BZ",
        "Europe/Rome",
    )
    IT_GR = (
        "10Y1001A1001A66F",
        "IT-GR BZ",
        "Europe/Rome",
    )
    IT_MACRO_NORTH = (
        "10Y1001A1001A84D",
        "IT-MACROZONE NORTH MBA",
        "Europe/Rome",
    )
    IT_MACRO_SOUTH = (
        "10Y1001A1001A85B",
        "IT-MACROZONE SOUTH MBA",
        "Europe/Rome",
    )
    IT_MALTA = (
        "10Y1001A1001A877",
        "IT-Malta BZ",
        "Europe/Rome",
    )
    IT_NORD = (
        "10Y1001A1001A73I",
        "IT-North BZ",
        "Europe/Rome",
    )
    IT_NORD_AT = (
        "10Y1001A1001A80L",
        "IT-North-AT BZ",
        "Europe/Rome",
    )
    IT_NORD_CH = (
        "10Y1001A1001A68B",
        "IT-North-CH BZ",
        "Europe/Rome",
    )
    IT_NORD_FR = (
        "10Y1001A1001A81J",
        "IT-North-FR BZ",
        "Europe/Rome",
    )
    IT_NORD_SI = (
        "10Y1001A1001A67D",
        "IT-North-SI BZ",
        "Europe/Rome",
    )
    IT_PRGP = (
        "10Y1001A1001A76C",
        "IT-Priolo BZ",
        "Europe/Rome",
    )
    IT_ROSN = (
        "10Y1001A1001A77A",
        "IT-Rossano BZ",
        "Europe/Rome",
    )
    IT_SARD = (
        "10Y1001A1001A74G",
        "IT-Sardinia BZ",
        "Europe/Rome",
    )
    IT_SICI = (
        "10Y1001A1001A75E",
        "IT-Sicily BZ",
        "Europe/Rome",
    )
    IT_SUD = (
        "10Y1001A1001A788",
        "IT-South BZ",
        "Europe/Rome",
    )
    RU_KGD = (
        "10Y1001A1001A50U",
        "Kaliningrad BZ / CA / MBA",
        "Europe/Kaliningrad",
    )
    LV = (
        "10YLV-1001A00074",
        "Latvia, AST BZ / CA / MBA",
        "Europe/Riga",
    )
    LT = (
        "10YLT-1001A0008Q",
        "Lithuania, Litgrid BZ / CA / MBA",
        "Europe/Vilnius",
    )
    LU = (
        "10YLU-CEGEDEL-NQ",
        "Luxembourg, CREOS CA",
        "Europe/Luxembourg",
    )
    LU_BZN = (
        "10Y1001A1001A82H",
        "Luxembourg",
        "Europe/Luxembourg",
    )
    MT = (
        "10Y1001A1001A93C",
        "Malta, Malta BZ / CA / MBA",
        "Europe/Malta",
    )
    ME = (
        "10YCS-CG-TSO---S",
        "Montenegro, CGES BZ / CA / MBA",
        "Europe/Podgorica",
    )
    GB = (
        "10YGB----------A",
        "National Grid BZ / CA/ MBA",
        "Europe/London",
    )
    GE = (
        "10Y1001A1001B012",
        "Georgia",
        "Asia/Tbilisi",
    )
    GB_IFA = (
        "10Y1001C--00098F",
        "GB(IFA) BZN",
        "Europe/London",
    )
    GB_IFA2 = (
        "17Y0000009369493",
        "GB(IFA2) BZ",
        "Europe/London",
    )
    GB_ELECLINK = (
        "11Y0-0000-0265-K",
        "GB(ElecLink) BZN",
        "Europe/London",
    )
    UK = (
        "10Y1001A1001A92E",
        "United Kingdom",
        "Europe/London",
    )
    NL = (
        "10YNL----------L",
        "Netherlands, TenneT NL BZ / CA/ MBA",
        "Europe/Amsterdam",
    )
    NO_1 = (
        "10YNO-1--------2",
        "NO1 BZ / MBA",
        "Europe/Oslo",
    )
    NO_1A = (
        "10Y1001A1001A64J",
        "NO1 A BZ",
        "Europe/Oslo",
    )
    NO_2 = (
        "10YNO-2--------T",
        "NO2 BZ / MBA",
        "Europe/Oslo",
    )
    NO_2_NSL = (
        "50Y0JVU59B4JWQCU",
        "NO2 NSL BZ / MBA",
        "Europe/Oslo",
    )
    NO_2A = (
        "10Y1001C--001219",
        "NO2 A BZ",
        "Europe/Oslo",
    )
    NO_3 = (
        "10YNO-3--------J",
        "NO3 BZ / MBA",
        "Europe/Oslo",
    )
    NO_4 = (
        "10YNO-4--------9",
        "NO4 BZ / MBA",
        "Europe/Oslo",
    )
    NO_5 = (
        "10Y1001A1001A48H",
        "NO5 BZ / MBA",
        "Europe/Oslo",
    )
    NO = (
        "10YNO-0--------C",
        "Norway, Norway MBA, Stattnet CA",
        "Europe/Oslo",
    )
    PL_CZ = (
        "10YDOM-1001A082L",
        "PL-CZ BZA / CA",
        "Europe/Warsaw",
    )
    PL = (
        "10YPL-AREA-----S",
        "Poland, PSE SA BZ / BZA / CA / MBA",
        "Europe/Warsaw",
    )
    PT = (
        "10YPT-REN------W",
        "Portugal, REN BZ / CA / MBA",
        "Europe/Lisbon",
    )
    MD = (
        "10Y1001A1001A990",
        "Republic of Moldova, Moldelectica BZ/CA/MBA",
        "Europe/Chisinau",
    )
    RO = (
        "10YRO-TEL------P",
        "Romania, Transelectrica BZ / CA/ MBA",
        "Europe/Bucharest",
    )
    RU = (
        "10Y1001A1001A49F",
        "Russia BZ / CA / MBA",
        "Europe/Moscow",
    )
    SE_1 = (
        "10Y1001A1001A44P",
        "SE1 BZ / MBA",
        "Europe/Stockholm",
    )
    SE_2 = (
        "10Y1001A1001A45N",
        "SE2 BZ / MBA",
        "Europe/Stockholm",
    )
    SE_3 = (
        "10Y1001A1001A46L",
        "SE3 BZ / MBA",
        "Europe/Stockholm",
    )
    SE_4 = (
        "10Y1001A1001A47J",
        "SE4 BZ / MBA",
        "Europe/Stockholm",
    )
    RS = (
        "10YCS-SERBIATSOV",
        "Serbia, EMS BZ / CA / MBA",
        "Europe/Belgrade",
    )
    SK = (
        "10YSK-SEPS-----K",
        "Slovakia, SEPS BZ / CA / MBA",
        "Europe/Bratislava",
    )
    SI = (
        "10YSI-ELES-----O",
        "Slovenia, ELES BZ / CA / MBA",
        "Europe/Ljubljana",
    )
    GB_NIR = (
        "10Y1001A1001A016",
        "Northern Ireland, SONI CA",
        "Europe/Belfast",
    )
    ES = (
        "10YES-REE------0",
        "Spain, REE BZ / CA / MBA",
        "Europe/Madrid",
    )
    SE = (
        "10YSE-1--------K",
        "Sweden, Sweden MBA, SvK CA",
        "Europe/Stockholm",
    )
    CH = (
        "10YCH-SWISSGRIDZ",
        "Switzerland, Swissgrid BZ / CA / MBA",
        "Europe/Zurich",
    )
    DE_TENNET = (
        "10YDE-EON------1",
        "TenneT GER CA",
        "Europe/Berlin",
    )
    DE_TRANSNET = (
        "10YDE-ENBW-----N",
        "TransnetBW CA",
        "Europe/Berlin",
    )
    TR = (
        "10YTR-TEIAS----W",
        "Turkey BZ / CA / MBA",
        "Europe/Istanbul",
    )
    UA = (
        "10Y1001C--00003F",
        "Ukraine, Ukraine BZ, MBA",
        "Europe/Kiev",
    )
    UA_DOBTPP = (
        "10Y1001A1001A869",
        "Ukraine-DobTPP CTA",
        "Europe/Kiev",
    )
    UA_BEI = (
        "10YUA-WEPS-----0",
        "Ukraine BEI CTA",
        "Europe/Kiev",
    )
    UA_IPS = (
        "10Y1001C--000182",
        "Ukraine IPS CTA",
        "Europe/Kiev",
    )
    XK = (
        "10Y1001C--00100H",
        "Kosovo/ XK CA / XK BZN",
        "Europe/Rome",
    )
    DE_AMP_LU = "10Y1001C--00002H", "Amprion LU CA", "Europe/Berlin"

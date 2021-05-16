"""Main module."""
from enum import Enum
import json
from qgis.core import QgsMessageLog, QgsBlockingNetworkRequest, Qgis
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtCore import QUrl
import urllib.parse
from osgeo import ogr

SERVICE_ENDPOINT = "https://geodata.nationaalgeoregister.nl/locatieserver/v3"
PLUGIN_NAME = "pdokservices-plugin"


class Projection(Enum):
    def __str__(self):
        return str(self.value)

    EPSG_4326 = "EPSG:4326"
    EPSG_28992 = "EPSG:28992"


class TypeFilterQuery:
    class LsType(Enum):
        provincie = "provincie"
        gemeente = "gemeente"
        woonplaats = "woonplaats"
        weg = "weg"
        postcode = "postcode"
        adres = "adres"
        perceel = "perceel"
        hectometerpaal = "hectometerpaal"
        wijk = "wijk"
        buurt = "buurt"
        waterschapsgrens = "waterschapsgrens"
        appartementsrecht = "appartementsrecht"

    def __init__(self, filter_types: "list[LsType]" = []):
        if len(filter_types) == 0:
            filter_types = list(map(lambda x: self.LsType[x.value], self.LsType))
        self.filter_types = filter_types

    def __str__(self):
        filter_types_str = list(map(lambda x: x.value, self.filter_types))
        filter_types_str = " OR ".join(filter_types_str)
        return urllib.parse.quote(f"type:({filter_types_str})")

    filter_types: "list[LsType]" = []


def get_network_request():
    return QgsBlockingNetworkRequest()


def get_request(url) -> dict:
    request = get_network_request()
    err = request.get(QNetworkRequest(QUrl(url)), True)
    if err is QgsBlockingNetworkRequest.NoError:
        # TODO: add proper error handling
        QgsMessageLog.logMessage("SERVER ERROR OCCURED", PLUGIN_NAME, level=Qgis.Info)

    reply = request.reply()
    if reply.error() is QNetworkReply.NoError:
        # TODO: add proper error handling
        QgsMessageLog.logMessage("SERVER ERROR OCCURED", PLUGIN_NAME, level=Qgis.Info)
    content_str = str(reply.content(), "utf-8")
    return json.loads(content_str)


proj_mapping = {
    Projection.EPSG_28992: "geometrie_rd",
    Projection.EPSG_4326: "geometrie_ll",
}


def url_encode_query_string(query_string):
    return urllib.parse.quote(query_string)


def suggest_query(query, type_fq=TypeFilterQuery(), rows=10) -> list:
    # TODO: add fields filter, with fl=id,geometrie_ll/rd or *
    query = url_encode_query_string(query)
    query_string = f"q={query}&rows={rows}&fq={type_fq}"
    url = f"{SERVICE_ENDPOINT}/suggest?{query_string}"
    content_obj = get_request(url)
    return content_obj["response"]["docs"]


def convert_to_gj(result_item):
    wkt = result_item["centroide_ll"]
    geom = ogr.CreateGeometryFromWkt(wkt)
    geojson = geom.ExportToJson()
    print(geojson)


def free_query(query, rows=10) -> "list[dict]":
    query = url_encode_query_string(query)
    query_string = f"q={query}&rows={rows}"
    url = f"{SERVICE_ENDPOINT}/free?{query_string}"
    content_obj = get_request(url)
    result = content_obj["response"]["docs"]

    map(convert_to_gj, result)
    return result


def lookup_object(object_id: str, proj: Projection) -> dict:
    # TODO: add fields filter, with fl=id,geometrie_ll/rd or fl=*
    geom_string = proj_mapping[proj]
    fields_filter = f"*,{geom_string}"
    fields_filter = url_encode_query_string(fields_filter)
    object_id = url_encode_query_string(object_id)
    query_string = f"id={object_id}&fl={fields_filter}"
    url = f"{SERVICE_ENDPOINT}/lookup?{query_string}"
    content_obj = get_request(url)
    if content_obj["response"]["numFound"] != 1:
        return None
    return content_obj["response"]["docs"][0]

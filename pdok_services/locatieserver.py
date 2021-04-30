"""Main module."""
from enum import Enum
import json
from qgis.core import QgsMessageLog, QgsBlockingNetworkRequest, Qgis
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtCore import QUrl

SERVICE_ENDPOINT = "https://geodata.nationaalgeoregister.nl/locatieserver/v3"
PLUGIN_NAME = "pdokservices-plugin"


class Projection(Enum):
    def __str__(self):
        epsg_code = str(self.value).split("_")[1]
        return f"EPSG:{epsg_code}"

    EPSG_4326 = 1
    EPSG_28992 = 2


class TypeFilterQuery:
    def __init__(
        self,
        filterType: str = ""
        # gemeente: bool = True,
        # woonplaats: bool = True,
        # weg: bool = True,
        # postcode: bool = True,
        # adres: bool = True,
    ):
        if filterType:
            class_attributes = filter(lambda x: not x.startswith("__"), dir(self))
            disable_attributes = (
                item for item in class_attributes if item != filterType
            )
            map(lambda x: setattr(self, x, False), disable_attributes)

    def __str__(self):
        class_attributes = filter(lambda x: not x.startswith("__"), dir(self))
        filter_types = map(lambda x: x if getattr(self, x) else None, class_attributes)
        filter_types = list(filter(lambda x: x is not None, filter_types))
        filter_types_str = " OR ".join(filter_types)
        return f"type:({filter_types_str})"

    gemeente = True  # pylint: disable=invalid-name
    woonplaats = True  # pylint: disable=invalid-name
    weg = True  # pylint: disable=invalid-name
    postcode = True  # pylint: disable=invalid-name
    adres = True  # pylint: disable=invalid-name


class LocatieServer:
    def get_request(self, url) -> str:
        print(url)
        request = QgsBlockingNetworkRequest()
        err = request.get(QNetworkRequest(QUrl(url)), True)
        if err is QgsBlockingNetworkRequest.NoError:
            # TODO: add proper error handling
            QgsMessageLog.logMessage(
                "SERVER ERROR OCCURED", PLUGIN_NAME, level=Qgis.Info
            )
        reply = request.reply()
        if reply.error() is QNetworkReply.NoError:
            # TODO: add proper error handling
            QgsMessageLog.logMessage(
                "SERVER ERROR OCCURED", PLUGIN_NAME, level=Qgis.Info
            )
        content_str = str(reply.content(), "utf-8")
        return content_str

    proj_mapping = {
        Projection.EPSG_28992: "geometrie_rd",
        Projection.EPSG_4326: "geometrie_ll",
    }

    def url_encode_query_string(self, query_string):
        # TODO: implementation
        return query_string

    def suggest_query(self, query, type_fq=TypeFilterQuery(), rows=5):
        # TODO: add fields filter, with fl=id,geometrie_ll/rd or *
        query_string = f"q={query}&rows={rows}&fq={type_fq}"
        query_string = self.url_encode_query_string(query_string)
        url = f"{SERVICE_ENDPOINT}/suggest?{query_string}"
        content_str = self.get_request(url)
        content_obj = json.loads(content_str)
        return content_obj["response"]["docs"]

    def free_query(self, query, type_fq=TypeFilterQuery(), rows=5):
        query_string = f"q={query}&rows={rows}&fq={type_fq}"
        query_string = self.url_encode_query_string(query_string)
        url = f"{SERVICE_ENDPOINT}/free?{query_string}"
        content_str = self.get_request(url)
        content_obj = json.loads(content_str)
        return content_obj["response"]["docs"]

    def lookup_object(self, object_id: str, proj: Projection) -> dict:
        # TODO: add fields filter, with fl=id,geometrie_ll/rd or fl=*
        geom_string = self.proj_mapping[proj]
        query_string = f"id={object_id}&fl=*,{geom_string}"
        query_string = self.url_encode_query_string(query_string)

        url = f"{SERVICE_ENDPOINT}/lookup?{query_string}"
        content_str = self.get_request(url)

        content_obj = json.loads(content_str)
        if content_obj["response"]["numFound"] != 1:
            return None
        return content_obj["response"]["docs"][0]

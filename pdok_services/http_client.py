import json
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtCore import QUrl
from qgis.core import (
    QgsMessageLog,
    QgsBlockingNetworkRequest,
    Qgis,
)

from pdok_services.config import PLUGIN_NAME


def get_reply(url):
    qgs_request = QgsBlockingNetworkRequest()
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b"User-Agent", b"qgis-pdokservices-plugin")
    err = qgs_request.get(request, True)

    if err is QgsBlockingNetworkRequest.NoError:
        # TODO: add proper error handling
        QgsMessageLog.logMessage("SERVER ERROR OCCURED", PLUGIN_NAME, level=Qgis.Info)

    reply = qgs_request.reply()
    if reply.error() is QNetworkReply.NoError:
        # TODO: add proper error handling
        QgsMessageLog.logMessage("SERVER ERROR OCCURED", PLUGIN_NAME, level=Qgis.Info)
    return reply


def get_request_bytes(url):
    reply = get_reply(url)
    return bytes(reply.content())


def get_request_json(url):
    reply = get_reply(url)
    content_type = bytes(reply.rawHeader(b"Content-Type")).decode(
        "ascii"
    )  # https://stackoverflow.com/a/4410331
    encoding = "utf-8"
    if len(content_type.split(";")) > 1:
        encoding = content_type.split(";")[1].replace("charset=", "")
    content_str = str(reply.content(), encoding)
    if not content_type.startswith("application/json"):
        raise ValueError(
            f"Received Content-Type:{content_type}  expected Content-Type:application/json"
        )
    return json.loads(content_str)

# -*- coding: utf-8 -*-
import uuid
import re
import struct
import traceback
from math import floor
import email.parser
from osgeo import gdal
from requests.structures import CaseInsensitiveDict
from owslib.wcs import WebCoverageService
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from PyQt5 import QtGui
from qgis.core import (
    QgsProject,
    QgsProcessing,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsFeature,
    QgsFeatureSink,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
)

from pdok_services.http_client import get_request_bytes


def get_boundary(response):
    pattern = b"^\r\n(--.*)\r\n"
    m = re.search(pattern, response)
    if m:
        return m.group(1)
    return ""


def split_on_find(content, bound):
    point = content.find(bound)
    return content[:point], content[point + len(bound) :]


def encode_with(string, encoding):
    if not (string is None or isinstance(string, bytes)):
        return string.encode(encoding)
    return string


def header_parser(string, encoding):
    string = string.decode(encoding)
    headers = email.parser.HeaderParser().parsestr(string).items()
    return ((encode_with(k, encoding), encode_with(v, encoding)) for k, v in headers)


def parse_response(content):
    encoding = "utf-8"
    sep = get_boundary(content)
    parts = content.split(b"".join((b"\r\n", sep)))
    parts = parts[1:-1]
    result = []
    for part in parts:
        if b"\r\n\r\n" in part:
            first, body = split_on_find(part, b"\r\n\r\n")
            headers = header_parser(first.lstrip(), encoding)
            headers = CaseInsensitiveDict(headers)
            item = {}
            item["headers"] = headers
            item["content"] = body
            result.append(item)
    return result


class PDOKWCSTool(QgsProcessingAlgorithm):
    """ """

    USER_AGENT_HEADER = {"User-Agent": "qgis-pdok-processing-tools"}

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        # Must return a new copy of your algorithm.
        return PDOKWCSTool()

    def name(self):
        """
        Returns the unique algorithm name.
        """
        return "pdok-ahn3-tool"

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr("PDOK AHN3 Tool")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr("AHN3")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs
        to.
        """
        return "pdok-ahn3"

    def icon(self):
        """Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        icon_path = ":/plugins/pdok_services/icon.png"
        icon = QtGui.QIcon(icon_path)
        return icon

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr(
            'This processing tool retrieves elevation data from the <a href="https://geodata.nationaalgeoregister.nl/ahn3/wcs?service=WCS&request=GetCapabilities">AHN3 WCS</a> \
            for each point in the point input layer. The output is a point layer with \
            the joined elevation attribute. \
            Parameters:\n\n\
            <ul><li><b>Input point layer</b></li>\
            <li><b>CoverageId:</b> type of coverage to query, see the <a href="https://www.ahn.nl/kwaliteitsbeschrijving">\
                AHN documentation</a></li>\
            <li><b>Attribute name:</b> name of attribution to store elevation data in</li>\
            <li><b>Target CRS:</b> CRS of the resulting output layer</li>\
            <li><b>Output layer:</b> resulting output layer</li></ul>'
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and outputs of the algorithm.
        """
        self.wcs_url = "https://geodata.nationaalgeoregister.nl/ahn3/wcs"
        self.wcs = WebCoverageService(self.wcs_url, version="2.0.1")
        _coverages = list(self.wcs.contents.keys())
        self.coverages = [(item, self.tr(item)) for item in _coverages]
        self.INPUT = "INPUT"  # recommended name for the main input parameter
        self.OUTPUT = "OUTPUT"  # recommended name for the main output parameter
        self.TARGET_CRS = "TARGET_CRS"
        self.ATTRIBUTE_NAME = "ATTRIBUTE_NAME"
        self.COVERAGE_ID = "COVERAGE_ID"

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input point layer"),
                types=[QgsProcessing.TypeVectorPoint],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.COVERAGE_ID,
                self.tr("CoverageId"),
                options=[p[1] for p in self.coverages],
                defaultValue=0,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.ATTRIBUTE_NAME,
                self.tr("Attribute name"),
                defaultValue="elevation",
                optional=True,
            )
        ),
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Output layer"))
        )
        self.addParameter(
            QgsProcessingParameterCrs(
                self.TARGET_CRS, self.tr("Target CRS"), "EPSG:4326"
            )
        )

    def get_ahn_val(self, x, y, coverage_id, feedback):
        origin = [float(i) for i in self.wcs.contents[coverage_id].grid.origin]
        cell_size = float(self.wcs.contents[coverage_id].grid.offsetvectors[0][0])
        x_lower_bound = origin[0] + (((x - origin[0]) // cell_size) * cell_size)
        x_upper_bound = x_lower_bound + (2 * cell_size)
        y_lower_bound = origin[1] + (((y - origin[1]) // cell_size) * cell_size)
        y_upper_bound = y_lower_bound + (2 * cell_size)
        url = f"{self.wcs_url}?service=WCS&Request=GetCoverage&version=2.0.1&CoverageId={coverage_id}&format=image/tiff&subset=x({x_lower_bound},{x_upper_bound})&subset=y({y_lower_bound},{y_upper_bound})"
        feedback.pushInfo(f"url: {url}")
        response_body = get_request_bytes(url)
        multipart_data = parse_response(response_body)
        for part in multipart_data:
            if part["headers"][b"content-type"] == b"image/tiff":
                coverage = part["content"]
        uuid_string = str(uuid.uuid4())
        tif_file_name = f"/vsimem/{uuid_string}.tif"
        gdal.UseExceptions()
        gdal.FileFromMemBuffer(tif_file_name, coverage)
        ds = gdal.Open(tif_file_name)
        band = ds.GetRasterBand(1)
        gt = ds.GetGeoTransform()
        px = floor((x - gt[0]) / gt[1])
        py = floor((y - gt[3]) / gt[5])
        structval = band.ReadRaster(px, py, 1, 1, buf_type=gdal.GDT_Float32)
        floatval = struct.unpack("f", structval)
        return floatval[0]

    def processAlgorithm(self, parameters, context, feedback):
        try:
            # read out parameters
            input_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
            out_crs = parameters[self.TARGET_CRS]
            attribute_name = parameters[self.ATTRIBUTE_NAME]
            coverage_id = [
                self.coverages[i][0]
                for i in self.parameterAsEnums(parameters, self.COVERAGE_ID, context)
            ][0]
            # start processing
            fields = input_layer.fields()
            fields.append(QgsField(attribute_name, QVariant.Double))
            field_names = [field.name() for field in fields]
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                input_layer.wkbType(),
                out_crs,
            )
            if feedback.isCanceled():
                return {}
            crs_uri = self.wcs.contents[coverage_id].boundingboxes[0]["nativeSrs"]
            feedback.pushInfo(f"crs_uri: {crs_uri}")
            in_crs = input_layer.crs()
            if in_crs.authid() != "EPSG:28992":
                rd_crs = QgsCoordinateReferenceSystem("EPSG:28992")
                transform_input = QgsCoordinateTransform(
                    in_crs, rd_crs, QgsProject.instance()
                )
            for feature in input_layer.getFeatures():
                geom = feature.geometry()
                if in_crs.authid() != "EPSG:28992":
                    geom.transform(transform_input)
                point_geom = QgsGeometry.asPoint(geom)
                point_xy = QgsPointXY(point_geom)
                x = point_xy.x()
                y = point_xy.y()
                attrs = feature.attributes()
                new_ft = QgsFeature(fields)
                for i in range(len(attrs)):
                    attr = attrs[i]
                    field_name = field_names[i]
                    new_ft.setAttribute(field_name, attr)
                ahn_val = self.get_ahn_val(x, y, coverage_id, feedback)
                # TODO: retrieve NODATA val from WCS service
                if ahn_val == 3.4028234663852886e38:
                    ahn_val = None
                new_ft.setAttribute(attribute_name, ahn_val)
                if out_crs.authid() != in_crs.authid():
                    transform = QgsCoordinateTransform(
                        in_crs, out_crs, QgsProject.instance()
                    )
                    geom.transform(transform)
                new_ft.setGeometry(geom)
                sink.addFeature(new_ft, QgsFeatureSink.FastInsert)
                if feedback.isCanceled():
                    return {}
            results = {}
            results[self.OUTPUT] = dest_id
            return results
        except Exception as e:
            traceback_str = traceback.format_exc()
            toolname = type(self).__name__
            raise QgsProcessingException(
                f"Unexpected error occured while running {toolname}: {e} - traceback: {traceback_str}"
            )

# -*- coding: utf-8 -*-

"""pdok-reverse-geocoder.py: QGIS Processing tool for reverse geocoding with the PDOK \
   Locatieserver. Tested with QGIS version 3.16, but will probably work with any \
   3.X version.
"""
import sys, traceback
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProject,
    QgsProcessing,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
    QgsFeature,
    QgsUnitTypes,
    QgsFeatureSink,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
)
from PyQt5 import QtGui

from qgis import processing
import requests
import json


class PDOKReverseGeocoder(QgsProcessingAlgorithm):
    """
    This processing tool queries the PDOK Locatieserver reverse geocoder service for each point in the input
    layer and adds the first result to the target attribute.
    """

    USER_AGENT_HEADER = {"User-Agent": "qgis-pdok-processing-tools"}

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        # Must return a new copy of your tool.
        return PDOKReverseGeocoder()

    def name(self):
        """
        Returns the unique tool name.
        """
        return "pdok-reverse-geocoder"

    def displayName(self):
        """
        Returns the translated tool name.
        """
        return self.tr("Reverse Geocoder")

    def group(self):
        """
        Returns the name of the group this tool belongs to.
        """
        return self.tr("Locatie Server")

    def icon(self):
        """Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        icon_path = ":/plugins/pdok_services/icon.png"
        icon = QtGui.QIcon(icon_path)
        return icon

    def groupId(self):
        """
        Returns the unique ID of the group this tool belongs
        to.
        """
        return "pdok-locatie-server"

    def shortHelpString(self):
        """
        Returns a localised short help string for the tool.
        """
        return self.tr(
            'This processing tool queries the PDOK Locatieserver reverse geocoder service for each\
            point in the input layer and adds the first result to the target attribute.\n\
            See PDOK Locatieserver documentation: https://github.com/PDOK/locatieserver/wiki/API-Reverse-Geocoder\n\
            Parameters:\n\n\
            - Input point layer (any projection): for each point the PDOK locatieserver reverse geocoder service will be queried\n\
            - Result type to query: defaults to "adres"\n\
            - Distance treshold, optional: objects returned by the PDOK locatieserver reverse geocoder \
            with a distance greater than the threshold will be excluded\n\
            - Attribute name, optional: defaults to result type, target attribute name results will be written to'
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and outputs of the tool.
        """

        self.predicates = [
            ("adres", self.tr("adres")),
            ("appartementsrecht", self.tr("appartementsrecht")),
            ("buurt", self.tr("buurt")),
            ("gemeente", self.tr("gemeente")),
            ("hectometerpaal", self.tr("hectometerpaal")),
            ("perceel", self.tr("perceel")),
            ("postcode", self.tr("postcode")),
            ("provincie", self.tr("provincie")),
            ("waterschap", self.tr("waterschap")),
            ("weg", self.tr("weg")),
            ("wijk", self.tr("wijk")),
            ("woonplaats", self.tr("woonplaats")),
        ]
        self.INPUT = "INPUT"  # recommended name for the main input parameter
        self.ATTRIBUTE_NAME = "ATTRIBUTE_NAME"
        self.RESULT_TYPE = "RESULT_TYPE"
        self.DISTANCE_TRESHOLD = "DISTANCE_TRESHOLD"
        self.OUTPUT = "OUTPUT"  # recommended name for the main output parameter

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input point layer"),
                types=[QgsProcessing.TypeVectorPoint],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.RESULT_TYPE,
                self.tr("Result type to query"),
                options=[p[1] for p in self.predicates],
                defaultValue=0,
                optional=True,
            )
        )
        dist_param = QgsProcessingParameterDistance(
            self.DISTANCE_TRESHOLD,
            self.tr("Distance treshold"),
            defaultValue=None,
            optional=True,
            minValue=0,
        )
        dist_param.setDefaultUnit(QgsUnitTypes.DistanceMeters)
        self.addParameter(dist_param)
        self.addParameter(
            QgsProcessingParameterString(
                self.ATTRIBUTE_NAME,
                self.tr("Attribute name"),
                defaultValue=None,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Output point layer")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        try:
            # read out algorithm parameters
            input_points = self.parameterAsVectorLayer(parameters, self.INPUT, context)
            distance_treshold = parameters[self.DISTANCE_TRESHOLD]
            target_att_name = parameters[self.ATTRIBUTE_NAME]
            result_type = [
                self.predicates[i][0]
                for i in self.parameterAsEnums(parameters, self.RESULT_TYPE, context)
            ][0]

            # Initialize output layer
            fields = input_points.fields()
            field_names = [field.name() for field in fields]
            if not target_att_name:
                target_att_name = result_type
            if target_att_name in fields:
                raise QgsProcessingException(
                    f"Target attribute name {field_name} already exists in input layer. \
                    Supply  different target attribute name."
                )
            fields.append(QgsField(target_att_name, QVariant.String))
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                QgsWkbTypes.Point,
                input_points.sourceCrs(),
            )

            # Setup transformation if required
            in_crs = input_points.crs()
            out_crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
            transform = None
            if in_crs.authid() != "EPSG:4326":
                transform = QgsCoordinateTransform(
                    in_crs, out_crs, QgsProject.instance()
                )

            if feedback.isCanceled():
                return {}

            # start processing features
            for point in input_points.getFeatures():
                geom = point.geometry()

                if transform:
                    geom.transform(transform)

                point_geom = QgsGeometry.asPoint(geom)
                pxy = QgsPointXY(point_geom)
                lon = pxy.x()
                lat = pxy.y()
                url = f"https://geodata.nationaalgeoregister.nl/locatieserver/v4/revgeo/?lon={lon}&type={result_type}&lat={lat}"
                feedback.pushInfo(f"INFO: HTTP GET {url}")
                response = requests.get(
                    url, headers=PDOKReverseGeocoder.USER_AGENT_HEADER
                )
                sc = response.status_code

                if response.status_code != 200:
                    raise QgsProcessingException(
                        f"Unexpected response from HTTP GET {url}, response code: {response.status_code}"
                    )

                data = response.json()
                result = ""

                if len(data["response"]["docs"]) > 0:
                    if (
                        distance_treshold != None
                        and data["response"]["docs"][0]["afstand"] > distance_treshold
                    ):
                        pass
                    else:
                        result = data["response"]["docs"][0]["weergavenaam"]

                attrs = point.attributes()
                new_ft = QgsFeature(fields)

                for i in range(len(attrs)):
                    attr = attrs[i]
                    field_name = field_names[i]
                    new_ft.setAttribute(field_name, attr)

                new_ft.setAttribute(target_att_name, result)
                new_ft.setGeometry(point.geometry())
                sink.addFeature(new_ft, QgsFeatureSink.FastInsert)

                if feedback.isCanceled():
                    return {}

            results = {}
            results[self.OUTPUT] = dest_id
            return results
        except Exception as e:
            raise QgsProcessingException(
                f"Unexpected error occured while running PDOKReverseGeocoder: {str(e)}"
            )

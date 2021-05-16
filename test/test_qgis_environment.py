# coding=utf-8
"""Tests for QGIS functionality.


.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""
__author__ = "tim@linfiniti.com"
__date__ = "20/01/2011"
__copyright__ = "Copyright 2012, Australia Indonesia Facility for " "Disaster Reduction"

import os
import sys
import unittest
from qgis.core import QgsProviderRegistry, QgsCoordinateReferenceSystem, QgsRasterLayer

from utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class PDOKQGISTest(unittest.TestCase):
    """Test the QGIS Environment"""

    def test_qgis_environment(self):
        """QGIS environment has the expected providers"""
        r = QgsProviderRegistry.instance()
        self.assertIn("gdal", r.providerList())
        self.assertIn("ogr", r.providerList())
        self.assertIn("vectortile", r.providerList())

    def test_projection(self):
        """Test that QGIS properly parses a wkt string."""

        # seems required because env var is passed in as "C:\OSGEO4~1\share\gdal"
        # suspect proj/gdal cannot handle the tilde in path
        if sys.executable.startswith("C:\OSGeo4W64"):
            os.environ["PROJ_LIB"] = r"C:\OSGeo4W64\share\proj"
            os.environ["GDAL_DATA"] = r"C:\OSGeo4W64\share\gdal"
            print(os.environ["PROJ_LIB"])
            print(os.environ["GDAL_DATA"])

        wkt = (
            'GEOGCS["WGS84", DATUM["WGS84", SPHEROID["WGS84", 6378137.0, 298.257223563]],'
            'PRIMEM["Greenwich", 0.0], UNIT["degree",0.017453292519943295],'
            'AXIS["Longitude",EAST], AXIS["Latitude",NORTH]]'
        )
        crs = QgsCoordinateReferenceSystem(wkt)
        self.assertTrue(crs.isValid())
        auth_id = crs.authid()
        expected_auth_id = "OGC:CRS84"
        self.assertEqual(auth_id, expected_auth_id)

        # now test for a loaded layer
        path = os.path.join(os.path.dirname(__file__), "data", "tenbytenraster.asc")
        title = "TestRaster"
        layer = QgsRasterLayer(path, title)
        auth_id = layer.crs().authid()
        self.assertEqual(auth_id, expected_auth_id)


if __name__ == "__main__":
    unittest.main()

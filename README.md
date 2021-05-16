# README



- Copy the entire directory containing your new plugin to the QGIS plugin
  directory
- Compile the resources file using pyrcc5
- Run the tests (``make test``)
- Test the plugin by enabling it in the QGIS plugin manager
- Customize it by editing the implementation file: ``pdok_services.py``
- Create your own custom icon, replacing the default icon.png
- Modify your user interface by opening PdokServices_dialog_base.ui in Qt Designer
- You can use the Makefile to compile your Ui and resource files when
  you make changes. This requires GNU make (gmake)



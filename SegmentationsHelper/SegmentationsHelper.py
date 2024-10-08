import logging
import os
from typing import Annotated, Optional

import vtk

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import qt
from slicer import vtkMRMLScalarVolumeNode
from time import sleep
import threading


class SegmentationsHelper(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("SegmentationsHelper")  
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Vision Pro Connection")]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Tony Zhang"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
        A module intended for use to automatically segment CT and MRI Images and use Apple Vision Pro for visualization
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _(""" """)


class SegmentationsHelperWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None
        self.connected = False
        self.monailabel = slicer.modules.monailabel.widgetRepresentation().self()

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        #Set slicer ui
        slicer.util.setStatusBarVisible(False)
        slicer.util.setToolbarsVisible(False)
        slicer.util.setModulePanelTitleVisible(False)
        slicer.util.setModuleHelpSectionVisible(False)
        slicer.util.selectModule('SegmentationsHelper')
        slicer.util.setPythonConsoleVisible(False)
        slicer.util.setDataProbeVisible(False)

        # Create main widget and layout
        panelWidget = qt.QWidget()
        layout = qt.QVBoxLayout(panelWidget)
        # Set scene in MRML widgets
        self.layout.addWidget(panelWidget)

        #CONFIGURATION SCREEN
        self.configurationScreen = qt.QWidget()
        configurationScreenLayout = qt.QVBoxLayout(self.configurationScreen
                                                   )

        configurationText = qt.QLabel("Initial Configuration:")
        configurationText.setStyleSheet("font-weight: bold; font-size: 20px")
        configurationScreenLayout.addWidget(configurationText)

        configurationScreenLayout.addStretch(1)

        self.openigt_address_input = qt.QLineEdit()
        self.openigt_address_input.setPlaceholderText("Vision Pro IP Address")
        self.openigt_address_input.setStyleSheet("background-color: white; font-weight: bold; font-size: 20px")

        self.image_server_address_input = qt.QLineEdit()
        self.image_server_address_input.setPlaceholderText("Imaging Server IP Address")
        self.image_server_address_input.setStyleSheet("background-color: white; font-weight: bold; font-size: 20px")

        configurationScreenLayout.addStretch(1)

        nextButton = qt.QPushButton("Next")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px")
        nextButton.clicked.connect(self.showImageSelector)
        configurationScreenLayout.addWidget(nextButton)

        layout.addWidget(self.imageSelector)

        #VOLUME SELECTOR

        self.imageSelector = qt.QWidget()
        imageSelectorLayout = qt.QVBoxLayout(self.imageSelector)

        imageSelectText = qt.QLabel("Select an Image Volume:")
        imageSelectText.setStyleSheet("font-weight: bold; font-size: 20px")
        imageSelectorLayout.addWidget(imageSelectText)

        optionsButton = qt.QPushButton("Set Options")
        optionsButton.setStyleSheet("font-weight: bold; font-size: 20px")
        optionsButton.clicked.connect(self.showConfigurationScreen)
        imageSelectorLayout.addWidget(nextButton)

        imageSelectorLayout.addStretch(1)

        # invoke Add Data window
        addDataButton = qt.QPushButton("Choose Volume From Files")
        addDataButton.setStyleSheet("font-weight: bold; font-size: 20px; background-color: blue")
        addDataButton.clicked.connect(slicer.util.openAddDataDialog)
        imageSelectorLayout.addWidget(addDataButton)

        # Load Data from Server
        loadDataButton = qt.QPushButton("Load Volume from Server")
        loadDataButton.setStyleSheet("font-weight: bold; font-size: 20px; background-color: green")
        # loadDataButton.clicked.connect(self.loadDataFromServer)
        imageSelectorLayout.addWidget(loadDataButton)

        imageSelectorLayout.addStretch(1)

        nextButton = qt.QPushButton("Perform Segmentation")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px")
        nextButton.clicked.connect(self.onPerformSegmentation)
        imageSelectorLayout.addWidget(nextButton)

        layout.addWidget(self.imageSelector)

        self.nodeAddedObserver = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAdded)

        #SEGMENTATIONS

        self.segmentationEditor = qt.QWidget()
        segmentationEditorLayout = qt.QVBoxLayout(self.segmentationEditor)
        self.segmentationEditor.hide()

        segmentationEditorLayout.addWidget(slicer.modules.segmenteditor.widgetRepresentation())

        segmentationEditorLayout.addStretch(1)
        # add next button
        nextButton = qt.QPushButton("Connect to Apple Vision Pro")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px")
        nextButton.clicked.connect(self.showVisionProInterface)
        segmentationEditorLayout.addWidget(nextButton)

        layout.addWidget(self.segmentationEditor)
        
        #VISION PRO CONNECTION

        self.visionProInterface = qt.QWidget()
        visionProInterfaceLayout = qt.QVBoxLayout(self.visionProInterface)
        self.visionProInterface.hide()

        visionProConnectionWidget = slicer.modules.applevisionpromodule.widgetRepresentation()
        visionProConnectionWidget.setContentsMargins(-10,-10,-10,-10)
        visionProInterfaceLayout.addWidget(visionProConnectionWidget)

        visionProInterfaceLayout.addStretch(1)

        backButton = qt.QPushButton("Back to Image Selector")
        backButton.setStyleSheet("font-weight: bold; font-size: 20px")
        backButton.clicked.connect(self.showImageSelector)
        visionProInterfaceLayout.addWidget(backButton)

        layout.addWidget(self.visionProInterface)
        

        # Create logic class instance
        self.logic = SegmentationsHelperLogic()
        # layout.addStretch(1)

        # Connections
        # Example connections to scene events
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.StartCloseEvent, self.onSceneStartClose)
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndCloseEvent, self.onSceneEndClose)
    
    def onPerformSegmentation(self):
        # slicer.modules.monailabel.widgetRepresentation().self().logic
        self.monailabel._volumeNode = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLScalarVolumeNode')
        showSegmentationEditor()

    def showConfigurationScreen(self):
        self.configurationScreen.show()
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.visionProInterface.hide()
        
    def showImageSelector(self):
        self.imageSelector.show()
        self.segmentationEditor.hide()
        self.visionProInterface.hide()
        self.configurationScreen.hide()

    def showSegmentationEditor(self):
        self.imageSelector.hide()
        self.segmentationEditor.show()
        self.visionProInterface.hide()
        self.configurationScreen.hide()
    
    def showVisionProInterface(self):
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.visionProInterface.show()
        self.configurationScreen.hide()

    def onNodeAdded(self, caller, event):
        """Called when a node is added to the scene."""
        node = caller.GetLastNode()
        if isinstance(node, vtkMRMLScalarVolumeNode):
            self.showSegmentationEditor()
            #remove other volumes
            for volume in slicer.util.getNodes('vtkMRMLScalarVolumeNode'):
                if volume != node:
                    slicer.mrmlScene.RemoveNode(volume)

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.logic.close()
        slicer.mrmlScene.RemoveObserver(self.nodeAddedObserver)

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed

    def exit(self) -> None:
        """Called each time the user opens a different module."""

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        slicer.mrmlScene.RemoveObserver(self.nodeAddedObserver)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        # close client
        self.logic.close()
#
# AppleVisionProModuleLogic
#


class SegmentationsHelperLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def close(self) -> None:
        pass

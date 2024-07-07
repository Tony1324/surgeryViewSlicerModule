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
import pyigtl
from time import sleep
import threading

#
# AppleVisionProModule
#


class AppleVisionProModule(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("AppleVisionProModule")  # TODO: make this more human readable by adding spaces
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Examples")]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["John Doe (AnyWare Corp.)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#AppleVisionProModule">module documentation</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""")


class AppleVisionProModuleWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Create main widget and layout
        panelWidget = qt.QWidget()
        layout = qt.QVBoxLayout(panelWidget)
        # Set scene in MRML widgets
        self.layout.addWidget(panelWidget)

        connectionContainer = qt.QWidget()
        connectionLayout = qt.QVBoxLayout(connectionContainer)
        #set background
        connectionContainer.setStyleSheet("background-color: #d0d0d0")
        layout.addWidget(connectionContainer)

        # Status Message
        self.status_label = qt.QLabel("Status: Not Connected")
        connectionLayout.addWidget(self.status_label)


        # IP Address Input
        ip_address_label = qt.QLabel("IP Address:")
        self.ip_address_input = qt.QLineEdit()
        self.ip_address_input.textChanged.connect(self.validateIPAddress)
        self.ip_address_input.setPlaceholderText("Enter IP Address")
        self.ip_address_input.setStyleSheet("background-color: white")
        ip_container = qt.QWidget() 
        ip_container_layout = qt.QHBoxLayout(ip_container)
        ip_container_layout.addWidget(ip_address_label)
        ip_container_layout.addWidget(self.ip_address_input)
        ip_container_layout.setContentsMargins(0,0,0,0)
        connectionLayout.addWidget(ip_container)

        # Connect Button
        self.connect_button = qt.QPushButton("Connect")
        self.connect_button.clicked.connect(self.onConnectButtonClicked)
        connectionLayout.addWidget(self.connect_button)

        # Volume
        self.label = qt.QLabel("Select an image volume:")
        layout.addWidget(self.label)
        self.volumeSelector = qt.QComboBox()
        layout.addWidget(self.volumeSelector)
        self.updateVolumeSelector()

        self.sendVolumeButton = qt.QPushButton("Send Volume")
        layout.addWidget(self.sendVolumeButton)
        self.sendVolumeButton.clicked.connect(self.onSendVolumeButtonClicked)
        self.sendVolumeButton.setEnabled(False)

        #Models
        self.sendModelsButton = qt.QPushButton("Send All Models")
        self.sendModelsButton.clicked.connect(self.onSendModelsButtonClicked)
        self.sendModelsButton.setEnabled(False)
        layout.addWidget(self.sendModelsButton)
    
        # add vertical spacer
        layout.addStretch(1)

        # Create logic class instance
        self.logic = AppleVisionProModuleLogic()

        # Connections
        # Example connections to scene events
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.StartCloseEvent, self.onSceneStartClose)
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndCloseEvent, self.onSceneEndClose)

    def updateVolumeSelector(self):
        self.volumeSelector.clear()
        volumes = slicer.mrmlScene.GetNodesByClass('vtkMRMLScalarVolumeNode')
        volumes.UnRegister(None)
        for i in range(volumes.GetNumberOfItems()):
            volume = volumes.GetItemAsObject(i)
            self.volumeSelector.addItem(volume.GetName(), volume.GetID())

    def onSendModelsButtonClicked(self):
        models = slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')
        
        for i in range(models.GetNumberOfItems()):
            model = models.GetItemAsObject(i)
            # Replace this print statement with the actual sending logic
            self.logic.sendModel(model)
            print(f"Sending model: {model.GetName()}")

    def validateIPAddress(self,string:str) -> None: 
        numerical = ""
        for i in string:
            if i.isnumeric() or i==".":
                numerical += i
        self.ip_address_input.setText(numerical)

    def onConnectButtonClicked(self) -> None:
        self.logic.onConnection = self.onConnection
        self.logic.initClient(self.ip_address_input.text)
    
    def onSendVolumeButtonClicked(self) -> None:
        volume = slicer.mrmlScene.GetNodeByID(self.volumeSelector.currentData)
        self.logic.sendImage(volume)
    
    def onConnection(self) -> None:
        self.connected = True
        self.status_label.setText("Status: CONNECTED")
        self.connect_button.setEnabled(False)
        self.sendVolumeButton.setEnabled(True)
        self.sendModelsButton.setEnabled(True)
        
    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        # self.logic.close()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.updateVolumeSelector()

    def exit(self) -> None:
        """Called each time the user opens a different module."""

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        # close client
        self.logic.close()
#
# AppleVisionProModuleLogic
#


class AppleVisionProModuleLogic(ScriptedLoadableModuleLogic):
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
        self.client = None
        self.onConnection = lambda: None

    def initClient(self,ip:str) -> None:
        self.client = pyigtl.OpenIGTLinkClient(host=ip, port=18944)
        self.client.start()
        threading.Thread(target=self._connect).start()

    def _connect(self) -> None:
        while not self.client.is_connected():
            sleep(0.5)
        self.onConnection()
        print("Connected to server")


    def sendImage(self, volume:vtkMRMLScalarVolumeNode) -> None:
        # Create a message with 32 bit int image data
        image = slicer.util.arrayFromVolume(volume)
        print(image.shape)
        imageMessage = pyigtl.ImageMessage(image=image, device_name="VisionProModule")
        self.client.send_message(imageMessage)

    def sendModel(self, model) -> None:
        # Create a message with 32 bit int image data
        modelMessage = pyigtl.PolyDataMessage(model.GetPolyData(), device_name="VisionProModule")
        self.client.send_message(modelMessage)
    
    # def sendTransform(self, transform: vtkMRMLLinearTransformNode) -> None:
    #     # Create a message with 32 bit int image data
    #     transformMessage = pyigtl.TransformMessage(transform=transform.GetMatrix(), device_name="VisionProModule")
    #     self.client.send_message(transformMessage)
    
    def sendString(self, string: str) -> None:
        # Create a message with 32 bit int image data
        stringMessage = pyigtl.StringMessage(string=string, device_name="VisionProModule")
        self.client.send_message(stringMessage)

    def close(self) -> None:
        if self.client is not None:
            self.client.stop()
            self.client = None
        

  
#
# AppleVisionProModuleTest
#


class AppleVisionProModuleTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_AppleVisionProModule1()

    def test_AppleVisionProModule1(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        # Get/create input data

        import SampleData

        registerSampleData()
        inputVolume = SampleData.downloadSample("AppleVisionProModule1")
        self.delayDisplay("Loaded test data set")

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = AppleVisionProModuleLogic()

        # Test algorithm with non-inverted threshold
        logic.process(inputVolume, outputVolume, threshold, True)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], threshold)

        # Test algorithm with inverted threshold
        logic.process(inputVolume, outputVolume, threshold, False)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        self.delayDisplay("Test passed")

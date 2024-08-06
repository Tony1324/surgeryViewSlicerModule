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

#
# AppleVisionProModule
#


class AppleVisionProModule(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("Apple Vision Pro Module")  
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Vision Pro Connection")]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Tony Zhang"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
        A module intended for use with Apple Vision Pro to send models via OpenIGTLink for visualization
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _(""" """)


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
        self.connect_button.setStyleSheet("background-color: green")
        connectionLayout.addWidget(self.connect_button)

        self.dataContainer = qt.QWidget()
        dataLayout = qt.QVBoxLayout(self.dataContainer)
        layout.addWidget(self.dataContainer)
        self.dataContainer.setEnabled(False)

        # Volume
        self.label = qt.QLabel("Select an image volume:")
        dataLayout.addWidget(self.label)
        self.volumeSelector = qt.QComboBox()
        dataLayout.addWidget(self.volumeSelector)
        self.updateVolumeSelector()

        self.sendVolumeButton = qt.QPushButton("Send Volume")
        dataLayout.addWidget(self.sendVolumeButton)
        self.sendVolumeButton.clicked.connect(self.onSendVolumeButtonClicked)

        #Models
        self.sendModelsButton = qt.QPushButton("Send All Models")
        self.sendModelsButton.clicked.connect(self.onSendModelsButtonClicked)
        dataLayout.addWidget(self.sendModelsButton)

        self.showSlices = qt.QCheckBox("Show Volume Slices")
        self.showSlices.click()
        dataLayout.addWidget(self.showSlices)
        self.showSlices.clicked.connect(self.onShowVolumeClicked)

        self.sendPointerToggle = qt.QCheckBox("Send Cursor Data")
        dataLayout.addWidget(self.sendPointerToggle)
    
        self.syncCameraToggle = qt.QCheckBox("Sync Camera Orientation")
        dataLayout.addWidget(self.syncCameraToggle)

        self.clearAllButton = qt.QPushButton("Clear All Data")
        self.clearAllButton.setStyleSheet("background-color: red")
        self.clearAllButton.clicked.connect(self.onClearAllButtonClicked)
        dataLayout.addWidget(self.clearAllButton)
        # add vertical spacer
        layout.addStretch(1)

        # Create logic class instance
        self.logic = AppleVisionProModuleLogic()


        
        # Connections
        # Example connections to scene events
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.StartCloseEvent, self.onSceneStartClose)
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndCloseEvent, self.onSceneEndClose)
        
        self.crosshairNode=slicer.util.getNode("Crosshair")
        self.crosshairNodeObserver = self.crosshairNode.AddObserver(slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent, self.onMouseMoved)

        self.greenSlice = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
        self.redSlice = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed")
        self.yellowSlice = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
        self.redSliceObserver = self.redSlice.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onRedSliceChanged)
        self.greenSliceObserver = self.greenSlice.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onGreenSliceChanged)
        self.yellowSliceObserver = self.yellowSlice.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onYellowSliceChanged)

        self.camera = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLCameraNode")
        self.cameraObserver = self.camera.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onCameraMoved)

    def onCameraMoved(self, *_): 
        if self.connected and self.syncCameraToggle.isChecked():
            self.logic.sendCameraTransform(slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLCameraNode").GetCamera().GetModelViewTransformMatrix())


    def onRedSliceChanged(self, *_):
        if self.connected:
            self.logic.sendString(str(slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed").GetSliceOffset()), "AXIAL")

    def onGreenSliceChanged(self, *_):
        if self.connected:
            self.logic.sendString(str(slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen").GetSliceOffset()), "CORONAL")

    def onYellowSliceChanged(self, *_):
        if self.connected:
            self.logic.sendString(str(slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow").GetSliceOffset()), "SAGGITAL")


    def onMouseMoved(self, observer,eventid):
        if self.connected and self.sendPointerToggle.isChecked():
            crosshairNode=slicer.util.getNode("Crosshair")
            ras=[0,0,0]
            crosshairNode.GetCursorPositionRAS(ras)
            self.logic.sendCursorPosition(ras)

    def updateVolumeSelector(self):
        self.volumeSelector.clear()
        volumes = slicer.mrmlScene.GetNodesByClass('vtkMRMLScalarVolumeNode')
        volumes.UnRegister(None)
        for i in range(volumes.GetNumberOfItems()):
            volume = volumes.GetItemAsObject(i)
            self.volumeSelector.addItem(volume.GetName(), volume)

    def onSendModelsButtonClicked(self):
        models = slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')

        for i in range(models.GetNumberOfItems()):
            model = models.GetItemAsObject(i)
            if "Volume Slice" in model.GetName():
                continue
            print(f"Sending model: {model.GetName()}")
            self.logic.sendModel(model)

    def validateIPAddress(self,string:str) -> None:
        numerical = ""
        for i in string:
            if i.isnumeric() or i==".":
                numerical += i
        self.ip_address_input.setText(numerical)

    def onConnectButtonClicked(self) -> None:
        if not self.connected:
            self.logic.onConnection = self.onConnection
            self.logic.onDisconnect = self.onDisconnect
            self.logic.initClient(self.ip_address_input.text)
        else:
            self.logic.close()
            self.connected = False
            self.connect_button.setText("Connect")
            self.dataContainer.setEnabled(False)

            self.status_label.setText("Status: Not Connected")

    def onSendVolumeButtonClicked(self) -> None:
        volume = self.volumeSelector.currentData
        self.logic.sendImage(volume)

    def onShowVolumeClicked(self) -> None:
        if (self.showSlices.isChecked()):
            self.logic.sendString("ENABLE","DICOM")
        else: 
            self.logic.sendString("DISABLE","DICOM")

    def onClearAllButtonClicked(self) -> None:
        self.logic.sendString("CLEAR", "CLEAR")
    
    def onDisconnect(self, *_) -> None:
            self.connected = False
            self.logic.close()
            self.connect_button.setText("Connect")
            self.dataContainer.setEnabled(False)
            self.status_label.setText("Status: Not Connected")

    def onConnection(self, *_) -> None:
        self.connected = True
        self.status_label.setText("Status: CONNECTED")
        self.connect_button.setText("Disconnect")
        self.dataContainer.setEnabled(True)

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.crosshairNode.RemoveObserver(self.crosshairNodeObserver)
        self.redSlice.RemoveObserver(self.redSliceObserver)
        self.greenSlice.RemoveObserver(self.greenSliceObserver)
        self.yellowSlice.RemoveObserver(self.yellowSliceObserver)
        self.camera.RemoveObserver(self.cameraObserver)
        self.logic.close()
        # self.logic.close()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.updateVolumeSelector()

    def exit(self) -> None:
        """Called each time the user opens a different module."""

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        self.crosshairNode.RemoveObserver(self.crosshairNodeObserver)
        self.redSlice.RemoveObserver(self.redSliceObserver)
        self.greenSlice.RemoveObserver(self.greenSliceObserver)
        self.yellowSlice.RemoveObserver(self.yellowSliceObserver)
        self.camera.RemoveObserver(self.cameraObserver)
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
        self.connector = None
        self.onConnection = lambda: None
        self.onDisconnect = lambda: None

    def initClient(self,ip:str) -> None:
        self.connector = cnode = slicer.vtkMRMLIGTLConnectorNode()
        slicer.mrmlScene.AddNode(cnode)
        cnode.SetTypeClient(ip, 18944)
        cnode.Start()
        # self.onConnection()
        cnode.AddObserver(cnode.ConnectedEvent, self.onConnection)
        cnode.AddObserver(cnode.DisconnectedEvent, self.onDisconnect)


    def sendImage(self, volume) -> None:
        # Create a message with 32 bit int image data
        # image = slicer.util.arrayFromVolume(volume)
        # print(image.shape)
        # imageMessage = pyigtl.ImageMessage(image, device_name="VisionProModule")
        # self.client.send_message(imageMessage)
        self.connector.RegisterOutgoingMRMLNode(volume)
        self.connector.PushNode(volume)

    def sendModel(self, model) -> None:
        self.connector.RegisterOutgoingMRMLNode(model)
        self.connector.PushNode(model)
        self.sendModelDisplayProperties(model)
        model.GetDisplayNode().AddObserver(vtk.vtkCommand.ModifiedEvent, (lambda a, b: self.sendModelDisplayProperties(model)) )

    def sendModelDisplayProperties(self, model) -> None:
        print("sending")
        color = model.GetDisplayNode().GetColor()
        self.sendString(model.GetName()+"---"+self.formatColor(color),"MODELCOLOR")
        opacity = model.GetDisplayNode().GetOpacity()  if model.GetDisplayNode().GetVisibility() else 0
        self.sendString(model.GetName()+"---"+str(opacity),"MODELVISIBILITY")

    def formatColor(self, color):
        return "#{:02X}{:02X}{:02X}".format(int(color[0]*255), int(color[1]*255), int(color[2]*255))

    def sendTransform(self, transform) -> None:
        self.connector.RegisterOutgoingMRMLNode(transform)
        self.connector.PushNode(transform)

    def sendCursorPosition(self, position) -> None:
        transform = slicer.vtkMRMLLinearTransformNode()
        transform.SetName("CURSOR")
        matrix = vtk.vtkMatrix4x4()
        matrix.SetElement(0, 3, position[0])
        matrix.SetElement(1, 3, position[1])
        matrix.SetElement(2, 3, position[2])
        transform.SetMatrixTransformToParent(matrix)
        slicer.mrmlScene.AddNode(transform)
        self.sendTransform(transform)
        self.connector.UnregisterOutgoingMRMLNode(transform)
        slicer.mrmlScene.RemoveNode(transform)
    
    def sendCameraTransform(self, matrix) -> None:
        transform = slicer.vtkMRMLLinearTransformNode()
        transform.SetName("CAMERA")
        matrix = matrix
        transform.SetMatrixTransformToParent(matrix)
        slicer.mrmlScene.AddNode(transform)
        self.sendTransform(transform)
        self.connector.UnregisterOutgoingMRMLNode(transform)
        slicer.mrmlScene.RemoveNode(transform)

    

    def sendString(self, string: str, type: str) -> None:
        # Create a message with 32 bit int image data
        text = slicer.vtkMRMLTextNode()
        text.SetName(type)
        text.SetText(string)
        slicer.mrmlScene.AddNode(text)
        self.connector.RegisterOutgoingMRMLNode(text)
        self.connector.PushNode(text)
        self.connector.UnregisterOutgoingMRMLNode(text)
        slicer.mrmlScene.RemoveNode(text)
        


    def close(self) -> None:
        if self.connector is not None:
            self.connector.Stop()
            self.connector = None

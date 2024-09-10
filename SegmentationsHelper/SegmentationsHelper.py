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

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Create main widget and layout
        panelWidget = qt.QWidget()
        layout = qt.QVBoxLayout(panelWidget)
        # Set scene in MRML widgets
        self.layout.addWidget(panelWidget)

        # Create logic class instance
        self.logic = SegmentationsHelperLogic()


        # Connections
        # Example connections to scene events
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.StartCloseEvent, self.onSceneStartClose)
        slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndCloseEvent, self.onSceneEndClose)

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.logic.close()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed

    def exit(self) -> None:
        """Called each time the user opens a different module."""

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        self.crosshairNode.RemoveObserver(self.crosshairNodeObserver)
        self.redSlice.RemoveObserver(self.redSliceObserver)
        self.greenSlice.RemoveObserver(self.greenSliceObserver)
        self.yellowSlice.RemoveObserver(self.yellowSliceObserver)
        self.camera.RemoveObserver(self.cameraObserver)
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
        self.connector = None
        self.onConnection = lambda: None
        self.onDisconnect = lambda: None

    def initClient(self,ip:str) -> None:
        self.connector = cnode = slicer.vtkMRMLIGTLConnectorNode()
        slicer.mrmlScene.AddNode(cnode)
        cnode.SetTypeClient(ip, 18944)
        cnode.Start()
        # self.onConnection()
        cnode.AddObserver(cnode.ConnectedEvent, self.processEvents)
        cnode.AddObserver(cnode.DisconnectedEvent, self.processEvents)
        cnode.SetCheckCRC(False)

    def processEvents(self, *_) -> None:
        if self.connector.GetState() == self.connector.StateConnected:
            self.onConnection()
        else:
            self.onDisconnect()

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
            slicer.mrmlScene.RemoveNode(self.connector)
            self.connector = None

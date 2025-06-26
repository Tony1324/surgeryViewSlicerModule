import vtk

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import qt

#
# AppleVisionProModule
#

class AppleVisionProModule(ScriptedLoadableModule):

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("Apple Vision Pro Module")  
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Vision Pro Connection")]
        self.parent.dependencies = ["OpenIGTLinkIF"]
        self.parent.contributors = ["Tony Zhang"]
        self.parent.helpText = _("""
        A module intended for use with Apple Vision Pro to send models via OpenIGTLink for visualization
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _(""" """)


class AppleVisionProModuleWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None
        self.connected = False
        self.session = None

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Create main widget and layout
        panelWidget = qt.QWidget()
        panelWidget.setStyleSheet("""
            QPushButton, QLineEdit { border-radius: 5px;  background-color: white; padding: 8px; opacity: 1} 
            QPushButton:hover { border: 2px solid black } 
            QLineEdit { border: 1px solid rgb(180,180,180)}
            QCheckBox::indicator {width: 20px; height: 20px; border: 1px solid gray; border-radius: 5px}
            QCheckBox::indicator:checked {background-color: rgb(50,200,100); width: 20px; height: 20px; border: 1px solid gray; border-radius: 5px}
        """)

        layout = qt.QVBoxLayout(panelWidget)
        # Set scene in MRML widgets
        self.layout.addWidget(panelWidget)

        connectionContainer = qt.QWidget()
        connectionLayout = qt.QVBoxLayout(connectionContainer)

        #set background
        layout.addWidget(connectionContainer)

        # Status Message
        self.status_label = qt.QLabel("Status: Not Connected")
        self.status_label.setStyleSheet("font-weight:bold; font-size: 20px")
        connectionLayout.addWidget(self.status_label)

        # IP Address Input
        self.ip_address_input = qt.QLineEdit()
        self.ip_address_input.textChanged.connect(self.validateIPAddress)
        self.ip_address_input.setPlaceholderText("Enter IP Address")
        self.ip_address_input.setStyleSheet("background-color: white")
        self.ip_address_input.setStyleSheet("font-weight: bold; font-size: 20px")
        ip_container = qt.QWidget()
        ip_container_layout = qt.QHBoxLayout(ip_container)
        ip_container_layout.addWidget(self.ip_address_input)
        ip_container_layout.setContentsMargins(0,0,0,0)
        connectionLayout.addWidget(ip_container)

        # Connect Button
        self.connect_button = qt.QPushButton("Connect")
        self.connect_button.clicked.connect(self.onConnectButtonClicked)
        self.connect_button.setStyleSheet("background-color: rgb(50,200,100); font-weight:bold; font-size: 20px")
        connectionLayout.addWidget(self.connect_button)
        
        self.dataContainer = qt.QWidget()
        dataLayout = qt.QVBoxLayout(self.dataContainer)
        layout.addWidget(self.dataContainer)
        self.dataContainer.setEnabled(False)
        dataLayout.setContentsMargins(0,0,0,0)

        sendDataContainer = qt.QWidget()
        sendDataLayout = qt.QVBoxLayout(sendDataContainer)
        dataLayout.addWidget(sendDataContainer)
        # sendDataContainer.setTitle("Data")

        self.sendAllDataButton = qt.QPushButton("Send All Data")
        self.sendAllDataButton.clicked.connect(self.onSendDataButtonClicked)
        self.sendAllDataButton.setStyleSheet("font-weight: bold; font-size: 20px")
        sendDataLayout.addWidget(self.sendAllDataButton)

        self.clearAllButton = qt.QPushButton("Clear All Data")
        self.clearAllButton.clicked.connect(self.onClearAllButtonClicked)
        self.clearAllButton.setStyleSheet("font-weight: bold; font-size: 20px")
        sendDataLayout.addWidget(self.clearAllButton)

        viewContainer = qt.QWidget()
        viewLayout = qt.QVBoxLayout(viewContainer)
        dataLayout.addWidget(viewContainer)

        self.showSlices = qt.QCheckBox("Show Volume Slices")
        self.showSlices.setStyleSheet("font-size: 20px")
        self.showSlices.click()
        viewLayout.addWidget(self.showSlices)
        self.showSlices.clicked.connect(self.onShowVolumeClicked)

        self.sendPointerToggle = qt.QCheckBox("Send Cursor Data")
        self.sendPointerToggle.setStyleSheet("font-size: 20px")
        viewLayout.addWidget(self.sendPointerToggle)
    
        self.syncCameraToggle = qt.QCheckBox("Sync Camera Orientation")
        self.syncCameraToggle.setStyleSheet("font-size: 20px")
        viewLayout.addWidget(self.syncCameraToggle)


        # add vertical spacer
        layout.addStretch(1)

        # Create logic class instance
        self.logic = AppleVisionProModuleLogic()

        # When the OpenIGTLinkModule receives messages with a certain device name, it creates texts nodes in the MRML Scene
        # By creating these nodes first, we can listen to updates set from the Apple Vision Pro

        self.axialText = slicer.vtkMRMLTextNode()
        self.axialText.SetName("AXIAL")
        slicer.mrmlScene.AddNode(self.axialText)
        self.addObserver(self.axialText, self.axialText.TextModifiedEvent, self.setAxialPosition)

        self.coronalText = slicer.vtkMRMLTextNode()
        self.coronalText.SetName("CORONAL")
        slicer.mrmlScene.AddNode(self.coronalText)
        self.addObserver(self.coronalText, self.coronalText.TextModifiedEvent, self.setCoronalPosition)

        self.sagittalText = slicer.vtkMRMLTextNode()
        self.sagittalText.SetName("SAGITTAL")
        slicer.mrmlScene.AddNode(self.sagittalText)
        self.addObserver(self.sagittalText, self.sagittalText.TextModifiedEvent, self.setSagittalPosition)

        self.entitySelection = slicer.vtkMRMLTextNode()
        self.entitySelection.SetName("ENTITY")
        slicer.mrmlScene.AddNode(self.entitySelection)
        self.addObserver(self.entitySelection, self.entitySelection.TextModifiedEvent, self.setSelectedEntity)

        # Used for updating cursor
        self.crosshairNode=slicer.util.getNode("Crosshair")
        self.addObserver(self.crosshairNode, slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent, self.onMouseMoved)

        self.greenSlice = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
        self.redSlice = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed")
        self.yellowSlice = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
        self.addObserver(self.redSlice, vtk.vtkCommand.ModifiedEvent, self.onRedSliceChanged)
        self.addObserver(self.greenSlice, vtk.vtkCommand.ModifiedEvent, self.onGreenSliceChanged)
        self.addObserver(self.yellowSlice, vtk.vtkCommand.ModifiedEvent, self.onYellowSliceChanged)

        self.camera = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLCameraNode")
        self.addObserver(self.camera, vtk.vtkCommand.ModifiedEvent, self.onCameraMoved)

        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.EndCloseEvent, self.onSceneEndClose)

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

    def onSendDataButtonClicked(self):
        self.onSendModelsButtonClicked()
        self.onSendVolumeButtonClicked()

    def onSendModelsButtonClicked(self):
        models = []
        if self.session == None:
            models = slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')
        else:
            _models = vtk.vtkIdList()
            if self.session and self.session.geometryNode:
                shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
                shNode.GetItemChildren(self.session.geometryNode, _models)
            for i in range(_models.GetNumberOfIds()):
                models.append(shNode.GetItemDataNode(_models.GetId(i)))

        for model in models:
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
        if self.session == None:
            volume = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
        else: 
            volume = slicer.mrmlScene.GetNodeByID(self.session.volumeNode)
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
            # self.logic.close()
            self.connect_button.setText("Connect")
            self.dataContainer.setEnabled(False)
            self.status_label.setText("Status: Not Connected")

    def onConnection(self, *_) -> None:
        self.connected = True
        self.status_label.setText("Status: CONNECTED")
        self.connect_button.setText("Disconnect")
        self.dataContainer.setEnabled(True)

    def setAxialPosition(self,*_):
        str = self.axialText.GetText()
        pos = float(str)
        print(pos)
        slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed").SetSliceOffset(pos)

    def setCoronalPosition(self,*_):
        str = self.coronalText.GetText()
        pos = float(str)
        slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen").SetSliceOffset(pos)

    def setSagittalPosition(self,*_):
        str = self.sagittalText.GetText()
        pos = float(str)
        slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow").SetSliceOffset(pos)

    def setSelectedEntity(self, *_):
        str = self.entitySelection.GetText()
        models = slicer.mrmlScene.GetNodesByClass("vtkMRMLModelNode")
        e = None

        for i in range(models.GetNumberOfItems()):
            m = models.GetItemAsObject(i)
            if m.GetName().startswith(str):
                e = m

        if hasattr(self, 'previousSelectedEntity'):
            self.previousSelectedEntity.GetDisplayNode().SetAmbient(0)

        if(e):
            self.previousSelectedEntity = e
            e.GetDisplayNode().SetAmbient(1.0)
            

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()
        self.logic.close()
        # self.logic.close()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed

    def exit(self) -> None:
        """Called each time the user opens a different module."""

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        self.removeObservers()
        self.onClearAllButtonClicked()

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

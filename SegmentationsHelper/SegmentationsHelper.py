import logging
import os
from typing import Annotated, Optional

import vtk

import slicer
from slicer.parameterNodeWrapper import *
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import qt
from slicer import vtkMRMLScalarVolumeNode
from time import sleep
import threading
import tempfile

@parameterPack
class SegmentationSession:
    name: str
    segmentationNode: Optional[slicer.vtkMRMLSegmentationNode] = None
    volumeNode: Optional[slicer.vtkMRMLScalarVolumeNode] = None

@parameterNodeWrapper
class SegmentationsHelperParameterNode:
    activeSession: Optional[int] = None
    sessions: list[SegmentationSession] = []



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
        self.logic = SegmentationsHelperLogic()
        self._parameterNode = None
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
        panelWidget.setStyleSheet("""
            QPushButton, QLineEdit { border-radius: 5px;  background-color: white; padding: 8px; opacity: 1} 
            QPushButton:hover { border: 2px solid black } 
            QLineEdit { border: 1px solid rgb(180,180,180)}
            QListWidget { font-size: 20px; border: 1px solid rgb(180,180,180); overflow: none; background-color: white; border-radius: 5px; height: 1000px }
            QListWidget::item { padding: 5px }
        """)

        #CONFIGURATION SCREEN
        self.configurationScreen = qt.QWidget()
        configurationScreenLayout = qt.QVBoxLayout(self.configurationScreen)

        configurationText = qt.QLabel("Initial Configuration:")
        configurationText.setStyleSheet("font-weight: bold; font-size: 20px")
        configurationScreenLayout.addWidget(configurationText)

        configurationScreenLayout.addStretch(1)

        self.toImageSelectorButton = qt.QPushButton("Next")
        self.toImageSelectorButton.setStyleSheet("font-weight: bold; font-size: 20px")
        self.toImageSelectorButton.clicked.connect(self.onFinishConfiguration)

        openigt_address_label = qt.QLabel("Vision Pro IP Address")
        configurationScreenLayout.addWidget(openigt_address_label)

        self.openigt_address_input = qt.QLineEdit()
        self.openigt_address_input.setPlaceholderText("Vision Pro IP Address")
        self.openigt_address_input.setStyleSheet("background-color: white; font-weight: bold; font-size: 20px; padding: 10px")
        self.openigt_address_input.textChanged.connect(self.validateIPAddress)
        configurationScreenLayout.addWidget(self.openigt_address_input)

        image_server_address_label = qt.QLabel("Imaging Server IP Address")
        configurationScreenLayout.addWidget(image_server_address_label)

        self.image_server_address_input = qt.QLineEdit()
        self.image_server_address_input.setPlaceholderText("Imaging Server IP Address")
        self.image_server_address_input.setStyleSheet("background-color: white; font-weight: bold; font-size: 20px; padding: 10px")
        self.image_server_address_input.textChanged.connect(self.validateIPAddress)
        configurationScreenLayout.addWidget(self.image_server_address_input)

        settings = qt.QSettings()
        saved_openigt_address = settings.value("SegmentationsHelper/openigt_address", "")
        saved_image_server_address = settings.value("SegmentationsHelper/image_server_address", "")

        self.openigt_address_input.setText(saved_openigt_address)
        self.image_server_address_input.setText(saved_image_server_address)
        
        configurationScreenLayout.addStretch(1)

        configurationScreenLayout.addWidget(self.toImageSelectorButton)

        layout.addWidget(self.configurationScreen)

        self.validateIPAddress()

        #SESSIONS LIST
        self.sessionsList = qt.QWidget()
        sessionsListLayout = qt.QVBoxLayout(self.sessionsList)
        self.sessionsList.hide()

        sessionsListTitle = qt.QLabel("All Sessions")
        sessionsListTitle.setStyleSheet("font-weight: bold; font-size: 20px")
        sessionsListLayout.addWidget(sessionsListTitle)

        optionsButton = qt.QPushButton("Server Options")
        optionsButton.setStyleSheet("font-size: 15px")
        optionsButton.setFixedWidth(120)
        optionsButton.clicked.connect(self.showConfigurationScreen)
        sessionsListLayout.addWidget(optionsButton)
        sessionsListLayout.addStretch(1)

        #add and remove buttons
        sessionListButtonContainer = qt.QWidget()
        sessionListButtonContainerLayout = qt.QHBoxLayout(sessionListButtonContainer)
        # remove margin to the sides of the buttons
        sessionListButtonContainerLayout.setContentsMargins(0, 0, 0, 0)

        self.addSessionButton = qt.QPushButton("Add Session")
        self.addSessionButton.setStyleSheet("font-weight: bold; font-size: 12px")
        self.addSessionButton.clicked.connect(self.addSession)

        self.removeSessionButton = qt.QPushButton("Remove Session")
        self.removeSessionButton.setStyleSheet("font-weight: bold; font-size: 12px; background-color: rgb(255,200,200)")
        self.removeSessionButton.clicked.connect(self.removeSession)
        
        sessionListButtonContainerLayout.addWidget(self.addSessionButton)
        sessionListButtonContainerLayout.addWidget(self.removeSessionButton)
        sessionsListLayout.addWidget(sessionListButtonContainer)

        self.sessionListSelector = qt.QListWidget()
        self.sessionListSelector.setFixedHeight(300)
        #listen for selection changes
        self.sessionListSelector.currentItemChanged.connect(self.syncSessionUI)
        sessionsListLayout.addWidget(self.sessionListSelector)

        sessionsListLayout.addStretch(1)

        self.loadSessionButton = qt.QPushButton("Load Session")
        self.loadSessionButton.setStyleSheet("font-weight: bold; font-size: 20px")
        self.loadSessionButton.clicked.connect(self.loadSession)
        sessionsListLayout.addWidget(self.loadSessionButton)

        layout.addWidget(self.sessionsList)
        

        #VOLUME SELECTOR

        self.imageSelector = qt.QWidget()
        imageSelectorLayout = qt.QVBoxLayout(self.imageSelector)
        self.imageSelector.hide()

        imageSelectText = qt.QLabel("Select an Image Volume:")
        imageSelectText.setStyleSheet("font-weight: bold; font-size: 20px")
        imageSelectorLayout.addWidget(imageSelectText)

        returnButton = qt.QPushButton("Back to Sessions List")
        returnButton.setStyleSheet("font-size: 15px")
        returnButton.setFixedWidth(200)
        returnButton.clicked.connect(self.resetToSessionsList)
        imageSelectorLayout.addWidget(returnButton)

        imageSelectorLayout.addStretch(1)

        # self.volumeIsOnServer = False

        self.sessionNameInput = qt.QLineEdit()
        self.sessionNameInput.setPlaceholderText("Session Name")
        self.sessionNameInput.setStyleSheet("background-color: white; font-weight: bold; font-size: 20px; padding: 10px")
        self.sessionNameInput.textChanged.connect(self.updateSessionName)
        imageSelectorLayout.addWidget(self.sessionNameInput)


        # invoke Add Data window
        self.addDataButton = qt.QPushButton("Choose Volume From Files")
        self.addDataButton.setStyleSheet("font-weight: bold; font-size: 20px; background-color: rgb(50,135,255)")
        self.addDataButton.clicked.connect(slicer.util.openAddDataDialog)
        imageSelectorLayout.addWidget(self.addDataButton)

        # Load Data from Server
        # loadDataButton = qt.QPushButton("Load Volume from Server")
        # loadDataButton.setStyleSheet("font-weight: bold; font-size: 20px; background-color: rgb(50,200,100)")
        # loadDataButton.clicked.connect(self.loadDataFromServer)
        # imageSelectorLayout.addWidget(loadDataButton)

        imageSelectorLayout.addStretch(1)

        nextButton = qt.QPushButton("Perform Segmentation")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px")
        nextButton.clicked.connect(self.onPerformSegmentation)
        imageSelectorLayout.addWidget(nextButton)

        layout.addWidget(self.imageSelector)

        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAdded)

        #SEGMENTATIONS

        self.segmentationEditor = qt.QWidget()
        segmentationEditorLayout = qt.QVBoxLayout(self.segmentationEditor)
        self.segmentationEditor.hide()

        segmentationEditorLayout.addWidget(slicer.modules.segmenteditor.widgetRepresentation())

        segmentationEditorLayout.addStretch(1)
        # add next button
        nextButton = qt.QPushButton("Finish and Send to Apple Vision Pro")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px")
        nextButton.clicked.connect(self.onFinishSegmentation)
        segmentationEditorLayout.addWidget(nextButton)

        layout.addWidget(self.segmentationEditor)
        
        #VISION PRO CONNECTION

        self.visionProInterface = qt.QWidget()
        visionProInterfaceLayout = qt.QVBoxLayout(self.visionProInterface)
        self.visionProInterface.hide()

        self.visionProConnectionWidget = slicer.modules.applevisionpromodule.widgetRepresentation()
        self.visionProConnectionWidget.setContentsMargins(-10,-10,-10,-10)
        visionProInterfaceLayout.addWidget(self.visionProConnectionWidget)

        visionProInterfaceLayout.addStretch(1)

        backButton = qt.QPushButton("Reset and Go Back to Image Selector")
        backButton.setStyleSheet("font-weight: bold; font-size: 20px")
        backButton.clicked.connect(self.resetToSessionsList)
        visionProInterfaceLayout.addWidget(backButton)

        layout.addWidget(self.visionProInterface)

        self.initializeParameterNode()
        # Connections
        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.EndCloseEvent, self.onSceneEndClose)

        if saved_openigt_address and saved_image_server_address:
            self.showSessionsList()

    def loadDataFromServer(self, *_):
        self.setIPAddresses()
        self.connectToImageServer()
        self.monailabel.ui.strategyBox.currentText = "first"
        self.monailabel.onNextSampleButton()
        # self.volumeIsOnServer = True

    def onFinishConfiguration(self):
        self.showSessionsList()
        self.saveIPAddresses()

    def onPerformSegmentation(self):

        self.setIPAddresses()
        self.connectToImageServer()
        # if not self.volumeIsOnServer:
        if self.hasActiveSession():
            if self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode:
                self.uploadVolume(self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode)

        # self.volumeIsOnServer = False
        self.showSegmentationEditor()


    #re-implementation from monai-label module
    def uploadVolume(self, volumeNode):
        image_id = volumeNode.GetName()

        if not self.monailabel.getPermissionForImageDataUpload():
            return False
        
        if not volumeNode:
            return False
        
        try:
            qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
            in_file = tempfile.NamedTemporaryFile(suffix=self.monailabel.file_ext, dir=self.monailabel.tmpdir).name

            slicer.util.saveNode(volumeNode, in_file)

            self.monailabel.logic.upload_image(in_file, image_id)
            self.monailabel.current_sample["session"] = False

            self.monailabel._volumeNode = volumeNode
            self.monailabel.initSample({"id": image_id}, autosegment=True)
            qt.QApplication.restoreOverrideCursor()

            return True
        except BaseException as e:
            msg = f"Message: {e.msg}" if hasattr(e, "msg") else ""
            qt.QApplication.restoreOverrideCursor()
            slicer.util.errorDisplay(
                _("Failed to upload volume to Server.\n{message}").format(message=msg),
            )

    def onFinishSegmentation(self):
        self.showVisionProInterface()
        self.monailabel.onSaveLabel()
        self.monailabel.onTraining()
        self.exportSegmentationsToModels()
        self.setIPAddresses()
   
    def resetToSessionsList(self):
        # self.volumeIsOnServer = False
        self.monailabel.onResetScribbles()
        if self.hasActiveSession():
            volume = self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode
            if volume:
                volume.GetDisplayNode().SetVisibility(False)
        self._parameterNode.activeSession = None
        self.showSessionsList()

    @vtk.calldata_type(vtk.VTK_OBJECT)
    def onNodeAdded(self, caller, event, callData):
        if self.hasActiveSession():
            node = callData
            if isinstance(node, vtkMRMLScalarVolumeNode):
                self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode = node

    #HANDLE LAYOUT "TABS"
    def showConfigurationScreen(self):
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.visionProInterface.hide()
        self.sessionsList.hide()
        self.configurationScreen.show()
    
    def showSessionsList(self):
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.visionProInterface.hide()
        self.configurationScreen.hide()
        self.sessionsList.show()

    def showImageSelector(self):
        self.sessionsList.hide()
        self.segmentationEditor.hide()
        self.visionProInterface.hide()
        self.configurationScreen.hide()
        self.imageSelector.show()
    
    def showSegmentationEditor(self):
        self.sessionsList.hide()
        self.imageSelector.hide()
        self.visionProInterface.hide()
        self.configurationScreen.hide()
        self.segmentationEditor.show()
    
    def showVisionProInterface(self):
        self.sessionsList.hide()
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.configurationScreen.hide()
        self.visionProInterface.show()
    
    def showVolumeNode(self, volumeNode):
        #loop through all volume nodes and hide them
        slicer.util.setSliceViewerLayers(background=volumeNode)
        slicer.util.resetSliceViews()


    def validateIPAddress(self, *_):
        if self.image_server_address_input.text.strip() == "" or self.openigt_address_input.text.strip() == "":
            self.toImageSelectorButton.setEnabled(False)
        else:
            self.toImageSelectorButton.setEnabled(True)

    def saveIPAddresses(self):
        """Save IP addresses to settings and move to the next screen."""
        settings = qt.QSettings()
        settings.setValue("SegmentationsHelper/openigt_address", self.openigt_address_input.text)
        settings.setValue("SegmentationsHelper/image_server_address", self.image_server_address_input.text)

    def setIPAddresses(self):
        openigt_address = self.openigt_address_input.text
        image_server_address = self.image_server_address_input.text
        self.monailabel.logic.setServer("http://"+str(image_server_address)+":8000")
        self.monailabel.ui.serverComboBox.currentText = "http://"+str(image_server_address)+":8000"
        self.visionProConnectionWidget.self().ip_address_input.setText(openigt_address)

    def connectToImageServer(self):
        self.monailabel.onClickFetchInfo() #establish connection to the server

    def exportSegmentationsToModels(self):
        segmentation_nodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "Segments")    
        for segmentation_node in segmentation_nodes:
            slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentation_node, exportFolderItemId)
    
    def loadSession(self):
        if self.sessionListSelector.currentRow == -1:
            self._parameterNode.activeSession = None
            return
        self._parameterNode.activeSession = self.sessionListSelector.currentRow
        self.showImageSelector()

    def updateSessionName(self,*_):
        if self.hasActiveSession():
            self._parameterNode.sessions[self._parameterNode.activeSession].name = str(self.sessionNameInput.text)
        
    def syncSessionUI(self):
        self.loadSessionButton.setEnabled(self.sessionListSelector.currentRow != -1)
        if self.sessionListSelector.currentRow == -1:
            return
        session = self._parameterNode.sessions[self.sessionListSelector.currentRow]
        if session:
            self.showVolumeNode(session.volumeNode)

    def addSession(self):
        if not self._parameterNode:
            self.initializeParameterNode()

        session = SegmentationSession()
        session.name = "Session " + str(len(self._parameterNode.sessions) + 1)
        self._parameterNode.sessions.append(session)

    def removeSession(self):
        if not self._parameterNode:
            self.initializeParameterNode()
        row = self.sessionListSelector.currentRow
        if row == -1:
            return
        if slicer.util.confirmOkCancelDisplay(_("Are you sure you want to remove this session?")):
            if self.hasActiveSession():
                if self._parameterNode.activeSession > row:
                    self._parameterNode.activeSession -= 1
                elif self._parameterNode.activeSession == row:
                    self._parameterNode.activeSession = None
            slicer.mrmlScene.RemoveNode(self._parameterNode.sessions[row].volumeNode)
            self._parameterNode.sessions.pop(row)


    def hasActiveSession(self):
        if not self._parameterNode:
            self.initializeParameterNode()
        return self._parameterNode.activeSession != None and self._parameterNode.activeSession < len(self._parameterNode.sessions)
            
    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.
        self.setParameterNode(self.logic.getParameterNode())
        self.onParameterNodeModified()

    def setParameterNode(self, parameterNode: SegmentationsHelperParameterNode) -> None:
        if self._parameterNode:
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.onParameterNodeModified)
        self._parameterNode = parameterNode
        if self._parameterNode:
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.onParameterNodeModified)

    def onParameterNodeModified(self, *_):
        self.removeSessionButton.setEnabled(len(self._parameterNode.sessions) != 0)

        if self.hasActiveSession():
            self.sessionListSelector.setCurrentRow(self._parameterNode.activeSession)
            self.sessionNameInput.setText(self._parameterNode.sessions[self._parameterNode.activeSession].name)
            self.showVolumeNode(self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode)
            if self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode:
                self.addDataButton.setText(self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode.GetName())
                self.addDataButton.setEnabled(False)
            else:
                self.addDataButton.setText("Choose Volume From Files")
                self.addDataButton.setEnabled(True)
        else: 
            self.sessionListSelector.setCurrentRow(-1)
            self.showSessionsList()
        self.sessionListSelector.clear()
        for session in self._parameterNode.sessions:
            if session:
                self.sessionListSelector.addItem(session.name)
        

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()
        self.logic.close()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.onParameterNodeModified)
        self._parameterNode = None

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        # close client
        self.logic.close()
        if self.parent.isEntered:
            self.initializeParameterNode()
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

    def getParameterNode(self):
        return SegmentationsHelperParameterNode(super().getParameterNode())

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def close(self) -> None:
        pass

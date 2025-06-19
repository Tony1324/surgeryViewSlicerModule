import logging
import os
import subprocess
import shutil
from typing import Annotated, Optional
import traceback
import codecs
import requests

import vtk
import SimpleITK as sitk
import sitkUtils

import slicer
import numpy as np
from slicer.parameterNodeWrapper import *
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import qt
from slicer import vtkMRMLScalarVolumeNode
from time import sleep
import tempfile
import re
import vtkSegmentationCorePython as vtkSegmentationCore


os.environ["PATH"] += os.pathsep + "/opt/homebrew/Cellar"
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"

try:
    import whisper
except:
    slicer.util.pip_install('openai-whisper')
    import whisper

try: 
    import markdown_pdf
except:
    slicer.util.pip_install('markdown-pdf')
    import markdown_pdf

try: 
    from transformers import pipeline
except:
    slicer.util.pip_install('transformers')
    from transformers import pipeline

import ScreenCapture

@parameterPack
class SegmentationSession:
    name: str
    segmentationNode: Optional[str] = None
    volumeNode: Optional[str] = None
    geometryNode: Optional[int] = None
    transcription: Optional[str] = None
    summary: Optional[str] = None

@parameterNodeWrapper
class SegmentationsHelperParameterNode:
    activeSession: Optional[int] = None
    previousActiveSession: Optional[int] = None
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
        self.recorder = AudioRecorder()
        self.tmpdir = "/tmp/slicer_segmentations_helper/"
        if not os.path.exists(self.tmpdir):
            os.mkdir(self.tmpdir)

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
            QPushButton:hover { border: 2px solid black} 
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
        
        #
        # SESSION UI
        #

        self.sessionContainer = qt.QWidget()
        sessionContainerLayout = qt.QVBoxLayout(self.sessionContainer)
        sessionContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.sessionContainer.hide()

        sessionTitleContainer = qt.QWidget()
        sessionTitleContainerLayout = qt.QHBoxLayout(sessionTitleContainer)

        sessionContainerLayout.addWidget(sessionTitleContainer)

        returnButton = qt.QPushButton("❮")
        returnButton.setStyleSheet("font-size: 25px; font-weight: bold; border: 1px solid gray; background-color: transparent")
        returnButton.setFixedHeight(40)
        returnButton.clicked.connect(self.resetToSessionsList)
        sessionTitleContainerLayout.addWidget(returnButton)

        self.sessionTitle = qt.QLabel("Session")
        self.sessionTitle.setStyleSheet("font-size: 25px; font-weight: bold")
        sessionTitleContainerLayout.addWidget(self.sessionTitle)

        sessionTitleContainerLayout.addStretch(1)

        sessionTabContainer = qt.QWidget()
        sessionTabContainerLayout = qt.QHBoxLayout(sessionTabContainer)
        sessionTabContainer.setStyleSheet("background-color:lightgray; border-radius: 5px")
        sessionContainerLayout.addWidget(sessionTabContainer)

        self.sessionTabImageButton = qt.QPushButton("Setup and Info")
        self.sessionTabImageButton.setStyleSheet("font-weight: bold; background-color: white")
        self.sessionTabImageButton.setFixedHeight(35)
        self.sessionTabImageButton.clicked.connect(self.showImageSelector)
        sessionTabContainerLayout.addWidget(self.sessionTabImageButton)    

        self.sessionTabSegmentationButton = qt.QPushButton("Segmentation")
        self.sessionTabSegmentationButton.setStyleSheet("background-color: transparent")
        self.sessionTabSegmentationButton.setFixedHeight(35)
        self.sessionTabSegmentationButton.clicked.connect(self.showSegmentationEditor)
        self.sessionTabSegmentationButton.setEnabled(False)
        sessionTabContainerLayout.addWidget(self.sessionTabSegmentationButton)    

        self.sessionTabSessionButton = qt.QPushButton("Patient")
        self.sessionTabSessionButton.setStyleSheet("background-color: transparent")
        self.sessionTabSessionButton.setFixedHeight(35)
        self.sessionTabSessionButton.clicked.connect(self.showActiveSessionInterface)
        # self.sessionTabSessionButton.setEnabled(False)
        sessionTabContainerLayout.addWidget(self.sessionTabSessionButton)    

        layout.addWidget(self.sessionContainer)


        #VOLUME SELECTOR

        self.imageSelector = qt.QWidget()
        imageSelectorLayout = qt.QVBoxLayout(self.imageSelector)
        imageSelectorLayout.setContentsMargins(0, 0, 0, 0)
        self.imageSelector.hide()

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
        sessionContainerLayout.addWidget(self.imageSelector)

        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAdded)

        #SEGMENTATIONS

        self.segmentationEditor = qt.QWidget()
        segmentationEditorLayout = qt.QVBoxLayout(self.segmentationEditor)
        segmentationEditorLayout.setContentsMargins(0, 0, 0, 0)
        self.segmentationEditor.hide()

        nextButton = qt.QPushButton("Perform Segmentation")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px")
        nextButton.clicked.connect(self.onPerformSegmentation)
        segmentationEditorLayout.addWidget(nextButton)

        self.segmentationEditorUI = slicer.qMRMLSegmentEditorWidget()
        self.segmentationEditorUI.setMRMLScene(slicer.mrmlScene)
        children = self.segmentationEditorUI.children()
        children[1].setVisible(False)
        children[2].setVisible(False)
        children[4].setVisible(False)
        children[5].setVisible(False)
        children[6].setVisible(False)
        segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
        slicer.mrmlScene.AddNode(segmentEditorNode)
        self.segmentationEditorUI.setMRMLSegmentEditorNode(segmentEditorNode)
        segmentationEditorLayout.addWidget(self.segmentationEditorUI)

        segmentationEditorLayout.addStretch(1)
        # add next button
        nextButton = qt.QPushButton("Submit Edits")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px")
        nextButton.clicked.connect(self.onFinishSegmentation)
        segmentationEditorLayout.addWidget(nextButton)

        sessionContainerLayout.addWidget(self.segmentationEditor)
        
        #PATIENT SESSION INTERFACE CONNECTION
        self.activeSessionInterface = qt.QWidget()
        activeSessionInterfaceLayout = qt.QVBoxLayout(self.activeSessionInterface)
        activeSessionInterfaceLayout.setContentsMargins(0, 0, 0, 0)
        self.activeSessionInterface.hide()
        sessionContainerLayout.addWidget(self.activeSessionInterface)

        visionProToggleButton = qt.QPushButton("▼ Vision Pro Connection")
        visionProToggleButton.setStyleSheet("font-weight: bold; font-size: 20px; background-color: lightgray")
        visionProToggleButton.clicked.connect(lambda *_: self.visionProInterface.setVisible(not self.visionProInterface.visible))
        activeSessionInterfaceLayout.addWidget(visionProToggleButton)

        self.visionProInterface = qt.QWidget()
        visionProInterfaceLayout = qt.QVBoxLayout(self.visionProInterface)

        self.visionProConnectionWidget = slicer.modules.applevisionpromodule.widgetRepresentation()
        self.visionProConnectionWidget.setContentsMargins(-10,-10,-10,-10)
        visionProInterfaceLayout.addWidget(self.visionProConnectionWidget)

        modelToggleButtons = qt.QWidget()
        modelToggleButtonsLayout = qt.QHBoxLayout(modelToggleButtons)
        modelToggleButtonsLayout.setContentsMargins(0,0,0,0)
        showAllModelButton = qt.QPushButton("Show All Models")
        hideAllModelButton = qt.QPushButton("Hide All Models")
        showAllModelButton.clicked.connect(lambda *_: self.updateGeometryModels(True))
        hideAllModelButton.clicked.connect(lambda *_: self.updateGeometryModels(False))
        modelToggleButtonsLayout.addWidget(showAllModelButton)
        modelToggleButtonsLayout.addWidget(hideAllModelButton)
        visionProInterfaceLayout.addWidget(modelToggleButtons)

        self.geometryModelsList = qt.QWidget()
        self.geometryModelsListLayout = qt.QVBoxLayout(self.geometryModelsList)
        self.geometryModelsListLayout.setContentsMargins(0, 0, 0, 0)
        visionProInterfaceLayout.addWidget(self.geometryModelsList)

        activeSessionInterfaceLayout.addWidget(self.visionProInterface)

        recordingSessionToggleButton = qt.QPushButton("▼ Record Tools")
        recordingSessionToggleButton.setStyleSheet("font-weight: bold; font-size: 20px; background-color: lightgray")
        recordingSessionToggleButton.clicked.connect(lambda *_: self.recordingSession.setVisible(not self.recordingSession.visible))
        activeSessionInterfaceLayout.addWidget(recordingSessionToggleButton)

        self.recordingSession = qt.QWidget()
        recordingSessionLayout = qt.QVBoxLayout(self.recordingSession)
        recordingSessionLayout.setContentsMargins(0,0,0,0)
        self.recordingSession.hide()

        self.recordButton = qt.QPushButton("Begin Recording")
        self.recordButton.setStyleSheet("font-weight: bold; font-size: 20px")
        self.recordButton.clicked.connect(self.onClickedRecord)
        recordingSessionLayout.addWidget(self.recordButton)

        self.recordTranscriptText = qt.QPlainTextEdit()
        self.recordTranscriptText.setStyleSheet("border: 1px solid rgb(180,180,180); border-radius: 5px; background-color: white")
        self.recordTranscriptText.textChanged.connect(self.transcriptTextChanged)
        recordingSessionLayout.addWidget(self.recordTranscriptText)

        self.summarizeTranscriptButton = qt.QPushButton("Summarize Transcript")
        self.summarizeTranscriptButton.setStyleSheet("font-weight: bold; font-size: 20px")
        self.summarizeTranscriptButton.clicked.connect(self.onSummarizeTranscript)
        recordingSessionLayout.addWidget(self.summarizeTranscriptButton)

        self.summarizedTranscriptText = qt.QPlainTextEdit()
        self.summarizedTranscriptText.setStyleSheet("border: 1px solid rgb(180,180,180); border-radius: 5px; background-color: white")
        self.summarizedTranscriptText.textChanged.connect(self.summarizedTranscriptTextChanged)
        recordingSessionLayout.addWidget(self.summarizedTranscriptText)

        self.captureImageButton = qt.QPushButton("Capture Current Screen")
        self.captureImageButton.setStyleSheet("font-weight: bold; font-size: 20px")
        self.captureImageButton.clicked.connect(self.onCaptureImage)
        recordingSessionLayout.addWidget(self.captureImageButton)

        self.exportPDFButton = qt.QPushButton("Export PDF")
        self.exportPDFButton.setStyleSheet("font-weight: bold; font-size: 20px")
        self.exportPDFButton.clicked.connect(self.onExportPDF)
        recordingSessionLayout.addWidget(self.exportPDFButton)

        activeSessionInterfaceLayout.addWidget(self.recordingSession)
        activeSessionInterfaceLayout.addStretch(1)

        self.initializeParameterNode()
        # Connections
        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.EndCloseEvent, self.onSceneEndClose)

        if saved_openigt_address and saved_image_server_address:
            self.showSessionsList()

    # def loadDataFromServer(self, *_):
    #     self.setIPAddresses()
    #     self.connectToImageServer()
    #     self.monailabel.ui.strategyBox.currentText = "first"
    #     self.monailabel.onNextSampleButton()
    #     # self.volumeIsOnServer = True

    def onFinishConfiguration(self):
        self.showSessionsList()
        self.saveIPAddresses()

    @vtk.calldata_type(vtk.VTK_OBJECT)
    def onNodeAdded(self, caller, event, callData):
        node = callData
        if isinstance(node, vtkMRMLScalarVolumeNode):
            if self.hasActiveSession() and self.getActiveSessionVolumeNode() is None:
                self.setActiveSessionVolumeNode(node)
                self.showSegmentationEditor()
                self.showSession(self.getActiveSession())

    #HANDLE LAYOUT "TABS"
    def showConfigurationScreen(self):
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.visionProInterface.hide()
        self.sessionsList.hide()
        self.sessionContainer.hide()
        self.configurationScreen.show()

    
    def showSessionsList(self):
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.activeSessionInterface.hide()
        self.configurationScreen.hide()
        self.sessionContainer.hide()
        self.sessionsList.show()

    def showImageSelector(self):
        self.sessionsList.hide()
        self.segmentationEditor.hide()
        self.activeSessionInterface.hide()
        self.configurationScreen.hide()
        self.sessionContainer.show()
        self.imageSelector.show()
        self.sessionTabImageButton.setStyleSheet("font-weight: bold; background-color: white")
        self.sessionTabSegmentationButton.setStyleSheet("background-color: transparent")
        self.sessionTabSessionButton.setStyleSheet("background-color: transparent")
    
    def showSegmentationEditor(self):
        self.sessionsList.hide()
        self.imageSelector.hide()
        self.activeSessionInterface.hide()
        self.configurationScreen.hide()
        self.segmentationEditor.show()
        self.sessionContainer.show()
        self.sessionTabSegmentationButton.setStyleSheet("font-weight: bold; background-color: white")
        self.sessionTabImageButton.setStyleSheet("background-color: transparent")
        self.sessionTabSessionButton.setStyleSheet("background-color: transparent")
    
    def showActiveSessionInterface(self):
        self.sessionsList.hide()
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.configurationScreen.hide()
        self.activeSessionInterface.show()
        self.sessionContainer.show()
        self.sessionTabSessionButton.setStyleSheet("font-weight: bold; background-color: white")
        self.sessionTabImageButton.setStyleSheet("background-color: transparent")
        self.sessionTabSegmentationButton.setStyleSheet("background-color: transparent")
    
        
    
    def resetToSessionsList(self):
        if self.hasActiveSession():
            self.showSession(None)
        self._parameterNode.activeSession = None
        self.showSessionsList()


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
        self.monailabel.logic.setClientId(slicer.util.settingsValue("MONAILabel/clientId", "user-xyz"))
        self.visionProConnectionWidget.self().ip_address_input.setText(openigt_address)

    def exportSegmentationToModels(self, session):
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), self.getVolumeNodeFromSession(session).GetName() + "_models")
        session.geometryNode = exportFolderItemId
        geoFolder = slicer.vtkMRMLFolderDisplayNode()
        slicer.mrmlScene.AddNode(geoFolder)
        shNode.SetItemDataNode(exportFolderItemId, geoFolder)
        segmentation = self.getSegmentationNodeFromSession(session)
        segmentation.GetDisplayNode().SetVisibility3D(False)
        segmentation.GetSegmentation().SetConversionParameter("Smoothing factor","1.0")
        segmentation.GetSegmentation().CreateRepresentation(vtkSegmentationCore.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName())
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentation, exportFolderItemId)
        self.updateGeometryModels()

    def getGeometryModels(self, session):
        models = vtk.vtkIdList()
        if session and session.geometryNode:
            shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
            shNode.GetItemChildren(session.geometryNode, models)
        return models
   
    def updateGeometryModels(self, toggle=None):
        if self.hasActiveSession():
            session = self.getActiveSession()
            models = self.getGeometryModels(session)
            shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
            while self.geometryModelsListLayout.count():
                item = self.geometryModelsListLayout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
            for i in range(models.GetNumberOfIds()):
                modelId = models.GetId(i)
                model = shNode.GetItemDataNode(modelId)
                if model:
                    toggleButton = qt.QPushButton(model.GetName())
                    toggleButton.setStyleSheet("font-weight: bold; font-size: 15px; text-align: left")
                    if model.GetDisplayNode():
                        if toggle == False:
                            model.GetDisplayNode().SetOpacity(0.1)
                        if toggle:
                            model.GetDisplayNode().SetOpacity(1)
                        if model.GetDisplayNode().GetOpacity() > 0.5:
                            toggleButton.setStyleSheet("font-weight: bold; font-size: 15px; text-align: left")
                        else:
                            toggleButton.setStyleSheet("font-weight: bold; font-size: 15px; text-align: left; background-color: lightgray")
                    
                    # on click, toggle the visibility of the model and change color
                    def clicked(*_, model=model, toggleButton=toggleButton):
                        if model.GetDisplayNode():
                            if model.GetDisplayNode().GetOpacity() > 0.5:
                                model.GetDisplayNode().SetOpacity(0.1)
                                toggleButton.setStyleSheet("font-weight: bold; font-size: 15px; text-align: left; background-color: lightgray")
                            else:
                                model.GetDisplayNode().SetOpacity(1)
                                toggleButton.setStyleSheet("font-weight: bold; font-size: 15px; text-align: left")
                    toggleButton.clicked.connect(clicked)
                    self.geometryModelsListLayout.addWidget(toggleButton)

    def onPerformSegmentation(self):
        self.setIPAddresses()
        if self.hasActiveSession():
            volume = self.getActiveSessionVolumeNode()
            if volume:
                self.uploadVolume(volume)
                slicer.app.processEvents()
                self.performSegmentation()
                self.showSegmentationEditor()

    def uploadVolume(self, volumeNode):
        image_id = volumeNode.GetName()

        if not self.monailabel.getPermissionForImageDataUpload():
            return False
        
        if not volumeNode:
            return False
        
        try:
            in_file = tempfile.NamedTemporaryFile(suffix=self.monailabel.file_ext, dir=self.monailabel.tmpdir).name

            slicer.util.saveNode(volumeNode, in_file)

            self.monailabel.logic.upload_image(in_file, image_id)

            if self._parameterNode.sessions[self._parameterNode.activeSession].segmentationNode is None:
                name = "segmentation_" + image_id
                segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
                segmentationNode.SetName(name)
                segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
                self.setActiveSessionSegmentationNode(segmentationNode)

            return True
        
        except BaseException as e:
            msg = f"Message: {e.msg}" if hasattr(e, "msg") else ""
            qt.QApplication.restoreOverrideCursor()
            slicer.util.errorDisplay(
                _("Failed to upload volume to Server.\n{message}").format(message=msg),
            )

    def performSegmentation(self):
        # try:
        model = "deepedit"
        image_file = self.getActiveSessionVolumeNode().GetName()
        params = self.monailabel.getParamsFromConfig("infer", model)

        result_file, params = self.monailabel.logic.infer(model, image_file, params)
        print(f"Result Params for Segmentation: {params}")

        labels = (
            params.get("label_names") if params and params.get("label_names") else self.models[model].get("labels")
        )
        if labels and isinstance(labels, dict):
            labels = [k for k, _ in sorted(labels.items(), key=lambda item: item[1])]
        # self.monailabel._segmentNode = self._parameterNode.sessions[self._parameterNode.activeSession].segmentationNode
        self.updateSegmentationMask(result_file, labels)
        # except BaseException as e:
        #     msg = f"Message: {e.msg}" if hasattr(e, "msg") else ""
        #     slicer.util.errorDisplay(
        #         _("Failed to run inference in MONAI Label Server.\n{message}").format(message=msg)
        #     )

    def updateSegmentationMask(self, in_file, labels):

        if in_file and not os.path.exists(in_file):
            return False

        segmentationNode = self.getActiveSessionSegmentationNode()
        segmentation = segmentationNode.GetSegmentation()

        if in_file is None:
            for label in labels:
                if not segmentation.GetSegmentIdBySegmentName(label):
                    segmentation.AddEmptySegment(label, label, self.getLabelColor(label))
            return True

        if in_file.endswith(".seg.nrrd") and self.file_ext == ".seg.nrrd":
            source_node = slicer.modules.segmentations.logic().LoadSegmentationFromFile(in_file, False)
            destination_node = segmentationNode
            destination_segmentations = destination_node.GetSegmentation()
            source_segmentations = source_node.GetSegmentation()

            destination_segmentations.DeepCopy(source_segmentations)

            if self._volumeNode:
                destination_node.SetReferenceImageGeometryParameterFromVolumeNode(self._volumeNode)

            slicer.mrmlScene.RemoveNode(source_node)
        elif in_file.endswith(".json"):
            slicer.util.loadMarkups(in_file)
            detectionROIs = slicer.mrmlScene.GetNodesByClass("vtkMRMLMarkupsROINode")  # Get all ROI node from scene
            numNodes = detectionROIs.GetNumberOfItems()
            for i in range(numNodes):
                ROINode = detectionROIs.GetItemAsObject(i)
                if ROINode.GetName() != "Scribbles ROI":
                    ROINode.SetName(f"Detection ROI - {i}")
                    ROINode.GetDisplayNode().SetInteractionHandleScale(0.7)  # set handle size
        else:
            labels = [label for label in labels if label != "background"]

            labelImage = sitk.ReadImage(in_file)
            labelmapVolumeNode = sitkUtils.PushVolumeToSlicer(labelImage, None, className="vtkMRMLLabelMapVolumeNode")

            segmentIds = vtk.vtkStringArray()
            for label in labels:
                segmentIds.InsertNextValue(label)

            # faster import (based on selected segmentIds)

            # ImportLabelmapToSegmentationNode overwrites segments, which removes all non-source representations.
            # We remember if closed surface representation was present and restore it after import.
            segmentationRepresentationNames = []
            segmentationNode.GetSegmentation().GetContainedRepresentationNames(segmentationRepresentationNames)
            hasClosedSurfaceRepresentation = (
                slicer.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName()
                in segmentationRepresentationNames
            )

            slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
                labelmapVolumeNode, segmentationNode, segmentIds
            )

            if hasClosedSurfaceRepresentation:
                segmentationNode.CreateClosedSurfaceRepresentation()

            slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
        return True

    def onSaveLabel(self):
        labelmapVolumeNode = None
        result = None

        try:
            qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

            segmentationNode = self.getActiveSessionSegmentationNode()
            segmentation = segmentationNode.GetSegmentation()
            totalSegments = segmentation.GetNumberOfSegments()
            segmentIds = [segmentation.GetNthSegmentID(i) for i in range(totalSegments)]

            # remove background and scribbles labels
            label_info = []
            save_segment_ids = vtk.vtkStringArray()
            for idx, segmentId in enumerate(segmentIds):
                segment = segmentation.GetSegment(segmentId)
                if segment.GetName() in ["background", "foreground_scribbles", "background_scribbles"]:
                    logging.info(f"Removing segment {segmentId}: {segment.GetName()}")
                    continue

                save_segment_ids.InsertNextValue(segmentId)
                label_info.append({"name": segment.GetName(), "idx": idx + 1})
                # label_info.append({"color": segment.GetColor()})

            # export labelmap
            labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
            slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
                segmentationNode, save_segment_ids, labelmapVolumeNode, self.getActiveSessionVolumeNode()
            )

            label_in = tempfile.NamedTemporaryFile(suffix=".nii.gz", dir=self.monailabel.tmpdir).name

            if (
                slicer.util.settingsValue("MONAILabel/allowOverlappingSegments", True, converter=slicer.util.toBool)
                and slicer.util.settingsValue("MONAILabel/fileExtension", self.file_ext) == ".seg.nrrd"
            ):
                slicer.util.saveNode(segmentationNode, label_in)
            else:
                slicer.util.saveNode(labelmapVolumeNode, label_in)

            result = self.monailabel.logic.save_label(self.getActiveSessionVolumeNode().GetName(), label_in, {"label_info": label_info})

        except BaseException as e:
            print(e)
            msg = f"Message: {e.msg}" if hasattr(e, "msg") else ""
            slicer.util.errorDisplay(
                _("Failed to save Label to MONAI Label Server.\n{message}").format(message=msg)
            )
        finally:
            qt.QApplication.restoreOverrideCursor()

            if labelmapVolumeNode:
                slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
            if result:
                slicer.util.infoDisplay(
                    _("Label-Mask saved into MONAI Label Server")
                )
    
    def onTraining(self):
        try:
            qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

            model = "deepedit"

            params = self.monailabel.getParamsFromConfig("train", model)

        except BaseException as e:
            msg = f"Message: {e.msg}" if hasattr(e, "msg") else ""
            slicer.util.errorDisplay(
                _("Failed to run training in MONAI Label Server.\n{message}").format(message=msg)
            )
        finally:
            qt.QApplication.restoreOverrideCursor()

    def onFinishSegmentation(self):
        self.showActiveSessionInterface()
        self.onSaveLabel()
        self.onTraining()
        self.exportSegmentationToModels(self.getActiveSession())
        self.setIPAddresses()

    def onClickedRecord(self):
        if self.recordButton.text == "Begin Recording":
            self.recordButton.setText("Recording")
            self.recordButton.setStyleSheet("background-color: red; font-weight: bold; font-size: 20px")
            self.recorder.startRecording()
        else:
            if slicer.util.confirmOkCancelDisplay(_("Stop Recording?")):
                self.recordButton.setText("Begin Recording")
                self.recordButton.setStyleSheet("font-weight: bold; font-size: 20px")
                text = self.recorder.stopRecording()
                if text:
                    self.recordTranscriptText.setPlainText(text)
                    self._parameterNode.sessions[self._parameterNode.activeSession].transcription = text
    
    def onSummarizeTranscript(self):
        if self.recordTranscriptText.toPlainText() == "":
            return
        text = self.logic.sendTranscriptForSummary(self.recordTranscriptText.toPlainText(), self.image_server_address_input.text)
        if text == "":
            return
        session = self.getActiveSession()
        if session:
            self.summarizedTranscriptText.setPlainText(codecs.decode(text, 'utf-8'))
            session.summary = codecs.decode(text, 'utf-8')
   
    def onCaptureImage(self):
        self.logic.captureMainScreen(self.tmpdir + self.getSessionFormattedName(self.getActiveSession()) + "_image.png")
    
    def onExportPDF(self):
        imagepath = self.getSessionFormattedName(self.getActiveSession()) + "_image.png"
        if not os.path.exists(imagepath):
            self.onCaptureImage()
        dir = qt.QFileDialog.getExistingDirectory()
        if not dir:
            return
        pdf = markdown_pdf.MarkdownPdf()
        pdf.add_section(markdown_pdf.Section("# Transcript Summary \n ![image](" + imagepath +") \n \n " + self.summarizedTranscriptText.toPlainText(), root=self.tmpdir, toc=False), user_css="* {font-family: sans-serif;}")

        pdf.save(os.path.join(dir, self.getSessionFormattedName(self.getActiveSession()) + "_transcript.pdf"))
        subprocess.call(('open', os.path.join(dir, self.getSessionFormattedName(self.getActiveSession()) + "_transcript.pdf")))

    def transcriptTextChanged(self):
        session = self.getActiveSession()
        if session:
            session.transcription = self.recordTranscriptText.toPlainText()

    def summarizedTranscriptTextChanged(self):
        session = self.getActiveSession()
        if session:
            session.summary = self.summarizedTranscriptText.toPlainText()

    def getActiveSession(self):
        if self.hasActiveSession():
            return self._parameterNode.sessions[self._parameterNode.activeSession]
        return None
    
    def getSessionFormattedName(self, session):
        if session:
            str = session.name
            cleaned = str.lower()
            cleaned = re.sub(r'[^a-z0-9_\-\.]', "_", cleaned)
            cleaned = re.sub(f'{re.escape("_")}+', "_", cleaned)
            cleaned = cleaned.strip("_")
            return cleaned
        return "default_session"
    
    def getVolumeNodeFromSession(self, session):
        if session and session.volumeNode:
            return slicer.mrmlScene.GetNodeByID(session.volumeNode)
        return None
    
    def getActiveSessionVolumeNode(self):
        if self.hasActiveSession():
           return self.getVolumeNodeFromSession(self._parameterNode.sessions[self._parameterNode.activeSession])
        return None
    
    def setActiveSessionVolumeNode(self, volumeNode):
        if self.hasActiveSession():
            self._parameterNode.sessions[self._parameterNode.activeSession].volumeNode = volumeNode.GetID()
    
    def getSegmentationNodeFromSession(self, session):
        if session and session.segmentationNode:
            return slicer.mrmlScene.GetNodeByID(session.segmentationNode)
        return None
    
    def getActiveSessionSegmentationNode(self):
        if self.hasActiveSession():
            return self.getSegmentationNodeFromSession(self._parameterNode.sessions[self._parameterNode.activeSession])
        return None

    def setActiveSessionSegmentationNode(self, segmentationNode):
        if self.hasActiveSession():
            self._parameterNode.sessions[self._parameterNode.activeSession].segmentationNode = segmentationNode.GetID()

    def getGeometryNodeFromSession(self, session):
        if session and session.geometryNode:
            folders = vtk.vtkCollection()
            slicer.mrmlScene.GetSubjectHierarchyNode().GetDataNodesInBranch(session.geometryNode, folders)
            return folders.GetItemAsObject(0)
        return None
    
    def getActiveSessionGeometryNode(self):
        if self.hasActiveSession():
            return self.getGeometryNodeFromSession(self._parameterNode.sessions[self._parameterNode.activeSession])
        return None

    def setActiveSessionGeometryNode(self, geometryNode):
        if self.hasActiveSession():
            self._parameterNode.sessions[self._parameterNode.activeSession].geometryNode = geometryNode.GetID()

    def loadSession(self):
        row = self.sessionListSelector.currentRow
        if row == -1:
            self._parameterNode.activeSession = None
            return
        self._parameterNode.activeSession = row
        
        session = self._parameterNode.sessions[row]
        if session.transcription:
            self.recordTranscriptText.setPlainText(session.transcription)
        else: 
            self.recordTranscriptText.setPlainText("")
        if session.summary:
            self.summarizedTranscriptText.setPlainText(session.summary)
        else:
            self.summarizedTranscriptText.setPlainText("")
        self.showImageSelector()

    def updateSessionName(self,*_):
        if self.hasActiveSession():
            self._parameterNode.sessions[self._parameterNode.activeSession].name = str(self.sessionNameInput.text)
    

    def showSession(self, session):
        for _session in self._parameterNode.sessions:
            try: 
                if (s:=self.getSegmentationNodeFromSession(_session)) != None:
                    s.GetDisplayNode().SetVisibility(False)
                if _session.geometryNode != None:
                    sh = slicer.mrmlScene.GetSubjectHierarchyNode()
                    sh.SetItemDisplayVisibility(_session.geometryNode, False)
            except:
                pass
        if session:
            try:
                slicer.util.setSliceViewerLayers(self.getVolumeNodeFromSession(session))
                if (s:=self.getSegmentationNodeFromSession(session)) != None:
                    s.GetDisplayNode().SetVisibility(True)
                if session.geometryNode != None:
                    print(session.geometryNode)
                    sh = slicer.mrmlScene.GetSubjectHierarchyNode()
                    sh.SetItemDisplayVisibility(session.geometryNode, True)
            except:
                pass
        else:
            slicer.util.setSliceViewerLayers(None)
        slicer.util.resetSliceViews()

    def syncSessionUI(self):
        self.loadSessionButton.setEnabled(self.sessionListSelector.currentRow != -1)
        if self.sessionListSelector.currentRow == -1:
            return
        session = self._parameterNode.sessions[self.sessionListSelector.currentRow]
        if session:
            self.showSession(session)

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
            if v:=self._parameterNode.sessions[row].volumeNode:
                slicer.mrmlScene.RemoveNode(slicer.mrmlScene.GetNodeByID(v))
            if s:=self._parameterNode.sessions[row].segmentationNode:
                slicer.mrmlScene.RemoveNode(slicer.mrmlScene.GetNodeByID(s))
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
            if self._parameterNode.activeSession != self._parameterNode.previousActiveSession:
                self.showSession(self._parameterNode.sessions[self._parameterNode.activeSession])
                self.sessionListSelector.setCurrentRow(self._parameterNode.activeSession)
                self.sessionNameInput.setText(self._parameterNode.sessions[self._parameterNode.activeSession].name)
                self.sessionTitle.setText(self._parameterNode.sessions[self._parameterNode.activeSession].name)

                self._parameterNode.previousActiveSession = self._parameterNode.activeSession
                self.updateGeometryModels()
                self.visionProConnectionWidget.self().session = self.getActiveSession()

            volume = self.getActiveSessionVolumeNode()
            if volume:
                self.addDataButton.setText(volume.GetName())
                self.addDataButton.setEnabled(False)
                self.sessionTabSegmentationButton.setEnabled(True)
            else:
                self.sessionTabSegmentationButton.setEnabled(False)
                # self.sessionTabSessionButton.setEnabled(False)
                self.addDataButton.setText("Choose Volume From Files")
                self.addDataButton.setEnabled(True)

            segmentation = self.getActiveSessionSegmentationNode()
            if segmentation:
                self.sessionTabSessionButton.setEnabled(True)
                self.segmentationEditorUI.setSegmentationNode(segmentation)
                self.segmentationEditorUI.setSourceVolumeNode(volume)
            else:
                self.segmentationEditorUI.setSegmentationNode(None)
                self.segmentationEditorUI.setSourceVolumeNode(None)
            
        else: 
            self.sessionListSelector.setCurrentRow(-1)
            self.sessionTabSegmentationButton.setEnabled(False)
            # self.sessionTabSessionButton.setEnabled(False)
            self.showSessionsList()
        self.sessionListSelector.clear()
        for session in self._parameterNode.sessions:
            if session:
                self.sessionListSelector.addItem(session.name)
        

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()
        self.visionProConnectionWidget.self().session = None
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
        self.logic.recordingStream.stop()
        self.logic.recordingStream.close()

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
    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)
        self.connector = None

    def getParameterNode(self):
        return SegmentationsHelperParameterNode(super().getParameterNode())
    
    def sendTranscriptForSummary(self, text, ip):
        headers = {'Content-Type': 'text/plain'}
        response = requests.post("http://"+ip+":18944",data="You are part of a medical software, a visualization tool that helps surgeons explain their own anatomy to patients. You are provided a transcript of their conversation during a session. Provide a brief paragraph summary of the conversation, then generate a list of questions of importance in detail and their responses. If transcript is too short to provide sufficient summary or questions, reduce length of output and do not speculate. Output in valid markdown without other formatting: " + text,headers=headers)
        print(response.content)
        return response.content

    def captureMainScreen(self, path):
        viewNodeID = "vtkMRMLViewNode1"
        cap = ScreenCapture.ScreenCaptureLogic()
        view = cap.viewFromNode(slicer.mrmlScene.GetNodeByID(viewNodeID))
        cap.captureImageFromView(view, path)

    def close(self) -> None:
        pass

class AudioRecorder:
    def __init__(self):
        self.process = None
        self.temp_audio_path = None

    def startRecording(self):
        """Starts the recording process using an external QProcess."""
        self.temp_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name  # Create a temp file
        self.process = qt.QProcess()
        
        # Construct recording command using FFmpeg (cross-platform)
        command = [
            "ffmpeg", "-y", "-f", "avfoundation", 
            "-i", ":default",
            "-ac", "1", "-ar", "14400", "-acodec", "pcm_s16le", self.temp_audio_path
        ]

        print(f"Starting recording: {' '.join(command)}")
        self.process.start(command[0], command[1:])

    def stopRecording(self):
        """Stops the recording process and processes the output file."""
        if self.process:
            self.process.write(b"q\n")
            self.process.waitForFinished()
            print(f"Recording stopped. Audio saved to: {self.temp_audio_path}")
            
            # Process the recorded file
            return self.transcribeAudio()

    def transcribeAudio(self):
        """Passes the recorded file to Whisper for transcription."""
        model = whisper.load_model("base")
        result = model.transcribe(self.temp_audio_path)
        return result["text"]
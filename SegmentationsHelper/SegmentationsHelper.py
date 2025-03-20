import logging
import os
from typing import Annotated, Optional

import vtk
import SimpleITK as sitk
import sitkUtils

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
    segmentationNode: Optional[str] = None
    volumeNode: Optional[str] = None
    geometryNode: Optional[str] = None

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
        
        #
        # SESSION UI
        #

        self.sessionContainer = qt.QWidget()
        sessionContainerLayout = qt.QVBoxLayout(self.sessionContainer)
        sessionContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.sessionContainer.hide()

        sessionTitleContainer = qt.QPushButton()
        sessionTitleContainerLayout = qt.QHBoxLayout(sessionTitleContainer)
        sessionTitleContainer.setStyleSheet("background-color: transparent; border-radius: 5px")
        sessionTitleContainer.clicked.connect(self.resetToSessionsList)

        sessionContainerLayout.addWidget(sessionTitleContainer)

        returnButton = qt.QLabel("<")
        returnButton.setStyleSheet("font-size: 25px; font-weight: bold")
        sessionTitleContainerLayout.addWidget(returnButton)

        self.sessionTitle = qt.QLabel("Session")
        self.sessionTitle.setStyleSheet("font-size: 25px; font-weight: bold")
        sessionTitleContainerLayout.addWidget(self.sessionTitle)

        sessionTitleContainerLayout.addStretch(1)

        sessionTabContainer = qt.QWidget()
        sessionTabContainerLayout = qt.QHBoxLayout(sessionTabContainer)
        sessionTabContainerLayout.setContentsMargins(0, 0, 0, 0)
        sessionTabContainer.setStyleSheet("background-color:lightgray; border-radius: 5px")
        sessionContainerLayout.addWidget(sessionTabContainer)

        sessionTabImageButton = qt.QPushButton("Setup and Info")
        sessionTabImageButton.setStyleSheet("font-weight: bold; background-color: white")
        sessionTabImageButton.clicked.connect(self.showImageSelector)
        sessionTabContainerLayout.addWidget(sessionTabImageButton)    

        sessionTabSegmentationButton = qt.QPushButton("Segmentation")
        sessionTabSegmentationButton.setStyleSheet("background-color: transparent")
        sessionTabSegmentationButton.clicked.connect(self.showSegmentationEditor)
        sessionTabContainerLayout.addWidget(sessionTabSegmentationButton)    

        sessionTabSessionButton = qt.QPushButton("Patient")
        sessionTabSessionButton.setStyleSheet("background-color: transparent")
        sessionTabSessionButton.clicked.connect(self.showVisionProInterface)
        sessionTabContainerLayout.addWidget(sessionTabSessionButton)    

        layout.addWidget(self.sessionContainer)


        #VOLUME SELECTOR

        self.imageSelector = qt.QWidget()
        imageSelectorLayout = qt.QVBoxLayout(self.imageSelector)
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
        self.segmentationEditor.hide()

        nextButton = qt.QPushButton("Perform Segmentation")
        nextButton.setStyleSheet("font-weight: bold; font-size: 20px; background-color: rgb(50,200,100)")
        nextButton.clicked.connect(self.onPerformSegmentation)
        segmentationEditorLayout.addWidget(nextButton)

        self.segmentationEditorUI = slicer.qMRMLSegmentEditorWidget()
        self.segmentationEditorUI.setMRMLScene(slicer.mrmlScene)
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
        
        #VISION PRO CONNECTION

        self.visionProInterface = qt.QWidget()
        visionProInterfaceLayout = qt.QVBoxLayout(self.visionProInterface)
        self.visionProInterface.hide()

        self.visionProConnectionWidget = slicer.modules.applevisionpromodule.widgetRepresentation()
        self.visionProConnectionWidget.setContentsMargins(-10,-10,-10,-10)
        visionProInterfaceLayout.addWidget(self.visionProConnectionWidget)

        visionProInterfaceLayout.addStretch(1)

        sessionContainerLayout.addWidget(self.visionProInterface)

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

    @vtk.calldata_type(vtk.VTK_OBJECT)
    def onNodeAdded(self, caller, event, callData):
        if self.hasActiveSession() and self.getActiveSessionVolumeNode() is None:

            node = callData
            if isinstance(node, vtkMRMLScalarVolumeNode):
               self.setActiveSessionVolumeNode(node)

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
        self.visionProInterface.hide()
        self.configurationScreen.hide()
        self.sessionContainer.hide()
        self.sessionsList.show()

    def showImageSelector(self):
        self.sessionsList.hide()
        self.segmentationEditor.hide()
        self.visionProInterface.hide()
        self.configurationScreen.hide()
        self.sessionContainer.show()
        self.imageSelector.show()
    
    def showSegmentationEditor(self):
        self.sessionsList.hide()
        self.imageSelector.hide()
        self.visionProInterface.hide()
        self.configurationScreen.hide()
        self.segmentationEditor.show()
        self.sessionContainer.show()
    
    def showVisionProInterface(self):
        self.sessionsList.hide()
        self.imageSelector.hide()
        self.segmentationEditor.hide()
        self.configurationScreen.hide()
        self.visionProInterface.show()
        self.sessionContainer.show()
    
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
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(self.getSegmentationNodeFromSession(session), exportFolderItemId)

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
                segmentationNode, save_segment_ids, labelmapVolumeNode, self._volumeNode
            )

            label_in = tempfile.NamedTemporaryFile(suffix=self.file_ext, dir=self.tmpdir).name

            if (
                slicer.util.settingsValue("MONAILabel/allowOverlappingSegments", True, converter=slicer.util.toBool)
                and slicer.util.settingsValue("MONAILabel/fileExtension", self.file_ext) == ".seg.nrrd"
            ):
                slicer.util.saveNode(segmentationNode, label_in)
            else:
                slicer.util.saveNode(labelmapVolumeNode, label_in)

            result = self.monailabel.logic.save_label(self.current_sample["id"], label_in, {"label_info": label_info})

        except BaseException as e:
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
                    _("Label-Mask saved into MONAI Label Server"), detailedText=json.dumps(result, indent=2)
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
        self.showVisionProInterface()
        self.onSaveLabel()
        self.onTraining()
        self.exportSegmentationToModels(self.getActiveSession())
        self.setIPAddresses()
   
    def getActiveSession(self):
        if self.hasActiveSession():
            return self._parameterNode.sessions[self._parameterNode.activeSession]
        return None
    
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
            return slicer.mrmlScene.GetNodeByID(session.geometryNode)
        return None
    
    def getActiveSessionGeometryNode(self):
        if self.hasActiveSession():
            return self.getGeometryNodeFromSession(self._parameterNode.sessions[self._parameterNode.activeSession])
        return None

    def setActiveSessionGeometryNode(self, geometryNode):
        if self.hasActiveSession():
            self._parameterNode.sessions[self._parameterNode.activeSession].geometryNode = geometryNode.GetID()

    def loadSession(self):
        if self.sessionListSelector.currentRow == -1:
            self._parameterNode.activeSession = None
            return
        self._parameterNode.activeSession = self.sessionListSelector.currentRow
        self.showImageSelector()

    def updateSessionName(self,*_):
        if self.hasActiveSession():
            self._parameterNode.sessions[self._parameterNode.activeSession].name = str(self.sessionNameInput.text)
    

    def showSession(self, session):
        slicer.util.resetSliceViews()
        for _session in self._parameterNode.sessions:
            if (s:=self.getSegmentationNodeFromSession(_session)) != None:
                s.GetDisplayNode().SetVisibility(False)
            if (g:=self.getGeometryNodeFromSession(_session)) != None:
                g.GetDisplayNode().VisibilityOff()
        if session:
            slicer.util.setSliceViewerLayers(self.getVolumeNodeFromSession(session))
            if (s:=self.getSegmentationNodeFromSession(session)) != None:
                s.GetDisplayNode().SetVisibility(True)
            if (g:=self.getGeometryNodeFromSession(session)) != None:
                g.GetDisplayNode().VisibilityOn()
        else:
            slicer.util.setSliceViewerLayers(None)

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
            self.sessionListSelector.setCurrentRow(self._parameterNode.activeSession)
            self.sessionNameInput.setText(self._parameterNode.sessions[self._parameterNode.activeSession].name)
            self.sessionTitle.setText(self._parameterNode.sessions[self._parameterNode.activeSession].name)
            self.showSession(self._parameterNode.sessions[self._parameterNode.activeSession])

            volume = self.getActiveSessionVolumeNode()
            if volume:
                self.addDataButton.setText(volume.GetName())
                self.addDataButton.setEnabled(False)
                self.segmentationEditorUI.setSourceVolumeNode(volume)
                self.segmentationEditorUI.setSegmentationNode(self.getActiveSessionSegmentationNode())
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

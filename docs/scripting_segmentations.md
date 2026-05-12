[3D Slicer\\
![Logo](https://slicer.readthedocs.io/en/latest/_static/3D-Slicer-Mark.png)](https://slicer.readthedocs.io/en/latest/index.html)

latest

5.10

5.8

5.6

5.4

5.2

5.0

v4.11


- [About 3D Slicer](https://slicer.readthedocs.io/en/latest/user_guide/about.html)
- [Getting Started](https://slicer.readthedocs.io/en/latest/user_guide/getting_started.html)
- [Get Help](https://slicer.readthedocs.io/en/latest/user_guide/get_help.html)
- [User Interface](https://slicer.readthedocs.io/en/latest/user_guide/user_interface.html)
- [Coordinate systems](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html)
- [Data Loading and Saving](https://slicer.readthedocs.io/en/latest/user_guide/data_loading_and_saving.html)
- [Image Segmentation](https://slicer.readthedocs.io/en/latest/user_guide/image_segmentation.html)
- [Registration](https://slicer.readthedocs.io/en/latest/user_guide/registration.html)
- [Modules](https://slicer.readthedocs.io/en/latest/user_guide/modules/index.html)
- [Extensions](https://slicer.readthedocs.io/en/latest/user_guide/extensions.html)
- [Application settings](https://slicer.readthedocs.io/en/latest/user_guide/settings.html)
- [Developer Guide](https://slicer.readthedocs.io/en/latest/developer_guide/index.html)

[3D Slicer](https://slicer.readthedocs.io/en/latest/index.html)

- [Home](https://slicer.readthedocs.io/en/latest/index.html)
- Segmentations
- [Edit on GitHub](https://github.com/slicer/slicer/blob/main/Docs/developer_guide/script_repository/segmentations.md)

* * *

# Segmentations [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#segmentations "Link to this heading")

## Load a 3D image or model file as segmentation [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#load-a-3d-image-or-model-file-as-segmentation "Link to this heading")

```
# Load segmentation from .seg.nrrd file (includes segment names and colors)
slicer.util.loadSegmentation("c:/tmp/tmp/Segmentation.nrrd")

# Create segmentation from a NIFTI + color table file
colorNode = slicer.util.loadColorTable('c:/tmp/tmp/Segmentation-label_ColorTable.ctbl')
slicer.util.loadSegmentation("c:/tmp/tmp/Segmentation.nii", {'colorNodeID': colorNode.GetID()})

# Create segmentation from a STL file
slicer.util.loadSegmentation("c:/tmp/Segment_1.stl")
```

## Create a segmentation from a labelmap volume and display in 3D [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#create-a-segmentation-from-a-labelmap-volume-and-display-in-3d "Link to this heading")

```
labelmapVolumeNode = getNode("label")
seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, seg)
seg.CreateClosedSurfaceRepresentation()
slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
```

The last line is optional. It removes the original labelmap volume so that the same information is not shown twice.

## Create segmentation from a model node [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#create-segmentation-from-a-model-node "Link to this heading")

```
# Create some model that will be added to a segmentation node
sphere = vtk.vtkSphereSource()
sphere.SetCenter(-6, 30, 28)
sphere.SetRadius(10)
modelNode = slicer.modules.models.logic().AddModel(sphere.GetOutputPort())

# Create segmentation
segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
segmentationNode.CreateDefaultDisplayNodes() # only needed for display

# Import the model into the segmentation node
slicer.modules.segmentations.logic().ImportModelToSegmentationNode(modelNode, segmentationNode)
```

## Export labelmap node from segmentation node [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#export-labelmap-node-from-segmentation-node "Link to this heading")

Export labelmap matching reference geometry of the segmentation:

```
segmentationNode = getNode("Segmentation")
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportAllSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode, slicer.vtkSegmentation.EXTENT_REFERENCE_GEOMETRY)
```

Export smallest possible labelmap:

```
segmentationNode = getNode("Segmentation")
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportAllSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode)
```

Export labelmap that matches geometry of a chosen reference volume:

```
segmentationNode = getNode("Segmentation")
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode, referenceVolumeNode)
```

Export a selection of segments (identified by their names):

```
segmentNames = ["Prostate", "Urethra"]
segmentIds = vtk.vtkStringArray()
for segmentName in segmentNames:
  segmentId = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
  segmentIds.InsertNextValue(segmentId)
slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsToLabelmapNode(segmentationNode, segmentIds, labelmapVolumeNode, referenceVolumeNode)
```

Export to file by pressing `Ctrl+Shift+S` key:

```
outputPath = "c:/tmp"

def exportLabelmap():
  segmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
  referenceVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
  labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
  slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode, referenceVolumeNode)
  filepath = outputPath + "/" + referenceVolumeNode.GetName() + "-label.nrrd"
  slicer.util.saveNode(labelmapVolumeNode, filepath)
  slicer.mrmlScene.RemoveNode(labelmapVolumeNode.GetDisplayNode().GetColorNode())
  slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
  slicer.util.delayDisplay("Segmentation saved to " + filepath)

shortcut = qt.QShortcut(slicer.util.mainWindow())
shortcut.setKey(qt.QKeySequence("Ctrl+Shift+s"))
shortcut.connect( "activated()", exportLabelmap)
```

## Import/export labelmap node using custom label value mapping [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#import-export-labelmap-node-using-custom-label-value-mapping "Link to this heading")

While in segmentation nodes segments are identified by segment ID, name, or terminology; in labelmap nodes a segment can be identified only by its label value.
Slicer can import a labelmap volume into segmentation, visualize/edit the segmentation, then export the segmentation into labelmap volume - preserving the label values in the output. This is achieved by using a color node during labelmap node import and export, which assigns a name for each label value. Segment corresponding to a label value is found by matching the color name to the segment name.

### Create color table node [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#create-color-table-node "Link to this heading")

A color table node can be loaded from a [color table file](https://slicer.readthedocs.io/en/latest/developer_guide/modules/colors.html#color-table-text-file-format-txt-ctbl) or created from scratch like this:

```
segment_names_to_labels = [("ribs", 10), ("right lung", 12), ("left lung", 6)]

colorTableNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLColorTableNode")
colorTableNode.SetTypeToUser()
colorTableNode.HideFromEditorsOff()  # make the color table selectable in the GUI outside Colors module
slicer.mrmlScene.AddNode(colorTableNode); colorTableNode.UnRegister(None)
largestLabelValue = max([name_value[1] for name_value in segment_names_to_labels])
colorTableNode.SetNumberOfColors(largestLabelValue + 1)
import random
for segmentName, labelValue in segment_names_to_labels:
    r = random.uniform(0.0, 1.0)
    g = random.uniform(0.0, 1.0)
    b = random.uniform(0.0, 1.0)
    a = 1.0
    success = colorTableNode.SetColor(labelValue, segmentName, r, g, b, a)
```

### Export labelmap node from segmentation node using custom label value mapping [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#export-labelmap-node-from-segmentation-node-using-custom-label-value-mapping "Link to this heading")

```
segmentationNode = getNode('Segmentation')  # source segmentation node
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")  # export to new labelmap volume
referenceVolumeNode = None # it could be set to the master volume
segmentIds = segmentationNode.GetSegmentation().GetSegmentIDs()  # export all segments
colorTableNode = ...  # created from scratch or loaded from file

slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentIds, labelmapVolumeNode, referenceVolumeNode, slicer.vtkSegmentation.EXTENT_REFERENCE_GEOMETRY, colorTableNode)
```

### Import labelmap node into segmentation node using custom label value mapping [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#import-labelmap-node-into-segmentation-node-using-custom-label-value-mapping "Link to this heading")

```
labelmapVolumeNode = getNode('Volume-label')
segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")  # import into new segmentation node
colorTableNode = ...  # created from scratch or loaded from file

labelmapVolumeNode.GetDisplayNode().SetAndObserveColorNodeID(colorTableNode.GetID())  # just in case the custom color table has not been already associated with the labelmap volume
slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, segmentationNode)
```

## Export model nodes from segmentation node [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#export-model-nodes-from-segmentation-node "Link to this heading")

```
segmentationNode = getNode("Segmentation")
shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "Segments")
slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentationNode, exportFolderItemId)
```

## Create a hollow model from boundary of solid segment [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#create-a-hollow-model-from-boundary-of-solid-segment "Link to this heading")

In most cases, the most robust and flexible tool for creating empty shell models (e.g., vessel wall model from contrast agent segmentation) is the “Hollow” effect in Segment Editor module. However, for very thin shells, extrusion of the exported surface mesh representation may be just as robust and require less memory and computation time. In this case it may be a better approach to to export the segment to a mesh and extrude it along surface normal direction:

Example using Dynamic Modeler module (allows real-time update of parameters, using GUI in Dynamic Modeler module):

```
segmentationNode = getNode("Segmentation")

# Export segments to models
shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "Segments")
slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentationNode, exportFolderItemId)
segmentModels = vtk.vtkCollection()
shNode.GetDataNodesInBranch(exportFolderItemId, segmentModels)
# Get exported model of first segment
modelNode = segmentModels.GetItemAsObject(0)

# Set up Hollow tool
hollowModeler = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLDynamicModelerNode")
hollowModeler.SetToolName("Hollow")
hollowModeler.SetNodeReferenceID("Hollow.InputModel", modelNode.GetID())
hollowedModelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode")  # this node will store the hollow model
hollowModeler.SetNodeReferenceID("Hollow.OutputModel", hollowedModelNode.GetID())
hollowModeler.SetAttribute("ShellThickness", "2.5")  # grow outside
hollowModeler.SetContinuousUpdate(True)  # auto-update output model if input parameters are changed

# Hide inputs, show output
segmentationNode.GetDisplayNode().SetVisibility(False)
modelNode.GetDisplayNode().SetVisibility(False)
hollowedModelNode.GetDisplayNode().SetOpacity(0.5)
```

Example using VTK filters:

```
# Get closed surface representation of the segment
shellThickness = 3.0  # mm
segmentationNode = getNode("Segmentation")
segmentationNode.CreateClosedSurfaceRepresentation()
polyData = segmentationNode.GetClosedSurfaceInternalRepresentation("Segment_1")

# Create shell
extrude = vtk.vtkLinearExtrusionFilter()
extrude.SetInputData(polyData)
extrude.SetExtrusionTypeToNormalExtrusion()
extrude.SetScaleFactor(shellThickness)

# Compute consistent surface normals
triangle_filter = vtk.vtkTriangleFilter()
triangle_filter.SetInputConnection(extrude.GetOutputPort())
normals = vtk.vtkPolyDataNormals()
normals.SetInputConnection(triangle_filter.GetOutputPort())
normals.FlipNormalsOn()

# Save result into new model node
slicer.modules.models.logic().AddModel(normals.GetOutputPort())
```

## Show a segmentation in 3D [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#show-a-segmentation-in-3d "Link to this heading")

Segmentation can only be shown in 3D if closed surface representation (or other 3D-displayable representation) is available. To create closed surface representation:

```
segmentation.CreateClosedSurfaceRepresentation()
```

## Modify segmentation display options [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#modify-segmentation-display-options "Link to this heading")

```
segmentation = getNode('Segmentation')
segmentID = 'Segment_1'

displayNode = segmentation.GetDisplayNode()
displayNode.SetOpacity3D(0.4)  # Set overall opacity of the segmentation
displayNode.SetSegmentOpacity3D(segmentID, 0.2)  # Set opacity of a single segment

# Segment color is not just a display property, but it is stored in the segment itself (and stored in the segmentation file)
segment = segmentation.GetSegmentation().GetSegment(segmentID)
segment.SetColor(1, 0, 0)  # red

# In very special cases (for example, when a segment's color only need to be changed in a specific view)
# the segment color can be overridden in the display node.
# This is not recommended for general use.
displayNode.SetSegmentOverrideColor(segmentID, 0, 0, 1)  # blue
```

## Get a representation of a segment [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#get-a-representation-of-a-segment "Link to this heading")

Access binary labelmap stored in a segmentation node (without exporting it to a volume node) - if it does not exist, it will return None:

```
image = slicer.vtkOrientedImageData()
segmentationNode.GetBinaryLabelmapRepresentation(segmentID, image)
```

Get closed surface, if it does not exist, it will return None:

```
outputPolyData = vtk.vtkPolyData()
segmentationNode.GetClosedSurfaceRepresentation(segmentID, outputPolyData)
```

Get binary labelmap representation. If it does not exist then it will be created for that single segment. Applies parent transforms by default (if not desired, another argument needs to be added to the end: false):

```
import vtkSegmentationCorePython as vtkSegmentationCore
outputOrientedImageData = vtkSegmentationCore.vtkOrientedImageData()
slicer.vtkSlicerSegmentationsModuleLogic.GetSegmentBinaryLabelmapRepresentation(segmentationNode, segmentID, outputOrientedImageData)
```

Same as above, for closed surface representation:

```
outputPolyData = vtk.vtkPolyData()
slicer.vtkSlicerSegmentationsModuleLogic.GetSegmentClosedSurfaceRepresentation(segmentationNode, segmentID, outputPolyData)
```

## Convert all segments using default path and conversion parameters [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#convert-all-segments-using-default-path-and-conversion-parameters "Link to this heading")

```
segmentationNode.CreateBinaryLabelmapRepresentation()
```

## Convert all segments using custom path or conversion parameters [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#convert-all-segments-using-custom-path-or-conversion-parameters "Link to this heading")

Change reference image geometry parameter based on an existing referenceImageData image:

```
referenceGeometry = slicer.vtkSegmentationConverter.SerializeImageGeometry(referenceImageData)
segmentation.SetConversionParameter(slicer.vtkSegmentationConverter.GetReferenceImageGeometryParameterName(), referenceGeometry)
```

## Re-convert using a modified conversion parameter [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#re-convert-using-a-modified-conversion-parameter "Link to this heading")

Changing smoothing factor for closed surface generation:

```
import vtkSegmentationCorePython as vtkSegmentationCore
segmentation = getNode("Segmentation").GetSegmentation()

# Turn of surface smoothing
segmentation.SetConversionParameter("Smoothing factor","0.0")

# Recreate representation using modified parameters (and default conversion path)
segmentation.RemoveRepresentation(vtkSegmentationCore.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName())
segmentation.CreateRepresentation(vtkSegmentationCore.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName())
```

## Create keyboard shortcut for toggling sphere brush for paint and erase effects [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#create-keyboard-shortcut-for-toggling-sphere-brush-for-paint-and-erase-effects "Link to this heading")

```
def toggleSphereBrush():
  segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
  paintEffect = segmentEditorWidget.effectByName("Paint")
  isSphere = paintEffect.integerParameter("BrushSphere")
  # BrushSphere is "common" parameter (shared between paint and erase)
  paintEffect.setCommonParameter("BrushSphere", 0 if isSphere else 1)

shortcut = qt.QShortcut(slicer.util.mainWindow())
shortcut.setKey(qt.QKeySequence("s"))
shortcut.connect("activated()", toggleSphereBrush)
```

## Create keyboard shortcut for toggling visibility of a set of segments [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#create-keyboard-shortcut-for-toggling-visibility-of-a-set-of-segments "Link to this heading")

This script toggles visibility of “completed” segments if Ctrl-k keyboard shortcut is pressed:

```
slicer.segmentationNode = getNode('Segmentation')
slicer.toggledSegmentState="completed"  # it could be "inprogress", "completed", "flagged"
slicer.visibility = True

def toggleSegmentVisibility():
    slicer.visibility = not slicer.visibility
    segmentation = slicer.segmentationNode.GetSegmentation()
    for segmentIndex in range(segmentation.GetNumberOfSegments()):
        segmentId = segmentation.GetNthSegmentID(segmentIndex)
        segmentationStatus = vtk.mutable("")
        if not segmentation.GetSegment(segmentId).GetTag("Segmentation.Status", segmentationStatus):
            continue
        if segmentationStatus != slicer.toggledSegmentState:
            continue
        slicer.segmentationNode.GetDisplayNode().SetSegmentVisibility(segmentId, slicer.visibility)

shortcut = qt.QShortcut(slicer.util.mainWindow())
shortcut.setKey(qt.QKeySequence("Ctrl+k"))
shortcut.connect( "activated()", toggleSegmentVisibility)
```

## Customize list of displayed Segment editor effects [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#customize-list-of-displayed-segment-editor-effects "Link to this heading")

Only show Paint and Erase effects:

```
segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
segmentEditorWidget.setEffectNameOrder(["Paint", "Erase"])
segmentEditorWidget.unorderedEffectsVisible = False
```

Show list of all available effect names:

```
segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
print(segmentEditorWidget.availableEffectNames())
```

## Center all views on a segment [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#center-all-views-on-a-segment "Link to this heading")

This example shows how to center all slice views and 3D views on a segment. The segment’s center is not the segment’s centroid, but the centroid of the largest island in the effect, because the centroid can be in an empty region if the segment is made up of multiple islands.

```
segmentationNode = getNode("Segmentation")
segmentId = "Segment_2"

position = segmentationNode.GetSegmentCenterRAS(segmentId)
print(position)

# Center slice views and cameras on this position
for sliceNode in slicer.util.getNodesByClass('vtkMRMLSliceNode'):
    sliceNode.JumpSliceByCentering(*position)
for camera in slicer.util.getNodesByClass('vtkMRMLCameraNode'):
    camera.SetFocalPoint(position)
```

## Read and write a segment as a numpy array [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#read-and-write-a-segment-as-a-numpy-array "Link to this heading")

This example shows how to read and write voxels of binary labelmap representation of a segment as a numpy array.

```
volumeNode = getNode('MRHead')
segmentationNode = getNode('Segmentation')
segmentId = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName('Segment_1')

# Get segment as numpy array
segmentArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId, volumeNode)

# Modify the segmentation
segmentArray[:] = 0  # clear the segmentation
segmentArray[ slicer.util.arrayFromVolume(volumeNode) > 80 ] = 1  # create segment by simple thresholding of an image
segmentArray[20:80, 40:90, 30:70] = 1  # fill a rectangular region using numpy indexing
slicer.util.updateSegmentBinaryLabelmapFromArray(segmentArray, segmentationNode, segmentId, volumeNode)
```

Segment arrays can also be used in numpy operations to read/write the corresponding region of a volume:

```
# Get voxels of a volume within the segmentation and compute some statistics
volumeArray = slicer.util.arrayFromVolume(volumeNode)
volumeVoxelsInSegmentArray = volumeArray[ segmentArray > 0 ]
print(f"Lowest voxel value in segment: {volumeVoxelsInSegmentArray.min()}")
print(f"Highest voxel value in segment: {volumeVoxelsInSegmentArray.max()}")

# Modify the volume
# For example, increase the contrast inside the selected segment by a factor of 4x:
volumeArray[ segmentArray > 0 ] = volumeArray[ segmentArray > 0 ] * 4
# Indicate that we have completed modifications on the volume array
slicer.util.arrayFromVolumeModified(volumeNode)
```

## Get centroid of a segment in world (RAS) coordinates [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#get-centroid-of-a-segment-in-world-ras-coordinates "Link to this heading")

This example shows how to get centroid of a segment in world coordinates and show that position in all slice views.

```
segmentationNode = getNode("Segmentation")
segmentId = "Segment_1"

# Get array voxel coordinates
import numpy as np
seg = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId)
# numpy array has voxel coordinates in reverse order (KJI instead of IJK)
# and the array is cropped to minimum size in the segmentation
mean_KjiCropped = [coords.mean() for coords in np.nonzero(seg)]

# Get segmentation voxel coordinates
segImage = slicer.vtkOrientedImageData()
segmentationNode.GetBinaryLabelmapRepresentation(segmentId, segImage)
segImageExtent = segImage.GetExtent()
# origin of the array in voxel coordinates is determined by the start extent
mean_Ijk = [mean_KjiCropped[2], mean_KjiCropped[1], mean_KjiCropped[0]] + np.array([segImageExtent[0], segImageExtent[2], segImageExtent[4]])

# Get segmentation physical coordinates
ijkToWorld = vtk.vtkMatrix4x4()
segImage.GetImageToWorldMatrix(ijkToWorld)
mean_World = [0, 0, 0, 1]
ijkToWorld.MultiplyPoint(np.append(mean_Ijk,1.0), mean_World)
mean_World = mean_World[0:3]

# If segmentation node is transformed, apply that transform to get RAS coordinates
transformWorldToRas = vtk.vtkGeneralTransform()
slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(segmentationNode.GetParentTransformNode(), None, transformWorldToRas)
mean_Ras = transformWorldToRas.TransformPoint(mean_World)

# Show mean position value and jump to it in all slice viewers
print(mean_Ras)
slicer.modules.markups.logic().JumpSlicesToLocation(mean_Ras[0], mean_Ras[1], mean_Ras[2], True)
```

## Get histogram of a segmented region [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#get-histogram-of-a-segmented-region "Link to this heading")

```
# Generate example input data (volumeNode, segmentationNode, segmentId)
################################################

# Load source volume
import SampleData
sampleDataLogic = SampleData.SampleDataLogic()
volumeNode = sampleDataLogic.downloadMRBrainTumor1()

# Create segmentation
segmentationNode = slicer.vtkMRMLSegmentationNode()
slicer.mrmlScene.AddNode(segmentationNode)
segmentationNode.CreateDefaultDisplayNodes() # only needed for display
segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

# Create segment
tumorSeed = vtk.vtkSphereSource()
tumorSeed.SetCenter(-6, 30, 28)
tumorSeed.SetRadius(25)
tumorSeed.Update()
segmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(tumorSeed.GetOutput(), "Segment A", [1.0,0.0,0.0])

# Compute histogram
################################################

# Get voxel values of volume in the segmented region
import numpy as np
volumeArray = slicer.util.arrayFromVolume(volumeNode)
segmentArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId, volumeNode)
segmentVoxels = volumeArray[segmentArray != 0]

# Compute histogram
import numpy as np
histogram = np.histogram(segmentVoxels, bins=50)

# Plot histogram
################################################

slicer.util.plot(histogram, xColumnIndex = 1)
```

## Get segments visible at a selected position [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#get-segments-visible-at-a-selected-position "Link to this heading")

Show in the console names of segments visible at a markups control point position:

```
segmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
pointListNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLMarkupsFiducialNode")
sliceViewLabel = "Red"  # any slice view where segmentation node is visible works

def printSegmentNames(unused1=None, unused2=None):

  sliceViewNode = slicer.mrmlScene.GetNodeByID(f"vtkMRMLSliceNode{sliceViewLabel}")
  appLogic = slicer.app.applicationLogic()
  segmentationsDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(sliceViewNode, "vtkMRMLSegmentationsDisplayableManager2D")
  ras = [0,0,0]
  pointListNode.GetNthControlPointPositionWorld(0, ras)
  segmentIds = vtk.vtkStringArray()
  segmentationsDisplayableManager.GetVisibleSegmentsForPosition(ras, segmentationNode.GetDisplayNode(), segmentIds)
  for idIndex in range(segmentIds.GetNumberOfValues()):
    segment = segmentationNode.GetSegmentation().GetSegment(segmentIds.GetValue(idIndex))
    print("Segment found at position {0}: {1}".format(ras, segment.GetName()))

# Observe markup node changes
pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, printSegmentNames)
printSegmentNames()
```

## Set default segmentation options [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#set-default-segmentation-options "Link to this heading")

Allow segments to overlap each other by default:

```
defaultSegmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
defaultSegmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)
slicer.mrmlScene.AddDefaultNode(defaultSegmentEditorNode)
```

To always make this the default, add the lines above to your [.slicerrc.py file](https://slicer.readthedocs.io/en/latest/user_guide/settings.html#application-startup-file).

## How to run segment editor effects from a script [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#how-to-run-segment-editor-effects-from-a-script "Link to this heading")

Editor effects are complex because they need to handle changing source volumes, undo/redo, masking operations, etc. Therefore, it is recommended to use the effect by instantiating a qMRMLSegmentEditorWidget or use/extract processing logic of the effect and use that from a script.

### Use Segment editor effects from script (qMRMLSegmentEditorWidget) [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#use-segment-editor-effects-from-script-qmrmlsegmenteditorwidget "Link to this heading")

Examples:

- [brain tumor segmentation using grow from seeds effect](https://gist.github.com/lassoan/2d5a5b73645f65a5eb6f8d5f97abf31b)

- [AI-assisted brain tumor segmentation](https://gist.github.com/lassoan/ef30bc27a22a648ead7f82243f5cc7d5)

- [skin surface extraction using thresholding and smoothing](https://gist.github.com/lassoan/1673b25d8e7913cbc245b4f09ed853f9)

- [mask a volume with segments and compute histogram for each region](https://gist.github.com/lassoan/2f5071c562108dac8efe277c78f2620f)

- [create fat/muscle/bone segment by thresholding and report volume of each segment](https://gist.github.com/lassoan/5ad51c89521d3cd9c5faf65767506b37)

- [segment cranial cavity automatically in dry bone skull CT](https://gist.github.com/lassoan/4d0b94bda52d5b099432e424e03aa2b1)

- [remove patient table from CT image](https://gist.github.com/lassoan/84d1f9a093dbb6a46c0fcc89279d8088)

- [fill holes inside bones](https://gist.github.com/lassoan/0f45db8bae792ea19ccad36ceefbf52d)


Description of effect parameters are available [here](https://slicer.readthedocs.io/en/latest/developer_guide/modules/segmenteditor.html#effect-parameters).

### Use logic of effect from a script [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#use-logic-of-effect-from-a-script "Link to this heading")

This example shows how to perform operations on segmentations using VTK filters _extracted_ from an effect:

- [brain tumor segmentation using grow from seeds effect](https://gist.github.com/lassoan/7c94c334653010696b2bf96abc0ac8e7)


## Process segment using a VTK filter [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#process-segment-using-a-vtk-filter "Link to this heading")

This example shows how to apply a VTK filter to a segment that dilates the image by a specified margin.

```
segmentationNode = getNode("Segmentation")
segmentId = "Segment_1"
kernelSize = [3,1,5]

# Export segment as vtkImageData (via temporary labelmap volume node)
segmentIds = vtk.vtkStringArray()
segmentIds.InsertNextValue(segmentId)
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentIds, labelmapVolumeNode)

# Process segmentation
segmentImageData = labelmapVolumeNode.GetImageData()
erodeDilate = vtk.vtkImageDilateErode3D()
erodeDilate.SetInputData(segmentImageData)
erodeDilate.SetDilateValue(1)
erodeDilate.SetErodeValue(0)
erodeDilate.SetKernelSize(*kernelSize)
erodeDilate.Update()
segmentImageData.DeepCopy(erodeDilate.GetOutput())

# Import segment from vtkImageData
slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, segmentationNode, segmentIds)

# Cleanup temporary nodes
slicer.mrmlScene.RemoveNode(labelmapVolumeNode.GetDisplayNode().GetColorNode())
slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
```

## Use segmentation files in Python - outside Slicer [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#use-segmentation-files-in-python-outside-slicer "Link to this heading")

You can use [slicerio](https://pypi.org/project/slicerio/) Python package (in any Python environment, not just within Slicer) to get information from segmentation (.seg.nrrd) files.

For example, a common need when training AI tools is to assemble data sets from various sources, which use different label values for the same segments.
If data sets are in .seg.nrrd format, then segment names or standard terminology can be used to identify segments and then assign label values consistently.

### Extract selected segments by standard terminology [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#extract-selected-segments-by-standard-terminology "Link to this heading")

[Segments cannot be reliably identified using “name” (simple string label)](https://github.com/lassoan/slicerio/blob/main/UsingStandardTerminology.md). Instead, it is recommended to use a standard terminology. This code snippet extracts selected segments from a segmentation and writes the result into a nrrd file.

```
# pip install slicerio

import slicerio

input_filename = "path/to/Segmentation.seg.nrrd"
output_filename = "path/to/SegmentationExtracted.seg.nrrd"
segments_to_labels = [\
   ({"category": ["SCT", "123037004", "Anatomical Structure"], "type": ["SCT", "113197003", "Ribs"]}, 1),\
   ({"category": ["SCT", "123037004", "Anatomical Structure"], "type": ["SCT", "39607008", "Lung"], "typeModifier": ["SCT", "24028007", "Right"]}, 3)\
   ]

segmentation = slicerio.read_segmentation(input_filename)
extracted_segmentation = slicerio.extract_segments(segmentation, segments_to_labels)
slicerio.write_segmentation(output_filename, extracted_segmentation)
```

### Extract selected segments by segment name [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#extract-selected-segments-by-segment-name "Link to this heading")

This code snippet extracts selected segments from a segmentation by segment name and writes it into a nrrd file.

```
# pip install slicerio

import slicerio
import nrrd

input_filename = "path/to/Segmentation.seg.nrrd"
output_filename = "path/to/SegmentationExtracted.seg.nrrd"
segment_names_to_labels = [("ribs", 10), ("right lung", 12), ("left lung", 6)]

# Read voxels and metadata from a .seg.nrrd file
voxels, header = nrrd.read(input_filename)
# Get selected segments in a 3D numpy array and updated segment metadata
extracted_voxels, extracted_header = slicerio.extract_segments(voxels, header, segmentation_info, segment_names_to_labels)
# Write extracted segments and metadata to .seg.nrrd file
nrrd.write(output_filename, extracted_voxels, extracted_header)
```

## Clone a segment [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#clone-a-segment "Link to this heading")

A copy of the segment can be created by using `CopySegmentFromSegmentation` method:

```
segmentationNode = getNode("Segmentation")
sourceSegmentName = "Segment_1"

segmentation = segmentationNode.GetSegmentation()
sourceSegmentId = segmentation.GetSegmentIdBySegmentName(sourceSegmentName)
segmentation.CopySegmentFromSegmentation(segmentation, sourceSegmentId)
```

## Resample segmentation to higher resolution [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#resample-segmentation-to-higher-resolution "Link to this heading")

This code snippet can be used to resample internal binary labelmap representation of a segmentation to allow segmenting finer details

```
# Set inputs
volumeNode = getNode("MRHead")
segmentationNode = getNode("Segmentation")

# The higher the oversampling factor is the finer resolution the segmentation will be,
# at the cost of more memory usage and longer computation times.
# Note that oversampling by a factor of 2 increases memory usage by a factor of 2 * 2 * 2 = 8.
oversamplingFactor = 2.0

# Make spacing value uniform for all axes.
# It is useful for removing staircase artifacts in 3D reconstructions but may increase
# memory usage and computation time.
isotropicSpacing = True

# Update geometry of internal binary labelmap representation in segmentation node
segmentationGeometryLogic = slicer.vtkSlicerSegmentationGeometryLogic()
segmentationGeometryLogic.SetInputSegmentationNode(segmentationNode)
segmentationGeometryLogic.SetSourceGeometryNode(volumeNode)
segmentationGeometryLogic.SetOversamplingFactor(oversamplingFactor)
segmentationGeometryLogic.SetIsotropicSpacing(isotropicSpacing)
segmentationGeometryLogic.CalculateOutputGeometry()
segmentationGeometryLogic.SetReferenceImageGeometryInSegmentationNode()
segmentationGeometryLogic.ResampleLabelmapsInSegmentationNode()
```

## Quantifying segments [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#quantifying-segments "Link to this heading")

### Get volume of each segment [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#get-volume-of-each-segment "Link to this heading")

```
segmentationNode = getNode("Segmentation")

# Compute segment statistics
import SegmentStatistics
segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
segStatLogic.computeStatistics()
stats = segStatLogic.getStatistics()

# Display volume of each segment
for segmentId in stats["SegmentIDs"]:
  volume_cm3 = stats[segmentId,"LabelmapSegmentStatisticsPlugin.volume_cm3"]
  segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
  print(f"{segmentName} volume = {volume_cm3} cm3")
```

### Get centroid of each segment [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#get-centroid-of-each-segment "Link to this heading")

Place a markups control point at the centroid of each segment.

```
segmentationNode = getNode("Segmentation")

# Compute centroids
import SegmentStatistics
segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.centroid_ras.enabled", str(True))
segStatLogic.computeStatistics()
stats = segStatLogic.getStatistics()

# Place a markup point in each centroid
pointListNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
pointListNode.CreateDefaultDisplayNodes()
for segmentId in stats["SegmentIDs"]:
  centroid_ras = stats[segmentId,"LabelmapSegmentStatisticsPlugin.centroid_ras"]
  segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
  pointListNode.AddControlPoint(centroid_ras, segmentName)
```

### Get size, position, and orientation of each segment [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#get-size-position-and-orientation-of-each-segment "Link to this heading")

Get oriented bounding box and display them using markups ROI node.

#### Markups ROI [](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html\#markups-roi "Link to this heading")

```
segmentationNode = getNode("Segmentation")

# Compute bounding boxes
import SegmentStatistics
segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_origin_ras.enabled",str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_diameter_mm.enabled",str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_x.enabled",str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_y.enabled",str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_z.enabled",str(True))
segStatLogic.computeStatistics()
stats = segStatLogic.getStatistics()

# Draw ROI for each oriented bounding box
import numpy as np
for segmentId in stats["SegmentIDs"]:
  # Get bounding box
  obb_origin_ras = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_origin_ras"])
  obb_diameter_mm = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_diameter_mm"])
  obb_direction_ras_x = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_x"])
  obb_direction_ras_y = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_y"])
  obb_direction_ras_z = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_z"])
  # Create ROI
  segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
  roi=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode")
  roi.SetName(segment.GetName() + " OBB")
  roi.GetDisplayNode().SetHandlesInteractive(False)  # do not let the user resize the box
  roi.SetSize(obb_diameter_mm)
  # Position and orient ROI using a transform
  obb_center_ras = obb_origin_ras+0.5*(obb_diameter_mm[0] * obb_direction_ras_x + obb_diameter_mm[1] * obb_direction_ras_y + obb_diameter_mm[2] * obb_direction_ras_z)
  boundingBoxToRasTransform = np.row_stack((np.column_stack((obb_direction_ras_x, obb_direction_ras_y, obb_direction_ras_z, obb_center_ras)), (0, 0, 0, 1)))
  boundingBoxToRasTransformMatrix = slicer.util.vtkMatrixFromArray(boundingBoxToRasTransform)
  roi.SetAndObserveObjectToNodeMatrix(boundingBoxToRasTransformMatrix)
```

Note

Complete list of available segment statistics parameters can be obtained by running `segStatLogic.getParameterNode().GetParameterNames()`.

* * *

© Copyright 2026, Slicer Community.

Built with [Sphinx](https://www.sphinx-doc.org/) using a
[theme](https://github.com/readthedocs/sphinx_rtd_theme)
provided by [Read the Docs](https://readthedocs.org/).


![Read the Docs](<Base64-Image-Removed>)latest
Versions**[latest](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html)**[5.10](https://slicer.readthedocs.io/en/5.10/developer_guide/script_repository/segmentations.html)[5.8](https://slicer.readthedocs.io/en/5.8/developer_guide/script_repository/segmentations.html)[5.6](https://slicer.readthedocs.io/en/5.6/developer_guide/script_repository/segmentations.html)[5.4](https://slicer.readthedocs.io/en/5.4/developer_guide/script_repository/segmentations.html)[5.2](https://slicer.readthedocs.io/en/5.2/developer_guide/script_repository/segmentations.html)[5.0](https://slicer.readthedocs.io/en/5.0/developer_guide/script_repository/segmentations.html)[v4.11](https://slicer.readthedocs.io/en/v4.11/developer_guide/script_repository/segmentations.html)Downloads[PDF](https://slicer.readthedocs.io/_/downloads/en/latest/pdf/)[EPUB](https://slicer.readthedocs.io/_/downloads/en/latest/epub/)On Read the Docs[Project Home](https://app.readthedocs.org/projects/slicer/?utm_source=slicer&utm_content=flyout)[Builds](https://app.readthedocs.org/projects/slicer/builds/?utm_source=slicer&utm_content=flyout)Search

* * *

[Addons documentation](https://docs.readthedocs.io/page/addons.html?utm_source=slicer&utm_content=flyout) ― Hosted by
[Read the Docs](https://about.readthedocs.com/?utm_source=slicer&utm_content=flyout)
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
- [Coordinate systems](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#)
  - [Introduction](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#introduction)
    - [World coordinate system](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#world-coordinate-system)
    - [Anatomical coordinate system](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#anatomical-coordinate-system)
    - [Image coordinate system](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#image-coordinate-system)
  - [Image transformation](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#image-transformation)
  - [2D example or calculating an _IJtoLS_-matrix](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#d-example-or-calculating-an-ijtols-matrix)
  - [Coordinate system convention in Slicer](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#coordinate-system-convention-in-slicer)
    - [Relations to other software/conventions](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#relations-to-other-software-conventions)
      - [ITK](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#itk)
      - [Using MATLAB to map Slicer RAS coordinates (e.g. fiducials) to voxel space of a NIfTI Image](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#using-matlab-to-map-slicer-ras-coordinates-e-g-fiducials-to-voxel-space-of-a-nifti-image)
  - [References](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html#references)
- [Data Loading and Saving](https://slicer.readthedocs.io/en/latest/user_guide/data_loading_and_saving.html)
- [Image Segmentation](https://slicer.readthedocs.io/en/latest/user_guide/image_segmentation.html)
- [Registration](https://slicer.readthedocs.io/en/latest/user_guide/registration.html)
- [Modules](https://slicer.readthedocs.io/en/latest/user_guide/modules/index.html)
- [Extensions](https://slicer.readthedocs.io/en/latest/user_guide/extensions.html)
- [Application settings](https://slicer.readthedocs.io/en/latest/user_guide/settings.html)
- [Developer Guide](https://slicer.readthedocs.io/en/latest/developer_guide/index.html)

[3D Slicer](https://slicer.readthedocs.io/en/latest/index.html)

- [Home](https://slicer.readthedocs.io/en/latest/index.html)
- Coordinate systems
- [Edit on GitHub](https://github.com/slicer/slicer/blob/main/Docs/user_guide/coordinate_systems.md)

* * *

# Coordinate systems [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#coordinate-systems "Link to this heading")

## Introduction [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#introduction "Link to this heading")

One of the issues while dealing with medical images and applications are the
differences between the coordinate systems. There are three coordinate systems
commonly used in imaging applications: a difference can be made between the
**world**, **anatomical** and the **image coordinate system**.

The following figure illustrates the three spaces and their corresponding
axes:

![coordinate_systems](https://github.com/Slicer/Slicer/releases/download/docs-resources/coordinate_systems.png)

Each coordinate system serves one purpose and represents its data in
a particular way.

Anatomy image based on an [image shared by the My MS organization](https://my-ms.org/mri_planes.htm).

Note that Chand John of Stanford created a [detailed presentation about the way coordinates are handled in Slicer](https://www.na-mic.org/w/img_auth.php/3/3f/Coordinate_Systems_Demystified.ppt).

### World coordinate system [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#world-coordinate-system "Link to this heading")

The world coordinate system is typically a Cartesian coordinate system in
which a model (e.g. a MRI scanner or a patient) is positioned. Every model has
its own coordinate system but there is only one world coordinate system to
define the position and orientation of each model.

### Anatomical coordinate system [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#anatomical-coordinate-system "Link to this heading")

The most important model coordinate system for medical imaging techniques is
the anatomical space (also called patient coordinate system). This space
consists of three planes to describe the standard anatomical position of a
human:

- the _axial plane_ is parallel to the ground and separates the head
(Superior) from the feet (Inferior).

- the _coronal plane_ is perpendicular to the ground and separates the front
(Anterior) from the back (Posterior).

- the _sagittal plane_ is perpendicular to the ground and separates the Left from the Right.


From these planes it follows that all axes have their notation in a positive
direction (e.g. the negative Superior axis is represented by the Inferior axis).

The anatomical coordinate system is a continuous three-dimensional space in
which an image has been sampled. In neuroimaging, it is common to define this
space with respect to the human whose brain is being scanned. Hence, the 3D
basis is defined along the anatomical axes of anterior-posterior,
inferior-superior, and left-right.

However different medical applications use different definitions of this 3D
basis. Most common are the following bases:

- LPS (Left, Posterior, Superior) is used in DICOM images


𝐿⁢𝑃⁢𝑆=⎧{
{⎨{
{⎩fromrighttowardsleftfromanteriortowardsposteriorfrominferiortowardssuperior⎫{
{⎬{
{⎭

- RAS (Right, Anterior, Superior) is similar to LPS with the first two axes
flipped


𝑅⁢𝐴⁢𝑆=⎧{
{⎨{
{⎩fromlefttowardsrightfromposteriortowardsanteriorfrominferiortowardssuperior⎫{
{⎬{
{⎭

Thus, the only difference between the two conventions is that the sign of the
first two coordinates is inverted.

Both bases are equally useful and logical. It is just necessary to know to
which basis an image is referenced.

### Image coordinate system [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#image-coordinate-system "Link to this heading")

The image coordinate system describes how an image was acquired with respect
to the anatomy. Medical scanners create regular, rectangular arrays of points
and cells which start at the upper left corner. The 𝑖 axis increases to the
right, the 𝑗 axis to the bottom and the 𝑘 axis backwards.

In addition to the intensity value of each voxel (𝑖⁢𝑗⁢𝑘) the origin and
spacing of the anatomical coordinates are stored too.

- The origin represents the position of the first voxel (0, 0, 0) in the
anatomical coordinate system, e.g. (100, 50, -25) mm.

- The spacing specifies the distance between voxels along each axis, e.g.
(1.5, 0.5, 0.5) mm.


The following 2D example shows the meaning of origin and spacing:

![image_coordinates](https://github.com/Slicer/Slicer/releases/download/docs-resources/coordinate_systems_image_coordinates.png)

Using the origin and spacing, the corresponding position of each (image
coordinate) voxel in anatomical coordinates can be calculated.

## Image transformation [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#image-transformation "Link to this heading")

The transformation from an image space vector (𝑖⁢𝑗⁢𝑘)′ to an anatomical
space vector ⃗𝑥 is an affine transformation, consists of a linear
transformation 𝐀 followed by a translation ⃗𝑡.

⃗𝑥=𝐴⁢(𝑖𝑗𝑘)′+⃗𝑡

The transformation matrix 𝐀 is a 3×3 matrix and carries
all information about space directions and axis scaling.

⃗𝑡 is a 3×1 vector and contains information about the
geometric position of the first voxel.

⎛⎜
⎜
⎜⎝𝑥1𝑥2𝑥3⎞⎟
⎟
⎟⎠=⎛⎜
⎜
⎜⎝𝐴11𝐴12𝐴13𝐴21𝐴22𝐴23𝐴31𝐴32𝐴33⎞⎟
⎟
⎟⎠⁢⎛⎜
⎜
⎜⎝𝑖𝑗𝑘⎞⎟
⎟
⎟⎠+⎛⎜
⎜
⎜⎝𝑡1𝑡2𝑡3⎞⎟
⎟
⎟⎠

The last equation shows that the linear transformation is performed by a
matrix multiplication and the translation by a vector addition. To represent
both, the transformation and the translation, by a matrix multiplication an
augmented matrix must be used. This technique requires that the matrix
𝐀 is augmented with an extra row of zeros at the bottom, an extra
column-the translation vector-to the right, and a 1 in the lower right
corner. Additionally, all vectors have to be written as homogeneous
coordinates, which means that a 1 is augmented at the end.

⎛⎜
⎜
⎜
⎜
⎜
⎜
⎜⎝𝑥1𝑥2𝑥31⎞⎟
⎟
⎟
⎟
⎟
⎟
⎟⎠=⎛⎜
⎜
⎜
⎜
⎜
⎜
⎜⎝𝐴11𝐴12𝐴13𝑡1𝐴21𝐴22𝐴23𝑡2𝐴31𝐴32𝐴33𝑡30001⎞⎟
⎟
⎟
⎟
⎟
⎟
⎟⎠⁢⎛⎜
⎜
⎜
⎜
⎜
⎜
⎜⎝𝑖𝑗𝑘1⎞⎟
⎟
⎟
⎟
⎟
⎟
⎟⎠

Depending on the used anatomical space (LPS or RAS) the 4×4 matrix is
called **IJKtoLPS**\- or **IJKtoRAS**-matrix, because it represents the
transformation from IJK to LPS or RAS.

## 2D example or calculating an _IJtoLS_-matrix [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#d-example-or-calculating-an-ijtols-matrix "Link to this heading")

The following figure shows the anatomical space with an L(P)S basis on the
left and the corresponding image coordinates on the right.

![IJtoLS](https://github.com/Slicer/Slicer/releases/download/docs-resources/coordinate_systems_IJtoLS.png)

The origin (the coordinates of the first pixel in anatomical space) is
(50, 300) mm and the spacing (the distance between two pixels) is
(50, 50) mm.

As this is a 2D example 𝐀 is a 2×2 matrix and ⃗𝑡 a
2×1 vector. Therefore, the equation of the affine transformation is:

⎛⎜
⎜
⎜⎝𝐿𝑆1⎞⎟
⎟
⎟⎠=⎛⎜
⎜
⎜⎝𝐴11𝐴12𝑡1𝐴21𝐴22𝑡2001⎞⎟
⎟
⎟⎠⁢⎛⎜
⎜
⎜⎝𝑖𝑗1⎞⎟
⎟
⎟⎠

By multiplying the **IJtoLS**-matrix and the vector of the right side, the
following product will be obtained:

![matrix_multiplication](https://github.com/Slicer/Slicer/releases/download/docs-resources/coordinate_systems_matrix_multiplication.png)

The last equation and the matrix product show that a total of 6 unknown
variables (𝐴11,𝐴12,𝐴21,𝐴22,𝑡1,𝑡2) have to be determined.
The knowledge of origin and spacing however allows the following relations
between image and anatomical space:

(𝐿𝑆)≡(𝑖𝑗)(50300)≡(00)(100300)≡(10)(50250)≡(01)…

Thus, at least six equations can be derived:

Erroneous nesting of equation structures

As mentioned above, the translation ⃗𝑡 contains the information about
the geometric position of the first pixel and is therefore equivalent to the
origin. This result is also confirmed by the first equations.

The solution of the other equations leads to the following **IJtoLS**-matrix:

𝐼⁢𝐽⁢𝑡⁢𝑜⁢𝐿⁢𝑆=⎛⎜
⎜
⎜⎝500500−50300001⎞⎟
⎟
⎟⎠

In the event that a R(A)S basis was used, just the left and anterior axis of
the anatomical space are flipped, and the image coordinate system appears in
the same way as in the L(P)S case.

![IJtoRS](https://github.com/Slicer/Slicer/releases/download/docs-resources/coordinate_systems_IJtoRS.png)

For this 2D example the **IJtoRS**-matrix would be:

𝐼⁢𝐽⁢𝑡⁢𝑜⁢𝑅⁢𝑆=⎛⎜
⎜
⎜⎝−5002500−50300001⎞⎟
⎟
⎟⎠

This matrix looks very similar to the **IJtoLS**-matrix with 2 differences:

- The translation ⃗𝑡 has changed because of another origin.

- The right axis is flipped, so the first column of the **IJtoRS**-matrix
has just an inverted sign.


## Coordinate system convention in Slicer [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#coordinate-system-convention-in-slicer "Link to this heading")

DICOM and most medical imaging software use the **LPS coordinate system** for
storing all data. The choice of origin is arbitrary because only relative
differences have meaning, so there is no universal standard, but it is often
set to some geometric center of the imaging system, or it is chosen to be
near the center of an object of interest.

Both LPS and RAS were in wide use in the early 2000s when development of
Slicer was started and Slicer developers chose to use the RAS coordinate
system. Historically scans by GE equipment used RAS while Siemens and others
used LPS. Since several GE researchers were early contributors to Slicer, RAS
was adopted for the internal representation.

Slicer still **uses RAS coordinate system for storing coordinate values**
**internally** for all data types, but for compatibility with other software, it
**assumes that all data in files are stored in LPS coordinate system** (unless
the coordinate system in the file is explicitly stated to be RAS). To achieve
this, whenever Slicer reads or writes a file, it may need to flip the sign of
the first two coordinate axes to convert the data to RAS coordinate system.

### Relations to other software/conventions [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#relations-to-other-software-conventions "Link to this heading")

#### ITK [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#itk "Link to this heading")

[ITK](https://itk.org/) uses the LPS convention.

#### Using MATLAB to map Slicer RAS coordinates (e.g. fiducials) to voxel space of a NIfTI Image [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#using-matlab-to-map-slicer-ras-coordinates-e-g-fiducials-to-voxel-space-of-a-nifti-image "Link to this heading")

To extract the “voxel to world” transformation matrix from a NIFTI file’s
header (entry: `qto_xyz:1-4`) in MATLAB:

```
d = inv(M) * [ R A S 1 ]'
```

where `M` is the matrix and `R A S` are coordinates in Slicer, then `d` gives
a vector of voxel coordinates.

(Solution courtesy of András Jakab, University of Debrecen)

## References [](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html\#references "Link to this heading")

- [https://people.cs.uchicago.edu/~glk/unlinked/nrrd-iomf.pdf](https://people.cs.uchicago.edu/~glk/unlinked/nrrd-iomf.pdf)

- [http://www.grahamwideman.com/gw/brain/orientation/orientterms.htm](http://www.grahamwideman.com/gw/brain/orientation/orientterms.htm)

- [https://nifti.nimh.nih.gov/nifti-1/documentation/faq](https://nifti.nimh.nih.gov/nifti-1/documentation/faq)

- [https://teem.sourceforge.net/nrrd/format.html](https://teem.sourceforge.net/nrrd/format.html)

- [DICOM 2013 PS3.3 Image Position and Image Orientation](https://dicom.nema.org/dicom/2013/output/chtml/part03/sect_C.7.html#sect_C.7.6.2.1.1)


[Previous](https://slicer.readthedocs.io/en/latest/user_guide/user_interface.html "User Interface") [Next](https://slicer.readthedocs.io/en/latest/user_guide/data_loading_and_saving.html "Data Loading and Saving")

* * *

© Copyright 2026, Slicer Community.

Built with [Sphinx](https://www.sphinx-doc.org/) using a
[theme](https://github.com/readthedocs/sphinx_rtd_theme)
provided by [Read the Docs](https://readthedocs.org/).


![Read the Docs](<Base64-Image-Removed>)latest
Versions**[latest](https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html)**[5.10](https://slicer.readthedocs.io/en/5.10/user_guide/coordinate_systems.html)[5.8](https://slicer.readthedocs.io/en/5.8/user_guide/coordinate_systems.html)[5.6](https://slicer.readthedocs.io/en/5.6/user_guide/coordinate_systems.html)[5.4](https://slicer.readthedocs.io/en/5.4/user_guide/coordinate_systems.html)[5.2](https://slicer.readthedocs.io/en/5.2/user_guide/coordinate_systems.html)[5.0](https://slicer.readthedocs.io/en/5.0/user_guide/coordinate_systems.html)[v4.11](https://slicer.readthedocs.io/en/v4.11/user_guide/coordinate_systems.html)Downloads[PDF](https://slicer.readthedocs.io/_/downloads/en/latest/pdf/)[EPUB](https://slicer.readthedocs.io/_/downloads/en/latest/epub/)On Read the Docs[Project Home](https://app.readthedocs.org/projects/slicer/?utm_source=slicer&utm_content=flyout)[Builds](https://app.readthedocs.org/projects/slicer/builds/?utm_source=slicer&utm_content=flyout)Search

* * *

[Addons documentation](https://docs.readthedocs.io/page/addons.html?utm_source=slicer&utm_content=flyout) ― Hosted by
[Read the Docs](https://about.readthedocs.com/?utm_source=slicer&utm_content=flyout)
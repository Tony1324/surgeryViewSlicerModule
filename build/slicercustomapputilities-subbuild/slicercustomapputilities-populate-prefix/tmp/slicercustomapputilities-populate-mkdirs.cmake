# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "/Users/breastcad/Downloads/SegmentationsTool/build/SlicerCustomAppUtilities"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-build"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/tmp"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp${cfgdir}") # cfgdir has leading slash
endif()

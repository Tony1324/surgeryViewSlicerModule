# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-src"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-build"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-subbuild/slicersources-populate-prefix"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-subbuild/slicersources-populate-prefix/tmp"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-subbuild/slicersources-populate-prefix/src/slicersources-populate-stamp"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-subbuild/slicersources-populate-prefix/src"
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-subbuild/slicersources-populate-prefix/src/slicersources-populate-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-subbuild/slicersources-populate-prefix/src/slicersources-populate-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-subbuild/slicersources-populate-prefix/src/slicersources-populate-stamp${cfgdir}") # cfgdir has leading slash
endif()

# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.24.1)

# We name the project and the target for the ExternalProject_Add() call
# to something that will highlight to the user what we are working on if
# something goes wrong and an error message is produced.

project(slicersources-populate NONE)


# Pass through things we've already detected in the main project to avoid
# paying the cost of redetecting them again in ExternalProject_Add()
set(GIT_EXECUTABLE [==[/usr/bin/git]==])
set(GIT_VERSION_STRING [==[2.39.3 (Apple Git-146)]==])
set_property(GLOBAL PROPERTY _CMAKE_FindGit_GIT_EXECUTABLE_VERSION
  [==[/usr/bin/git;2.39.3 (Apple Git-146)]==]
)


include(ExternalProject)
ExternalProject_Add(slicersources-populate
                     "GIT_REPOSITORY" "https://github.com/Slicer/Slicer" "GIT_TAG" "db8a5cfd4dda452c10d8d4e30fa3406c1ae38a94" "GIT_PROGRESS" "1"
                    SOURCE_DIR          "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-src"
                    BINARY_DIR          "/Users/breastcad/Downloads/SegmentationsTool/build/slicersources-build"
                    CONFIGURE_COMMAND   ""
                    BUILD_COMMAND       ""
                    INSTALL_COMMAND     ""
                    TEST_COMMAND        ""
                    USES_TERMINAL_DOWNLOAD  YES
                    USES_TERMINAL_UPDATE    YES
                    USES_TERMINAL_PATCH     YES
)



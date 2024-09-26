# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

if(EXISTS "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitclone-lastrun.txt" AND EXISTS "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitinfo.txt" AND
  "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitclone-lastrun.txt" IS_NEWER_THAN "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitinfo.txt")
  message(STATUS
    "Avoiding repeated git clone, stamp file is up to date: "
    "'/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitclone-lastrun.txt'"
  )
  return()
endif()

execute_process(
  COMMAND ${CMAKE_COMMAND} -E rm -rf "/Users/breastcad/Downloads/SegmentationsTool/build/SlicerCustomAppUtilities"
  RESULT_VARIABLE error_code
)
if(error_code)
  message(FATAL_ERROR "Failed to remove directory: '/Users/breastcad/Downloads/SegmentationsTool/build/SlicerCustomAppUtilities'")
endif()

# try the clone 3 times in case there is an odd git clone issue
set(error_code 1)
set(number_of_tries 0)
while(error_code AND number_of_tries LESS 3)
  execute_process(
    COMMAND "/usr/bin/git" 
            clone --no-checkout --progress --config "advice.detachedHead=false" "https://github.com/KitwareMedical/SlicerCustomAppUtilities.git" "SlicerCustomAppUtilities"
    WORKING_DIRECTORY "/Users/breastcad/Downloads/SegmentationsTool/build"
    RESULT_VARIABLE error_code
  )
  math(EXPR number_of_tries "${number_of_tries} + 1")
endwhile()
if(number_of_tries GREATER 1)
  message(STATUS "Had to git clone more than once: ${number_of_tries} times.")
endif()
if(error_code)
  message(FATAL_ERROR "Failed to clone repository: 'https://github.com/KitwareMedical/SlicerCustomAppUtilities.git'")
endif()

execute_process(
  COMMAND "/usr/bin/git" 
          checkout "1d984a2c9143e2617ff1ffa9d86c51e07dc6321e" --
  WORKING_DIRECTORY "/Users/breastcad/Downloads/SegmentationsTool/build/SlicerCustomAppUtilities"
  RESULT_VARIABLE error_code
)
if(error_code)
  message(FATAL_ERROR "Failed to checkout tag: '1d984a2c9143e2617ff1ffa9d86c51e07dc6321e'")
endif()

set(init_submodules TRUE)
if(init_submodules)
  execute_process(
    COMMAND "/usr/bin/git" 
            submodule update --recursive --init 
    WORKING_DIRECTORY "/Users/breastcad/Downloads/SegmentationsTool/build/SlicerCustomAppUtilities"
    RESULT_VARIABLE error_code
  )
endif()
if(error_code)
  message(FATAL_ERROR "Failed to update submodules in: '/Users/breastcad/Downloads/SegmentationsTool/build/SlicerCustomAppUtilities'")
endif()

# Complete success, update the script-last-run stamp file:
#
execute_process(
  COMMAND ${CMAKE_COMMAND} -E copy "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitinfo.txt" "/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitclone-lastrun.txt"
  RESULT_VARIABLE error_code
)
if(error_code)
  message(FATAL_ERROR "Failed to copy script-last-run stamp file: '/Users/breastcad/Downloads/SegmentationsTool/build/slicercustomapputilities-subbuild/slicercustomapputilities-populate-prefix/src/slicercustomapputilities-populate-stamp/slicercustomapputilities-populate-gitclone-lastrun.txt'")
endif()

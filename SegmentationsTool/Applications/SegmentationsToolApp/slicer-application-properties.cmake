
set(APPLICATION_NAME
  SegmentationsTool
  )

set(VERSION_MAJOR
  0
  )
set(VERSION_MINOR
  1
  )
set(VERSION_PATCH
  0
  )

set(DESCRIPTION_SUMMARY
  "Automatic segmentation and display via Apple Vision Pro"
  )
set(DESCRIPTION_FILE
  ${Slicer_SOURCE_DIR}/README.md
  )

set(LAUNCHER_SPLASHSCREEN_FILE
  "${CMAKE_CURRENT_LIST_DIR}/Resources/Images/SplashScreen.png"
  )
set(APPLE_ICON_FILE
  "${CMAKE_CURRENT_LIST_DIR}/Resources/Icons/DesktopIcon.icns"
  )
set(WIN_ICON_FILE
  "${CMAKE_CURRENT_LIST_DIR}/Resources/Icons/DesktopIcon.ico"
  )

set(LICENSE_FILE
  "${SegmentationsTool_SOURCE_DIR}/LICENSE"
  )

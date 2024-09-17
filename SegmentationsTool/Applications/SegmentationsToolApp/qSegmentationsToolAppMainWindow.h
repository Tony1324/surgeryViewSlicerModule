/*==============================================================================

  Copyright (c) Kitware, Inc.

  See http://www.slicer.org/copyright/copyright.txt for details.

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  This file was originally developed by Julien Finet, Kitware, Inc.
  and was partially funded by NIH grant 3P41RR013218-12S1

==============================================================================*/

#ifndef __qSegmentationsToolAppMainWindow_h
#define __qSegmentationsToolAppMainWindow_h

// SegmentationsTool includes
#include "qSegmentationsToolAppExport.h"
class qSegmentationsToolAppMainWindowPrivate;

// Slicer includes
#include "qSlicerMainWindow.h"

class Q_SEGMENTATIONSTOOL_APP_EXPORT qSegmentationsToolAppMainWindow : public qSlicerMainWindow
{
  Q_OBJECT
public:
  typedef qSlicerMainWindow Superclass;

  qSegmentationsToolAppMainWindow(QWidget *parent=0);
  virtual ~qSegmentationsToolAppMainWindow();

public slots:
  void on_HelpAboutSegmentationsToolAppAction_triggered();

protected:
  qSegmentationsToolAppMainWindow(qSegmentationsToolAppMainWindowPrivate* pimpl, QWidget* parent);

private:
  Q_DECLARE_PRIVATE(qSegmentationsToolAppMainWindow);
  Q_DISABLE_COPY(qSegmentationsToolAppMainWindow);
};

#endif

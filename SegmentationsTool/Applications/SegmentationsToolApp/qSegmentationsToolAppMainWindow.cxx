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

// SegmentationsTool includes
#include "qSegmentationsToolAppMainWindow.h"
#include "qSegmentationsToolAppMainWindow_p.h"

// Qt includes
#include <QDesktopWidget>
#include <QLabel>

// Slicer includes
#include "qSlicerApplication.h"
#include "qSlicerAboutDialog.h"
#include "qSlicerMainWindow_p.h"
#include "qSlicerModuleSelectorToolBar.h"

//-----------------------------------------------------------------------------
// qSegmentationsToolAppMainWindowPrivate methods

qSegmentationsToolAppMainWindowPrivate::qSegmentationsToolAppMainWindowPrivate(qSegmentationsToolAppMainWindow& object)
  : Superclass(object)
{
}

//-----------------------------------------------------------------------------
qSegmentationsToolAppMainWindowPrivate::~qSegmentationsToolAppMainWindowPrivate()
{
}

//-----------------------------------------------------------------------------
void qSegmentationsToolAppMainWindowPrivate::init()
{
#if (QT_VERSION >= QT_VERSION_CHECK(5, 7, 0))
  QApplication::setAttribute(Qt::AA_UseHighDpiPixmaps);
#endif
  Q_Q(qSegmentationsToolAppMainWindow);
  this->Superclass::init();
}

//-----------------------------------------------------------------------------
void qSegmentationsToolAppMainWindowPrivate::setupUi(QMainWindow * mainWindow)
{
  qSlicerApplication * app = qSlicerApplication::application();

  //----------------------------------------------------------------------------
  // Add actions
  //----------------------------------------------------------------------------
  QAction* helpAboutSlicerAppAction = new QAction(mainWindow);
  helpAboutSlicerAppAction->setObjectName("HelpAboutSegmentationsToolAppAction");
  helpAboutSlicerAppAction->setText("About " + app->applicationName());

  //----------------------------------------------------------------------------
  // Calling "setupUi()" after adding the actions above allows the call
  // to "QMetaObject::connectSlotsByName()" done in "setupUi()" to
  // successfully connect each slot with its corresponding action.
  this->Superclass::setupUi(mainWindow);

  // Add Help Menu Action
  this->HelpMenu->addAction(helpAboutSlicerAppAction);

  //----------------------------------------------------------------------------
  // Configure
  //----------------------------------------------------------------------------
  mainWindow->setWindowIcon(QIcon(":/Icons/Medium/DesktopIcon.png"));

  QLabel* logoLabel = new QLabel();
  logoLabel->setObjectName("LogoLabel");
  logoLabel->setPixmap(qMRMLWidget::pixmapFromIcon(QIcon(":/LogoFull.png")));
  this->PanelDockWidget->setTitleBarWidget(logoLabel);

  // Hide the menus
  //this->menubar->setVisible(false);
  //this->FileMenu->setVisible(false);
  //this->EditMenu->setVisible(false);
  //this->ViewMenu->setVisible(false);
  //this->LayoutMenu->setVisible(false);
  //this->HelpMenu->setVisible(false);
}

//-----------------------------------------------------------------------------
// qSegmentationsToolAppMainWindow methods

//-----------------------------------------------------------------------------
qSegmentationsToolAppMainWindow::qSegmentationsToolAppMainWindow(QWidget* windowParent)
  : Superclass(new qSegmentationsToolAppMainWindowPrivate(*this), windowParent)
{
  Q_D(qSegmentationsToolAppMainWindow);
  d->init();
}

//-----------------------------------------------------------------------------
qSegmentationsToolAppMainWindow::qSegmentationsToolAppMainWindow(
  qSegmentationsToolAppMainWindowPrivate* pimpl, QWidget* windowParent)
  : Superclass(pimpl, windowParent)
{
  // init() is called by derived class.
}

//-----------------------------------------------------------------------------
qSegmentationsToolAppMainWindow::~qSegmentationsToolAppMainWindow()
{
}

//-----------------------------------------------------------------------------
void qSegmentationsToolAppMainWindow::on_HelpAboutSegmentationsToolAppAction_triggered()
{
  qSlicerAboutDialog about(this);
  about.setLogo(QPixmap(":/Logo.png"));
  about.exec();
}

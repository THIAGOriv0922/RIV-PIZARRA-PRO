"""RIV 0.5: integrate into the native OpenBoard layout. GPL-3.0-or-later."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
def patch(path,old,new):
    p=root/path
    s=p.read_text(encoding='utf-8')
    if s.count(old)!=1: raise RuntimeError(f'{path}: expected one anchor: {old[:80]}')
    p.write_text(s.replace(old,new,1),encoding='utf-8')

# Reuse the existing list and MIME handling, but replace the independent QDockWidget.
h='src/core/RIVResourceDock.h'
p=root/h
s=p.read_text(encoding='utf-8')
s=s.replace('#include <QDockWidget>', '#include <QLabel>\n#include "gui/UBDockPaletteWidget.h"')
start=s.index('inline void installResourceDock(')
end=s.index('    const QDir root',start)
s=s[:start]+'''class ResourcePanel final : public UBDockPaletteWidget {
public:
    explicit ResourcePanel(UBBoardController* controller) : UBDockPaletteWidget(nullptr, "rivResourcePanel") {
    mName = QStringLiteral("RIVResources");
    mVisibleState = true;
    mIconToLeft = QIcon(QStringLiteral(":/riv/icon.svg")).pixmap(32,32);
    mIconToRight = mIconToLeft;
    auto* panel = this;
    auto* layout = new QVBoxLayout(panel);
    layout->setContentsMargins(8,8,8,8);
    layout->setSpacing(7);
    auto* heading = new QLabel(QStringLiteral("RECURSOS RIV"),panel);
    heading->setObjectName(QStringLiteral("rivPanelHeading"));
    auto* category = new QComboBox(panel);
    auto* search = new QLineEdit(panel);
    search->setPlaceholderText(QStringLiteral("Buscar recurso..."));
    search->setClearButtonEnabled(true);
    auto* list = new ResourceList(panel);
    list->setObjectName(QStringLiteral("rivResources"));
    list->setGridSize(QSize(96,94));
    layout->addWidget(heading);
    layout->addWidget(category);
    layout->addWidget(search);
    layout->addWidget(list,1);
'''+s[end:]
start=s.index('    dock->setWidget(panel);')
s=s[:start]+'''    }
    bool visibleInMode(eUBDockPaletteWidgetMode mode) override {
        return mode == eUBDockPaletteWidget_BOARD;
    }
};
}
'''
p.write_text(s,encoding='utf-8')

app='src/core/UBApplication.cpp'
patch(app,'#include "RIVResourceDock.h"','#include <QLabel>\n#include <QToolBar>\n#include <QHBoxLayout>')
patch(app,'    RIV::installResourceDock(mainWindow, boardController);','''    // Brand belongs to the existing native top toolbar, not a floating widget.
    for (QToolBar* bar : {mainWindow->boardToolBar, mainWindow->webToolBar, mainWindow->documentToolBar}) {
        auto* brand = new QWidget(bar);
        brand->setObjectName(QStringLiteral("rivBrand"));
        auto* row = new QHBoxLayout(brand);
        row->setContentsMargins(8,3,10,3);
        row->setSpacing(6);
        auto* logo = new QLabel(brand);
        logo->setPixmap(QIcon(QStringLiteral(":/riv/icon.svg")).pixmap(26,26));
        auto* title = new QLabel(QStringLiteral("RIV PIZARRA"),brand);
        title->setObjectName(QStringLiteral("rivBrandTitle"));
        row->addWidget(logo);
        row->addWidget(title);
        bar->insertWidget(bar->actions().value(0),brand);
        bar->setIconSize(QSize(28,28));
    }
    // Native, fixed bottom toolbar: the same actions and state as OpenBoard.
    auto* ink = new QToolBar(QStringLiteral("Herramientas RIV"), mainWindow);
    ink->setObjectName(QStringLiteral("rivInkBar"));
    ink->setMovable(false);
    ink->setFloatable(false);
    ink->setAllowedAreas(Qt::BottomToolBarArea);
    ink->setIconSize(QSize(28,28));
    ink->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
    ink->addAction(mainWindow->actionSelector);
    ink->addAction(mainWindow->actionPen);
    ink->addAction(mainWindow->actionMarker);
    ink->addAction(mainWindow->actionEraser);
    ink->addSeparator();
    ink->addAction(mainWindow->actionHand);
    ink->addAction(mainWindow->actionPointer);
    ink->addAction(mainWindow->actionLine);
    ink->addAction(mainWindow->actionText);
    ink->addSeparator();
    ink->addAction(mainWindow->actionZoomOut);
    ink->addAction(mainWindow->actionZoomIn);
    ink->addAction(mainWindow->actionCapture);
    mainWindow->addToolBar(Qt::BottomToolBarArea, ink);
    mainWindow->actionStylus->setChecked(false);
    mainWindow->actionStylus->setToolTip(QStringLiteral("Mostrar herramientas flotantes opcionales"));
    QObject::connect(applicationController, &UBApplicationController::mainModeChanged, ink,
        [ink](UBApplicationController::MainMode mode) { ink->setVisible(mode == UBApplicationController::Board); });
    QObject::connect(applicationController, &UBApplicationController::desktopMode, ink,
        [ink](bool desktop) { ink->setVisible(!desktop && UBApplication::applicationController->displayMode() == UBApplicationController::Board); });
    ink->setVisible(applicationController->displayMode() == UBApplicationController::Board);''')
# Native library tabs use existing mode changes, resize and drag/drop handling.
pal='src/board/UBBoardPaletteManager.cpp'
patch(pal,'#include "core/UBApplication.h"','#include "core/UBApplication.h"\n#include "core/RIVResourceDock.h"')
patch(pal,'    mRightPalette->addTab(mpFeaturesWidget);','''    mRightPalette->addTab(mpFeaturesWidget);
    auto* rivResources = new RIV::ResourcePanel(mBoardControler);
    mRightPalette->registerWidget(rivResources);
    mRightPalette->addTab(rivResources);''')
patch(pal,'    mStylusPalette->show(); // always show stylus palette at startup','    mStylusPalette->hide(); // native RIV ink toolbar is the default')
# Select a different tab even when the native palette is collapsed.
dock='src/gui/UBDockPalette.cpp'
patch(dock,'        showTabWidget(tabIndex);\n    }\n    // else collapse','        showTabWidget(tabIndex);\n        if (width() < mCollapseWidth) toggleCollapseExpand();\n    }\n    // else collapse')
# Keep the full control view out from under either expanded native side panel.
patch(dock,'#include "UBDockPalette.h"','#include "UBDockPalette.h"\n#include <QTimer>\n#include <QLayout>')
patch(dock,'    move(origin.x(), origin.y());\n    moveTabs();','''    move(origin.x(), origin.y());
    moveTabs();
    QWidget* container = parentWidget();
    if (container && container->objectName() == QStringLiteral("ubBoardControlContainer")) {
        QTimer::singleShot(0,container,[container]() {
            auto* layout = container->layout();
            if (!layout) return;
            auto* left = container->findChild<UBDockPalette*>(QStringLiteral("UBLeftPalette"),Qt::FindDirectChildrenOnly);
            auto* right = container->findChild<UBDockPalette*>(QStringLiteral("UBRightPalette"),Qt::FindDirectChildrenOnly);
            const int l = left && !left->isHidden() ? left->width()+30 : 0;
            const int r = right && !right->isHidden() ? right->width()+30 : 0;
            const QMargins wanted(l,0,r,0);
            if (layout->contentsMargins() != wanted) layout->setContentsMargins(wanted);
        });
    }''')
# Opaque matching palette color instead of translucent gray.
patch('src/core/UBSettings.cpp','QColor UBSettings::paletteColor = QColor(127, 127, 127, 127);','QColor UBSettings::paletteColor = QColor(37, 59, 82, 255);')
# Prevent the adaptive toolbar from resetting our compact icons.
patch('src/core/UBApplicationController.cpp','mMainWindow->boardToolBar->setIconSize(QSize(highResolution ? 48 : 42, mMainWindow->boardToolBar->iconSize().height()));','mMainWindow->boardToolBar->setIconSize(QSize(28, 28));')
qss=root/'resources/riv/riv.qss'
with qss.open('a',encoding='utf-8') as f:
    f.write("""
QToolBar { background: #f6f8fb; spacing: 3px; padding: 3px; }
QToolBar QToolButton { height: 37px; padding: 4px 5px; margin: 1px; }
QToolBar QToolButton:pressed, QToolBar QToolButton:checked { height: 37px; background: #d7e7fb; border: 1px solid #a7c1e4; }
QWidget#rivBrand { background: #253b52; border-radius: 7px; }
QLabel#rivBrandTitle { background: transparent; color: #ffffff; font-size: 13px; font-weight: bold; }
QToolBar#rivInkBar { background: #f6f8fb; border-top: 1px solid #cbd5e1; border-bottom: 0; }
QToolBar#rivInkBar QToolButton { height: 30px; padding: 4px 6px; }
QLabel#rivPanelHeading { background: transparent; color: #ffffff; font-size: 12px; font-weight: bold; }
QWidget#rivResourcePanel QLineEdit, QWidget#rivResourcePanel QComboBox { background: #ffffff; color: #263c53; border: 1px solid #bccde0; border-radius: 5px; padding: 6px; }
QWidget#rivResourcePanel QListWidget { background: #e8eef6; border: 0; }
QWidget#rivResourcePanel QListWidget::item { background: #ffffff; color: #263c53; border: 1px solid #d5dfeb; border-radius: 6px; }
QWidget#rivResourcePanel QListWidget::item:selected { background: #c9dffc; }
""")
# Set safe defaults for first launch. Existing documents and settings remain untouched.
config=root/'resources/etc/OpenBoard.config'
s=config.read_text(encoding='utf-8')
s=s.replace('EnableAutomaticSoftwareUpdates=true','EnableAutomaticSoftwareUpdates=false').replace('EnableSoftwareUpdates=true','EnableSoftwareUpdates=false').replace('HideCheckForSoftwareUpdate=false','HideCheckForSoftwareUpdate=true').replace('EnableStartupHints=true','EnableStartupHints=false')
config.write_text(s,encoding='utf-8')
print('RIV 0.5: barra fija, identidad y recursos integrados')

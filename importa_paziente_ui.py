from PyQt6 import QtCore, QtGui, QtWidgets

class UiMainWindow(object):
    def __init__(self):
        self.languageActionGroup = None
        self.actionItalian = None
        self.actionEnglish = None
        self.menuLanguage = None
        self.actionImport = None
        self.actionClear_all = None
        self.actionClear_copies = None
        self.actionClear_links = None
        self.actionExport = None
        self.menuWorkspace = None
        self.menuHelp = None
        self.menuSettings = None
        self.menuFile = None
        self.menubar = None
        self.pushButton = None
        self.labelDropText = None
        self.horizontalLayout_2 = None
        self.dropFrame = None
        self.treeView = None
        self.splitter = None
        self.verticalLayout_3 = None
        self.centralwidget = None

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(840, 441)
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout_3.setObjectName("verticalLayout_3")

        # --- Splitter and its children ---
        self.splitter = QtWidgets.QSplitter(parent=self.centralwidget)
        self.splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setObjectName("splitter")

        self.treeView = QtWidgets.QTreeView(parent=self.splitter)
        self.treeView.setMinimumSize(QtCore.QSize(200, 0))
        self.treeView.setObjectName("treeView")

        self.dropFrame = DropFrame(parent=self.splitter)
        self.dropFrame.setEnabled(True)
        self.dropFrame.setStyleSheet("border: 2px dashed gray;")
        self.dropFrame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.dropFrame.setObjectName("dropFrame")

        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.dropFrame)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.labelDropText = QtWidgets.QLabel(parent=self.dropFrame)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.labelDropText.setFont(font)
        self.labelDropText.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.labelDropText.setObjectName("labelDropText")
        self.horizontalLayout_2.addWidget(self.labelDropText)

        # Re-size the splitter with its children
        self.splitter.setSizes([200, 600])

        self.verticalLayout_3.addWidget(self.splitter)

        # --- Push button at the bottom ---
        self.pushButton = QtWidgets.QPushButton(parent=self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.pushButton.setSizePolicy(sizePolicy)
        self.pushButton.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self.pushButton.setObjectName("pushButton")
        self.verticalLayout_3.addWidget(self.pushButton, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        MainWindow.setCentralWidget(self.centralwidget)

        # --- Language ---
        # self.actionEnglish.triggered.connect(lambda: self.set_language("en"))
        # self.actionItalian.triggered.connect(lambda: self.set_language("it"))

        # --- Menu setup ---
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 840, 24))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(parent=self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuSettings = QtWidgets.QMenu(parent=self.menubar)
        self.menuSettings.setObjectName("menuSettings")
        self.menuHelp = QtWidgets.QMenu(parent=self.menubar)
        self.menuHelp.setObjectName("menuHelp")
        self.menuWorkspace = QtWidgets.QMenu(parent=self.menubar)
        self.menuWorkspace.setObjectName("menuWorkspace")
        self.menuLanguage = QtWidgets.QMenu(parent=self.menubar)
        self.menuLanguage.setObjectName("menuLanguage")
        MainWindow.setMenuBar(self.menubar)

        self.actionExport = QtGui.QAction(parent=MainWindow)
        self.actionExport.setObjectName("actionExport")
        self.actionClear_links = QtGui.QAction(parent=MainWindow)
        self.actionClear_links.setObjectName("actionClear_links")
        self.actionClear_copies = QtGui.QAction(parent=MainWindow)
        self.actionClear_copies.setObjectName("actionClear_copies")
        self.actionClear_all = QtGui.QAction(parent=MainWindow)
        self.actionClear_all.setObjectName("actionClear_all")
        self.actionImport = QtGui.QAction(parent=MainWindow)
        self.actionImport.setObjectName("actionImport")
        self.actionEnglish = QtGui.QAction(parent=MainWindow)
        self.actionEnglish.setObjectName("actionEnglish")
        self.actionItalian = QtGui.QAction(parent=MainWindow)
        self.actionItalian.setObjectName("actionItalian")

        self.languageActionGroup = QtGui.QActionGroup(MainWindow)
        self.languageActionGroup.setExclusive(True)

        self.actionEnglish.setCheckable(True)
        self.actionItalian.setCheckable(True)

        self.languageActionGroup.addAction(self.actionEnglish)
        self.languageActionGroup.addAction(self.actionItalian)

        # English as a default language
        self.actionEnglish.setChecked(True)

        self.menuFile.addAction(self.actionImport)
        self.menuFile.addAction(self.actionExport)
        self.menuWorkspace.addAction(self.actionClear_links)
        self.menuWorkspace.addAction(self.actionClear_copies)
        self.menuWorkspace.addAction(self.actionClear_all)
        self.menuLanguage.addAction(self.actionEnglish)
        self.menuLanguage.addAction(self.actionItalian)

        self.menuSettings.addMenu(self.menuLanguage)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuWorkspace.menuAction())
        self.menubar.addAction(self.menuSettings.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Glioma Patient Data Importer"))
        self.labelDropText.setText(_translate("MainWindow", "Import or select patients' data"))
        self.pushButton.setText(_translate("MainWindow", "Next"))
        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.menuSettings.setTitle(_translate("MainWindow", "Settings"))
        self.menuHelp.setTitle(_translate("MainWindow", "Help"))
        self.menuWorkspace.setTitle(_translate("MainWindow", "Workspace"))
        self.actionExport.setText(_translate("MainWindow", "Export"))
        self.actionClear_links.setText(_translate("MainWindow", "Clear link"))
        self.actionClear_copies.setText(_translate("MainWindow", "Clear copies"))
        self.actionClear_all.setText(_translate("MainWindow", "Clear all"))
        self.actionImport.setText(_translate("MainWindow", "Import"))
        self.menuLanguage.setTitle(_translate("MainWindow", "Language"))
        self.actionEnglish.setText(_translate("MainWindow", "English"))
        self.actionItalian.setText(_translate("MainWindow", "Italiano"))

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UiMainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
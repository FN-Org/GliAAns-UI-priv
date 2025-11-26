"""
tool_selection_page.py

This module defines the `ToolChoicePage` class — a PyQt6 page that allows the user
to select the next processing step in the GliAAns pipeline.

The available options include:
- Skull Stripping
- Automatic Drawing
- Deep Learning Segmentation (Linux + CUDA only)
- Full Pipeline Execution

Depending on the selected option, the next page is dynamically loaded.
"""

import platform
import torch
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QGroupBox, QRadioButton, QButtonGroup, QSizePolicy,
    QWidget, QHBoxLayout, QMessageBox, QApplication
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QCoreApplication

from components.info_label import InfoLabel
from ui.nifti_mask_selection_page import MaskNiftiSelectionPage
from ui.dl_selection_page import DlNiftiSelectionPage
from ui.pipeline_patient_selection_page import PipelinePatientSelectionPage
from ui.skull_stripping_page import SkullStrippingPage
from page import Page


class ToolSelectionPage(Page):
    """
    A UI page for selecting the next processing step in the workflow.

    This class extends `Page` and displays a set of radio buttons representing
    different data processing operations. The user’s selection determines which
    next page in the pipeline will be opened.

    Attributes
    ----------
    context : dict
        Shared application state, including navigation and configuration.
    previous_page : Page
        Reference to the previous page for backward navigation.
    selected_option : int or None
        The currently selected radio button ID.
    """

    def __init__(self, context=None, previous_page=None):
        """Initialize the ToolSelectionPage UI."""
        super().__init__()

        self.context = context
        self.previous_page = previous_page

        # References to next pages for each option
        self.next_skull_stripping = None
        self.next_manual_draw = None
        self.next_deep_learning = None
        self.next_pipeline = None

        # === Layout setup ===
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(30)
        self.setLayout(self.layout)

        # --- Title ---
        self.title = QLabel("Select the Next Processing Step")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.layout.addWidget(self.title)

        # --- GroupBox for options ---
        self.radio_group_box = QGroupBox("Available Processes")
        self.radio_group_box.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                border: 1px solid #bdc3c7;
                border-radius: 10px;
                padding: 20px;
                background-color: #e5e5e5;
            }
        """)
        self.radio_group_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.radio_group_box.setMaximumHeight(400)

        radio_layout = QVBoxLayout()
        radio_layout.setSpacing(20)
        radio_layout.setContentsMargins(10, 10, 10, 10)

        self.radio_group = QButtonGroup(self)

        # --- Radio Buttons for each processing option ---
        self.radio_skull = QRadioButton("Skull Stripping")
        self.radio_draw = QRadioButton("Automatic Drawing")
        self.radio_dl = QRadioButton("Deep Learning Segmentation")
        self.radio_analysis = QRadioButton("Full Pipeline")

        self.radio_buttons = [
            self.radio_skull,
            self.radio_draw,
            self.radio_dl,
            self.radio_analysis,
        ]

        # Apply consistent style to all buttons
        for btn in self.radio_buttons:
            btn.setFont(QFont("Arial", 14))
            btn.setStyleSheet("""
                QRadioButton {
                    padding: 5px;
                    border: 1px solid #bdc3c7;
                    border-radius: 8px;
                    background-color: white;
                    spacing: 10px;
                }
                QRadioButton::hover {
                    background-color: #dff9fb;
                    border: 1px solid #3498db;
                }
                QRadioButton::checked {
                    background-color: #d6eaf8;
                    border: 2px solid #2980b9;
                }
            """)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Add buttons to layout and group
        for i, btn in enumerate(self.radio_buttons):
            self.radio_group.addButton(btn, id=i)
            if btn == self.radio_dl:
                # Add info tooltip for Deep Learning option
                dl_widget = QWidget()
                dl_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                dl_layout = QHBoxLayout(dl_widget)
                dl_layout.setContentsMargins(0, 0, 0, 0)
                dl_layout.setSpacing(5)

                self.dl_info_label = InfoLabel(
                    text="i",
                    tooltip_text=QCoreApplication.translate(
                        "ToolSelectionPage",
                        "To use this function you need Linux and a CUDA capable GPU"
                    )
                )
                dl_layout.addWidget(self.radio_dl)
                dl_layout.addWidget(self.dl_info_label)
                radio_layout.addWidget(dl_widget)
            else:
                radio_layout.addWidget(btn)

        self.radio_group.buttonToggled.connect(lambda: self.on_selection())

        self.radio_group_box.setLayout(radio_layout)
        self.layout.addWidget(self.radio_group_box)

        self.selected_option = None

        # Connect language change signal if available
        self._translate_ui()
        if context and "language_changed" in context:
            context["language_changed"].connect(self._translate_ui)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def on_selection(self):
        """Triggered when a radio button is toggled."""
        self.selected_option = self.radio_group.checkedId()
        if self.context and "update_main_buttons" in self.context:
            self.context["update_main_buttons"]()

    def is_ready_to_advance(self):
        """Return True if an option has been selected."""
        return self.radio_group.checkedId() != -1

    def is_ready_to_go_back(self):
        """Always allows going back from this page."""
        return True

    def next(self, context):
        """
        Return the next page based on the selected option.

        Handles platform and CUDA availability checks for Deep Learning mode.
        """
        page_classes = {
            0: ("next_skull_stripping", SkullStrippingPage),
            1: ("next_manual_draw", MaskNiftiSelectionPage),
            2: ("next_deep_learning", DlNiftiSelectionPage),
            3: ("next_pipeline", PipelinePatientSelectionPage),
        }

        if self.selected_option not in page_classes:
            return None

        # Check CUDA and OS support for Deep Learning mode
        is_linux = platform.system() == "Linux"
        has_gpu = torch.cuda.is_available()

        if self.selected_option == 2 and (not has_gpu or not is_linux):
            QMessageBox.warning(
                self,
                QCoreApplication.translate("ToolSelectionPage", "Not available for this platform"),
                QCoreApplication.translate(
                    "ToolSelectionPage",
                    "The deep learning segmentation is not available for this platform: {0}"
                ).format(platform.system()),
            )
            return self

        # Create or reuse the next page instance
        attr_name, page_class = page_classes[self.selected_option]
        next_page = getattr(self, attr_name, None)

        if not next_page:
            next_page = page_class(context, self)
            setattr(self, attr_name, next_page)
            self.context["history"].append(next_page)

        next_page.on_enter()
        return next_page

    def back(self):
        """Navigate back to the previous page if available."""
        if self.previous_page:
            self.previous_page.on_enter()
            return self.previous_page
        return None

    def reset_page(self):
        """Reset selection state when the page is revisited."""
        self.radio_group.setExclusive(False)
        for button in self.radio_group.buttons():
            button.setChecked(False)
        self.radio_group.setExclusive(True)
        self.selected_option = None

    def _translate_ui(self):
        """Translate all text elements (supports multi-language UI)."""
        self.title.setText(QApplication.translate("ToolSelectionPage", "Select the Next Processing Step"))
        self.radio_group_box.setTitle(QApplication.translate("ToolSelectionPage", "Available Processes"))
        self.radio_skull.setText(QApplication.translate("ToolSelectionPage", "Skull Stripping"))
        self.radio_draw.setText(QApplication.translate("ToolSelectionPage", "Automatic Drawing"))
        self.radio_dl.setText(QApplication.translate("ToolSelectionPage", "Deep Learning Segmentation"))
        self.radio_analysis.setText(QApplication.translate("ToolSelectionPage", "Full Pipeline"))
        self.dl_info_label.setToolTip(QApplication.translate("ToolSelectionPage", "To use this function you need Linux and a CUDA capable GPU"))

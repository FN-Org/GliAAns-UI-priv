import inspect
import pytest

from main.page import Page
from main.ui.dl_execution_page import DlExecutionPage
from main.ui.dl_selection_page import DlNiftiSelectionPage
from main.ui.import_page import ImportPage
from main.ui.nifti_mask_selection_page import MaskNiftiSelectionPage
from main.ui.patient_selection_page import PatientSelectionPage
from main.ui.pipeline_execution_page import PipelineExecutionPage
from main.ui.pipeline_patient_selection_page import PipelinePatientSelectionPage
from main.ui.pipeline_review_page import PipelineReviewPage
from main.ui.skull_stripping_page import SkullStrippingPage
from main.ui.tool_selection_page import ToolSelectionPage

# You can add other child classes here if there are more
ALL_PAGE_SUBCLASSES = [
    ImportPage,
    PatientSelectionPage,
    ToolSelectionPage,
    SkullStrippingPage,
    MaskNiftiSelectionPage,
    PipelinePatientSelectionPage,
    PipelineReviewPage,
    PipelineExecutionPage,
    DlNiftiSelectionPage,
    DlExecutionPage,
]


def get_method_signatures(cls):
    """Return a dict {method_name: signature} for all public methods."""
    methods = {}
    for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
        # exclude private methods like _setup_ui
        if not name.startswith("_"):
            methods[name] = inspect.signature(member)
    return methods


@pytest.mark.parametrize("subclass", ALL_PAGE_SUBCLASSES)
def test_page_subclass_contract(subclass):
    """Verify that each subclass of Page respects the contract of public methods."""
    base_methods = get_method_signatures(Page)
    subclass_methods = get_method_signatures(subclass)

    for method_name, base_sig in base_methods.items():
        assert method_name in subclass_methods, (
            f"The class {subclass.__name__} does not implement the required method '{method_name}'"
        )

        subclass_sig = subclass_methods[method_name]
        assert subclass_sig == base_sig, (
            f"The signature of the method '{method_name}' in {subclass.__name__} "
            f"does not match the one in Page.\n"
            f"Expected: {base_sig}\nFound: {subclass_sig}"
        )
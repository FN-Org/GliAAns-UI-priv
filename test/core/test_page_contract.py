import inspect
import pytest
from page import Page
from ui.ui_dl_execution_page import DlExecutionPage
from ui.ui_dl_selection_page import DlNiftiSelectionPage
from ui.ui_import_page import ImportPage
from ui.ui_mask_selection_page import MaskNiftiSelectionPage
from ui.ui_patient_selection_page import PatientSelectionPage
from ui.ui_pipeline_execution_page import PipelineExecutionPage
from ui.ui_pipeline_patient_selection_page import PipelinePatientSelectionPage
from ui.ui_pipeline_review_page import PipelineReviewPage
from ui.ui_skull_stripping_page import SkullStrippingPage
from ui.ui_tool_selection_page import ToolSelectionPage

# Puoi aggiungere qui altre classi figlie se ne hai più di una
ALL_PAGE_SUBCLASSES = [ImportPage, PatientSelectionPage, ToolSelectionPage, SkullStrippingPage, MaskNiftiSelectionPage,
                       PipelinePatientSelectionPage, PipelineReviewPage, PipelineExecutionPage,
                       DlNiftiSelectionPage, DlExecutionPage]


def get_method_signatures(cls):
    """Ritorna un dict {method_name: signature} per tutti i metodi pubblici."""
    methods = {}
    for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
        # escludiamo metodi privati tipo _setup_ui
        if not name.startswith("_"):
            methods[name] = inspect.signature(member)
    return methods


@pytest.mark.parametrize("subclass", ALL_PAGE_SUBCLASSES)
def test_page_subclass_contract(subclass):
    """Verifica che ogni sottoclasse di Page rispetti il contratto dei metodi pubblici."""
    base_methods = get_method_signatures(Page)
    subclass_methods = get_method_signatures(subclass)

    for method_name, base_sig in base_methods.items():
        assert method_name in subclass_methods, (
            f"La classe {subclass.__name__} non implementa il metodo richiesto '{method_name}'"
        )

        subclass_sig = subclass_methods[method_name]
        assert subclass_sig == base_sig, (
            f"La firma del metodo '{method_name}' in {subclass.__name__} "
            f"non coincide con quella in Page.\n"
            f"Atteso: {base_sig}\nTrovato: {subclass_sig}"
        )
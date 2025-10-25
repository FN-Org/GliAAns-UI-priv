from PyQt6.QtWidgets import QWidget


class Page(QWidget):
    """
    Base class for all application pages.

    This abstract widget defines the lifecycle and navigation interface
    shared by all pages in the UI (e.g., `on_enter`, `next`, `back`).
    Subclasses should override relevant methods to implement page-specific
    logic, layout, and transitions.
    """

    def _setup_ui(self):
        """
        Initialize and configure the page's user interface.

        To be implemented by subclasses for defining layouts, widgets,
        and signal connections.
        """
        pass

    def is_ready_to_advance(self):
        """
        Check whether the page is ready to advance to the next step.

        Returns
        -------
        bool
            True if navigation to the next page is allowed.
        """
        return True

    def is_ready_to_go_back(self):
        """
        Check whether the page can return to the previous step.

        Returns
        -------
        bool
            True if navigation backward is allowed.
        """
        return True

    def reset_page(self):
        """
        Reset the page state and clear any user input or temporary data.

        Should be overridden by subclasses that maintain internal state.
        """
        pass

    def on_enter(self):
        """
        Hook called when this page becomes active.

        Used for refreshing content or resetting temporary UI state.
        Subclasses can override this to perform actions when the user
        navigates to this page.
        """
        pass

    def next(self, context):
        """
        Handle transition to the next page.

        Parameters
        ----------
        context : dict
            Shared application context passed across pages.

        Returns
        -------
        Page | None
            The next page instance, or None if navigation should stop.
        """
        pass

    def back(self):
        """
        Handle transition to the previous page.

        Returns
        -------
        Page | None
            The previous page instance, or None if there is no previous page.
        """
        pass

    def _translate_ui(self):
        """
        Update translatable text in the UI when the language changes.

        Subclasses should override this method to refresh localized labels,
        buttons, and other text elements.
        """
        pass

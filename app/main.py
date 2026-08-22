"""Entry point.

1. Launches a visible, persistent Chromium window at Google Maps.
2. User searches manually in that window.
3. Opens the PinScout window (Start / Stop / Clear results / Export + live grid).
4. Start scrapes whatever is currently shown in the results panel.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

from app.automation_loop import AutomationLoop
from app.browser import launch_maps_session, close_session
from app.gui import ScraperGUI


def _get_icon_path() -> Path | None:
    # Check directory relative to this file
    p1 = Path(__file__).resolve().parent.parent / "assets" / "app_icon.ico"
    if p1.exists():
        return p1
    # Check current working directory
    p2 = Path.cwd() / "assets" / "app_icon.ico"
    if p2.exists():
        return p2
    return None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    automation = AutomationLoop()

    print("Launching Google Chrome and navigating to Google Maps — please wait...")
    launch_future = automation.submit(launch_maps_session())
    context, page = launch_future.result()  # blocks until the window is ready
    print("Browser ready. Search for a business type/location in that window, "
          "then use PinScout to start scraping.")

    page_ref = {"page": page, "context": context, "automation": automation}

    root = tk.Tk()

    # Set window and taskbar icon
    icon_path = _get_icon_path()
    if icon_path is not None:
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass

    ScraperGUI(root, page_ref, keyword=None)
    root.mainloop()



    # Window closed — clean up the browser/event loop.
    automation.submit(close_session(context)).result()
    automation.shutdown()


if __name__ == "__main__":
    main()

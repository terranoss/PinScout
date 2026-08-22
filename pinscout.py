import os
import sys
import traceback
from pathlib import Path

def _run() -> None:
    try:
        from app.main import main
        main()
    except Exception as exc:
        err_msg = traceback.format_exc()
        try:
            log_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "PinScout"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "crash.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- Crash at {os.environ.get('TIME', '')} ---\n{err_msg}\n")
        except Exception:
            pass

        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("PinScout Error", f"An error occurred during execution:\n\n{exc}\n\nCheck crash.log for details.")
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    _run()


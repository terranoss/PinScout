"""PinScout scout-desk window:
  - Left rail: title, Start / Stop / Clear results / Export, short checklist
  - Main pane: keyword chip + filters, results table, activity log

The Chromium Maps window is separate — search there, then click Start here.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from app.models import Listing, EXPORT_COLUMN_ORDER, FIELD_TO_EXPORT_HEADER
from app.exporter import export
from app import scraper_engine  # background asyncio worker, see main.py
from app.version import get_git_short_sha

# Map export headers to model field names for treeview extraction
EXPORT_HEADER_TO_FIELD = {v: k for k, v in FIELD_TO_EXPORT_HEADER.items()}
COLUMNS = [EXPORT_HEADER_TO_FIELD[h] for h in EXPORT_COLUMN_ORDER if h in EXPORT_HEADER_TO_FIELD]
COLUMN_DISPLAY_NAMES = [h for h in EXPORT_COLUMN_ORDER if h in EXPORT_HEADER_TO_FIELD]

RAIL_BG = "#1B2430"
SURFACE = "#F7F4EE"
INK = "#1B2430"
COPPER = "#C45C26"
COPPER_HOVER = "#A84C1F"
SAGE = "#3F6F5A"
ERROR = "#A33B32"
RAIL_MUTED = "#A8B0BA"
CHIP_BG = "#EDE6D9"

RAIL_STEPS = (
    "1  Search Maps in the browser",
    "2  Wait for the results feed",
    "3  Click Start",
)


class ScraperGUI:
    def __init__(self, root: tk.Tk, page_ref: dict, keyword: str | None = None):
        self.root = root
        self.page_ref = page_ref  # holds the live Playwright `page` object
        self.keyword = keyword
        self.listings: list[Listing] = []
        self.filtered_listings: list[Listing] = []
        self.event_queue: "queue.Queue" = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.stop_flag = threading.Event()
        self.filter_email = tk.BooleanVar(value=False)
        self.filter_phone = tk.BooleanVar(value=False)
        self.filter_website = tk.BooleanVar(value=False)
        self.filter_unclaimed = tk.BooleanVar(value=False)
        self.filter_rating = tk.StringVar(value="Any")
        self.filter_reviews = tk.StringVar(value="Any")
        self.filter_search = tk.StringVar(value="")

        root.title("PinScout")
        root.geometry("1280x800")
        root.minsize(960, 640)
        root.configure(bg=SURFACE)

        self._build_layout()
        self._poll_queue()

    def _apply_theme(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Scout.Treeview",
            background="#FFFDF8",
            fieldbackground="#FFFDF8",
            foreground=INK,
            rowheight=24,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Scout.Treeview.Heading",
            background="#E8E1D4",
            foreground=INK,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Scout.Treeview", background=[("selected", "#D9C4B0")])
        style.map("Scout.Treeview.Heading", background=[("active", "#DDD4C4")])
        style.configure(
            "Scout.TCombobox",
            fieldbackground="#FFFDF8",
            background="#E8E1D4",
            foreground=INK,
            arrowsize=14,
        )
        style.configure(
            "Scout.Vertical.TScrollbar",
            background="#E8E1D4",
            troughcolor=SURFACE,
            borderwidth=0,
            arrowsize=12,
        )
        style.configure(
            "Scout.Horizontal.TScrollbar",
            background="#E8E1D4",
            troughcolor=SURFACE,
            borderwidth=0,
            arrowsize=12,
        )

    def _rail_button(self, parent: tk.Frame, text: str, command, *, primary: bool = False) -> tk.Button:
        if primary:
            return tk.Button(
                parent,
                text=text,
                command=command,
                bg=COPPER,
                fg="#FFFFFF",
                activebackground=COPPER_HOVER,
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
                pady=8,
            )
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=RAIL_BG,
            fg="#F7F4EE",
            activebackground="#2A3544",
            activeforeground="#FFFFFF",
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground="#4A5563",
            highlightcolor="#4A5563",
            font=("Segoe UI", 10),
            cursor="hand2",
            pady=7,
        )

    def _build_layout(self) -> None:
        self._apply_theme()

        rail = tk.Frame(self.root, bg=RAIL_BG, width=220)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        tk.Label(
            rail,
            text="PINSCOUT",
            bg=RAIL_BG,
            fg="#FFFFFF",
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).pack(fill="x", padx=18, pady=(22, 4))
        tk.Label(
            rail,
            text="Maps lead desk",
            bg=RAIL_BG,
            fg=RAIL_MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 22))

        rev = get_git_short_sha()
        tk.Label(
            rail,
            text=f"rev {rev}",
            bg=RAIL_BG,
            fg=RAIL_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 18))

        btn_wrap = tk.Frame(rail, bg=RAIL_BG)
        btn_wrap.pack(fill="x", padx=16)
        self.start_btn = self._rail_button(btn_wrap, "Start", self.start_bot, primary=True)
        self.start_btn.pack(fill="x", pady=(0, 8))
        self.stop_btn = self._rail_button(btn_wrap, "Stop", self.stop_bot)
        self.stop_btn.config(state="disabled")
        self.stop_btn.pack(fill="x", pady=(0, 8))
        self.delete_btn = self._rail_button(btn_wrap, "Clear results", self.delete_data)
        self.delete_btn.pack(fill="x", pady=(0, 8))
        self.export_btn = self._rail_button(btn_wrap, "Export", self.export_data)
        self.export_btn.config(state="disabled")
        self.export_btn.pack(fill="x")

        steps = tk.Frame(rail, bg=RAIL_BG)
        steps.pack(side="bottom", fill="x", padx=18, pady=(0, 24))
        tk.Label(
            steps,
            text="HOW TO RUN",
            bg=RAIL_BG,
            fg=COPPER,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        for line in RAIL_STEPS:
            tk.Label(
                steps,
                text=line,
                bg=RAIL_BG,
                fg=RAIL_MUTED,
                font=("Segoe UI", 9),
                anchor="w",
                justify="left",
                wraplength=180,
            ).pack(fill="x", pady=2)

        main = tk.Frame(self.root, bg=SURFACE)
        main.pack(side="left", fill="both", expand=True)

        toolbar = tk.Frame(main, bg=SURFACE)
        toolbar.pack(fill="x", padx=16, pady=(14, 8))

        self.keyword_chip = tk.Label(
            toolbar,
            text="Keyword  —",
            bg=CHIP_BG,
            fg=INK,
            font=("Segoe UI", 9),
            padx=10,
            pady=4,
        )
        self.keyword_chip.pack(side="left", padx=(0, 12))

        for text, var in (
            ("Has Email", self.filter_email),
            ("Has Phone", self.filter_phone),
            ("Has Website", self.filter_website),
            ("Unclaimed Only", self.filter_unclaimed),
        ):
            tk.Checkbutton(
                toolbar,
                text=text,
                variable=var,
                command=self._on_filter_change,
                bg=SURFACE,
                fg=INK,
                activebackground=SURFACE,
                selectcolor=SURFACE,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=4)

        tk.Label(toolbar, text="Rating", bg=SURFACE, fg=INK, font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        rating_opt = ttk.Combobox(
            toolbar,
            textvariable=self.filter_rating,
            values=["Any", "≥ 4.0★", "≥ 4.5★", "< 4.0★"],
            width=7,
            state="readonly",
            style="Scout.TCombobox",
        )
        rating_opt.pack(side="left")
        rating_opt.bind("<<ComboboxSelected>>", lambda e: self._on_filter_change())

        tk.Label(toolbar, text="Reviews", bg=SURFACE, fg=INK, font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        reviews_opt = ttk.Combobox(
            toolbar,
            textvariable=self.filter_reviews,
            values=["Any", "≥ 10", "≥ 50", "≥ 100", "≥ 500"],
            width=7,
            state="readonly",
            style="Scout.TCombobox",
        )
        reviews_opt.pack(side="left")
        reviews_opt.bind("<<ComboboxSelected>>", lambda e: self._on_filter_change())

        tk.Label(toolbar, text="Search", bg=SURFACE, fg=INK, font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        search_entry = tk.Entry(
            toolbar,
            textvariable=self.filter_search,
            width=16,
            bg="#FFFDF8",
            fg=INK,
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
        )
        search_entry.pack(side="left")
        self.filter_search.trace_add("write", lambda *args: self._on_filter_change())

        tk.Button(
            toolbar,
            text="Reset filters",
            command=self.reset_filters,
            bg="#E8E1D4",
            fg=INK,
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            cursor="hand2",
        ).pack(side="left", padx=(8, 0))

        self.filter_status_lbl = tk.Label(
            toolbar,
            text="Showing all 0 record(s)",
            bg=SURFACE,
            fg="#6B7280",
            font=("Segoe UI", 9),
        )
        self.filter_status_lbl.pack(side="right")

        grid_frame = tk.Frame(main, bg=SURFACE)
        grid_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.tree = ttk.Treeview(grid_frame, columns=COLUMNS, show="headings", style="Scout.Treeview")
        self.tree.column("#0", width=0, minwidth=0, stretch=False)
        for col_field, display_name in zip(COLUMNS, COLUMN_DISPLAY_NAMES):
            self.tree.heading(col_field, text=display_name)
            self.tree.column(col_field, width=120, minwidth=40, stretch=False, anchor="w")
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)

        vsb = ttk.Scrollbar(grid_frame, orient="vertical", command=self.tree.yview, style="Scout.Vertical.TScrollbar")
        hsb = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.tree.xview, style="Scout.Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        grid_frame.rowconfigure(0, weight=1)
        grid_frame.columnconfigure(0, weight=1)

        activity_wrap = tk.Frame(main, bg=SURFACE)
        activity_wrap.pack(fill="x", padx=16, pady=(0, 14))
        tk.Label(
            activity_wrap,
            text="Activity",
            bg=SURFACE,
            fg=INK,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self.progress_text = tk.Text(
            activity_wrap,
            height=5,
            wrap="word",
            state="disabled",
            bg="#FFFDF8",
            fg=INK,
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=6,
        )
        self.progress_text.tag_config("complete_tag", background=SAGE, foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.progress_text.tag_config("error_tag", background=ERROR, foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.progress_text.pack(fill="x")

        self._set_keyword_chip(self.keyword)

    def _set_keyword_chip(self, keyword: str | None) -> None:
        label = (keyword or "").strip() or "—"
        self.keyword_chip.config(text=f"Keyword  {label}")

    def _on_filter_change(self) -> None:
        self._apply_filters()

    def _on_tree_double_click(self, event) -> str | None:
        if self.tree.identify_region(event.x, event.y) != "heading":
            return None
        self._reset_column_widths()
        return "break"

    def _reset_column_widths(self) -> None:
        self.tree.column("#0", width=0, minwidth=0, stretch=False)
        for col_field in COLUMNS:
            self.tree.column(col_field, width=120, minwidth=40, stretch=False, anchor="w")

    def reset_filters(self) -> None:
        self.filter_email.set(False)
        self.filter_phone.set(False)
        self.filter_website.set(False)
        self.filter_unclaimed.set(False)
        self.filter_rating.set("Any")
        self.filter_reviews.set("Any")
        self.filter_search.set("")
        self._apply_filters()

    def _apply_filters(self) -> None:
        email_only = self.filter_email.get()
        phone_only = self.filter_phone.get()
        website_only = self.filter_website.get()
        unclaimed_only = self.filter_unclaimed.get()
        rating_val = self.filter_rating.get()
        reviews_val = self.filter_reviews.get()
        query = self.filter_search.get().strip().lower()

        res = []
        for l in self.listings:
            if email_only and not l.email:
                continue
            if phone_only and not l.phone:
                continue
            if website_only and not l.website:
                continue
            if unclaimed_only and l.verification_text != "Claim this business":
                continue
            if rating_val == "≥ 4.0★" and (not l.rating or l.rating < 4.0):
                continue
            elif rating_val == "≥ 4.5★" and (not l.rating or l.rating < 4.5):
                continue
            elif rating_val == "< 4.0★" and (l.rating and l.rating >= 4.0):
                continue
            if reviews_val == "≥ 10" and (not l.review_count or l.review_count < 10):
                continue
            elif reviews_val == "≥ 50" and (not l.review_count or l.review_count < 50):
                continue
            elif reviews_val == "≥ 100" and (not l.review_count or l.review_count < 100):
                continue
            elif reviews_val == "≥ 500" and (not l.review_count or l.review_count < 500):
                continue
            if query:
                searchable = f"{l.name or ''} {l.category or ''} {l.city or ''} {l.keyword or ''}".lower()
                if query not in searchable:
                    continue
            res.append(l)

        self.filtered_listings = res
        self._refresh_treeview()

    def _refresh_treeview(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for l in self.filtered_listings:
            self.tree.insert("", "end", values=[getattr(l, c) or "" for c in COLUMNS])
        total = len(self.listings)
        shown = len(self.filtered_listings)
        if shown == total:
            self.filter_status_lbl.config(text=f"Showing all {total} record(s)")
        else:
            self.filter_status_lbl.config(text=f"Showing {shown} of {total} record(s)")

    def start_bot(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.stop_flag.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.export_btn.config(state="disabled")
        self._log("Starting crawler...")
        existing_urls = {l.maps_url for l in self.listings if l.maps_url}
        self.worker_thread = threading.Thread(
            target=scraper_engine.run_scrape_in_thread,
            args=(self.page_ref, self.keyword, self.event_queue, self.stop_flag, existing_urls),
            daemon=True,
        )
        self.worker_thread.start()

    def stop_bot(self) -> None:
        self.stop_flag.set()
        self._log("Stop requested — finishing current listing then halting...")
        self.stop_btn.config(state="disabled")

    def delete_data(self) -> None:
        if not messagebox.askyesno("Confirm", "Clear all current in-memory results?"):
            return
        self.listings.clear()
        self.filtered_listings.clear()
        self.tree.delete(*self.tree.get_children())
        self._clear_log()
        self.filter_status_lbl.config(text="Showing all 0 record(s)")
        self.export_btn.config(state="disabled")
        self._set_keyword_chip(self.keyword)

    def export_data(self) -> None:
        data_to_export = self.filtered_listings if self.filtered_listings else self.listings
        if not data_to_export:
            messagebox.showinfo("No data", "There is no data to export yet.")
            return
        out_path = export(data_to_export, fmt="xlsx")
        # Export mutates in-memory Listing objects (Saved_Image_Name + Status),
        # so refresh the table to reflect photo download results.
        self._apply_filters()
        messagebox.showinfo("Export complete", f"Saved {len(data_to_export)} record(s) to:\n{out_path}")

    def _log(self, line: str, tag: str | None = None) -> None:
        self.progress_text.config(state="normal")
        if tag:
            self.progress_text.insert("end", line + "\n", tag)
        elif "complete" in line.lower():
            self.progress_text.insert("end", line + "\n", "complete_tag")
        elif "error" in line.lower():
            self.progress_text.insert("end", line + "\n", "error_tag")
        else:
            self.progress_text.insert("end", line + "\n")
        self.progress_text.see("end")
        self.progress_text.config(state="disabled")

    def _clear_log(self) -> None:
        self.progress_text.config(state="normal")
        self.progress_text.delete("1.0", "end")
        self.progress_text.config(state="disabled")

    def _poll_queue(self) -> None:
        """Runs on the Tkinter main thread; drains events pushed by the
        background scraping thread and updates the UI accordingly.
        """
        try:
            while True:
                event = self.event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _handle_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "listing":
            listing: Listing = event["listing"]
            self.listings.append(listing)
            if listing.keyword:
                self.keyword = listing.keyword
                self._set_keyword_chip(listing.keyword)
            self._apply_filters()
            self._log(
                f"Record #{len(self.listings)} --------------\n"
                f"Keyword: {listing.keyword}\n"
                f"Name: {listing.name}\n"
                f"Full Address: {listing.full_address}"
            )
        elif kind == "update":
            index: int = event["index"]
            listing: Listing = event["listing"]
            self.listings[index] = listing
            self._apply_filters()
        elif kind == "log":
            self._log(event["message"])
        elif kind == "done":
            self._log("Crawler complete...")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.export_btn.config(state="normal" if self.listings else "disabled")
        elif kind == "error":
            self._log(f"ERROR: {event['message']}")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")

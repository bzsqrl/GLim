"""
FFMaker – Shader to FFGL Converter
main_gui.py – Queue-first layout with drag-and-drop batch processing.
"""
import customtkinter as ctk
import gc
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ffmaker import pipeline, emit_isf, build_ffgl, paths as ffpaths   # noqa: E402
from ffmaker import convert as ffconvert                               # noqa: E402
from ffmaker import settings as ffsettings                             # noqa: E402
from editor_panel import EditorPanel                                   # noqa: E402


# --- Drag-and-drop support (optional, graceful fallback) ---
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Status icons / colours
STATUS_PENDING  = ("—",  "#6b7280")   # grey
STATUS_BUILDING = ("⟳",  "#f59e0b")   # amber
STATUS_DONE     = ("✓",  "#10b981")   # green
STATUS_ERROR    = ("✗",  "#ef4444")   # red

VALID_EXTENSIONS = {".fs", ".txt", ".glsl", ".frag", ".shader"}
LOG_MAX_LINES = 5000    # older build-log lines are dropped so long batches stay fast


# ---------------------------------------------------------------------------
# Auto-detect shader format from path or content
# ---------------------------------------------------------------------------
def detect_format(path: str = None, code: str = None) -> str:
    """Short label for the queue badge, e.g. 'ISF FX', 'Shadertoy', 'GLSL'."""
    try:
        if code is None:
            code = open(path, encoding="utf-8", errors="replace").read()
        ir = ffconvert.convert(code, extract_params=False)
    except Exception:
        return "?"
    base = {"isf": "ISF", "shadertoy": "Shadertoy", "glsl": "GLSL"}[ir.dialect]
    if ir.kind == "effect":
        return base + " FX" if base != "Shadertoy" else "ST FX"
    if ir.kind == "mixer":
        return base + " Mix"
    return base


# ---------------------------------------------------------------------------
# Small data class for queue items
# ---------------------------------------------------------------------------
class QueueItem:
    def __init__(self, path: str):
        self.path   = path
        self.name   = Path(path).stem
        self.fname  = Path(path).name
        self.fmt    = "…"           # filled in by a background thread (detect_format)
        self.status = "pending"     # pending / building / done / error
        self.error  = ""
        self.iid    = None          # row id in the queue Treeview


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------
class FFMakerApp(ctk.CTk if not _DND_AVAILABLE else TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        if _DND_AVAILABLE:
            ctk.set_appearance_mode("Dark")

        self.title("FFMaker – Shader to FFGL Converter")
        # Fit the screen (minus taskbar), up to 1440x900.
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1440, sw - 60), min(900, sh - 110)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(860, 540)

        self._queue: list[QueueItem] = []
        self._building = False
        self._cancel_event = threading.Event()
        self._source_stem = "FFMakerPlugin"   # for single-file tab
        self._source_path = None
        self.settings = {}                    # single-file tab: the shader's .ffmaker.json
        self.extract_params_var = ctk.BooleanVar(value=True)

        # Force dark background regardless of TkinterDnD vs CTk base class
        self.configure(bg="#1a1a2e")

        self._build_layout()
        self._set_icon()
        if isinstance(self, ctk.CTk):        # CTk puts its own icon back shortly after start
            self.after(300, self._set_icon)
        # Create the GPU validation context now, on the main thread (required on
        # macOS; also makes the first Analyze faster).
        self.after(50, self._init_gpu)
        # Garbage collection runs on this thread only. Left automatic, it runs on
        # whichever thread is allocating, e.g. the output render thread while it holds
        # the GPU lock. Collected Tk objects (fonts and variables from replaced
        # parameter widgets) then wait for this thread, which may itself be waiting
        # for the GPU lock: a deadlock (seen in the queue slideshow).
        gc.disable()
        self.after(50, self._collect_garbage)

    def _collect_garbage(self):
        """Python's automatic collection schedule, run from the Tk loop."""
        (c0, c1, c2), (t0, t1, t2) = gc.get_count(), gc.get_threshold()
        if c0 >= t0:
            gc.collect(2 if c1 >= t1 and c2 >= t2 else 1 if c1 >= t1 else 0)
        self.after(50, self._collect_garbage)

    def _set_icon(self):
        """FFMaker's icon for its windows (title bar, taskbar, Alt+Tab; the Dock
        when run from source on macOS)."""
        d = ffpaths.icon_dir()
        try:
            if sys.platform == "win32":
                self.iconbitmap(default=os.path.join(d, "FFMaker.ico"))
            self._icon_photos = [tk.PhotoImage(file=os.path.join(d, "png", f"ffmaker_{s}.png"))
                                 for s in (16, 32, 48, 64, 128, 256)]
            self.iconphoto(True, *self._icon_photos)
        except Exception as e:          # icons are cosmetic; never block startup
            print(f"FFMaker: window icon not set ({e})")

    def _init_gpu(self):
        try:
            from ffmaker import validate as V
            with V.gpu() as ctx:
                self.log(f"GPU: {ctx.renderer}")
        except Exception as e:
            self.log(f"GPU validation unavailable ({e}). Shaders will be built without compile checks.")

    # CustomTkinter's DPI tracker calls these on CTk windows; TkinterDnD.Tk lacks them.
    def block_update_dimensions_event(self):
        pass

    def unblock_update_dimensions_event(self):
        pass

    # -----------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------
    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        # ── Title row ──
        frame_title = ctk.CTkFrame(self, fg_color="transparent")
        frame_title.grid(row=0, column=0, padx=20, pady=(12, 4), sticky="ew")
        ctk.CTkLabel(frame_title, text="FFMaker",
                     font=("Arial", 24, "bold"),
                     text_color="#ffffff").pack(side="left")

        # Global extraction toggle
        self.cb_extract = ctk.CTkCheckBox(frame_title, text="Extract User Parameters",
                                         variable=self.extract_params_var,
                                         onvalue=True, offvalue=False,
                                         font=("Arial", 12))
        self.cb_extract.pack(side="right", padx=(10, 0))

        # ── Tab view ──
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="nsew")
        self.tabs.add("Queue")
        self.tabs.add("Single File")
        self.tabs.tab("Queue").grid_columnconfigure(0, weight=1)
        self.tabs.tab("Queue").grid_rowconfigure(0, weight=0)  # toolbar
        self.tabs.tab("Queue").grid_rowconfigure(1, weight=0)  # column headers
        self.tabs.tab("Queue").grid_rowconfigure(2, weight=1)  # queue list
        self.tabs.tab("Single File").grid_columnconfigure(0, weight=1)
        self.tabs.tab("Single File").grid_rowconfigure(1, weight=1)

        self._build_queue_tab()
        self._build_singlefile_tab()

        # ── Shared log ──
        frame_log = ctk.CTkFrame(self)
        frame_log.grid(row=2, column=0, padx=20, pady=(0, 14), sticky="ew")
        frame_log.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame_log, text="Build Log", font=("Arial", 11, "bold"),
                     anchor="w").grid(row=0, column=0, padx=10, pady=(6, 0), sticky="w")
        self.textbox_log = ctk.CTkTextbox(frame_log, font=("Consolas", 11),
                                          text_color="#10b981", height=110)
        self.textbox_log.grid(row=1, column=0, padx=10, pady=(2, 8), sticky="ew")
        self.log("System ready.")

    # -----------------------------------------------------------------------
    # Queue tab
    # -----------------------------------------------------------------------
    def _build_queue_tab(self):
        tab = self.tabs.tab("Queue")

        # Toolbar
        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=6, pady=(6, 12), sticky="ew")

        ctk.CTkButton(toolbar, text="＋ Add Files", width=110,
                      command=self._add_files_dialog).pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar, text="📁 Add Folder", width=120,
                      command=self._add_folder_dialog).pack(side="left", padx=(0, 6))
        self.btn_reset_queue = ctk.CTkButton(
            toolbar, text="⟲ Reset Status", width=150,
            fg_color="#374151", hover_color="#4b5563",
            command=self._reset_status)
        self.btn_reset_queue.pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar, text="✓ Clear Completed", width=140,
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._clear_completed).pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar, text="Clear All", width=90,
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._clear_queue).pack(side="left", padx=(0, 20))

        self.btn_export_isf_queue = ctk.CTkButton(
            toolbar, text="↑ Export ISF", width=170,
            fg_color="#10b981", hover_color="#059669",
            command=self._start_export_isf_queue)
        self.btn_export_isf_queue.pack(side="right", padx=(6, 0))

        self.btn_build_queue = ctk.CTkButton(
            toolbar, text="▶  Build Queue", width=170,
            fg_color="#6366f1", hover_color="#4f46e5",
            command=self._start_build_queue)
        self.btn_build_queue.pack(side="right")

        # Queue list: a native Treeview only draws the visible rows, so it stays
        # fast with thousands of files (one widget per row did not).
        box = ctk.CTkFrame(tab, fg_color="#111827")
        box.grid(row=2, column=0, padx=6, pady=(0, 6), sticky="nsew")
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(0, weight=1)

        scale = ctk.ScalingTracker.get_widget_scaling(box)
        style = ttk.Style(self)
        style.theme_use("clam")      # the native Windows/macOS themes ignore these colours
        style.configure("Queue.Treeview", background="#111827", fieldbackground="#111827",
                        foreground="#e5e7eb", bordercolor="#111827", borderwidth=0,
                        rowheight=int(28 * scale), font=("Segoe UI", 12))
        style.map("Queue.Treeview", background=[("selected", "#374151")],
                  foreground=[("selected", "#ffffff")])
        style.configure("Queue.Treeview.Heading", background="#1e2230", foreground="#9ca3af",
                        bordercolor="#111827", relief="flat", font=("Segoe UI", 12, "bold"))
        style.map("Queue.Treeview.Heading", background=[("active", "#2a3040")])
        style.layout("Queue.Treeview", [("Treeview.treearea", {"sticky": "nsew"})])

        self.tree = ttk.Treeview(box, style="Queue.Treeview", show="headings",
                                 columns=("num", "file", "type", "status"))
        for col, text, width, anchor, stretch in (
                ("num", "#", 50, "e", False), ("file", "Filename", 360, "w", True),
                ("type", "Type", 110, "center", False), ("status", "Status", 260, "w", True)):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=int(width * scale), minwidth=int(40 * scale),
                             anchor=anchor, stretch=stretch)
        for status, (_, color) in (("pending", STATUS_PENDING), ("building", STATUS_BUILDING),
                                   ("done", STATUS_DONE), ("error", STATUS_ERROR)):
            self.tree.tag_configure(status, foreground=color)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        sb = ctk.CTkScrollbar(box, command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns", pady=4)
        self.tree.configure(yscrollcommand=sb.set)
        self._items_by_iid: dict[str, QueueItem] = {}
        self._next_iid = 0

        # Remove with Delete/Backspace; right-click for a menu; double-click opens the file.
        # With rows selected, Build / Export act on just those (the buttons say so).
        self.tree.bind("<Delete>", lambda e: self._remove_selected())
        self.tree.bind("<BackSpace>", lambda e: self._remove_selected())
        self.tree.bind("<Escape>", lambda e: self.tree.selection_set(()))
        self.tree.bind("<Button-1>", self._on_queue_click, add="+")
        self.tree.bind("<Double-1>", self._on_queue_double_click)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_queue_buttons())
        self._queue_menu = tk.Menu(self, tearoff=0)
        self._queue_menu.add_command(label="Build Selected", command=self._start_build_queue)
        self._queue_menu.add_command(label="Export Selected to ISF", command=self._start_export_isf_queue)
        self._queue_menu.add_separator()
        self._queue_menu.add_command(label="Reset Status", command=self._reset_status)
        self._queue_menu.add_command(label="Open in Single File", command=self._open_selected)
        self._queue_menu.add_command(label="Remove", command=self._remove_selected)
        self.tree.bind("<Button-3>", self._on_queue_right_click)
        if sys.platform == "darwin":    # older Tk on macOS reports right-click as button 2 (elsewhere it's the middle button)
            self.tree.bind("<Button-2>", self._on_queue_right_click)
            self.tree.bind("<Control-Button-1>", self._on_queue_right_click)   # Mac Control-click
        # Ctrl+A (⌘A on macOS) selects every queue row anywhere in the window,
        # except in text fields, which keep their own Ctrl+A.
        mod = "Command" if sys.platform == "darwin" else "Control"
        for key in ("a", "A"):
            self.bind_all(f"<{mod}-{key}>", self._select_all_queue, add="+")

        # Drop-zone label (shown when empty)
        self.lbl_drop = ctk.CTkLabel(
            box,
            text="Drop .fs or .txt shader files here, or use 'Add Files' / 'Add Folder'",
            text_color="#4b5563", fg_color="#111827", font=("Arial", 13))
        self._show_drop_hint(True)

        # Wire up drag-and-drop
        if _DND_AVAILABLE:
            self.tree.drop_target_register(DND_FILES)
            self.tree.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)

    # -----------------------------------------------------------------------
    # Single-file tab (existing workflow, preserved)
    # -----------------------------------------------------------------------
    def _build_singlefile_tab(self):
        tab = self.tabs.tab("Single File")

        # Tools row
        tools = ctk.CTkFrame(tab, fg_color="transparent")
        tools.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkButton(tools, text="Open File", command=self.open_file, width=100).pack(side="left", padx=(0, 6))
        ctk.CTkButton(tools, text="Analyze Code", command=self.analyze_code,
                      fg_color="#10b981", hover_color="#059669").pack(side="left", padx=6)

        ctk.CTkLabel(tools, text="Output Name:").pack(side="left", padx=(10, 4))
        self.entry_plugin_name = ctk.CTkEntry(tools, width=200, placeholder_text="PluginName")
        self.entry_plugin_name.pack(side="left", padx=0)
        self.entry_plugin_name.insert(0, self._source_stem)

        self.btn_build_single = ctk.CTkButton(
            tools, text="Compile FFGL (.dll)", command=self._build_single,
            fg_color="#6366f1", hover_color="#4f46e5")
        self.btn_build_single.pack(side="right", padx=(6, 0))

        self.btn_export_isf_single = ctk.CTkButton(
            tools, text="Export ISF (.fs)", command=self._export_isf_single,
            fg_color="#10b981", hover_color="#059669")
        self.btn_export_isf_single.pack(side="right")

        # Paned Window (Row 1) - horizontal resizable split
        self.panes = tk.PanedWindow(tab, orient=tk.HORIZONTAL, bg="#1a1a2e",
                                    bd=0, sashwidth=4, sashpad=0,
                                    showhandle=False, opaqueresize=True)
        self.panes.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="nsew")

        # Left Pane: Code editor
        self.textbox_code = ctk.CTkTextbox(self.panes, font=("Consolas", 13), wrap="none")
        self.textbox_code.insert("1.0", "// Paste your shader code here...")
        self.textbox_code.bind("<FocusIn>", self._on_code_focus)
        self.panes.add(self.textbox_code, stretch="always")

        # Right Pane: Parameters
        self.editor = EditorPanel(self.panes, on_recompile=lambda: self.analyze_code(keep_time=True),
                                  log=self.log)
        self.panes.add(self.editor, stretch="always", minsize=760)
        # ← / → (buttons, or keys in the output window) step through the queue,
        # loading each shader here; the output follows.
        self.editor.get_playlist = lambda: [i.path for i in self._queue]
        self.editor.convert_path = self._convert_for_preview
        self.editor.on_select = lambda path, res: self._load_file_path(path, res=res)
        self.textbox_code.bind("<Control-Return>", lambda e: (self.analyze_code(), "break")[1])
        if sys.platform == "darwin":
            self.textbox_code.bind("<Command-Return>", lambda e: (self.analyze_code(), "break")[1])

        self.after(200, self._set_initial_sash)

    def _set_initial_sash(self):
        """Initial split for the Single File tab: code on the left, editor panel on the right.
        Retries until the tab has been shown and laid out."""
        try:
            w = self.panes.winfo_width()
            if w > 200:
                self.panes.sash_place(0, max(300, w - 860), 0)
                return
        except Exception:
            pass
        self.after(300, self._set_initial_sash)

    def _on_code_focus(self, event):
        if self.textbox_code.get("1.0", "end-1c").strip() == "// Paste your shader code here...":
            self.textbox_code.delete("1.0", "end")

    # -----------------------------------------------------------------------
    # Shared log helper
    # -----------------------------------------------------------------------
    def log(self, text: str):
        self.textbox_log.insert("end", f"> {text}\n")
        lines = int(self.textbox_log.index("end-1c").split(".")[0])
        if lines > LOG_MAX_LINES + 500:
            self.textbox_log.delete("1.0", f"{lines - LOG_MAX_LINES}.0")
        self.textbox_log.see("end")

    def _gui_log(self, msg: str):
        self.after(0, lambda m=msg: self.log(m))

    # -----------------------------------------------------------------------
    # Queue management
    # -----------------------------------------------------------------------
    def _add_paths(self, paths: list[str]):
        """Add a list of file paths to the queue (dedup by path)."""
        existing = {item.path for item in self._queue}
        new_items = []
        for p in paths:
            if not os.path.isfile(p):
                continue
            if Path(p).suffix.lower() not in VALID_EXTENSIONS:
                continue
            if p in existing:
                continue
            item = QueueItem(p)
            self._queue.append(item)
            existing.add(p)
            self._add_queue_row(item)
            new_items.append(item)
        if new_items:
            self._show_drop_hint(False)
            self.log(f"Added {len(new_items)} file(s) to queue. Total: {len(self._queue)}")
            # Detecting the type runs the converter (~15 ms a file), so do it off the UI thread.
            threading.Thread(target=self._detect_formats, args=(new_items,), daemon=True).start()

    def _detect_formats(self, items: list[QueueItem]):
        for item in items:
            fmt = detect_format(item.path)
            self.after(0, lambda it=item, f=fmt: self._set_item_format(it, f))

    def _set_item_format(self, item: QueueItem, fmt: str):
        item.fmt = fmt
        if item.iid and self.tree.exists(item.iid):
            self.tree.set(item.iid, "type", fmt)

    def _show_drop_hint(self, show: bool):
        if show:
            self.lbl_drop.place(relx=0.5, rely=0.25, anchor="center")
        else:
            self.lbl_drop.place_forget()

    def _add_files_dialog(self):
        paths = ctk.filedialog.askopenfilenames(
            title="Add shader files",
            filetypes=[("Shader Source", "*.fs *.txt *.glsl"), ("All Files", "*.*")])
        if paths:
            self._add_paths(list(paths))

    def _add_folder_dialog(self):
        folder = ctk.filedialog.askdirectory(title="Add folder of shader files")
        if not folder:
            return
        paths = []
        for root, _, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in VALID_EXTENSIONS:
                    paths.append(os.path.join(root, f))
        paths.sort()
        self._add_paths(paths)

    def _on_drop(self, event):
        """Handle drag-and-drop onto the queue area."""
        raw = event.data
        # tkinterdnd2 wraps paths in {} if they contain spaces
        import re
        paths = re.findall(r'\{([^}]+)\}|(\S+)', raw)
        flat = [p[0] or p[1] for p in paths]
        all_files = []
        for p in flat:
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if Path(f).suffix.lower() in VALID_EXTENSIONS:
                            all_files.append(os.path.join(root, f))
            elif os.path.isfile(p):
                all_files.append(p)
        self._add_paths(all_files)

        # If dropping while the Single File tab is active, load the first file into the editor.
        if all_files and self.tabs.get() == "Single File":
            self._load_file_path(all_files[0])

    def _remove_items(self, items: list[QueueItem]):
        """Remove items from the queue (never the one being built) and renumber."""
        items = [i for i in items if i.status != "building"]
        if not items:
            return 0
        gone = set(map(id, items))
        self.tree.delete(*[i.iid for i in items])
        for i in items:
            self._items_by_iid.pop(i.iid, None)
        self._queue = [i for i in self._queue if id(i) not in gone]
        for n, item in enumerate(self._queue, 1):
            self.tree.set(item.iid, "num", n)
        if not self._queue:
            self._show_drop_hint(True)
        return len(items)

    def _clear_completed(self):
        """Remove only successfully built items from the queue."""
        n = self._remove_items([item for item in self._queue if item.status == "done"])
        self.log(f"Cleared {n} completed item(s). Remaining: {len(self._queue)}")

    def _reset_status(self):
        """Set done / failed rows back to Pending (the selection, or the whole queue),
        so Build Queue converts them again without reloading the files."""
        items = self._selected_items() or self._queue
        items = [i for i in items if i.status in ("done", "error")]
        for item in items:
            item.status, item.error = "pending", ""
            self._set_item_status(item, "pending", "Pending")
        self.log(f"Reset {len(items)} item(s) to Pending.")

    def _clear_queue(self):
        n = self._remove_items(list(self._queue))
        self.log("Queue cleared." if not self._queue else
                 f"Cleared {n} item(s); the one being built stays. Remaining: {len(self._queue)}")

    def _selected_items(self) -> list[QueueItem]:
        return [self._items_by_iid[i] for i in self.tree.selection() if i in self._items_by_iid]

    def _remove_selected(self):
        self._remove_items(self._selected_items())

    def _open_selected(self):
        items = self._selected_items()
        if items:
            self.tabs.set("Single File")
            self._load_file_path(items[0].path)

    def _on_queue_double_click(self, event):
        if self.tree.identify_row(event.y):
            self._open_selected()

    def _select_all_queue(self, event):
        if self.tabs.get() != "Queue" or isinstance(event.widget, (tk.Text, tk.Entry, ttk.Entry)):
            return None
        self.tree.selection_set(self.tree.get_children())
        self.tree.focus_set()       # so Delete / Esc act on the selection next
        return "break"

    def _on_queue_click(self, event):
        # Clicking empty space below the rows clears the selection (back to whole-queue mode).
        if self.tree.identify_region(event.x, event.y) == "nothing":
            self.tree.selection_set(())

    def _on_queue_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        busy = "disabled" if self._building else "normal"
        self._queue_menu.entryconfigure("Build Selected", state=busy)
        self._queue_menu.entryconfigure("Export Selected to ISF",
                                        state=self.btn_export_isf_queue.cget("state"))
        self._queue_menu.tk_popup(event.x_root, event.y_root)

    def _update_queue_buttons(self):
        """Label Build / Export for what they will act on: the selection, or the whole queue."""
        n = len(self.tree.selection())
        if not self._building:
            self.btn_build_queue.configure(
                state="normal", fg_color="#6366f1", hover_color="#4f46e5",
                text=f"▶  Build Selected ({n})" if n else "▶  Build Queue")
        self.btn_export_isf_queue.configure(
            text=f"↑ Export Selected ({n})" if n else "↑ Export ISF")
        self.btn_reset_queue.configure(
            text=f"⟲ Reset Selected ({n})" if n else "⟲ Reset Status")

    def _add_queue_row(self, item: QueueItem):
        """Add one row to the queue list."""
        self._next_iid += 1
        item.iid = f"q{self._next_iid}"
        self._items_by_iid[item.iid] = item
        self.tree.insert("", "end", iid=item.iid, tags=("pending",),
                         values=(len(self._queue), item.fname, item.fmt,
                                 f"{STATUS_PENDING[0]}  Pending"))

    def _set_item_status(self, item: QueueItem, status: str, text: str = ""):
        icon_char = {"building": STATUS_BUILDING, "done": STATUS_DONE,
                     "error": STATUS_ERROR}.get(status, STATUS_PENDING)[0]
        label = text or status.capitalize()

        def _update():
            if item.iid and self.tree.exists(item.iid):
                self.tree.item(item.iid, tags=(status,))
                self.tree.set(item.iid, "status", f"{icon_char}  {label}")
        self.after(0, _update)

    # -----------------------------------------------------------------------
    # Batch build
    # -----------------------------------------------------------------------
    def _start_build_queue(self):
        if self._building:
            self._cancel_event.set()
            self.btn_build_queue.configure(state="disabled", text="Cancelling…")
            self._gui_log("── Cancel requested... ──")
            return
            
        selected = set(self.tree.selection())
        if selected:        # selected rows are (re)built whatever their status
            pending = [i for i in self._queue if i.iid in selected and i.status != "building"]
        else:
            pending = [i for i in self._queue if i.status in ("pending", "error")]
        if not pending:
            self.log("Nothing to build (all items are done or queue is empty).")
            return
        if selected:
            self.log(f"Building {len(pending)} selected item(s)…")

        self._building = True
        self._cancel_event.clear()
        self.btn_build_queue.configure(text="Cancel Build", fg_color="#ef4444", hover_color="#dc2626")
        t = threading.Thread(target=self._build_queue_thread,
                             args=(pending, self.extract_params_var.get()), daemon=True)
        t.start()

    def _build_queue_thread(self, items: list[QueueItem], extract_params: bool):
        output_dir = ffpaths.default_output_dir()
        suffix = "-p" if extract_params else ""

        ok = err = 0
        was_cancelled = False
        visible_names = set()

        for item in items:
            if self._cancel_event.is_set():
                was_cancelled = True
                break
            if item.iid not in self._items_by_iid:     # removed from the queue after the build started
                continue

            item.status = "building"
            self._set_item_status(item, "building", "Building…")
            self._gui_log(f"[{item.fname}] Starting…")

            try:
                code = open(item.path, encoding="utf-8", errors="replace").read()
                wanted = ffsettings.load(item.path).get("plugin_name") or item.name + suffix
                name = build_ffgl.unique_plugin_name(wanted, visible_names)
                status, text = self._convert_and_build(code, name, item.path, output_dir,
                                                       extract_params=extract_params)
                if status == "cancelled":
                    item.status = "pending"
                    self._set_item_status(item, "pending", "Pending")
                    self._gui_log(f"[{item.fname}] Cancelled.")
                    was_cancelled = True
                    break
                item.status = status
                self._set_item_status(item, status, text)
                if status == "done":
                    ok += 1
                else:
                    err += 1
            except Exception as exc:
                self._gui_log(f"  EXCEPTION: {exc}")
                item.status = "error"
                self._set_item_status(item, "error", "Exception")
                err += 1

        if was_cancelled:
            self._gui_log(f"── Batch cancelled: {ok} succeeded, {err} failed ──")
        else:
            self._gui_log(f"── Batch complete: {ok} succeeded, {err} failed ──")
            
        self._building = False
        self.after(0, self._update_queue_buttons)

    # -----------------------------------------------------------------------
    # Single-file tab methods (unchanged from original)
    # -----------------------------------------------------------------------
    def _convert_and_build(self, code, name, path, output_dir, settings=None, extract_params=False):
        """Shared by queue and single-file builds. Returns (status, label).
        settings=None uses the shader's saved .ffmaker.json. Runs on worker
        threads, so callers read extract_params from the checkbox beforehand."""
        log = self._gui_log
        try:
            res = pipeline.convert_ffgl(code, name=name, path=path, settings=settings,
                                        extract_params=extract_params)
        except ffconvert.ConvertError as e:
            log(f"  ERROR: {e}")
            return "error", "Not a shader"
        for w in res.ir.warnings:
            log(f"  WARN: {w}")
        if res.demoted:
            log(f"  Kept as constants (would not compile as sliders): {', '.join(res.demoted)}")
        if not res.ok:
            log("  Shader does not compile:")
            for ln, msg in res.errors[:8]:
                log(f"    line {ln}: {msg}")
            return "error", "Shader error"
        if not res.validated:
            log(f"  Note: shader not GPU-validated {res.log}")
        try:
            dst = build_ffgl.build(res.ir, res.ffgl_glsl, name, out_dir=output_dir,
                                   log=lambda m: log("  " + m), cancel_event=self._cancel_event)
        except build_ffgl.BuildError as e:
            if str(e) == "cancelled":
                return "cancelled", ""
            log(f"  Build failed: {e}")
            return "error", "Build failed"
        log(f"[{name}] ✓ {res.ir.kind}, {len(res.ir.params)} params → {dst}")
        return "done", os.path.basename(dst)

    def analyze_code(self, keep_time=False, res=None):
        code = self.textbox_code.get("1.0", "end-1c")
        if not keep_time:
            self.log("Analyzing shader code...")
        if not self.entry_plugin_name.get().strip():
            self.entry_plugin_name.delete(0, "end")
            self.entry_plugin_name.insert(0, "FFMakerPlugin")

        try:
            if res is None:
                res = pipeline.convert_ffgl(code, name=self.entry_plugin_name.get().strip(),
                                            path=self._source_path, settings=self.settings,
                                            extract_params=self.extract_params_var.get())
        except ffconvert.ConvertError as e:
            self.log(f"ERROR: {e}")
            return
        ir = res.ir
        if not keep_time:
            self.log(f"Detected: {ir.dialect} {ir.kind}"
                     + (f", {len(ir.programs)} passes" if len(ir.programs) > 1 else ""))
            for w in ir.warnings:
                self.log(f"WARNING: {w}")
        if res.demoted:
            self.log(f"Kept as constants (would not compile as sliders): {', '.join(res.demoted)}")
        if not res.ok:
            self.log("Shader does not compile:")
            for ln, msg in res.errors[:8]:
                self.log(f"  line {ln}: {msg}")
        elif res.validated and not keep_time:
            promoted = [p for p in ir.params if p.origin in ("const", "define")]
            self.log(f"✓ Compiles on this GPU. {len(ir.params)} parameter(s)"
                     + (f", {len(promoted)} from constants." if promoted else "."))
        self.editor.load(res, self.settings, self._source_path, keep_time=keep_time)

    def _build_single(self):
        self.log("Starting build…")
        self.btn_build_single.configure(state="disabled")
        code = self.textbox_code.get("1.0", "end-1c")
        name = self.entry_plugin_name.get().strip() or "FFMakerPlugin"
        path = self._source_path
        self._remember_plugin_name(name)
        if path:
            ffsettings.save(path, self.settings)     # queue builds of this file use the same settings
        settings = dict(self.settings)
        extract = self.extract_params_var.get()

        def run():
            try:
                self._cancel_event.clear()
                self._convert_and_build(code, name, path, ffpaths.default_output_dir(), settings, extract)
            except Exception as exc:
                self._gui_log(f"EXCEPTION: {exc}")
            finally:
                self.after(0, lambda: self.btn_build_single.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def open_file(self):
        path = ctk.filedialog.askopenfilename(
            filetypes=[("Shader Source", "*.fs *.txt *.glsl"), ("All Files", "*.*")])
        if path:
            self._load_file_path(path)

    def _remember_plugin_name(self, name):
        if self._source_path and name != Path(self._source_path).stem:
            self.settings["plugin_name"] = name
        else:
            self.settings.pop("plugin_name", None)

    def _convert_for_preview(self, path):
        """Convert a queue file (with its saved settings) for ← / → in Single File."""
        code = open(path, encoding="utf-8", errors="replace").read()
        name = ffsettings.load(path).get("plugin_name") or Path(path).stem
        return pipeline.convert_ffgl(code, name=name, path=path,
                                     extract_params=self.extract_params_var.get())

    def _load_file_path(self, path: str, res=None):
        """Helper to load a file into the Single File editor and analyze it.
        res: an existing conversion of the file (with its saved settings) to reuse."""
        try:
            code = open(path, encoding="utf-8").read()
            self.textbox_code.delete("1.0", "end")
            self.textbox_code.insert("1.0", code)
            
            self.settings = ffsettings.load(path)
            self.entry_plugin_name.delete(0, "end")
            self.entry_plugin_name.insert(0, self.settings.get("plugin_name") or Path(path).stem)

            self._source_stem = Path(path).stem
            self._source_path = path
            if self.settings:
                self.log(f"Loaded saved settings: {ffsettings.path_for(path)}")
            self.log(f"Loaded: {Path(path).name} (will export as {self.entry_plugin_name.get()}.dll)")
            self.analyze_code(res=res)
        except Exception as e:
            self.log(f"Error reading file: {e}")


    # -----------------------------------------------------------------------
    # ISF Export
    # -----------------------------------------------------------------------
    def _isf_export(self, code, name, path, out_dir, settings=None, extract_params=None):
        """Write <name>.fs (plus texture files) into out_dir. Returns (fs_path, note).
        Worker threads pass extract_params; None reads the checkbox."""
        if extract_params is None:
            extract_params = self.extract_params_var.get()
        res = pipeline.convert_ffgl(code, name=name, path=path, settings=settings,
                                    extract_params=extract_params)
        if res.ir.dialect == "isf":
            dst = os.path.join(out_dir, name + ".fs")
            with open(dst, "w", encoding="utf-8") as f:
                f.write(emit_isf.apply_settings_to_isf(code, res.ir))
            vs = os.path.splitext(path)[0] + ".vs" if path else ""
            if vs and os.path.isfile(vs):
                import shutil
                shutil.copy2(vs, os.path.join(out_dir, name + ".vs"))
            return dst, "ISF source: header updated with your settings"
        if not res.ok:
            raise RuntimeError("shader does not compile: " +
                               "; ".join(f"line {l}: {m}" for l, m in res.errors[:3]))
        res.ir.name = name
        return emit_isf.write(res.ir, out_dir), f"{len(res.ir.params)} inputs"

    def _export_isf_single(self):
        code = self.textbox_code.get("1.0", "end-1c").strip()
        if not code or code == "// Paste your shader code here...":
            self.log("ERROR: No code to export.")
            return

        name = self.entry_plugin_name.get().strip() or "ExportedISF"
        suffix = "-p" if self.extract_params_var.get() else ""
        save_path = ctk.filedialog.asksaveasfilename(
            title="Export ISF Shader",
            initialfile=f"{name}{suffix}.fs",
            defaultextension=".fs",
            filetypes=[("ISF Shader", "*.fs"), ("All Files", "*.*")])
        if not save_path:
            return
        try:
            dst, note = self._isf_export(code, Path(save_path).stem, self._source_path,
                                         os.path.dirname(save_path), settings=self.settings)
            self.log(f"✓ Exported ISF to {dst} ({note})")
        except Exception as exc:
            self.log(f"ERROR: Export failed: {exc}")

    def _start_export_isf_queue(self):
        selected = set(self.tree.selection())
        items = [i for i in self._queue if i.status in ("pending", "done", "error")
                 and (not selected or i.iid in selected)]
        if not items:
            self.log("Nothing to export.")
            return
        out_dir = ctk.filedialog.askdirectory(title="Select folder for ISF exports")
        if not out_dir:
            return

        self.log(f"Exporting {len(items)} items to ISF...")
        extract = self.extract_params_var.get()
        suffix = "-p" if extract else ""
        self.btn_export_isf_queue.configure(state="disabled")

        def run():          # off the UI thread, so long exports don't freeze the window
            ok = 0
            for item in items:
                try:
                    code = open(item.path, encoding="utf-8", errors="replace").read()
                    _, note = self._isf_export(code, item.name + suffix, item.path, out_dir,
                                               extract_params=extract)
                    self._gui_log(f"  [{item.fname}] ✓ {note}")
                    ok += 1
                except Exception as exc:
                    self._gui_log(f"  [{item.fname}] Export failed: {exc}")
            self._gui_log(f"✓ ISF Export complete: {ok}/{len(items)} successful.")
            self.after(0, lambda: self.btn_export_isf_queue.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

def _selftest(shader, out_dir):
    """Headless check of a (packaged) build: convert, GPU-validate and build one
    shader. Writes selftest.log into out_dir. Usage: FFMaker.exe --selftest <shader> <out_dir>"""
    import traceback
    os.makedirs(out_dir, exist_ok=True)
    lines = []
    try:
        code = open(shader, encoding="utf-8", errors="replace").read()
        res = pipeline.convert_ffgl(code, name=Path(shader).stem, path=shader)
        lines.append(f"ok={res.ok} validated={res.validated} kind={res.ir.kind} params={len(res.ir.params)} {res.log}")
        dst = build_ffgl.build(res.ir, res.ffgl_glsl, Path(shader).stem, out_dir=out_dir, log=lines.append)
        lines.append(f"built {dst}")
    except Exception:
        lines.append(traceback.format_exc())
    with open(os.path.join(out_dir, "selftest.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--selftest":
        _selftest(sys.argv[2], sys.argv[3])
        sys.exit(0)
    if sys.platform == "win32":
        # Own taskbar entry and icon, also when run from source (not Python's).
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FFMaker.FFMaker")
        except Exception:
            pass
    app = FFMakerApp()
    app.mainloop()

"""
FFMaker – Shader to FFGL Converter
main_gui.py – Queue-first layout with drag-and-drop batch processing.
"""
import customtkinter as ctk
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ffmaker import pipeline, emit_isf, build_ffgl, paths as ffpaths   # noqa: E402
from ffmaker import convert as ffconvert                               # noqa: E402


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
        self.fmt    = detect_format(path)
        self.status = "pending"     # pending / building / done / error
        self.error  = ""
        # UI widgets (filled in when row is created)
        self.row_frame   = None
        self.lbl_status  = None
        self.lbl_icon    = None


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------
class FFMakerApp(ctk.CTk if not _DND_AVAILABLE else TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        if _DND_AVAILABLE:
            ctk.set_appearance_mode("Dark")

        self.title("FFMaker – Shader to FFGL Converter")
        self.geometry("1050x680")
        self.minsize(860, 540)

        self._queue: list[QueueItem] = []
        self._building = False
        self._cancel_event = threading.Event()
        self._source_stem = "FFMakerPlugin"   # for single-file tab
        self.extract_params_var = ctk.BooleanVar(value=True)

        # Force dark background regardless of TkinterDnD vs CTk base class
        self.configure(bg="#1a1a2e")

        self._build_layout()

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
                                          text_color="#10b981", height=160)
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
        ctk.CTkButton(toolbar, text="✓ Clear Completed", width=140,
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._clear_completed).pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar, text="Clear All", width=90,
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._clear_queue).pack(side="left", padx=(0, 20))

        self.btn_export_isf_queue = ctk.CTkButton(
            toolbar, text="↑ Export ISF", width=120,
            fg_color="#10b981", hover_color="#059669",
            command=self._start_export_isf_queue)
        self.btn_export_isf_queue.pack(side="right", padx=(6, 0))

        self.btn_build_queue = ctk.CTkButton(
            toolbar, text="▶  Build Queue", width=140,
            fg_color="#6366f1", hover_color="#4f46e5",
            command=self._start_build_queue)
        self.btn_build_queue.pack(side="right")

        # Column headers
        hdr = ctk.CTkFrame(tab, fg_color="#1e2230", corner_radius=6)
        hdr.grid(row=1, column=0, padx=6, pady=(0, 2), sticky="ew")
        ctk.CTkLabel(hdr, text="#",        width=28,  anchor="center", text_color="#9ca3af", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(10, 4))
        
        self.hdr_fname = ctk.CTkLabel(hdr, text="Filename", width=290, anchor="w", text_color="#9ca3af", font=("Segoe UI", 12, "bold"))
        self.hdr_fname.pack(side="left")
        
        # Drag handle 1
        self.drag_fname = ctk.CTkFrame(hdr, width=4, height=24, fg_color="transparent", cursor="sb_h_double_arrow")
        self.drag_fname.pack(side="left")
        self.drag_fname.bind("<ButtonPress-1>", self._on_press_fname)
        self.drag_fname.bind("<B1-Motion>", self._on_drag_fname)
        self.drag_fname.bind("<ButtonRelease-1>", self._on_release_fname)

        self.hdr_type = ctk.CTkLabel(hdr, text="Type",     width=78,  anchor="center", text_color="#9ca3af", font=("Segoe UI", 12, "bold"))
        self.hdr_type.pack(side="left", padx=6)
        
        # Drag handle 2
        self.drag_type = ctk.CTkFrame(hdr, width=4, height=24, fg_color="transparent", cursor="sb_h_double_arrow")
        self.drag_type.pack(side="left")
        self.drag_type.bind("<ButtonPress-1>", self._on_press_type)
        self.drag_type.bind("<B1-Motion>", self._on_drag_type)
        self.drag_type.bind("<ButtonRelease-1>", self._on_release_type)

        self.hdr_status = ctk.CTkLabel(hdr, text="Status",   width=114, anchor="w", text_color="#9ca3af", font=("Segoe UI", 12, "bold"))
        self.hdr_status.pack(side="left", padx=0)

        # Scrollable queue list
        self.queue_frame = ctk.CTkScrollableFrame(tab, fg_color="#111827")
        self.queue_frame.grid(row=2, column=0, padx=6, pady=(0, 6), sticky="nsew")

        # Drop-zone label (shown when empty)
        self.lbl_drop = ctk.CTkLabel(
            self.queue_frame,
            text="Drop .fs or .txt shader files here, or use 'Add Files' / 'Add Folder'",
            text_color="#4b5563", font=("Arial", 13))
        self.lbl_drop.pack(pady=40)

        # Wire up drag-and-drop
        if _DND_AVAILABLE:
            self.queue_frame.drop_target_register(DND_FILES)
            self.queue_frame.dnd_bind("<<Drop>>", self._on_drop)
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
        self.frame_params = ctk.CTkFrame(self.panes)
        self.panes.add(self.frame_params, stretch="never", minsize=180)

        ctk.CTkLabel(self.frame_params, text="Detected Parameters",
                     font=("Arial", 13, "bold")).pack(anchor="w", padx=10, pady=5)
        self.scroll_params = ctk.CTkScrollableFrame(self.frame_params)
        self.scroll_params.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.label_no_params = ctk.CTkLabel(
            self.scroll_params,
            text="Click 'Analyze Code' to detect globals...", text_color="gray")
        self.label_no_params.pack(pady=10)

        # Set initial 80/20 split after rendering
        self.after(200, self._set_initial_sash)

    def _set_initial_sash(self):
        """Set the initial horizontal split (exactly 80/20) for the Single File tab."""
        try:
            self.update() # Force layout calculation
            w = self.panes.winfo_width()
            if w > 200:
                self.panes.sash_place(0, int(w * 0.80), 0)
        except Exception:
            pass

    def _on_code_focus(self, event):
        if self.textbox_code.get("1.0", "end-1c").strip() == "// Paste your shader code here...":
            self.textbox_code.delete("1.0", "end")

    # -----------------------------------------------------------------------
    # Shared log helper
    # -----------------------------------------------------------------------
    def log(self, text: str):
        self.textbox_log.insert("end", f"> {text}\n")
        self.textbox_log.see("end")

    def _gui_log(self, msg: str):
        self.after(0, lambda m=msg: self.log(m))

    # -----------------------------------------------------------------------
    # Queue management
    # -----------------------------------------------------------------------
    def _add_paths(self, paths: list[str]):
        """Add a list of file paths to the queue (dedup by path)."""
        existing = {item.path for item in self._queue}
        added = 0
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
            added += 1
        if added:
            self.lbl_drop.pack_forget()
            self.log(f"Added {added} file(s) to queue. Total: {len(self._queue)}")

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

    def _clear_completed(self):
        """Remove only successfully built items from the queue."""
        to_remove = [item for item in self._queue if item.status == "done"]
        for item in to_remove:
            if item.row_frame:
                item.row_frame.destroy()
            self._queue.remove(item)
        if not self._queue:
            self.lbl_drop.pack(pady=40)
        self.log(f"Cleared {len(to_remove)} completed item(s). Remaining: {len(self._queue)}")

    def _clear_queue(self):
        for item in self._queue:
            if item.row_frame:
                item.row_frame.destroy()
        self._queue.clear()
        self.lbl_drop.pack(pady=40)
        self.log("Queue cleared.")

    def _add_queue_row(self, item: QueueItem):
        """Render one row in the queue list."""
        idx = len(self._queue)

        row = ctk.CTkFrame(self.queue_frame, fg_color="#1a2030",
                           corner_radius=6, height=34)
        row.pack(fill="x", padx=4, pady=2)
        row.pack_propagate(False)
        item.row_frame = row


        # Index
        ctk.CTkLabel(row, text=f"{idx:>2}", width=28,
                     font=("Segoe UI", 12), text_color="#6b7280").pack(side="left", padx=(10, 4))

        # Filename (truncated)
        fname_lbl = ctk.CTkLabel(row, text=self._truncate_fname(item.fname, self.hdr_fname.cget("width")), 
                                 width=self.hdr_fname.cget("width"), anchor="w", font=("Segoe UI", 13))
        fname_lbl.pack(side="left")
        item.lbl_fname = fname_lbl

        # Spacer to align with header drag handle
        ctk.CTkFrame(row, width=4, height=24, fg_color="transparent").pack(side="left")

        # Type badge
        fmt_short = item.fmt
        if item.fmt.endswith(" FX") or item.fmt.endswith(" Mix"):
            fmt_color = "#0d9488"   # teal
        elif item.fmt.startswith("ISF"):
            fmt_color = "#2563eb"
        elif item.fmt.startswith("GLSL"):
            fmt_color = "#ea580c"   # orange
        elif item.fmt == "?":
            fmt_color = "#6b7280"
        else:
            fmt_color = "#7c3aed"   # purple

        type_lbl = ctk.CTkLabel(row, text=f" {fmt_short} ", fg_color=fmt_color,
                     corner_radius=4, text_color="white",
                     font=("Segoe UI", 11, "bold"), width=self.hdr_type.cget("width"))
        type_lbl.pack(side="left", padx=6)
        item.lbl_type = type_lbl

        # Spacer to align with header drag handle
        ctk.CTkFrame(row, width=4, height=24, fg_color="transparent").pack(side="left")

        # Status (icon + text)
        icon_lbl = ctk.CTkLabel(row, text=STATUS_PENDING[0], width=22,
                                font=("Arial", 13), text_color=STATUS_PENDING[1])
        icon_lbl.pack(side="left")
        status_lbl = ctk.CTkLabel(row, text="Pending", width=90, anchor="w",
                                  font=("Segoe UI", 12), text_color=STATUS_PENDING[1])
        status_lbl.pack(side="left", padx=(2, 0))

        item.lbl_icon   = icon_lbl
        item.lbl_status = status_lbl

        # Remove button
        def _remove_self(it=item):
            it.row_frame.destroy()
            if it in self._queue:
                self._queue.remove(it)
            if not self._queue:
                self.lbl_drop.pack(pady=40)
        ctk.CTkButton(row, text="✕", width=28, height=24,
                      fg_color="transparent", hover_color="#374151",
                      command=_remove_self).pack(side="right", padx=4)

    def _set_item_status(self, item: QueueItem, status: str, text: str = ""):
        icons = {
            "pending":  STATUS_PENDING,
            "building": STATUS_BUILDING,
            "done":     STATUS_DONE,
            "error":    STATUS_ERROR,
        }
        icon_char, color = icons.get(status, STATUS_PENDING)
        label = text or status.capitalize()
        def _update():
            if item.lbl_icon:
                item.lbl_icon.configure(text=icon_char, text_color=color)
            if item.lbl_status:
                item.lbl_status.configure(text=label, text_color=color)
        self.after(0, _update)

    # -----------------------------------------------------------------------
    # Column Resizing Logic
    # -----------------------------------------------------------------------
    def _truncate_fname(self, text: str, width: int) -> str:
        # Approximate width for Segoe UI 13 is ~7.5 pixels per char
        max_chars = max(5, int(width / 7.5))
        if len(text) > max_chars:
            return text[:max_chars - 1] + "…"
        return text

    def _on_press_fname(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_w = self.hdr_fname.cget("width")

    def _on_drag_fname(self, event):
        delta = event.x_root - self._drag_start_x
        new_width = max(100, self._drag_start_w + delta)
        self.hdr_fname.configure(width=new_width)

    def _on_release_fname(self, event):
        new_width = self.hdr_fname.cget("width")
        for item in self._queue:
            if hasattr(item, "lbl_fname"):
                item.lbl_fname.configure(width=new_width, text=self._truncate_fname(item.fname, new_width))

    def _on_press_type(self, event):
        self._drag_start_x_type = event.x_root
        self._drag_start_w_type = self.hdr_type.cget("width")

    def _on_drag_type(self, event):
        delta = event.x_root - self._drag_start_x_type
        new_width = max(60, self._drag_start_w_type + delta)
        self.hdr_type.configure(width=new_width)

    def _on_release_type(self, event):
        new_width = self.hdr_type.cget("width")
        for item in self._queue:
            if hasattr(item, "lbl_type"):
                item.lbl_type.configure(width=new_width)

    # -----------------------------------------------------------------------
    # Batch build
    # -----------------------------------------------------------------------
    def _start_build_queue(self):
        if self._building:
            self._cancel_event.set()
            self.btn_build_queue.configure(state="disabled", text="Cancelling…")
            self._gui_log("── Cancel requested... ──")
            return
            
        pending = [i for i in self._queue if i.status in ("pending", "error")]
        if not pending:
            self.log("Nothing to build (all items are done or queue is empty).")
            return
            
        self._building = True
        self._cancel_event.clear()
        self.btn_build_queue.configure(text="Cancel Build", fg_color="#ef4444", hover_color="#dc2626")
        t = threading.Thread(target=self._build_queue_thread, args=(pending,), daemon=True)
        t.start()

    def _build_queue_thread(self, items: list[QueueItem]):
        output_dir = ffpaths.default_output_dir()

        ok = err = 0
        was_cancelled = False
        visible_names = set()

        for item in items:
            if self._cancel_event.is_set():
                was_cancelled = True
                break

            item.status = "building"
            self._set_item_status(item, "building", "Building…")
            self._gui_log(f"[{item.fname}] Starting…")

            try:
                code = open(item.path, encoding="utf-8", errors="replace").read()
                suffix = "-p" if self.extract_params_var.get() else ""
                name = build_ffgl.unique_plugin_name(item.name + suffix, visible_names)
                status, text = self._convert_and_build(code, name, item.path, output_dir)
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
        self.after(0, lambda: self.btn_build_queue.configure(
            state="normal", text="▶  Build Queue", fg_color="#6366f1", hover_color="#4f46e5"))

    # -----------------------------------------------------------------------
    # Single-file tab methods (unchanged from original)
    # -----------------------------------------------------------------------
    def _convert_and_build(self, code, name, path, output_dir):
        """Shared by queue and single-file builds. Returns (status, label)."""
        log = self._gui_log
        try:
            res = pipeline.convert_ffgl(code, name=name, path=path,
                                        extract_params=self.extract_params_var.get())
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

    def analyze_code(self):
        self.log("Analyzing shader code...")
        code = self.textbox_code.get("1.0", "end-1c")

        if not self.entry_plugin_name.get().strip():
            self.entry_plugin_name.delete(0, "end")
            self.entry_plugin_name.insert(0, "FFMakerPlugin")

        try:
            res = pipeline.convert_ffgl(code, name=self.entry_plugin_name.get().strip(),
                                        path=getattr(self, "_source_path", None),
                                        extract_params=self.extract_params_var.get())
        except ffconvert.ConvertError as e:
            self.log(f"ERROR: {e}")
            return
        ir = res.ir
        self.log(f"Detected: {ir.dialect} {ir.kind}")
        for w in ir.warnings:
            self.log(f"WARNING: {w}")
        if res.demoted:
            self.log(f"Kept as constants (would not compile as sliders): {', '.join(res.demoted)}")
        if not res.ok:
            self.log("Shader does not compile:")
            for ln, msg in res.errors[:8]:
                self.log(f"  line {ln}: {msg}")
        elif res.validated:
            self.log("✓ Shader compiles on this GPU.")

        # Rebuild the params panel
        self.label_no_params.pack_forget()
        for widget in self.scroll_params.winfo_children():
            if widget != self.label_no_params:
                widget.destroy()

        promoted = [p for p in ir.params if p.origin in ("const", "define")]
        self.log(f"Found {len(ir.params)} controllable parameter(s).")
        if promoted:
            self.log(f"  [{len(promoted)} auto-detected from constants]")

        for p in ir.params:
            row = ctk.CTkFrame(self.scroll_params, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=1)
            ctk.CTkLabel(row, text=p.display(), anchor="w").pack(side="left")
            kind = p.kind
            if p.kind in ("float", "int", "speed") and p.min is not None:
                kind += f" {p.min:g}–{p.max:g}"
            ctk.CTkLabel(row, text=kind, text_color="#60a5fa", anchor="w").pack(side="left", padx=(6, 0))
            if p.origin in ("const", "define"):
                ctk.CTkLabel(row, text="[const]", text_color="#9ca3af",
                             font=("Consolas", 11)).pack(side="left", padx=(6, 0))

    def _build_single(self):
        self.log("Starting build…")
        self.btn_build_single.configure(state="disabled")
        code = self.textbox_code.get("1.0", "end-1c")
        name = self.entry_plugin_name.get().strip() or "FFMakerPlugin"
        path = getattr(self, "_source_path", None)

        def run():
            try:
                self._cancel_event.clear()
                self._convert_and_build(code, name, path, ffpaths.default_output_dir())
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

    def _load_file_path(self, path: str):
        """Helper to load a file into the Single File editor and analyze it."""
        try:
            code = open(path, encoding="utf-8").read()
            self.textbox_code.delete("1.0", "end")
            self.textbox_code.insert("1.0", code)
            
            # Update output name entry
            self.entry_plugin_name.delete(0, "end")
            self.entry_plugin_name.insert(0, Path(path).stem)

            self._source_stem = Path(path).stem
            self._source_path = path
            self.log(f"Loaded: {Path(path).name} (will export as {self.entry_plugin_name.get()}.dll)")
            self.analyze_code()
        except Exception as e:
            self.log(f"Error reading file: {e}")


    # -----------------------------------------------------------------------
    # ISF Export
    # -----------------------------------------------------------------------
    def _isf_text(self, code, name, path):
        """Returns (text, note) or raises."""
        res = pipeline.convert_ffgl(code, name=name, path=path,
                                    extract_params=self.extract_params_var.get())
        if res.ir.dialect == "isf":
            return code, "already ISF, copied unchanged"
        if not res.ok:
            raise RuntimeError("shader does not compile: " +
                               "; ".join(f"line {l}: {m}" for l, m in res.errors[:3]))
        return emit_isf.emit(res.ir), f"{len(res.ir.params)} inputs"

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
            text, note = self._isf_text(code, name, getattr(self, "_source_path", None))
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(text)
            self.log(f"✓ Exported ISF to {save_path} ({note})")
        except Exception as exc:
            self.log(f"ERROR: Export failed: {exc}")

    def _start_export_isf_queue(self):
        items = [i for i in self._queue if i.status in ("pending", "done", "error")]
        if not items:
            self.log("Nothing to export.")
            return
        out_dir = ctk.filedialog.askdirectory(title="Select folder for ISF exports")
        if not out_dir:
            return

        self.log(f"Exporting {len(items)} items to ISF...")
        ok = 0
        suffix = "-p" if self.extract_params_var.get() else ""
        for item in items:
            try:
                code = open(item.path, encoding="utf-8", errors="replace").read()
                text, note = self._isf_text(code, item.name, item.path)
                out_path = os.path.join(out_dir, f"{item.name}{suffix}.fs")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.log(f"  [{item.fname}] ✓ {note}")
                ok += 1
            except Exception as exc:
                self.log(f"  [{item.fname}] Export failed: {exc}")

        self.log(f"✓ ISF Export complete: {ok}/{len(items)} successful.")

if __name__ == "__main__":
    app = FFMakerApp()
    app.mainloop()

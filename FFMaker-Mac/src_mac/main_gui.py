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
from builder import build_plugin
from paths import get_resource_path


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

VALID_EXTENSIONS = {".fs", ".txt", ".glsl"}


# ---------------------------------------------------------------------------
# Auto-detect shader format from path or content
# ---------------------------------------------------------------------------
def detect_format(path: str = None, code: str = None) -> str:
    # 1. Peak at code for characteristic headers
    if not code and path:
        try:
            # Only read the first 2KB for detection
            code = open(path, encoding="utf-8", errors="replace").read(2000)
        except Exception:
            pass

    if code:
        if "/*{" in code or "/*\n{" in code or "/* {" in code:
            # Peek inside the ISF JSON header to distinguish FX from Source
            import re, json
            m = re.search(r'/\*\s*\{(.*?)\}\s*\*/', code, re.DOTALL)
            if m:
                try:
                    hdr = json.loads("{" + m.group(1) + "}")
                    inputs = hdr.get("INPUTS", [])
                    cats   = [c.lower() for c in hdr.get("CATEGORIES", [])]
                    has_image = any(i.get("TYPE", "").lower() == "image" for i in inputs)
                    is_filter = any(c in cats for c in ("filter", "transition", "distortion", "blur", "stylize", "color effect"))
                    if has_image or is_filter:
                        return "ISF FX"
                except Exception:
                    pass
            return "ISF (.fs)"
        if "uniform float time;" in code and "uniform vec2 resolution;" in code:
            return "GLSL Sandbox"
        if "void mainImage" in code:
            return "Shadertoy"

    # 2. Fallback based on extension
    if path:
        ext = Path(path).suffix.lower()
        if ext == ".fs":
            return "ISF (.fs)"
        if ext == ".txt":
            return "Shadertoy"

    return "ISF (.fs)"  # Default fallback


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

        # Force dark background regardless of TkinterDnD vs CTk base class
        self.configure(bg="#1a1a2e")

        self._build_layout()

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
        ctk.CTkButton(toolbar, text="✕ Remove Selected", width=140,
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._remove_selected).pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar, text="Clear All", width=90,
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._clear_queue).pack(side="left", padx=(0, 20))

        self.btn_build_queue = ctk.CTkButton(
            toolbar, text="▶  Build Queue", width=140,
            fg_color="#6366f1", hover_color="#4f46e5",
            command=self._start_build_queue)
        self.btn_build_queue.pack(side="right")

        # Column headers
        hdr = ctk.CTkFrame(tab, fg_color="#1e2230", corner_radius=6)
        hdr.grid(row=1, column=0, padx=6, pady=(0, 2), sticky="ew")
        ctk.CTkLabel(hdr, text="",         width=28).pack(side="left", padx=(10, 0)) # space for checkbox (6) + row padx (4)
        ctk.CTkLabel(hdr, text="#",        width=28,  anchor="center", text_color="#9ca3af", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(2, 4))
        
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
        self.btn_build_single.pack(side="right")

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

    def _remove_selected(self):
        """Remove items whose checkbox is checked."""
        to_remove = [item for item in self._queue if getattr(item, '_selected', False)]
        if not to_remove:
            # If nothing explicitly selected, remove last item
            to_remove = self._queue[-1:] if self._queue else []
        for item in to_remove:
            if item.row_frame:
                item.row_frame.destroy()
            self._queue.remove(item)
        if not self._queue:
            self.lbl_drop.pack(pady=40)
        self.log(f"Removed {len(to_remove)} item(s). Queue: {len(self._queue)}")

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

        # Checkbox / select
        var = tk.BooleanVar(value=False)
        item._sel_var = var
        item._selected = False
        def _toggle(v=var, it=item):
            it._selected = v.get()
        chk = ctk.CTkCheckBox(row, variable=var, text="", width=28,
                              checkbox_width=16, checkbox_height=16,
                              command=_toggle)
        chk.pack(side="left", padx=(6, 0))

        # Index
        ctk.CTkLabel(row, text=f"{idx:>2}", width=28,
                     font=("Segoe UI", 12), text_color="#6b7280").pack(side="left", padx=(2, 4))

        # Filename (truncated)
        fname_lbl = ctk.CTkLabel(row, text=self._truncate_fname(item.fname, self.hdr_fname.cget("width")), 
                                 width=self.hdr_fname.cget("width"), anchor="w", font=("Segoe UI", 13))
        fname_lbl.pack(side="left")
        item.lbl_fname = fname_lbl

        # Spacer to align with header drag handle
        ctk.CTkFrame(row, width=4, height=24, fg_color="transparent").pack(side="left")

        # Type badge
        if item.fmt == "ISF FX":
            fmt_short = "ISF FX"
            fmt_color = "#0d9488"   # teal
        elif "ISF" in item.fmt:
            fmt_short = "ISF"
            fmt_color = "#2563eb"
        elif "Sandbox" in item.fmt:
            fmt_short = "Sandbox"
            fmt_color = "#ea580c" # orange
        else:
            fmt_short = "Shadertoy"
            fmt_color = "#7c3aed" # purple
            
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
        output_dir = get_resource_path("boilerplates")

        ok = err = 0
        was_cancelled = False

        for item in items:
            if self._cancel_event.is_set():
                was_cancelled = True
                break
                
            item.status = "building"
            self._set_item_status(item, "building", "Building…")
            self._gui_log(f"[{item.fname}] Starting…")

            try:
                code = open(item.path, encoding="utf-8", errors="replace").read()
                from parser import parse_code
                parsed = parse_code(code, item.fmt)

                if "error" in parsed:
                    for line in parsed["error"].splitlines():
                        if line.strip():
                            self._gui_log(f"  ERROR: {line}")
                    item.status = "error"
                    self._set_item_status(item, "error", "Parse error")
                    err += 1
                    continue

                for w in parsed.get("warnings", []):
                    self._gui_log(f"  WARN: {w}")

                res = build_plugin(parsed, output_dir,
                                   log_callback=self._gui_log,
                                   plugin_name=item.name,
                                   cancel_event=self._cancel_event)

                if res and res.get("status") == "cancelled":
                    item.status = "pending"
                    self._set_item_status(item, "pending", "Pending")
                    self._gui_log(f"[{item.fname}] Cancelled.")
                    was_cancelled = True
                    break
                elif res and res.get("status") == "success":
                    dll = res.get("dll_name", f"{item.name}.dll")
                    item.status = "done"
                    self._set_item_status(item, "done", dll)
                    self._gui_log(f"[{item.fname}] ✓ Done → {dll}")
                    ok += 1
                else:
                    item.status = "error"
                    self._set_item_status(item, "error", "Build failed")
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
    def analyze_code(self):
        self.log("Analyzing shader code...")
        code = self.textbox_code.get("1.0", "end-1c")

        # If name entry is empty, populate a generic name
        if not self.entry_plugin_name.get().strip():
            self.entry_plugin_name.delete(0, "end")
            self.entry_plugin_name.insert(0, "FFMakerPlugin")

        fmt  = detect_format(code=code)
        self.log(f"Auto-detected format: {fmt}")

        from parser import parse_code
        result = parse_code(code, fmt)

        if "error" in result:
            for line in result["error"].splitlines():
                self.log(f"ERROR: {line}" if line.strip() else "")
            return

        for w in result.get("warnings", []):
            self.log(f"WARNING: {w}")

        # Rebuild the params panel
        self.label_no_params.pack_forget()
        for widget in self.scroll_params.winfo_children():
            if widget != self.label_no_params:
                widget.destroy()

        inputs = result.get("inputs", [])
        user_inputs  = [i for i in inputs if not i.get("_builtin")]
        const_inputs = [i for i in user_inputs if i.get("_source") == "const_extract"]

        self.log(f"Found {len(user_inputs)} controllable parameter(s).")
        if const_inputs:
            self.log(f"  [{len(const_inputs)} auto-detected from const declarations]")

        for inp in user_inputs:
            name   = inp.get("NAME", "Unknown")
            t      = inp.get("TYPE", "float")
            source = inp.get("_source", "")

            row = ctk.CTkFrame(self.scroll_params, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=1)

            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=t, text_color="#60a5fa", anchor="w").pack(side="left", padx=(6, 0))

            if source == "const_extract":
                ctk.CTkLabel(row, text="[const]", text_color="#9ca3af",
                             font=("Consolas", 11)).pack(side="left", padx=(6, 0))

    def _build_single(self):
        self.log("Starting build…")
        self.btn_build_single.configure(state="disabled")

        def gui_log(msg):
            self.after(0, lambda m=msg: self.log(m))

        def run():
            from parser import parse_code
            code   = self.textbox_code.get("1.0", "end-1c")
            fmt    = detect_format(code=code)
            parsed = parse_code(code, fmt)
            out    = get_resource_path("boilerplates")

            plugin_name = self.entry_plugin_name.get().strip() or "FFMakerPlugin"
            res = build_plugin(parsed, out, log_callback=gui_log,
                               plugin_name=plugin_name)
            self.after(0, lambda: self.btn_build_single.configure(state="normal"))
            if res and res.get("status") == "success":
                dll = res.get("dll_name", "plugin.dll")
                gui_log(f">> {dll} generated successfully!")

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
            self.log(f"Loaded: {Path(path).name} (will export as {self.entry_plugin_name.get()}.dll)")
            self.analyze_code()
        except Exception as e:
            self.log(f"Error reading file: {e}")


if __name__ == "__main__":
    app = FFMakerApp()
    app.mainloop()

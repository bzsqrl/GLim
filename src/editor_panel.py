"""Right-hand panel of the Studio tab: live preview, channel sources and
the parameter editor. Edits are written into a settings dict (the shader's
.ffmaker.json); changes that alter the GLSL ask the app to recompile."""
import math
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser

import customtkinter as ctk
from PIL import Image, ImageTk

from ffmaker import settings as S

import fast_widgets as W

PREVIEW_W, PREVIEW_H = 384, 216
SMALL_FPS_WITH_OUTPUT = 10      # small preview rate while the output window draws the full one
AUTO_SECONDS = 10.0             # slideshow: default time each queue shader shows
AUTO_MIN_SECONDS = 1.0
GPU_REFRESH_S = 0.25            # live GPU readout update interval (output open)
GPU_SAMPLE_S = 1.0              # Analyze with the output open (Live off): time the output this long
LIVE_RUN_S = 0.5                # Live, output closed: length of each measuring run (a reading each)
LOAD_COLOURS = ("#22c55e", "#f59e0b", "#ef4444")   # GPU load: light / heavy / over a 60 fps frame
CHANNEL_CHOICES = ["input", "noise", "audio", "none", "file…"]
FILTER_CHOICES = ["filter", "nearest", "linear", "mipmap"]   # first entry = Shadertoy default
WRAP_CHOICES = ["wrap", "clamp", "repeat"]


def gpu_cache_key(res, values=None):
    """Key for a GPU measurement: the converted GLSL plus the param values it ran
    with (the defaults when values is None), so the queue's measurements and the
    Studio tab's share results."""
    if values is None:
        values = {i: p.default for i, p in enumerate(res.ir.params)}
    return (tuple(res.ffgl_glsl), repr(sorted(values.items())))


TOGGLE_GUARD_S = 0.3            # a toggle button ignores a second click this soon after one


def toggle_command(command):
    """For on/off buttons: ignore a second click within TOGGLE_GUARD_S, so a quick
    double click (or a bounce) doesn't switch something on and straight off again.
    (← / → and other one-shot buttons count every click.)"""
    last = [0.0]

    def run():
        now = time.perf_counter()
        if now - last[0] >= TOGGLE_GUARD_S:
            last[0] = now
            command()
    return run


def _tk_bg(widget):
    """The colour a CustomTkinter frame actually shows (for plain Tk children)."""
    return tk.Frame.cget(widget, "bg")


class EditorPanel(ctk.CTkFrame):
    def __init__(self, master, on_recompile, log):
        super().__init__(master)
        W.setup(self)
        self.on_recompile = on_recompile      # callback: settings changed in a way that needs a rebuild
        self.log = log
        self.settings = {}
        self.shader_path = None
        self.res = None
        self.previewer = None
        self.playing = True
        self.sim_time = 0.0
        self.last_tick = None
        self._photo = None
        self._input_image = None              # (w, h, rgba) for effect previews
        self._fs = None                       # fullscreen state, see "Fullscreen" below
        # Set by the app: the queue's file paths, a function converting one for
        # preview, and on_select(path, res), which loads a converted queue file
        # into the Studio tab (the output then follows, see load()).
        self.get_playlist = lambda: []
        self.convert_path = None
        self.on_select = None
        self._queue_label_tick = 0
        self._small_visible = False         # main thread → output thread: draw the small preview
        self.gpu_cache = {}                 # gpu_cache_key → benchmark result (shared with the queue)
        self._bench_gen = 0                 # bumped to cancel a running measurement
        self._gpu_shown = 0.0
        self.gpu_live = False               # Live: time the preview (at 1080p) or the output, continuously
        self._live_visible = False          # main thread → Live's measuring thread: the preview is showing

        # Two columns: preview + channels on the left, parameters on the right.
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, 4))
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # ── Preview ──
        self.preview = tk.Label(left, bg="#000000", width=PREVIEW_W, height=PREVIEW_H)
        self.preview.pack(padx=8, pady=(8, 4))
        transport = ctk.CTkFrame(left, fg_color="transparent")
        transport.pack(fill="x", padx=8)
        self.btn_play = ctk.CTkButton(transport, text="⏸", width=36, command=toggle_command(self._toggle_play))
        self.btn_play.pack(side="left")
        ctk.CTkButton(transport, text="⟲", width=36, command=self.restart).pack(side="left", padx=4)
        # ⧉ (a window over a window): the output window; ⛶: fullscreen.
        self.btn_output = ctk.CTkButton(transport, text="⧉", width=36, command=toggle_command(self.open_output_window))
        self.btn_output.pack(side="left")
        self.btn_fullscreen = ctk.CTkButton(transport, text="⛶", width=36,
                                            command=toggle_command(self._toggle_fullscreen))
        self.btn_fullscreen.pack(side="left", padx=(4, 0))
        self._output_btn_colors = (self.btn_output.cget("fg_color"), self.btn_output.cget("hover_color"))
        self._output_btn_open = False
        self._fullscreen_btn_on = False
        self.preview.bind("<Double-Button-1>", lambda e: self._toggle_fullscreen())
        # Esc in FFStudio also leaves fullscreen (e.g. with the output on another monitor).
        top = self.winfo_toplevel()
        top.bind("<Escape>", lambda e: self._escape_output(), add="+")
        # Ctrl+F (⌘F on macOS) toggles fullscreen while the Studio tab is showing.
        mod = "Command" if sys.platform == "darwin" else "Control"
        for key in ("f", "F"):
            top.bind(f"<{mod}-{key}>", self._toggle_fullscreen, add="+")
        self.lbl_time = ctk.CTkLabel(transport, text="", width=70, anchor="w", text_color="#9ca3af")
        self.lbl_time.pack(side="left", padx=4)
        self.input_menu = ctk.CTkOptionMenu(transport, values=["Test pattern", "Load image…"],
                                            width=130, command=self._input_choice)
        self.input_menu.pack(side="right")
        # Previous / next shader in the queue (also ← / → in the output window).
        queue_nav = ctk.CTkFrame(left, fg_color="transparent")
        queue_nav.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkButton(queue_nav, text="←", width=36, command=lambda: self.step_queue(-1)).pack(side="left")
        ctk.CTkButton(queue_nav, text="→", width=36, command=lambda: self.step_queue(1)).pack(side="left", padx=4)
        # Slideshow: Auto steps to the next shader every N seconds, looping the queue.
        self.btn_auto = ctk.CTkButton(queue_nav, text="Auto", width=50, command=toggle_command(self._toggle_auto))
        self.btn_auto.pack(side="left")
        self._auto_btn_colors = (self.btn_auto.cget("fg_color"), self.btn_auto.cget("hover_color"))
        self.auto_seconds = AUTO_SECONDS
        self.entry_auto = ctk.CTkEntry(queue_nav, width=46, justify="right")
        self.entry_auto.insert(0, self._fmt_seconds(self.auto_seconds))
        self.entry_auto.pack(side="left", padx=(4, 0))
        self.entry_auto.bind("<Return>", self._apply_auto_seconds)
        self.entry_auto.bind("<KP_Enter>", self._apply_auto_seconds)
        self.entry_auto.bind("<FocusOut>", self._apply_auto_seconds)
        ctk.CTkLabel(queue_nav, text="s", text_color="#9ca3af").pack(side="left", padx=(2, 0))
        self.auto = False
        self._auto_elapsed = 0.0                # seconds the current shader has shown (while playing)
        self.lbl_queue = ctk.CTkLabel(queue_nav, text="", anchor="w", text_color="#9ca3af")
        self.lbl_queue.pack(side="left", padx=6)
        # GPU load of the loaded shader (see "GPU load" below).
        gpu_row = ctk.CTkFrame(left, fg_color="transparent")
        gpu_row.pack(fill="x", padx=8, pady=(8, 0))
        bg = _tk_bg(gpu_row)
        W.label(gpu_row, "GPU", fg=W.DIM, bg=bg).pack(side="left")
        self.gpu_bar = tk.Canvas(gpu_row, width=W.px(100), height=W.px(10), bg="#111827",
                                 highlightthickness=0, bd=0)
        self.gpu_bar.pack(side="left", padx=6)
        self.lbl_gpu = W.label(gpu_row, "", bg=bg, anchor="w")
        self.lbl_gpu.pack(side="left")
        self.btn_measure = ctk.CTkButton(gpu_row, text="Analyze", width=70, fg_color="#374151",
                                         hover_color="#4b5563", command=self.measure_gpu)
        self.btn_measure.pack(side="right")
        self._gpu_btn_colors = ("#374151", "#4b5563")
        self.btn_gpu_live = ctk.CTkButton(gpu_row, text="Live", width=50, fg_color=self._gpu_btn_colors[0],
                                          hover_color=self._gpu_btn_colors[1], command=toggle_command(self.toggle_gpu_live))
        self.btn_gpu_live.pack(side="right", padx=(0, 4))
        self.lbl_gpu_detail = W.label(left, "", fg=W.DIM, bg=bg, anchor="w")
        self.lbl_gpu_detail.pack(fill="x", padx=8)

        # ── Channels (Shadertoy) ──
        self.channel_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.channel_frame.pack(fill="x", padx=8, pady=(6, 0))

        # ── Parameters ──
        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkLabel(hdr, text="Parameters", font=("Arial", 13, "bold")).pack(side="left")
        ctk.CTkButton(hdr, text="Save settings", width=110, command=self.save).pack(side="right")
        ctk.CTkButton(hdr, text="Reset", width=60, fg_color="#374151", hover_color="#4b5563",
                      command=self.reset_settings).pack(side="right", padx=4)
        self.params_frame = ctk.CTkScrollableFrame(right)
        self.params_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self._params_bg = _tk_bg(self.params_frame)
        self.lbl_empty = ctk.CTkLabel(self.params_frame, text="Click 'Process Code' to load a shader.",
                                      text_color="gray")
        self.lbl_empty.pack(pady=10)

        self.after(100, self._tick)

    # ── Loading ──────────────────────────────────────────────────────────────
    def load(self, res, settings, shader_path, keep_time=False):
        """Show a pipeline result. `settings` is edited in place."""
        self.res = res
        self.settings = settings
        self.shader_path = shader_path
        self._close_previewer()
        if not keep_time:
            self.sim_time = 0.0
        # Previewer first: it switches the output, which then keeps playing (on its
        # own thread) while the slower parameter widgets are rebuilt.
        if res.ok and res.validated:
            self._open_previewer()
        self._build_channels()
        self._build_params()
        if res.ir.kind in ("effect", "mixer"):
            self.input_menu.pack(side="right")
        else:
            self.input_menu.pack_forget()
        self._auto_elapsed = 0.0            # the slideshow times each shader from its load
        self._gpu_after_load()
        self._update_queue_label()

    def _open_previewer(self):
        try:
            from ffmaker import validate as V
            with V.gpu():
                self.previewer = V.Previewer(self.res.ir, self.res.ffgl_glsl, PREVIEW_W, PREVIEW_H)
                if self._input_image:
                    w, h, px = self._input_image
                    self.previewer.set_input_image(w, h, px, 0)
                    self.previewer.set_input_image(w, h, px, 1)
            for i, p in enumerate(self.res.ir.params):
                self.previewer.values[i] = p.default
        except Exception as e:
            self.previewer = None
            self.log(f"Preview unavailable: {e}")
            return
        self._sync_output()

    def _sync_output(self):
        """The output (fullscreen or output window) always shows the shader loaded
        here: switch it to the new previewer's shader, sharing its slider values."""
        if not self._fs or not self.previewer:
            return
        from ffmaker import validate as V
        view, old = self._fs["view"], self._fs["pv"]
        try:
            with V.gpu():                   # the output thread renders only while holding this
                pv = self._fs_previewer(view, self.res)
                pv.values = self.previewer.values
                self._fs.update(pv=pv, res=self.res, path=self.shader_path)
                self._fs["timer"].reset()    # a new shader: start the average over
                self._fs.pop("gpu", None)
                old.close()
                view.reattach()
        except Exception as e:
            self.log(f"Output stopped: {e}")
            self.exit_fullscreen()

    def _close_previewer(self):
        if self.previewer:
            try:
                from ffmaker import validate as V
                with V.gpu():
                    self.previewer.close()
            except Exception:
                pass
        self.previewer = None

    def restart(self):
        self.sim_time = 0.0
        if self.res:
            self._close_previewer()
            if self.res.ok and self.res.validated:
                self._open_previewer()

    def _toggle_play(self):
        self.playing = not self.playing
        self.btn_play.configure(text="⏸" if self.playing else "▶")

    def _input_choice(self, choice):
        if choice == "Load image…":
            path = ctk.filedialog.askopenfilename(
                title="Preview input image",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tga *.gif *.webp"), ("All", "*.*")])
            if not path:
                self.input_menu.set("Test pattern")
                return
            im = Image.open(path).convert("RGBA")
            im.thumbnail((1024, 1024))
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
            self._input_image = (im.size[0], im.size[1], im.tobytes())
            self.input_menu.set(os.path.basename(path)[:16])
        else:
            self._input_image = None
        self.restart()

    # ── Fullscreen ───────────────────────────────────────────────────────────
    # self._fs = {"view", "pv", "res", "path"} while fullscreen or the output window
    # is open. It always shows the shader loaded in this tab (see _sync_output);
    # Left/Right in it step through the queue (step_queue).

    def _fs_previewer(self, view, res):
        from ffmaker import validate as V
        pv = V.Previewer(res.ir, res.ffgl_glsl, *(view.render_size() or (960, 540)))
        if self._input_image:
            w, h, px = self._input_image
            pv.set_input_image(w, h, px, 0)
            pv.set_input_image(w, h, px, 1)
        return pv

    def enter_fullscreen(self, windowed=False):
        """Show the preview fullscreen on FFStudio's monitor (Esc returns), or with
        windowed=True in an output window that can go fullscreen on another monitor."""
        if self._fs or not self.previewer:
            return
        from ffmaker import validate as V
        top = self.winfo_toplevel()
        near = (top.winfo_rootx() + top.winfo_width() // 2, top.winfo_rooty() + top.winfo_height() // 2)
        view = pv = None
        try:
            with V.gpu():
                view = V.OutputView(near, windowed=windowed)
                pv = self._fs_previewer(view, self.res)
                timer = V.GpuTimer(V.context().gl)
            pv.values = self.previewer.values     # same dict: slider moves show up live
            stop = threading.Event()
            self._fs = {"view": view, "pv": pv, "res": self.res, "path": self.shader_path,
                        "stop": stop, "error": None, "timer": timer}
            self._gpu_after_load()                # Live: the output's own timing from now on
            self._fs["thread"] = threading.Thread(target=self._output_loop, args=(self._fs, stop),
                                                  daemon=True)
            self._fs["thread"].start()
        except Exception as e:
            self.log(f"{'Output window' if windowed else 'Fullscreen'} unavailable: {e}")
            with V.gpu():
                if pv:
                    pv.close()
                if view:
                    view.close()

    def open_output_window(self):
        """The Output button toggles the output window: the live render in its own
        window, which can be moved to another monitor and made fullscreen there
        (double-click or Ctrl+F). A second press closes it, unless it's fullscreen
        (Esc first) or plain fullscreen is showing."""
        if not self._fs:
            self.enter_fullscreen(windowed=True)
        elif self._fs["view"].windowed and not self._fs["view"].fullscreen:
            self.exit_fullscreen()
        self._update_output_button()

    def _update_output_button(self):
        """Highlight ⧉ while the output window is open, and ⛶ while something is
        fullscreen (plain fullscreen, or the output window made fullscreen)."""
        view = self._fs["view"] if self._fs else None
        is_open = bool(view and view.windowed)
        if is_open != self._output_btn_open:
            self._output_btn_open = is_open
            fg, hover = ("#f59e0b", "#d97706") if is_open else self._output_btn_colors
            self.btn_output.configure(fg_color=fg, hover_color=hover)
        full = bool(view and view.fullscreen and not view.closed)
        if full != self._fullscreen_btn_on:
            self._fullscreen_btn_on = full
            fg, hover = ("#f59e0b", "#d97706") if full else self._output_btn_colors
            self.btn_fullscreen.configure(fg_color=fg, hover_color=hover)

    def _escape_output(self):
        """Esc in FFStudio: the output window leaves fullscreen; plain fullscreen closes."""
        if self._fs:
            from ffmaker import validate as V
            with V.window_lock():
                self._fs["view"].escape()

    # ── Queue playlist ───────────────────────────────────────────────────────
    def step_queue(self, direction):
        """Load the previous / next shader in the queue that compiles into this tab
        (the output follows). Wraps around; starts at either end if the current
        shader isn't in the queue. The ← / → buttons and the output's arrow keys."""
        paths = self.get_playlist()
        self._update_queue_label()
        if not paths:
            self.log("The queue is empty: add shaders on the Queue tab to step through them.")
            return
        cur = self.shader_path
        i = paths.index(cur) if cur in paths else (-1 if direction > 0 else len(paths))
        for _ in range(len(paths)):
            i = (i + direction) % len(paths)
            path = paths[i]
            if path == cur:
                break                       # went all the way round
            name = os.path.basename(path)
            try:
                res = self.convert_path(path)
            except Exception as e:
                self.log(f"Queue: skipped {name} ({e})")
                continue
            if not (res.ok and res.validated):
                self.log(f"Queue: skipped {name} (doesn't compile)")
                continue
            self.log(f"▶ {name} ({i + 1}/{len(paths)})")
            self.on_select(path, res)       # loads it here, from the start; the output follows
            return
        self.log("No other shader in the queue compiles.")

    def _update_queue_label(self):
        paths = self.get_playlist()
        if not paths:
            text = "queue empty"
        elif self.shader_path in paths:
            text = f"{paths.index(self.shader_path) + 1} / {len(paths)}"
        else:
            text = f"not in queue ({len(paths)})"
        if self.auto and paths:
            left = max(0, math.ceil(self.auto_seconds - self._auto_elapsed))
            text += f" · next in {left}s" if self.playing else " · paused"
        if text != self.lbl_queue.cget("text"):
            self.lbl_queue.configure(text=text)

    # ── Slideshow ────────────────────────────────────────────────────────────
    # Auto: every auto_seconds of playing time, step to the next shader in the
    # queue (step_queue wraps from the last back to the first). Pausing the
    # preview holds the countdown; a manual ← / → restarts it.

    def _toggle_auto(self):
        self._apply_auto_seconds()
        if not self.auto and not self.get_playlist():
            self.log("The queue is empty: add shaders on the Queue tab for the slideshow.")
            return
        self.auto = not self.auto
        self._auto_elapsed = 0.0
        fg, hover = ("#f59e0b", "#d97706") if self.auto else self._auto_btn_colors
        self.btn_auto.configure(fg_color=fg, hover_color=hover)
        if self.auto:
            self.log(f"Slideshow on: next shader every {self._fmt_seconds(self.auto_seconds)} s.")
        self._update_queue_label()

    @staticmethod
    def _fmt_seconds(s):
        return f"{s:g}"

    def _apply_auto_seconds(self, _e=None):
        """Read the seconds entry; an invalid value reverts to the current one."""
        try:
            s = float(self.entry_auto.get().strip().rstrip("s"))
            if not math.isfinite(s):
                raise ValueError
            self.auto_seconds = max(AUTO_MIN_SECONDS, s)
        except ValueError:
            pass
        self.entry_auto.delete(0, "end")
        self.entry_auto.insert(0, self._fmt_seconds(self.auto_seconds))
        self._update_queue_label()
        if _e is not None and _e.keysym in ("Return", "KP_Enter"):
            self.winfo_toplevel().focus_set()     # done editing: keys go back to the app
            return "break"

    def _tick_auto(self, dt):
        if not self.auto:
            return
        if not self.get_playlist():
            self._toggle_auto()                 # queue cleared: stop
            return
        if self.playing and self.res:
            self._auto_elapsed += dt
        if self._auto_elapsed >= self.auto_seconds:
            self._auto_elapsed = 0.0           # also if nothing else compiles: try again later
            if self.get_playlist() != [self.shader_path]:   # a one-shader queue just stays
                self.step_queue(1)
        self._update_queue_label()

    def _toggle_fullscreen(self, _e=None):
        """⛶, Ctrl+F, double-click: with the output window open, toggle its
        fullscreen; otherwise open / close fullscreen on FFStudio's monitor."""
        if self._fs:
            from ffmaker import validate as V
            with V.window_lock():
                self._fs["view"].toggle()      # plain fullscreen: marks it closed
        elif self.winfo_viewable():         # only from the Studio tab
            self.enter_fullscreen()
        else:
            return None
        return "break"

    def exit_fullscreen(self):
        """Close fullscreen / the output window. (It always shows the shader loaded
        here, so nothing needs reloading.)"""
        if not self._fs:
            return
        fs, self._fs = self._fs, None
        fs["stop"].set()
        fs["thread"].join(timeout=2)
        try:
            from ffmaker import validate as V
            with V.gpu():
                fs["timer"].close()
                fs["pv"].close()
                fs["view"].close()
        except Exception:
            pass
        try:
            self.winfo_toplevel().focus_force()
        except tk.TclError:
            pass
        if self.res:
            self._gpu_after_load()             # back to the 1080p measurement

    # ── Render loop ──────────────────────────────────────────────────────────
    def _tick(self):
        now = time.perf_counter()
        dt = 0.0 if self.last_tick is None else min(now - self.last_tick, 0.25)
        self.last_tick = now
        self._queue_label_tick += 1
        if self._queue_label_tick % 30 == 0:       # the queue can change on the other tab
            self._update_queue_label()
        self._update_output_button()               # the output can also close from its own window
        self._tick_auto(dt)
        if self._fs:
            # The output draws itself on its own thread (and advances the clock), along
            # with the small preview at a lower rate (SMALL_FPS_WITH_OUTPUT); here: its
            # events and keys, and showing the small preview's pixels.
            self._small_visible = bool(self.previewer) and self.winfo_ismapped()
            self._tick_output()
            px = self._fs.pop("small_px", None) if self._fs else None
            if px:
                self._show_small(px)
            self.after(15, self._tick)
            return
        self._live_visible = self.winfo_viewable()      # Live measures only while it's seen
        self._draw_small(dt)
        self.after(33, self._tick)

    def _draw_small(self, dt):
        """Render the small preview (while the output is closed)."""
        if not (self.previewer and self.winfo_ismapped()):
            return
        try:
            from ffmaker import validate as V
            speed = self._speed()
            if self.playing:
                self.sim_time += dt * speed
            with V.gpu():
                self.previewer.render_frame(self.sim_time, min(dt, 0.25) * speed if self.playing else 0.0)
                px = self.previewer.read()
        except Exception as e:
            self.log(f"Preview stopped: {e}")
            self._close_previewer()
            return
        self._show_small(px)

    def _show_small(self, px):
        try:
            img = Image.frombytes("RGBA", (PREVIEW_W, PREVIEW_H), px).transpose(Image.FLIP_TOP_BOTTOM)
            bg = Image.new("RGBA", img.size, (24, 24, 24, 255))   # show transparency as dark grey
            img = Image.alpha_composite(bg, img).convert("RGB")
            if self._photo is None:
                self._photo = ImageTk.PhotoImage(img)
                self.preview.configure(image=self._photo, width=PREVIEW_W, height=PREVIEW_H)
            else:
                self._photo.paste(img)
            self.lbl_time.configure(text=f"{self.sim_time:6.1f}s")
        except Exception as e:
            self.log(f"Preview stopped: {e}")
            self._close_previewer()

    def _render_small_for_output(self, fs, dt):
        """Output thread, inside gpu(): render the small preview too, and leave its
        pixels for the main thread to show (which then needn't wait for the GPU)."""
        pv = self.previewer
        if not (self._small_visible and pv and pv.progs):     # closed: being replaced
            return
        try:
            speed = next((float(pv.values.get(i, p.default)) for i, p in enumerate(pv.ir.params)
                          if p.kind == "speed"), 1.0)      # pv's own params (self.res may be newer)
            pv.render_frame(self.sim_time, dt * speed if self.playing else 0.0)
            fs["small_px"] = pv.read()
        except Exception:
            self._small_visible = False

    def _speed(self, res=None, pv=None):
        res, pv = res or self.res, pv or self.previewer
        for i, p in enumerate(res.ir.params):
            if p.kind == "speed":
                return float(pv.values.get(i, p.default))
        return 1.0

    def _tick_output(self):
        """Main thread, while the output is open: its window events (GLFW requires
        the main thread for them), Left/Right, and the time readout. The small
        preview pauses meanwhile."""
        fs = self._fs
        if fs["error"]:
            self.log(f"Output stopped: {fs['error']}")
            self.exit_fullscreen()
            return
        try:
            # Window events can resize the window or switch it to fullscreen, which on
            # macOS mustn't overlap a frame being drawn on the output thread.
            from ffmaker import validate as V
            with V.window_lock():
                alive = fs["view"].poll()
        except Exception as e:
            self.log(f"Output stopped: {e}")
            self.exit_fullscreen()
            return
        if not alive:
            self.exit_fullscreen()
            return
        view = fs["view"]
        if view.nav:
            direction, view.nav = view.nav, 0
            self.step_queue(direction)
        self.lbl_time.configure(text=f"{self.sim_time:6.1f}s")
        now = time.perf_counter()
        until = self._fs.get("sample_until", 0.0) if self._fs else 0.0
        if self._fs and (self.gpu_live or until) and now - self._gpu_shown >= GPU_REFRESH_S:
            self._gpu_shown = now
            ms, size = self._fs.get("gpu") or (None, None)
            if self.gpu_live:
                if ms is not None:
                    self._show_gpu({"ms": ms, "size": size}, "live in the output")
            elif now >= until:                  # Analyze's sample is done
                self._fs["sample_until"] = 0.0
                if ms is not None:
                    self._show_gpu({"ms": ms, "size": size}, "measured in the output")
                else:
                    self._show_gpu(None, "couldn't measure (no frames drawn)")

    def _output_loop(self, fs, stop):
        """Output thread: render and show frames until stopped. It runs alongside
        the UI, so rebuilding the parameter widgets after a shader switch (up to a
        second for big shaders) doesn't stall the output. Holds gpu() per frame;
        the shader it draws is whatever fs holds (switched under the same lock)."""
        from ffmaker import validate as V
        last = time.perf_counter()
        due = None                          # when the next frame is due, if not paced by vsync
        small_t = 0.0                       # when the small preview was last drawn
        while not stop.is_set():
            start = time.perf_counter()
            dt, last = min(start - last, 0.25), start
            try:
                with V.gpu():
                    if stop.is_set():
                        break
                    view, pv, res = fs["view"], fs["pv"], fs["res"]
                    size = view.render_size()  # follows the window as it's resized / goes fullscreen
                    if size:
                        if size != (pv.width, pv.height):
                            pv.resize(*size)
                            view.reattach()
                        speed = self._speed(res, pv)
                        if self.playing:
                            self.sim_time += dt * speed
                        timing = self.gpu_live or start < fs.get("sample_until", 0.0)
                        if timing:
                            fs["timer"].begin()
                        pv.render_frame(self.sim_time, dt * speed if self.playing else 0.0)
                        if timing:
                            fs["timer"].end()
                            fs["gpu"] = (fs["timer"].ms, (pv.width, pv.height))
                        view.show(pv)          # vsync in the swap paces this loop
                        if start - small_t >= 1 / SMALL_FPS_WITH_OUTPUT:
                            self._render_small_for_output(fs, min(start - small_t, 0.25))
                            small_t = start
            except Exception as e:
                fs["error"] = e
                return
            V.let_waiters_in()              # the UI may be waiting to switch shaders etc.
            # No vsync wait (minimised / hidden window, or a macOS display where the
            # swap doesn't block): pace to the monitor's refresh rate instead, and leave
            # the UI thread time (Python runs one thread at a time). A frame that took
            # over half a refresh already waited for vsync, so it doesn't sleep (sleep
            # overshoots, and would miss the next refresh). Sleeping toward a running
            # deadline keeps those overshoots from adding up.
            frame = 1 / fs["view"].refresh
            now = time.perf_counter()
            if not size:
                time.sleep(0.05)
            elif now - start > frame / 2:
                due = now
            else:
                due = max(due + frame, now - frame) if due else now + frame
                if due > now:
                    time.sleep(due - now)

    # ── GPU load ─────────────────────────────────────────────────────────────
    # How heavy the loaded shader is, as GPU time per frame.
    # Live on: measured continuously, following slider moves and shader switches.
    # With the output closed, by back-to-back 1920x1080 runs on a worker thread
    # (validate.benchmark, ~0.5 s each, a new reading after each). Timing the 30 fps
    # preview itself would read up to 2x high: with so little to do, the GPU lowers
    # its clocks. While the output is open, its own frames are timed
    # (validate.GpuTimer) at its own size.
    # Live off: nothing is measured unless asked, so shader switches (e.g. a
    # slideshow) cost the least. Analyze: a 1920x1080 run (validate.benchmark) with
    # the current slider values, or a 1 s sample of the output while it's open.
    # Results (gpu_cache) are shared with the queue's GPU column and shown again.

    def toggle_gpu_live(self):
        self.gpu_live = not self.gpu_live
        fg, hover = ("#f59e0b", "#d97706") if self.gpu_live else self._gpu_btn_colors
        self.btn_gpu_live.configure(fg_color=fg, hover_color=hover)
        # Live readings are continuous, so Analyze has nothing to add meanwhile.
        self.btn_measure.configure(state="disabled" if self.gpu_live else "normal")
        if self._fs:
            self._fs["timer"].reset()         # start the live average afresh
            self._fs.pop("gpu", None)
        self._gpu_after_load()

    def _measure_live(self):
        """Live on, output closed: measure the loaded shader again and again on a
        worker thread, with the slider values at the start of each run, until the
        shader, Live or the output changes (_bench_gen). Pauses while the preview
        isn't showing (e.g. the Queue tab), so the GPU isn't kept busy for nothing."""
        from ffmaker import validate as V
        gen, res = self._bench_gen, self.res
        live = lambda: gen == self._bench_gen

        def work():
            warm = True
            while live():
                if not self._live_visible:
                    time.sleep(0.2)
                    warm = True                     # the GPU may have clocked down meanwhile
                    continue
                values = self._values()
                try:
                    r = V.benchmark(res.ir, res.ffgl_glsl, values, seconds=LIVE_RUN_S,
                                    warmup_s=0.2 if warm else 0.0, cancel=lambda: not live())
                except Exception as e:
                    self.after(0, lambda e=e: live() and self._show_gpu(None, f"couldn't measure: {e}"))
                    return
                if r is None:
                    return
                warm = False
                self.gpu_cache[gpu_cache_key(res, values)] = r     # still shown after Live is off
                self.after(0, lambda r=r: live() and self._show_gpu(r, "live"))
        threading.Thread(target=work, daemon=True).start()

    def _gpu_after_load(self):
        self._bench_gen += 1                    # stops a measurement still running
        if not (self.res and self.res.ok and self.res.validated):
            self._show_gpu(None, "—  (the shader doesn't compile)")
            return
        if self.gpu_live:
            if self._fs:
                self._show_gpu(None, "measuring live in the output…")
            else:
                self._show_gpu(None, "measuring live…")
                self._measure_live()
            return
        hit = self.gpu_cache.get(gpu_cache_key(self.res, self._values()))
        if hit:
            self._show_gpu(hit, "measured")
        else:
            self._show_gpu(None, "not measured · Analyze, or Live to measure continuously")

    def _values(self):
        return dict(self.previewer.values) if self.previewer else None

    def measure_gpu(self):
        """Measure the loaded shader's GPU time per frame at 1920x1080 with the
        current slider values, on a worker thread."""
        if self.gpu_live or not (self.res and self.res.ok and self.res.validated):
            return
        if self._fs:
            # A separate 1080p run would compete with the output: time the output
            # itself for a moment instead (at its own resolution).
            self._fs["timer"].reset()
            self._fs.pop("gpu", None)
            self._fs["sample_until"] = time.perf_counter() + GPU_SAMPLE_S
            self._show_gpu(None, "measuring in the output…")
            return
        from ffmaker import validate as V
        self._bench_gen += 1
        gen, res, values = self._bench_gen, self.res, self._values()
        key = gpu_cache_key(res, values)
        self._show_gpu(None, "measuring…")

        def work():
            try:
                r = V.benchmark(res.ir, res.ffgl_glsl, values, cancel=lambda: gen != self._bench_gen)
            except Exception as e:
                r = e
            self.after(0, lambda: self._gpu_measured(gen, key, r))
        threading.Thread(target=work, daemon=True).start()

    def _gpu_measured(self, gen, key, r):
        if isinstance(r, Exception):
            if gen == self._bench_gen:
                self._show_gpu(None, f"couldn't measure: {r}")
            return
        if r is None:                       # cancelled
            return
        self.gpu_cache[key] = r
        if gen == self._bench_gen and not self._fs:
            self._show_gpu(r, "measured")

    def _show_gpu(self, r, note):
        """r: a benchmark result ({"ms", "size"}) or None (note says why)."""
        from ffmaker import validate as V
        bar = self.gpu_bar
        bar.delete("all")
        if not r:
            self.lbl_gpu.configure(text="", fg=W.FG)
            self.lbl_gpu_detail.configure(text=note)
            return
        load, detail, level = V.load_text(r["ms"], r["size"])
        w, h = int(bar.cget("width")), int(bar.cget("height"))
        frac = min(1.0, r["ms"] / V.FRAME_60_MS)
        bar.create_rectangle(0, 0, max(1, int(w * frac)), h, fill=LOAD_COLOURS[level], width=0)
        self.lbl_gpu.configure(text=load, fg=LOAD_COLOURS[level])
        self.lbl_gpu_detail.configure(text=f"{detail} · {note}")

    # ── Settings helpers ─────────────────────────────────────────────────────
    def _pset(self, key):
        return self.settings.setdefault("params", {}).setdefault(key, {})

    def save(self):
        if not self.shader_path:
            self.log("Settings are kept for this session only (code wasn't loaded from a file).")
            return
        path = S.save(self.shader_path, self.settings)
        self.log(f"✓ Settings saved to {path}" if path else "Settings cleared.")

    def reset_settings(self):
        name = self.settings.get("plugin_name")
        self.settings.clear()
        if name:
            self.settings["plugin_name"] = name
        self.on_recompile()

    # ── Channels ─────────────────────────────────────────────────────────────
    def _build_channels(self):
        for w in self.channel_frame.winfo_children():
            w.destroy()
        ir = self.res.ir
        chans = [i for i in ir.images if i.name.startswith("iChannel")] if ir.dialect == "shadertoy" else []
        if not chans or any(p.label for p in ir.programs):    # multi-buffer projects: wiring is in the file
            return
        bg = _tk_bg(self.channel_frame)
        W.label(self.channel_frame, "Channels", bg=bg).pack(anchor="w")
        for im in sorted(chans, key=lambda i: i.name):
            row = W.frame(self.channel_frame, bg=bg)
            row.pack(fill="x", pady=1)
            W.label(row, im.name, bg=bg, width=9, anchor="w").pack(side="left")
            val, opts = self._channel_value(im)
            shown = val if val in CHANNEL_CHOICES else os.path.basename(val)
            menu = W.Menu(row, CHANNEL_CHOICES, width=12,
                          command=lambda c, n=im.name: self._channel_choice(n, c))
            menu.set(shown)
            menu.pack(side="left", padx=4)
            if im.source == "audio":
                continue
            # Per-channel sampler settings, as on Shadertoy.
            for key, choices in (("filter", FILTER_CHOICES), ("wrap", WRAP_CHOICES)):
                m = W.Menu(row, choices, width=6,
                           command=lambda c, n=im.name, k=key: self._sampler_choice(n, k, c))
                m.set(opts.get(key, choices[0]))
                m.pack(side="left", padx=2)

    def _channel_value(self, im):
        """(source, sampler options) for a channel: the saved setting, else what
        the shader's own directives produced."""
        from ffmaker.convert import split_channel_options
        saved = self.settings.get("channels", {}).get(im.name)
        if saved is not None:
            return split_channel_options(saved)
        val = {"host": "input", "audio": "audio", "none": "none"}.get(im.source, "noise")
        opts = {}
        if im.source == "imported":
            if im.path:
                val = im.path
                if self.shader_path:
                    try:
                        val = os.path.relpath(im.path, os.path.dirname(self.shader_path))
                    except ValueError:
                        pass
            if not im.repeat:
                opts["wrap"] = "clamp"
            if not im.flip:
                opts["vflip"] = False
        elif im.wrap:
            opts["wrap"] = im.wrap
        if im.filter:
            opts["filter"] = im.filter
        return val, opts

    def _store_channel(self, name, val, opts):
        parts = [val] + [f"{k}={str(v).lower()}" for k, v in opts.items()]
        self.settings.setdefault("channels", {})[name] = " ".join(parts)
        self.on_recompile()

    def _sampler_choice(self, name, key, choice):
        im = next(i for i in self.res.ir.images if i.name == name)
        val, opts = self._channel_value(im)
        if choice in (FILTER_CHOICES[0], WRAP_CHOICES[0]):
            opts.pop(key, None)
        else:
            opts[key] = choice
        self._store_channel(name, val, opts)

    def _channel_choice(self, name, choice):
        if choice == "file…":
            path = ctk.filedialog.askopenfilename(
                title=f"Image for {name}",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tga *.gif *.webp"), ("All", "*.*")])
            if not path:
                return
            if self.shader_path:
                try:
                    path = os.path.relpath(path, os.path.dirname(self.shader_path))
                except ValueError:
                    pass
            choice = path
        im = next((i for i in self.res.ir.images if i.name == name), None)
        opts = self._channel_value(im)[1] if im else {}
        self._store_channel(name, choice, opts)

    # ── Parameters ───────────────────────────────────────────────────────────
    # Built from fast_widgets (plain Tk/ttk): the list is rebuilt on every shader
    # switch, and CustomTkinter widgets made that take up to half a second.
    def _build_params(self):
        """Rebuild the parameter rows: built in a frame that isn't shown yet, which
        then replaces the old one in one step (so the list lays out once)."""
        old = self.params_frame.winfo_children()
        self._params_box = box = W.frame(self.params_frame, bg=self._params_bg)
        self._fill_params(box)
        box.pack(fill="x")
        for w in old:
            w.destroy()

    def _fill_params(self, box):
        ir = self.res.ir
        if not ir.params and not S.excluded_constants(self.settings):
            W.label(box, "No parameters.", fg="gray", bg=self._params_bg).pack(pady=10)
            return
        for i, p in enumerate(ir.params):
            self._param_row(i, p)
        # Constants the user chose to hide: listed so they can be re-exposed.
        present = {S.param_key(p) for p in ir.params}
        for nm in sorted(S.excluded_constants(self.settings) - present):
            row = W.frame(box)
            row.pack(fill="x", pady=2)
            var = tk.BooleanVar(row, value=False)
            W.check(row, var, command=lambda n=nm: self._set_expose(n, True)).pack(side="left", padx=4, pady=4)
            W.label(row, f"{nm}  (kept as constant)", fg=W.MUTED).pack(side="left")
        for nm in self.res.demoted:
            W.label(box, f"{nm}: can't be a slider (would not compile)", fg=W.MUTED,
                    bg=self._params_bg, anchor="w").pack(fill="x")

    def _set_expose(self, key, on):
        self._pset(key)["expose"] = bool(on)
        if on:
            self.settings["params"][key].pop("expose")
        self.on_recompile()

    def _set_value(self, i, p, v, save=True):
        if self.previewer:
            self.previewer.values[i] = v
        if save:
            self._pset(S.param_key(p))["default"] = v

    def _param_row(self, i, p):
        key = S.param_key(p)
        row = W.frame(self._params_box)
        row.pack(fill="x", pady=2)
        top = W.frame(row)
        top.pack(fill="x", padx=6, pady=(4, 2))
        if p.kind != "fft":
            var = tk.BooleanVar(row, value=not p.hidden)
            W.check(top, var, command=lambda: self._set_expose(key, var.get())).pack(side="left", padx=(0, 4))
        entry = W.entry(top, 18)
        entry.insert(0, p.display())
        entry.pack(side="left", padx=(0, 6))

        def commit_label(_e=None):
            txt = entry.get().strip()
            if txt and txt != p.display():
                self._pset(key)["label"] = txt
                p.label = txt
        entry.bind("<Return>", commit_label)
        entry.bind("<FocusOut>", commit_label)
        kind_txt = p.kind + (" (from const)" if p.origin in ("const", "define") else "")
        W.label(top, kind_txt, fg=W.KIND).pack(side="left")

        body = W.frame(row)
        body.pack(fill="x", padx=6, pady=(0, 5))
        enabled = not p.hidden
        if p.kind in ("float", "int", "speed"):
            self._range_control(body, i, p, key, enabled)
        elif p.kind in ("bool", "mouseclick"):
            on = tk.BooleanVar(row, value=bool(p.default))
            sw = W.check(body, on, command=lambda: self._set_value(i, p, bool(on.get())))
            if not enabled:
                sw.state(["disabled"])
            sw.pack(side="left")
        elif p.kind == "event":
            W.Button(body, "Trigger", lambda: self._set_value(i, p, True, save=False),
                     enabled=enabled).pack(side="left")
        elif p.kind == "long":
            def pick(lbl):
                self._set_value(i, p, p.values[p.labels.index(lbl)])
            om = W.Menu(body, list(p.labels), command=pick, enabled=enabled)
            om.set(p.labels[p.values.index(p.default)] if p.default in p.values else "")
            om.pack(side="left")
        elif p.kind == "color":
            self._color_control(body, i, p, enabled)
        elif p.kind in ("point2D", "mouse"):
            mn, mx = (p.min or [0.0, 0.0]), (p.max or [1.0, 1.0])
            if p.pixel_space:
                mn, mx = [0.0, 0.0], [1920.0, 1080.0]
            vals = list(p.default)
            for axis in (0, 1):
                line = W.frame(body)
                line.pack(fill="x")
                W.label(line, "XY"[axis], width=2).pack(side="left")
                lbl = W.label(line, f"{vals[axis]:.3f}", width=7)

                def move(v, a=axis, l=lbl):
                    vals[a] = float(v)
                    l.configure(text=f"{vals[a]:.3f}")
                    self._set_value(i, p, list(vals))
                sl = W.scale(line, mn[axis], mx[axis], command=move)
                sl.set(vals[axis])
                sl.pack(side="left", fill="x", expand=True, padx=4)
                if enabled:
                    self._arrow_keys(sl, move)
                else:
                    sl.state(["disabled"])
                lbl.pack(side="left")
        elif p.kind == "fft":
            W.label(body, "Live audio spectrum from the host (preview uses a test spectrum)",
                    fg=W.DIM).pack(side="left")

    def _range_control(self, body, i, p, key, enabled):
        is_int = p.kind == "int"
        fmt = lambda v: str(int(round(v))) if is_int else f"{v:.3f}"
        line = W.frame(body)
        line.pack(fill="x")
        # Value readout; click it to type a value (Enter applies, Esc cancels).
        readout = W.frame(line, width=W.px(60), height=W.px(24))
        readout.pack(side="right", padx=(6, 0))
        readout.pack_propagate(False)
        val_lbl = W.label(readout, fmt(p.default))
        val_lbl.pack(fill="both", expand=True)
        val_entry = W.entry(readout, 7)
        e_max = W.entry(line, 6)
        e_max.insert(0, f"{p.max:g}")
        e_max.pack(side="right")
        e_min = W.entry(line, 6)
        e_min.insert(0, f"{p.min:g}")
        e_min.pack(side="left")

        def move(v):
            v = int(round(float(v))) if is_int else float(v)
            val_lbl.configure(text=fmt(v))
            self._set_value(i, p, v)
        sl = W.scale(line, p.min, p.max, command=move)
        sl.set(p.default)
        sl.pack(side="left", fill="x", expand=True, padx=6)

        def set_range(lo, hi):
            p.min, p.max = lo, hi
            ov = self._pset(key)
            ov["min"], ov["max"] = lo, hi
            for e, x in ((e_min, lo), (e_max, hi)):
                e.delete(0, "end")
                e.insert(0, f"{x:g}")
            sl.configure(from_=lo, to=hi)

        def set_value(v):
            """Move the slider to v, widening the range first if v is outside it."""
            v = int(round(v)) if is_int else float(v)
            if v < p.min or v > p.max:
                set_range(min(p.min, v), max(p.max, v))
            sl.set(v)
            move(v)

        def commit_range(_e=None):
            try:
                lo, hi = float(e_min.get()), float(e_max.get())
            except ValueError:
                return
            if lo == hi or (lo, hi) == (p.min, p.max):
                return
            lo, hi = min(lo, hi), max(lo, hi)
            cur = min(max(sl.get(), lo), hi)
            set_range(lo, hi)
            sl.set(cur)
            move(cur)
        for e in (e_min, e_max):
            e.bind("<Return>", commit_range)
            e.bind("<FocusOut>", commit_range)

        if not enabled:
            sl.state(["disabled"])
            return
        self._arrow_keys(sl, move, is_int)

        def reset(_e=None):
            # Back to the shader's own default; drop the saved default override.
            set_value(p.source_default if p.source_default is not None else p.default)
            self._pset(key).pop("default", None)
            return "break"
        for seq in ["<Button-3>"] + (["<Button-2>", "<Control-Button-1>"] if sys.platform == "darwin" else []):
            sl.bind(seq, reset)

        def edit(_e=None):
            val_entry.delete(0, "end")
            val_entry.insert(0, val_lbl.cget("text"))
            val_lbl.pack_forget()
            val_entry.pack(fill="both", expand=True)
            val_entry.focus_set()
            val_entry.select_range(0, "end")

        def finish(apply):
            if not val_entry.winfo_ismapped():
                return
            txt = val_entry.get().strip()
            val_entry.pack_forget()
            val_lbl.pack(fill="both", expand=True)
            if apply:
                try:
                    set_value(float(txt))
                except ValueError:
                    pass
        val_lbl.bind("<Button-1>", edit)
        val_lbl.configure(cursor="xterm")
        val_entry.bind("<Return>", lambda e: finish(True))
        val_entry.bind("<KP_Enter>", lambda e: finish(True))
        val_entry.bind("<FocusOut>", lambda e: finish(True))
        val_entry.bind("<Escape>", lambda e: finish(False))

    def _color_control(self, body, i, p, enabled):
        rgba = (list(p.default) + [1.0] * 4)[:4]

        def hexcol(c):
            return "#%02x%02x%02x" % tuple(int(max(0, min(1, x)) * 255) for x in c[:3])

        def pick():
            res = colorchooser.askcolor(color=hexcol(rgba), title=p.display())
            if res and res[0]:
                rgba[:3] = [c / 255.0 for c in res[0]]
                btn.set_colour(hexcol(rgba))
                self._set_value(i, p, list(rgba))
        btn = W.Button(body, "", pick, width=6, enabled=enabled, bg=hexcol(rgba), hover=hexcol(rgba))
        btn.configure(highlightthickness=1, highlightbackground=W.BORDER)
        btn.pack(side="left")
        if p.glsl_type == "vec4":
            W.label(body, "alpha").pack(side="left", padx=(8, 2))

            def alpha(v):
                rgba[3] = float(v)
                self._set_value(i, p, list(rgba))
            sl = W.scale(body, 0, 1, command=alpha)
            sl.configure(length=W.px(120))
            sl.set(rgba[3])
            sl.pack(side="left")
            if enabled:
                self._arrow_keys(sl, alpha)
            else:
                sl.state(["disabled"])

    def _arrow_keys(self, sl, command, is_int=False):
        """Click a slider to focus it (its handle turns amber); Left/Right then
        step it by 1/100 of its range (1 for integers), within min/max."""
        sl.bind("<Button-1>", lambda e: sl.focus_set(), add=True)

        def step(direction):
            lo, hi = sorted((float(sl.cget("from")), float(sl.cget("to"))))
            d = 1.0 if is_int else (hi - lo) / 100.0
            sl.set(min(max(sl.get() + direction * d, lo), hi))
            command(sl.get())
            return "break"
        sl.bind("<Left>", lambda e: step(-1))
        sl.bind("<Right>", lambda e: step(1))

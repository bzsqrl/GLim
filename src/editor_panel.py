"""Right-hand panel of the Single File tab: live preview, channel sources and
the parameter editor. Edits are written into a settings dict (the shader's
.ffmaker.json); changes that alter the GLSL ask the app to recompile."""
import os
import sys
import time
import tkinter as tk
from tkinter import colorchooser

import customtkinter as ctk
from PIL import Image, ImageTk

from ffmaker import settings as S

PREVIEW_W, PREVIEW_H = 384, 216
CHANNEL_CHOICES = ["input", "noise", "audio", "none", "file…"]
FILTER_CHOICES = ["filter", "nearest", "linear", "mipmap"]   # first entry = Shadertoy default
WRAP_CHOICES = ["wrap", "clamp", "repeat"]


class EditorPanel(ctk.CTkFrame):
    def __init__(self, master, on_recompile, log):
        super().__init__(master)
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
        # Set by the app: the queue's file paths (fullscreen playlist), a function
        # converting one for preview, and a callback loading a path into the editor.
        self.get_playlist = lambda: []
        self.convert_path = None
        self.on_fullscreen_exit = None

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
        self.btn_play = ctk.CTkButton(transport, text="⏸", width=36, command=self._toggle_play)
        self.btn_play.pack(side="left")
        ctk.CTkButton(transport, text="⟲", width=36, command=self.restart).pack(side="left", padx=4)
        ctk.CTkButton(transport, text="⛶", width=36, command=self.enter_fullscreen).pack(side="left")
        self.preview.bind("<Double-Button-1>", lambda e: self.enter_fullscreen())
        # Esc in FFMaker also leaves fullscreen (e.g. with FFMaker on another monitor).
        top = self.winfo_toplevel()
        top.bind("<Escape>", lambda e: self.exit_fullscreen(), add="+")
        # Ctrl+F (⌘F on macOS) toggles fullscreen while the Single File tab is showing.
        mod = "Command" if sys.platform == "darwin" else "Control"
        for key in ("f", "F"):
            top.bind(f"<{mod}-{key}>", self._toggle_fullscreen, add="+")
        self.lbl_time = ctk.CTkLabel(transport, text="", width=70, anchor="w", text_color="#9ca3af")
        self.lbl_time.pack(side="left", padx=4)
        self.input_menu = ctk.CTkOptionMenu(transport, values=["Test pattern", "Load image…"],
                                            width=130, command=self._input_choice)
        self.input_menu.pack(side="right")

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
        self.lbl_empty = ctk.CTkLabel(self.params_frame, text="Click 'Analyze Code' to load a shader.",
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
        self._build_channels()
        self._build_params()
        if res.ir.kind in ("effect", "mixer"):
            self.input_menu.pack(side="right")
        else:
            self.input_menu.pack_forget()
        if res.ok and res.validated:
            self._open_previewer()

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

    def _close_previewer(self):
        self.exit_fullscreen(load_last=False)
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
    # self._fs = {"view", "pv", "res", "path"} while fullscreen. Left/Right step
    # through the app's queue (get_playlist) like a playlist; on exit the app
    # loads the last shader shown into the Single File tab (on_fullscreen_exit).

    def _fs_previewer(self, view, res):
        from ffmaker import validate as V
        pv = V.Previewer(res.ir, res.ffgl_glsl, *view.render_size)
        if self._input_image:
            w, h, px = self._input_image
            pv.set_input_image(w, h, px, 0)
            pv.set_input_image(w, h, px, 1)
        return pv

    def enter_fullscreen(self):
        """Show the preview fullscreen on FFMaker's monitor; Esc returns."""
        if self._fs or not self.previewer:
            return
        from ffmaker import validate as V
        top = self.winfo_toplevel()
        near = (top.winfo_rootx() + top.winfo_width() // 2, top.winfo_rooty() + top.winfo_height() // 2)
        view = pv = None
        try:
            with V.gpu():
                view = V.FullscreenView(near)
                pv = self._fs_previewer(view, self.res)
            pv.values = self.previewer.values     # same dict: slider moves show up live
            self._fs = {"view": view, "pv": pv, "res": self.res, "path": self.shader_path}
        except Exception as e:
            self.log(f"Fullscreen unavailable: {e}")
            with V.gpu():
                if pv:
                    pv.close()
                if view:
                    view.close()

    def _fs_step(self, direction):
        """Fullscreen playlist: show the previous / next shader in the queue that compiles."""
        from ffmaker import validate as V
        paths = self.get_playlist()
        if not paths:
            return
        cur = self._fs["path"]
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
                self.log(f"Playlist: skipped {name} ({e})")
                continue
            if not (res.ok and res.validated):
                self.log(f"Playlist: skipped {name} (doesn't compile)")
                continue
            view, old = self._fs["view"], self._fs["pv"]
            try:
                with V.gpu():
                    pv = self._fs_previewer(view, res)
                    for k, p in enumerate(res.ir.params):
                        pv.values[k] = p.default
                    old.close()
                    view.reattach()
            except Exception as e:
                self.log(f"Playlist: skipped {name} ({e})")
                continue
            self._fs.update(pv=pv, res=res, path=path)
            self.sim_time = 0.0             # each shader starts from the beginning
            self.log(f"▶ {name} ({i + 1}/{len(paths)})")
            return

    def _toggle_fullscreen(self, _e=None):
        if self._fs:
            self.exit_fullscreen()
        elif self.winfo_viewable():         # only from the Single File tab
            self.enter_fullscreen()
        else:
            return None
        return "break"

    def exit_fullscreen(self, load_last=True):
        """Leave fullscreen. If the playlist moved on to another shader, the app
        loads it into the Single File tab (unless load_last is False)."""
        if not self._fs:
            return
        fs, self._fs = self._fs, None
        try:
            from ffmaker import validate as V
            with V.gpu():
                fs["pv"].close()
                fs["view"].close()
        except Exception:
            pass
        try:
            self.winfo_toplevel().focus_force()
        except tk.TclError:
            pass
        if load_last and fs["path"] and fs["path"] != self.shader_path and self.on_fullscreen_exit:
            self.on_fullscreen_exit(fs["path"])

    # ── Render loop ──────────────────────────────────────────────────────────
    def _tick(self):
        now = time.perf_counter()
        dt = 0.0 if self.last_tick is None else min(now - self.last_tick, 0.25)
        self.last_tick = now
        if self._fs and self.previewer:
            self._tick_fullscreen(dt)       # vsync in the swap paces this to the display
            self.after(1, self._tick)
            return
        if self.previewer and self.winfo_ismapped():
            try:
                from ffmaker import validate as V
                speed = self._speed()
                if self.playing:
                    self.sim_time += dt * speed
                with V.gpu():
                    self.previewer.render_frame(self.sim_time, dt * speed if self.playing else 0.0)
                    px = self.previewer.read()
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
        self.after(33, self._tick)

    def _speed(self, res=None, pv=None):
        res, pv = res or self.res, pv or self.previewer
        for i, p in enumerate(res.ir.params):
            if p.kind == "speed":
                return float(pv.values.get(i, p.default))
        return 1.0

    def _tick_fullscreen(self, dt):
        """While fullscreen, render there (at screen size) instead of the small preview."""
        from ffmaker import validate as V
        view = self._fs["view"]
        try:
            with V.gpu():
                alive = view.poll()
            if not alive:
                raise StopIteration
            if view.nav:
                direction, view.nav = view.nav, 0
                self._fs_step(direction)
            pv, res = self._fs["pv"], self._fs["res"]
            with V.gpu():
                speed = self._speed(res, pv)
                if self.playing:
                    self.sim_time += dt * speed
                pv.render_frame(self.sim_time, dt * speed if self.playing else 0.0)
                view.show(pv)
            self.lbl_time.configure(text=f"{self.sim_time:6.1f}s")
        except StopIteration:
            self.exit_fullscreen()
        except Exception as e:
            self.log(f"Fullscreen stopped: {e}")
            self.exit_fullscreen()

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
        ctk.CTkLabel(self.channel_frame, text="Channels", font=("Arial", 13, "bold")).pack(anchor="w")
        for im in sorted(chans, key=lambda i: i.name):
            row = ctk.CTkFrame(self.channel_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=im.name, width=80, anchor="w").pack(side="left")
            val, opts = self._channel_value(im)
            shown = val if val in CHANNEL_CHOICES else os.path.basename(val)
            menu = ctk.CTkOptionMenu(row, values=CHANNEL_CHOICES, width=130,
                                     command=lambda c, n=im.name: self._channel_choice(n, c))
            menu.set(shown)
            menu.pack(side="left", padx=4)
            if im.source == "audio":
                continue
            # Per-channel sampler settings, as on Shadertoy.
            for key, choices in (("filter", FILTER_CHOICES), ("wrap", WRAP_CHOICES)):
                m = ctk.CTkOptionMenu(row, values=choices, width=80,
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
    def _build_params(self):
        for w in self.params_frame.winfo_children():
            w.destroy()
        ir = self.res.ir
        if not ir.params and not S.excluded_constants(self.settings):
            ctk.CTkLabel(self.params_frame, text="No parameters.", text_color="gray").pack(pady=10)
            return
        for i, p in enumerate(ir.params):
            self._param_row(i, p)
        # Constants the user chose to hide: listed so they can be re-exposed.
        present = {S.param_key(p) for p in ir.params}
        for nm in sorted(S.excluded_constants(self.settings) - present):
            row = ctk.CTkFrame(self.params_frame, fg_color="#1f2430", corner_radius=6)
            row.pack(fill="x", pady=2)
            var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(row, text="", width=24, variable=var,
                            command=lambda n=nm: self._set_expose(n, True)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"{nm}  (kept as constant)", text_color="#6b7280").pack(side="left")
        for nm in self.res.demoted:
            ctk.CTkLabel(self.params_frame, text=f"{nm}: can't be a slider (would not compile)",
                         text_color="#6b7280", anchor="w").pack(fill="x")

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
        row = ctk.CTkFrame(self.params_frame, fg_color="#1f2430", corner_radius=6)
        row.pack(fill="x", pady=2)
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=4, pady=(3, 0))
        if p.kind != "fft":
            var = ctk.BooleanVar(value=not p.hidden)
            ctk.CTkCheckBox(top, text="", width=24, variable=var,
                            command=lambda: self._set_expose(key, var.get())).pack(side="left")
        entry = ctk.CTkEntry(top, width=150)
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
        ctk.CTkLabel(top, text=kind_txt, text_color="#60a5fa").pack(side="left")

        body = ctk.CTkFrame(row, fg_color="transparent")
        body.pack(fill="x", padx=4, pady=(0, 4))
        state = "disabled" if p.hidden else "normal"
        if p.kind in ("float", "int", "speed"):
            self._range_control(body, i, p, key, state)
        elif p.kind in ("bool", "mouseclick"):
            sw = ctk.CTkSwitch(body, text="", state=state,
                               command=lambda: self._set_value(i, p, bool(sw.get())))
            if p.default:
                sw.select()
            sw.pack(side="left")
        elif p.kind == "event":
            ctk.CTkButton(body, text="Trigger", width=80, state=state,
                          command=lambda: self._set_value(i, p, True, save=False)).pack(side="left")
        elif p.kind == "long":
            def pick(lbl):
                self._set_value(i, p, p.values[p.labels.index(lbl)])
            om = ctk.CTkOptionMenu(body, values=list(p.labels), width=160, state=state, command=pick)
            if p.default in p.values:
                om.set(p.labels[p.values.index(p.default)])
            om.pack(side="left")
        elif p.kind == "color":
            self._color_control(body, i, p, state)
        elif p.kind in ("point2D", "mouse"):
            mn, mx = (p.min or [0.0, 0.0]), (p.max or [1.0, 1.0])
            if p.pixel_space:
                mn, mx = [0.0, 0.0], [1920.0, 1080.0]
            vals = list(p.default)
            for axis in (0, 1):
                line = ctk.CTkFrame(body, fg_color="transparent")
                line.pack(fill="x")
                ctk.CTkLabel(line, text="XY"[axis], width=14).pack(side="left")
                lbl = ctk.CTkLabel(line, text=f"{vals[axis]:.3f}", width=50)

                def move(v, a=axis, l=lbl):
                    vals[a] = float(v)
                    l.configure(text=f"{vals[a]:.3f}")
                    self._set_value(i, p, list(vals))
                sl = ctk.CTkSlider(line, from_=mn[axis], to=mx[axis], state=state, command=move)
                sl.set(vals[axis])
                sl.pack(side="left", fill="x", expand=True)
                if state != "disabled":
                    self._arrow_keys(sl, move)
                lbl.pack(side="left")
        elif p.kind == "fft":
            ctk.CTkLabel(body, text="Live audio spectrum from the host (preview uses a test spectrum)",
                         text_color="#9ca3af").pack(side="left")

    def _range_control(self, body, i, p, key, state):
        is_int = p.kind == "int"
        fmt = lambda v: str(int(round(v))) if is_int else f"{v:.3f}"
        line = ctk.CTkFrame(body, fg_color="transparent")
        line.pack(fill="x")
        # Value readout; click it to type a value (Enter applies, Esc cancels).
        readout = ctk.CTkFrame(line, fg_color="transparent", width=56, height=28)
        readout.pack(side="right", padx=(6, 0))
        readout.pack_propagate(False)
        val_lbl = ctk.CTkLabel(readout, text=fmt(p.default), width=56)
        val_lbl.pack(fill="both", expand=True)
        val_entry = ctk.CTkEntry(readout, width=56)
        e_max = ctk.CTkEntry(line, width=50)
        e_max.insert(0, f"{p.max:g}")
        e_max.pack(side="right")
        e_min = ctk.CTkEntry(line, width=50)
        e_min.insert(0, f"{p.min:g}")
        e_min.pack(side="left")
        steps = lambda lo, hi: int(hi - lo) if is_int and 0 < hi - lo <= 1000 else None

        def move(v):
            v = int(round(v)) if is_int else float(v)
            val_lbl.configure(text=fmt(v))
            self._set_value(i, p, v)
        sl = ctk.CTkSlider(line, from_=p.min, to=p.max, number_of_steps=steps(p.min, p.max),
                           state=state, command=move)
        sl.set(p.default)
        sl.pack(side="left", fill="x", expand=True, padx=4)

        def set_range(lo, hi):
            p.min, p.max = lo, hi
            ov = self._pset(key)
            ov["min"], ov["max"] = lo, hi
            for e, x in ((e_min, lo), (e_max, hi)):
                e.delete(0, "end")
                e.insert(0, f"{x:g}")
            sl.configure(from_=lo, to=hi, number_of_steps=steps(lo, hi))

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

        if state == "disabled":
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

    def _color_control(self, body, i, p, state):
        rgba = (list(p.default) + [1.0] * 4)[:4]

        def hexcol(c):
            return "#%02x%02x%02x" % tuple(int(max(0, min(1, x)) * 255) for x in c[:3])
        btn = ctk.CTkButton(body, text="", width=60, height=22, state=state,
                            fg_color=hexcol(rgba), hover_color=hexcol(rgba))

        def pick():
            res = colorchooser.askcolor(color=hexcol(rgba), title=p.display())
            if res and res[0]:
                rgba[:3] = [c / 255.0 for c in res[0]]
                btn.configure(fg_color=hexcol(rgba), hover_color=hexcol(rgba))
                self._set_value(i, p, list(rgba))
        btn.configure(command=pick)
        btn.pack(side="left")
        if p.glsl_type == "vec4":
            ctk.CTkLabel(body, text="alpha").pack(side="left", padx=(8, 2))
            sl = ctk.CTkSlider(body, from_=0, to=1, width=120, state=state)

            def alpha(v):
                rgba[3] = float(v)
                self._set_value(i, p, list(rgba))
            sl.configure(command=alpha)
            sl.set(rgba[3])
            sl.pack(side="left")
            if state != "disabled":
                self._arrow_keys(sl, alpha)

    def _arrow_keys(self, sl, command, is_int=False):
        """Click a slider to focus it (its handle turns amber); Left/Right then
        step it by 1/100 of its range (1 for integers), within min/max."""
        canvas = sl._canvas
        sl.bind("<Button-1>", lambda e: canvas.focus_set(), add=True)
        normal = sl.cget("button_color")
        canvas.bind("<FocusIn>", lambda e: sl.configure(button_color="#f59e0b"), add="+")
        canvas.bind("<FocusOut>", lambda e: sl.configure(button_color=normal), add="+")

        def step(direction):
            lo, hi = sorted((float(sl.cget("from_")), float(sl.cget("to"))))
            d = 1.0 if is_int else (hi - lo) / 100.0
            sl.set(min(max(sl.get() + direction * d, lo), hi))
            command(sl.get())
            return "break"
        canvas.bind("<Left>", lambda e: step(-1))
        canvas.bind("<Right>", lambda e: step(1))

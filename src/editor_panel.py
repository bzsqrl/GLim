"""Right-hand panel of the Single File tab: live preview, channel sources and
the parameter editor. Edits are written into a settings dict (the shader's
.ffmaker.json); changes that alter the GLSL ask the app to recompile."""
import os
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

    # ── Render loop ──────────────────────────────────────────────────────────
    def _tick(self):
        now = time.perf_counter()
        dt = 0.0 if self.last_tick is None else min(now - self.last_tick, 0.25)
        self.last_tick = now
        if self.previewer and self.winfo_ismapped():
            try:
                from ffmaker import validate as V
                speed = 1.0
                for i, p in enumerate(self.res.ir.params):
                    if p.kind == "speed":
                        speed = float(self.previewer.values.get(i, p.default))
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
                lbl.pack(side="left")
        elif p.kind == "fft":
            ctk.CTkLabel(body, text="Live audio spectrum from the host (preview uses a test spectrum)",
                         text_color="#9ca3af").pack(side="left")

    def _range_control(self, body, i, p, key, state):
        is_int = p.kind == "int"
        line = ctk.CTkFrame(body, fg_color="transparent")
        line.pack(fill="x")
        val_lbl = ctk.CTkLabel(line, text=f"{p.default:.3f}" if not is_int else str(int(p.default)), width=56)
        val_lbl.pack(side="right", padx=(6, 0))
        e_max = ctk.CTkEntry(line, width=50)
        e_max.insert(0, f"{p.max:g}")
        e_max.pack(side="right")
        e_min = ctk.CTkEntry(line, width=50)
        e_min.insert(0, f"{p.min:g}")
        e_min.pack(side="left")
        steps = int(p.max - p.min) if is_int and 0 < p.max - p.min <= 1000 else None

        def move(v):
            v = int(round(v)) if is_int else float(v)
            val_lbl.configure(text=str(v) if is_int else f"{v:.3f}")
            self._set_value(i, p, v)
        sl = ctk.CTkSlider(line, from_=p.min, to=p.max, number_of_steps=steps, state=state, command=move)
        sl.set(p.default)
        sl.pack(side="left", fill="x", expand=True, padx=4)

        def commit_range(_e=None):
            try:
                lo, hi = float(e_min.get()), float(e_max.get())
            except ValueError:
                return
            if lo == hi or (lo, hi) == (p.min, p.max):
                return
            lo, hi = min(lo, hi), max(lo, hi)
            p.min, p.max = lo, hi
            ov = self._pset(key)
            ov["min"], ov["max"] = lo, hi
            cur = min(max(sl.get(), lo), hi)
            sl.configure(from_=lo, to=hi, number_of_steps=int(hi - lo) if is_int and 0 < hi - lo <= 1000 else None)
            sl.set(cur)
            move(cur)
        for e in (e_min, e_max):
            e.bind("<Return>", commit_range)
            e.bind("<FocusOut>", commit_range)

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

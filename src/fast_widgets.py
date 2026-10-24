"""Lightweight Tk/ttk widgets in FFStudio's colours (theme.py).

Every CustomTkinter widget is a canvas that draws its own rounded shapes, so
building many is slow: a 13-slider parameter list took about half a second,
and the parameter editor is rebuilt on every shader switch (the queue
slideshow, ← / →). These native widgets take a fraction of that. They look
flatter (square corners) but behave the same."""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import customtkinter as ctk

import theme as T

BG = T.INSET            # the scrollable parameter list
ROW = T.ROW             # one parameter's row
FG = T.FG
DIM = T.DIM
MUTED = T.MUTED
KIND = T.TAG
ENTRY_BG = T.INSET
BORDER = T.BORDER
ACCENT = T.ACCENT
ACCENT_HOVER = T.ACCENT_HOVER
BUTTON = T.BUTTON
BUTTON_HOVER = T.BUTTON_HOVER
FOCUS = T.AMBER         # a slider with keyboard focus (← / → step it)
TROUGH = T.BORDER
DISABLED = T.LINE

_font = None
_scaling = 1.0


def setup(widget):
    """Fonts and ttk styles, once (after the app window exists)."""
    global _font, _scaling
    if _font is not None:
        return
    try:
        _scaling = ctk.ScalingTracker.get_widget_scaling(widget)
    except Exception:
        _scaling = 1.0
    family = ctk.ThemeManager.theme["CTkFont"]["family"]
    if family not in tkfont.families(widget):
        family = tkfont.nametofont("TkDefaultFont", root=widget).cget("family")
    _font = tkfont.Font(root=widget, family=family, size=-round(13 * _scaling))   # px, like CTk
    st = ttk.Style(widget)
    if st.theme_use() != "clam":        # the native themes ignore colours
        st.theme_use("clam")
    st.configure("FF.Horizontal.TScale", troughcolor=TROUGH, background=ACCENT, bordercolor=ROW,
                 lightcolor=ACCENT, darkcolor=ACCENT, gripcount=0, sliderlength=px(14),
                 sliderthickness=px(14), troughrelief="flat")
    st.map("FF.Horizontal.TScale",
           background=[("disabled", DISABLED), ("focus", FOCUS), ("active", T.ACCENT_ACTIVE)],
           lightcolor=[("disabled", DISABLED), ("focus", FOCUS), ("active", T.ACCENT_ACTIVE)],
           darkcolor=[("disabled", DISABLED), ("focus", FOCUS), ("active", T.ACCENT_ACTIVE)])
    st.configure("FF.TCheckbutton", background=ROW, foreground=FG, font=_font, focuscolor=ROW,
                 indicatorbackground=ENTRY_BG, indicatorforeground="white", indicatormargin=px(2),
                 upperbordercolor=BORDER, lowerbordercolor=BORDER)
    st.map("FF.TCheckbutton", background=[("active", ROW)],
           indicatorbackground=[("selected", ACCENT), ("pressed", ACCENT_HOVER)])


def px(n):
    return max(1, round(n * _scaling))


def font():
    return _font


def frame(parent, bg=ROW, **kw):
    return tk.Frame(parent, bg=bg, highlightthickness=0, bd=0, **kw)


def label(parent, text="", fg=FG, bg=ROW, **kw):
    return tk.Label(parent, text=text, fg=fg, bg=bg, font=_font, bd=0, **kw)


def entry(parent, chars):
    return tk.Entry(parent, width=chars, bg=ENTRY_BG, fg=FG, insertbackground=FG, font=_font,
                    relief="flat", bd=px(2), highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT, selectbackground=ACCENT, selectforeground="white",
                    disabledbackground=ROW, disabledforeground=MUTED)


class Scale(ttk.Scale):
    """A slider that behaves like CTkSlider: set() doesn't call the command (ttk's
    does, which would save every default as an edit), and a click on the track
    jumps there (ttk moves one unit) and can be dragged on from there."""

    def __init__(self, parent, lo, hi, command=None):
        self._command, self._quiet = command, False
        super().__init__(parent, from_=lo, to=hi, orient="horizontal", style="FF.Horizontal.TScale",
                         command=self._changed)
        self.bind("<Button-1>", self._jump, add=True)

    def _changed(self, v):
        if not self._quiet and self._command:
            self._command(v)

    def set(self, value):
        self._quiet = True
        try:
            super().set(value)
        finally:
            self._quiet = False

    def _jump(self, e):
        if self.instate(["disabled"]) or "slider" in self.identify(e.x, e.y):
            return
        super().set(self.get(e.x, e.y))     # calls the command
        # Lay the handle out at its new place now, so ttk's own binding (next) finds
        # it under the pointer and starts a drag, instead of moving another unit.
        self.update_idletasks()


def scale(parent, lo, hi, command=None):
    return Scale(parent, lo, hi, command)


def check(parent, variable, command=None, text=""):
    return ttk.Checkbutton(parent, text=text, variable=variable, command=command,
                           style="FF.TCheckbutton", takefocus=False)


class Button(tk.Label):
    """A flat button (tk.Button ignores colours on macOS)."""

    def __init__(self, parent, text, command, width=None, enabled=True, bg=BUTTON, hover=BUTTON_HOVER):
        super().__init__(parent, text=text, fg=FG, bg=bg, font=_font, padx=px(10), pady=px(2),
                         cursor="hand2", width=width or 0)
        self._bg, self._hover, self._command, self._enabled = bg, hover, command, True
        self.bind("<Enter>", lambda e: self._enabled and tk.Label.configure(self, bg=self._hover))
        self.bind("<Leave>", lambda e: tk.Label.configure(self, bg=self._bg if self._enabled else DISABLED))
        self.bind("<Button-1>", lambda e: self._enabled and self._command and self._command())
        if not enabled:
            self.set_enabled(False)

    def set_colour(self, bg, hover=None):
        self._bg, self._hover = bg, hover or bg
        tk.Label.configure(self, bg=bg)

    def set_enabled(self, on):
        self._enabled = on
        tk.Label.configure(self, bg=self._bg if on else DISABLED, fg=FG if on else MUTED,
                           cursor="hand2" if on else "")


class Menu(Button):
    """A drop-down choice (in place of CTkOptionMenu): click for a menu of values."""

    def __init__(self, parent, values, command=None, width=None, enabled=True):
        super().__init__(parent, "", self._popup, width=width, enabled=enabled)
        self.configure(anchor="w")
        self._values, self._on_pick, self._value = list(values), command, ""

    def set(self, value):
        self._value = value
        self.configure(text=f"{value}  ▾")

    def get(self):
        return self._value

    def _popup(self):
        m = tk.Menu(self, tearoff=False, bg=BUTTON, fg=FG, activebackground=ACCENT,
                    activeforeground="white", font=_font, bd=0)
        for v in self._values:
            m.add_command(label=v, command=lambda v=v: self._pick(v))
        try:
            m.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        finally:
            m.grab_release()

    def _pick(self, v):
        self.set(v)
        if self._on_pick:
            self._on_pick(v)

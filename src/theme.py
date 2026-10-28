"""GLim's colours and fonts, in one place.

One family of dark surfaces, from the window to a button; one accent, for the
main actions and for toggles that are on; and green / amber / red only where
they mean done / busy or warning / error. apply() patches CustomTkinter's theme,
so its widgets take these colours without being told; call it once the app
window exists (fonts need it) and before any other widget is made."""
import re
import sys
from tkinter import font as tkfont

import customtkinter as ctk

# Surfaces, dark to light.
WINDOW = "#0f1217"
INSET = "#12161c"        # code box, parameter list, queue list, text fields
PANEL = "#171b22"        # the editor panel and the build log
ROW = "#1c2129"          # one parameter's row
BUTTON = "#262d38"       # a secondary button
BUTTON_HOVER = "#313a47"
LINE = "#232a35"         # panel outlines, dividers, the GPU bar's track
BORDER = "#2c3440"       # text fields, the slider track
BORDER_STRONG = "#3a4453"
SELECTED = "#24274a"     # a selected queue row: the accent over INSET
TAB_SELECTED = "#3a4453" # the Queue / Studio button of the tab showing

# Text.
FG = "#e6e9ef"
DIM = "#8b95a5"          # secondary text, section labels
TAG = "#7f8a9b"          # a parameter's type
MUTED = "#6b7585"        # disabled
LOG = "#b6c0cc"          # build log lines that are neither good nor bad news

# Colour with a meaning.
ACCENT = "#5b5bd6"
ACCENT_HOVER = "#4b4bc0"
ACCENT_ACTIVE = "#7070e0"   # a slider handle under the pointer
GREEN = "#22c55e"
AMBER = "#f59e0b"
RED = "#ef4444"
RED_HOVER = "#dc2626"
GREEN_TEXT = "#34d399"
AMBER_TEXT = "#fbbf24"
RED_TEXT = "#f87171"

# Fonts: the first family installed, per platform (set by apply()).
_UI_FAMILIES = {"win32": ("Segoe UI Variable Text", "Segoe UI"),
                "darwin": (".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue")}
_MONO_FAMILIES = {"win32": ("Cascadia Mono", "Consolas"),
                  "darwin": ("SF Mono", "Menlo", "Monaco")}
UI_FAMILY = "TkDefaultFont"
MONO_FAMILY = "TkFixedFont"


def ui(size=13, weight="normal"):
    """A UI font (size in pixels, as CustomTkinter takes it)."""
    return (UI_FAMILY, size, weight)


def mono(size=13):
    return (MONO_FAMILY, size)


def section(parent, text, **kw):
    """A small section label: PREVIEW, PARAMETERS, BUILD LOG."""
    return ctk.CTkLabel(parent, text=text.upper(), font=ui(11, "bold"), text_color=DIM, **kw)


_LOG_ERROR = re.compile(r"\b(ERROR|EXCEPTION)\b|failed|does not compile|unavailable|✗")
_LOG_WARN = re.compile(r"\bWARN(ING)?\b|\bNote:")


def log_tag(text):
    """The build log's colour for a line: "ok", "warn", "error" or None."""
    if _LOG_ERROR.search(text):
        return "error"
    if _LOG_WARN.search(text):
        return "warn"
    return "ok" if "✓" in text else None


def _pick(root, candidates, fallback):
    families = set(tkfont.families(root))
    for f in candidates.get(sys.platform, ()):
        if f in families or f.startswith("."):      # macOS's system font isn't listed
            return f
    return tkfont.nametofont(fallback, root=root).cget("family")


def _both(c):
    return [c, c]                   # CustomTkinter's (light, dark) pair: dark only


def apply(root):
    global UI_FAMILY, MONO_FAMILY
    UI_FAMILY = _pick(root, _UI_FAMILIES, "TkDefaultFont")
    MONO_FAMILY = _pick(root, _MONO_FAMILIES, "TkFixedFont")
    t = ctk.ThemeManager.theme
    t["CTkFont"].update(family=UI_FAMILY, size=13)
    for key in ("CTk", "CTkToplevel"):
        t[key]["fg_color"] = _both(WINDOW)
    t["CTkFrame"].update(fg_color=_both(PANEL), top_fg_color=_both(ROW), border_color=_both(LINE))
    t["CTkButton"].update(fg_color=_both(BUTTON), hover_color=_both(BUTTON_HOVER),
                          border_color=_both(BORDER_STRONG), text_color=_both(FG),
                          text_color_disabled=_both(MUTED))
    t["CTkLabel"]["text_color"] = _both(FG)
    t["CTkEntry"].update(fg_color=_both(INSET), border_color=_both(BORDER), border_width=1,
                         text_color=_both(FG), placeholder_text_color=_both(MUTED))
    t["CTkOptionMenu"].update(fg_color=_both(BUTTON), button_color=_both(BUTTON),
                              button_hover_color=_both(BUTTON_HOVER), text_color=_both(FG),
                              text_color_disabled=_both(MUTED))
    t["CTkCheckBox"].update(fg_color=_both(ACCENT), hover_color=_both(ACCENT_HOVER),
                            border_color=_both(BORDER_STRONG), text_color=_both(FG))
    t["CTkScrollbar"].update(button_color=_both(BUTTON), button_hover_color=_both(BUTTON_HOVER))
    t["CTkSegmentedButton"].update(fg_color=_both(PANEL), selected_color=_both(BUTTON),
                                   selected_hover_color=_both(BUTTON_HOVER),
                                   unselected_color=_both(PANEL), unselected_hover_color=_both(ROW),
                                   text_color=_both(FG), text_color_disabled=_both(MUTED))
    t["CTkTextbox"].update(fg_color=_both(INSET), border_color=_both(LINE), text_color=_both(FG),
                           scrollbar_button_color=_both(BUTTON),
                           scrollbar_button_hover_color=_both(BUTTON_HOVER))
    t["DropdownMenu"].update(fg_color=_both(BUTTON), hover_color=_both(ACCENT), text_color=_both(FG))


def colour_title_bar(window):
    """Windows: a dark title bar in the window's colour (Windows 11; Windows 10
    gets the plain dark one). CustomTkinter only darkens its own CTk windows,
    and GLim's window is TkinterDnD's when drag and drop is available."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute

        def put(attr, value):
            v = ctypes.c_int(value)
            dwm(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        put(20, 1)                                       # DWMWA_USE_IMMERSIVE_DARK_MODE
        r, g, b = (int(WINDOW[i:i + 2], 16) for i in (1, 3, 5))
        put(35, r | g << 8 | b << 16)                    # DWMWA_CAPTION_COLOR (COLORREF)
        r, g, b = (int(FG[i:i + 2], 16) for i in (1, 3, 5))
        put(36, r | g << 8 | b << 16)                    # DWMWA_TEXT_COLOR
    except Exception:
        pass                        # cosmetic: never block startup

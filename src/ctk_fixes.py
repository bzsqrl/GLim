"""Fixes for CustomTkinter (5.2.2) behaviour. Call apply() once at startup.

CTkButton runs its command on mouse release only if its _mouse_inside flag is
set, but that flag is unreliable, so clicks were silently ignored:
- each click clears it (_on_leave, for the click animation) until 100 ms later,
  so the second of two quick clicks did nothing;
- it's only set by an <Enter> event, so when the pointer is already over the
  button without having entered it (a window over it just closed or opened,
  e.g. fullscreen / the output window, or focus came back to FFMaker), clicks did
  nothing until the mouse left the button and came back.
The fix asks where the pointer is at release instead: inside the button runs the
command (dragging off a button before letting go still cancels, as before).
The CTkSegmentedButton tabs are CTkButtons too."""
import tkinter

import customtkinter as ctk


def _pointer_over(widget, event):
    try:
        x, y = event.x_root, event.y_root
        wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
        return wx <= x < wx + widget.winfo_width() and wy <= y < wy + widget.winfo_height()
    except (AttributeError, tkinter.TclError):
        return True


def _on_release(self, event=None):
    if self._state == tkinter.DISABLED:
        return
    if event is not None and not _pointer_over(self, event):
        return
    # Click animation as in CTk: normal colour now, hover colour again 100 ms later.
    self._on_leave()
    self._click_animation_running = True
    self.after(100, self._click_animation)
    self._mouse_inside = True           # the pointer is over it, whatever <Enter> said
    if self._command is not None:
        self._command()


def apply():
    ctk.CTkButton._on_release = _on_release

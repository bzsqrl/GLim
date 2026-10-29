"""Remote control of the Studio tab over the network with OSC (e.g. TouchOSC).

Always on: GLim listens on UDP port PORT. A client is any address that has
sent it a message; GLim sends it the Studio tab's state, and again whenever
something changes, to FEEDBACK_PORT on that address (and to the port the message
came from, when that's another). A client that has sent nothing for
CLIENT_TIMEOUT_S gets no more (the TouchOSC layouts send /glim/ping every
second).

Addresses (all under /glim). Switches take 1 / 0 (no argument: toggle);
buttons act on a message with no argument or with a value of 1 (not on the 0 a
button sends when released):

  /play  /auto  /output  /fullscreen  /spout  /ndi  /ndi/720p   switches
  /restart  /prev  /next  /auto/seconds/up  /auto/seconds/down   buttons
  /auto/seconds <s>        the slideshow time, in seconds
  /param/<n> <0..1>        parameter slot n (1..SLOTS), as a fader's 0..1
  /ping                    answered with /pong <text>
  /sync                    send the whole state again

Feedback: the switches' states (1 / 0) and /param/<n> (0..1) on the same
addresses, and text for labels: /shader, /queue, /time, /auto/label,
/spout/name (Spout or Syphon), /params, /param/<n>/name and /param/<n>/value
(both "" for an unused slot).

Parameter slots follow the loaded shader's parameter list (as in the Studio
tab, without those kept as constants): one slot per value, so a colour takes
one per channel (R, G, B and A) and a point one per axis (X, Y). A slot's 0..1
covers the parameter's range, or its options for a choice; a switch is on from
0.5, and a trigger fires at 1."""
import queue
import socket
import threading
import time

PORT = 8000                 # GLim listens here (TouchOSC: the connection's send port)
FEEDBACK_PORT = 8001        # and replies here (TouchOSC: the connection's receive port)
PREFIX = "/glim"
SLOTS = 24                  # parameter slots in the TouchOSC layouts (enough for every
                            # shader in original-shaders)
TICK_MS = 30                # main thread: handle messages, send what changed
CLIENT_TIMEOUT_S = 30.0
ECHO_HOLD_S = 0.3           # don't send an address back to the client that's moving it
AUTO_STEPS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 45, 60, 90, 120, 180, 240, 300)

SWITCHES = ("/play", "/auto", "/output", "/fullscreen", "/spout", "/ndi", "/ndi/720p")


def local_ip():
    """This computer's address on the local network (what to enter in TouchOSC)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))     # sends nothing: only picks the interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _norm(ctl):
    """A RemoteControl's value as a fader's 0..1."""
    v = ctl.get()
    if ctl.kind == "toggle":
        return 1.0 if v else 0.0
    if ctl.kind == "trigger":
        return 0.0
    if ctl.kind == "choice":
        n = len(ctl.options)
        return round(v / (n - 1), 4) if n > 1 else 0.0
    lo, hi = ctl.bounds()
    return round(min(max((v - lo) / (hi - lo), 0.0), 1.0), 4) if hi != lo else 0.0


def _set_norm(ctl, x):
    x = min(max(float(x), 0.0), 1.0)
    if ctl.kind == "toggle":
        ctl.set(x >= 0.5)
    elif ctl.kind == "trigger":
        if x >= 0.5:
            ctl.set(True)
    elif ctl.kind == "choice":
        ctl.set(round(x * (len(ctl.options) - 1)))
    else:
        lo, hi = ctl.bounds()
        v = lo + x * (hi - lo)
        ctl.set(int(round(v)) if ctl.kind == "int" else v)


def _text(ctl):
    v = ctl.get()
    if ctl.kind == "toggle":
        return "on" if v else "off"
    if ctl.kind == "trigger":
        return "tap"
    if ctl.kind == "choice":
        return ctl.options[v] if 0 <= v < len(ctl.options) else ""
    if ctl.kind == "int":
        return str(int(round(v)))
    return f"{v:.3f}"


class OscRemote:
    def __init__(self, root, editor, log):
        """root: the Tk window (for after()); editor: the Studio tab's EditorPanel."""
        self.root, self.editor, self.log = root, editor, log
        self.server = None
        self._inbox = queue.SimpleQueue()     # (client, address, args) from the server thread
        self._clients = {}                    # ip -> {"ports", "seen", "sent", "held"}
        self._error_logged = False
        try:
            from pythonosc import dispatcher, osc_server
            d = dispatcher.Dispatcher()
            d.set_default_handler(self._received, needs_reply_address=True)
            self.server = osc_server.BlockingOSCUDPServer(("0.0.0.0", PORT), d)
        except ImportError:
            log("OSC remote control unavailable: python-osc is not installed.")
            return
        except OSError as e:
            log(f"OSC remote control unavailable: UDP port {PORT} is in use ({e}).")
            return
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        log(f"OSC remote control: {local_ip()}, port {PORT} (feedback to port {FEEDBACK_PORT}).")
        root.after(TICK_MS, self._tick)

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def _received(self, client, address, *args):      # the server's thread
        self._inbox.put((client, address, args))

    def _tick(self):
        if not self.server:
            return
        try:
            while True:
                client, address, args = self._inbox.get_nowait()
                self._handle(client, address, args)
        except queue.Empty:
            pass
        try:
            self._send_changes()
        except Exception as e:
            self._log_error(e)
        self.root.after(TICK_MS, self._tick)

    def _log_error(self, e):
        if not self._error_logged:          # once: a broken message may repeat many times a second
            self._error_logged = True
            self.log(f"OSC: {e}")

    # ── Incoming ─────────────────────────────────────────────────────────────

    def _handle(self, client, address, args):
        ip, port = client
        now = time.monotonic()
        c = self._clients.get(ip)
        if c is None:
            c = self._clients[ip] = {"sent": {}, "held": {}}
        c["seen"] = now
        c["ports"] = {FEEDBACK_PORT, port}
        if address == PREFIX + "/ping":
            self._send(c, ip, PREFIX + "/pong", f"GLim on {socket.gethostname()}")
            return
        if address == PREFIX + "/sync":
            c["sent"].clear()
            return
        # Hold back this address's feedback to this client while it's moving the
        # control, then send the actual state (e.g. a switch GLim didn't turn on).
        c["held"][address] = now
        c["sent"].pop(address, None)
        try:
            self._command(address[len(PREFIX):] if address.startswith(PREFIX + "/") else None, args)
        except Exception as e:
            self._log_error(f"{address}: {e}")

    def _command(self, tail, args):
        if tail is None or (args and not isinstance(args[0], (int, float, bool))):
            return                          # e.g. text where a number belongs
        value = float(args[0]) if args else None
        pressed = value is None or value >= 0.5      # buttons: not on release
        ed = self.editor
        if tail in SWITCHES:
            state = self._switches()
            on = (not state[tail]) if value is None else value >= 0.5
            {"/play": ed.set_playing, "/auto": ed.set_auto, "/output": ed.set_output_window,
             "/fullscreen": ed.set_fullscreen,
             "/spout": lambda on: ed.set_sending("spout", on),
             "/ndi": lambda on: ed.set_sending("ndi", on),
             "/ndi/720p": lambda on: ed.set_ndi_size("720p" if on else "1080p")}[tail](on)
        elif tail in ("/restart", "/prev", "/next"):
            if pressed:
                {"/restart": ed.restart, "/prev": lambda: ed.step_queue(-1),
                 "/next": lambda: ed.step_queue(1)}[tail]()
        elif tail == "/auto/seconds" and value is not None:
            ed.set_auto_seconds(value)
        elif tail in ("/auto/seconds/up", "/auto/seconds/down"):
            if pressed:
                s = ed.auto_seconds
                if tail.endswith("up"):
                    ed.set_auto_seconds(next((x for x in AUTO_STEPS if x > s), AUTO_STEPS[-1]))
                else:
                    ed.set_auto_seconds(next((x for x in reversed(AUTO_STEPS) if x < s), AUTO_STEPS[0]))
        elif tail.startswith("/param/") and value is not None:
            try:
                n = int(tail[len("/param/"):])
            except ValueError:
                return
            controls = ed.remote_controls()
            if 1 <= n <= min(SLOTS, len(controls)):
                _set_norm(controls[n - 1], value)

    # ── Feedback ─────────────────────────────────────────────────────────────

    def _switches(self):
        s = self.editor.remote_state()
        return {"/play": s["playing"], "/auto": s["auto"], "/output": s["output"],
                "/fullscreen": s["fullscreen"], "/spout": s["spout"], "/ndi": s["ndi"],
                "/ndi/720p": s["ndi_size"] == "720p"}

    def state(self):
        """Every feedback address and its current value."""
        s = self.editor.remote_state()
        out = {PREFIX + k: 1.0 if on else 0.0 for k, on in self._switches().items()}
        controls = self.editor.remote_controls()
        n = len(controls)
        out.update({
            PREFIX + "/shader": s["shader"] or "no shader loaded",
            PREFIX + "/queue": s["queue"],
            PREFIX + "/time": f"{s['time']:.1f} s",
            PREFIX + "/auto/label": f"{s['auto_seconds']:g} s",
            PREFIX + "/spout/name": s["sender"],
            PREFIX + "/params": (f"{n} parameters" if n <= SLOTS else
                                 f"{n} parameters: the first {SLOTS} are here") if n != 1 else "1 parameter",
        })
        for i in range(SLOTS):
            ctl = controls[i] if i < n else None
            base = f"{PREFIX}/param/{i + 1}"
            out[base] = _norm(ctl) if ctl else 0.0
            out[base + "/name"] = ctl.name() if ctl else ""
            out[base + "/value"] = _text(ctl) if ctl else ""
        return out

    def _send_changes(self):
        now = time.monotonic()
        for ip in [ip for ip, c in self._clients.items() if now - c["seen"] > CLIENT_TIMEOUT_S]:
            del self._clients[ip]
        if not self._clients:
            return
        state = self.state()
        for ip, c in self._clients.items():
            sent, held = c["sent"], c["held"]
            for address, value in state.items():
                if sent.get(address) == value or now - held.get(address, -1e9) < ECHO_HOLD_S:
                    continue
                if self._send(c, ip, address, value):
                    sent[address] = value

    def _send(self, c, ip, address, value):
        from pythonosc.osc_message_builder import OscMessageBuilder
        b = OscMessageBuilder(address)
        b.add_arg(value, "s" if isinstance(value, str) else "f")
        data = b.build().dgram
        try:
            for port in c["ports"]:
                self.server.socket.sendto(data, (ip, port))
            return True
        except OSError:
            return False                    # e.g. the network went away: try again next tick

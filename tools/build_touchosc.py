"""Generate the TouchOSC layouts for GLim's OSC remote control (src/osc_remote.py):

    venv\\Scripts\\python tools\\build_touchosc.py

writes touchosc/GLim_desktop.tosc (one landscape page, for TouchOSC on a
computer or tablet) and touchosc/GLim_phone.tosc (portrait pages for tall
phones such as the Pixel 7a: CONTROL, then the parameters 8 to a page).

Both send and receive on all of TouchOSC's connections, so any one can be
used: set it to UDP, host = the GLim computer's address, send port 8000,
receive port 8001 (osc_remote.PORT / FEEDBACK_PORT). Other enabled connections
get the /glim messages too, which other apps ignore.

Switches and faders take GLim's feedback on their own addresses (TouchOSC
updates them without sending anything back). The root script shows the text
feedback (shader, queue, time, parameter names and values), hides unused
parameter slots, and sends /glim/ping every second: GLim answers, which
keeps the feedback coming and shows "connected" on the layout. On load, and
after the connection comes back, it asks for the whole state (/glim/sync).

A .tosc file is zlib-compressed XML (the format of osc-vlc's
build_touchosc_layout.py, which is in use with TouchOSC)."""
import sys
import uuid
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import osc_remote as R                                                 # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "touchosc"
CONNECTIONS = range(1, 11)          # all of TouchOSC's connections (numbered 1-10)
P = R.PREFIX

# GLim's colours (src/theme.py), as TouchOSC's 0..1 RGBA
def rgb(hex_, a=1.0):
    return tuple(round(int(hex_[i:i + 2], 16) / 255, 3) for i in (1, 3, 5)) + (a,)


BG = rgb("#0f1217")
PANEL = rgb("#171b22")
GREY = rgb("#3a4453")
ACCENT = rgb("#5b5bd6")
TEXT = rgb("#e6e9ef")
DIM = rgb("#8b95a5")


# ── XML ────────────────────────────────────────────────────────────────────────

def cdata(s):
    return f"<![CDATA[{s}]]>"


def prop(ptype, key, value):
    if ptype == "r":
        inner = "".join(f"<{k}>{int(round(v))}</{k}>" for k, v in zip("xywh", value))
    elif ptype == "c":
        inner = "".join(f"<{k}>{v}</{k}>" for k, v in zip("rgba", value))
    elif ptype == "s":
        inner = cdata(value)
    elif ptype == "b":
        inner = str(int(bool(value)))
    else:
        inner = str(value)
    return f"<property type='{ptype}'><key>{cdata(key)}</key><value>{inner}</value></property>"


def value(key, default):
    d = cdata(default) if isinstance(default, str) else default
    return (f"<value><key>{cdata(key)}</key><locked>0</locked>"
            f"<lockedDefaultCurrent>0</lockedDefaultCurrent>"
            f"<default>{d}</default><defaultPull>0</defaultPull></value>")


def partial(ptype, conversion, val, scale=(0, 1)):
    return (f"<partial><type>{ptype}</type><conversion>{conversion}</conversion>"
            f"<value>{cdata(val)}</value>"
            f"<scaleMin>{scale[0]}</scaleMin><scaleMax>{scale[1]}</scaleMax></partial>")


def mask():
    """TouchOSC's connection mask: connection 1 is the rightmost digit."""
    return "".join("1" if i in CONNECTIONS else "0" for i in range(10, 0, -1))


def osc(path, args, trigger="ANY", receive=False):
    """One OSC message on CONNECTIONS. receive: incoming messages on `path` set
    the control's value (without sending it back)."""
    return ("<osc><enabled>1</enabled><send>1</send>"
            f"<receive>{int(receive)}</receive><feedback>0</feedback><noDuplicates>0</noDuplicates>"
            f"<connections>{mask()}</connections>"
            f"<triggers><trigger><var>{cdata('x')}</var>"
            f"<condition>{trigger}</condition></trigger></triggers>"
            f"<path>{partial('CONSTANT', 'STRING', path)}</path>"
            f"<arguments>{''.join(args)}</arguments></osc>")


def node(ntype, props, values=(), messages=(), children=()):
    return (f"<node ID='{uuid.uuid4()}' type='{ntype}'>"
            f"<properties>{''.join(props)}</properties>"
            f"<values>{''.join(values)}</values>"
            f"<messages>{''.join(messages)}</messages>"
            f"<children>{''.join(children)}</children></node>")


# ── Controls ───────────────────────────────────────────────────────────────────
# Each builder returns XML; Layout keeps the names the root script needs.

class Layout:
    def __init__(self):
        self.names = set()
        self.labels = {}            # feedback address -> label names showing its text
        self.slots = {}             # /param/<n>/name -> names hidden while that slot is unused
        self.align = {}             # label name -> LEFT / RIGHT (the script sets it)
        self.status = []            # labels showing the connection state

    def _name(self, name):
        assert name not in self.names, name
        self.names.add(name)
        return name

    def label(self, name, frame, text, size=18, color=TEXT, background=False, align=None, feed=None):
        """feed: the feedback address whose text this label shows."""
        if align:
            self.align[name] = align
        if feed:
            self.labels.setdefault(P + feed, []).append(name)
        return node("LABEL", [
            prop("s", "name", self._name(name)),
            prop("r", "frame", frame),
            prop("c", "color", PANEL),
            prop("b", "background", background),
            prop("b", "outline", False),
            prop("b", "interactive", False),
            prop("c", "textColor", color),
            prop("i", "textSize", size),
        ], [value("text", text)])

    def caption(self, name, frame, text, size=15):
        return self.label(name, frame, text, size=size, color=DIM, align="LEFT")

    def switch(self, name, frame, text, address, size=20, feed=None):
        """A toggle button: sends 1 / 0, and shows GLim's state on the same address."""
        btn = node("BUTTON", [
            prop("s", "name", self._name(name)),
            prop("r", "frame", frame),
            prop("c", "color", ACCENT),
            prop("i", "buttonType", 1),
        ], [value("x", 0)], [osc(P + address, [partial("VALUE", "FLOAT", "x")], receive=True)])
        return btn + self.label(name + "_lbl", frame, text, size=size, feed=feed)

    def push(self, name, frame, text, address, size=20):
        """A momentary button: sends `address` with no argument when pressed."""
        btn = node("BUTTON", [
            prop("s", "name", self._name(name)),
            prop("r", "frame", frame),
            prop("c", "color", GREY),
            prop("i", "buttonType", 0),
        ], [value("x", 0)], [osc(P + address, [], trigger="RISE")])
        return btn + self.label(name + "_lbl", frame, text, size=size)

    def fader(self, name, frame, address):
        return node("FADER", [
            prop("s", "name", self._name(name)),
            prop("r", "frame", frame),
            prop("c", "color", ACCENT),
            prop("i", "orientation", 1),            # horizontal, left to right
        ], [value("x", 0)], [osc(P + address, [partial("VALUE", "FLOAT", "x")], receive=True)])

    def slot(self, n, frame, size=15):
        """Parameter slot n: its name and value above a fader, all hidden while unused."""
        x, y, w, h = frame
        top = size + 13
        names = (f"p{n}_name", f"p{n}_value", f"p{n}_fader")
        self.slots[f"{P}/param/{n}/name"] = list(names)
        return (self.label(names[0], (x, y, w * 0.64, top), "", size=size, align="LEFT",
                           feed=f"/param/{n}/name")
                + self.label(names[1], (x + w * 0.64, y, w * 0.36, top), "", size=size, color=DIM,
                             align="RIGHT", feed=f"/param/{n}/value")
                + self.fader(names[2], (x, y + top + 2, w, h - top - 2), f"/param/{n}"))

    def status_label(self, name, frame, size=14):
        self.status.append(name)
        return self.label(name, frame, "not connected", size=size, color=DIM, align="LEFT")

    def script(self):
        return ROOT_SCRIPT % {
            "conn": "{ " + ", ".join("true" if i in CONNECTIONS else "false" for i in range(1, 11)) + " }",
            "port": R.PORT, "feedback": R.FEEDBACK_PORT,
            "labels": lua_map(self.labels), "slots": lua_map(self.slots),
            "align": "{ " + ", ".join(f"['{k}'] = AlignH.{v}" for k, v in sorted(self.align.items())) + " }",
            "status": lua_list(self.status),
        }


def lua_list(items):
    return "{ " + ", ".join(f"'{s}'" for s in items) + " }"


def lua_map(d):
    return "{\n" + "".join(f"  ['{k}'] = {lua_list(v)},\n" for k, v in sorted(d.items())) + "}"


def row(y, h, x0, x1, n, gap):
    """Split a horizontal strip into n equal frames."""
    w = (x1 - x0 - gap * (n - 1)) / n
    return [(x0 + i * (w + gap), y, w, h) for i in range(n)]


ROOT_SCRIPT = r"""
-- GLim remote control (generated by GLim's tools/build_touchosc.py).
-- Any connection: host = the GLim computer, send port %(port)d, receive
-- port %(feedback)d.
local CONN = %(conn)s
local PING_MS = 1000
local LOST_MS = 3500
local LABELS = %(labels)s
local SLOTS = %(slots)s
local ALIGN = %(align)s
local STATUS = %(status)s
local NOT_CONNECTED = 'not connected: set a connection to GLim\'s address, ' ..
  'send port %(port)d, receive port %(feedback)d'
local lastPing, lastPong, host, shown = -PING_MS, -1, '', nil
local cache = {}

local function ctl(name)
  local c = cache[name]
  if c == nil then
    c = root:findByName(name, true) or false
    cache[name] = c
    if c and ALIGN[name] then c.properties.textAlignH = ALIGN[name] end
  end
  return c
end

local function setText(name, text)
  local c = ctl(name)
  if c then c.values.text = text end
end

local function sync()
  sendOSC('/glim/sync', CONN)
end

function init()
  for name, _ in pairs(ALIGN) do ctl(name) end
  for _, names in pairs(SLOTS) do
    for _, name in ipairs(names) do
      local c = ctl(name)
      if c then c.properties.visible = false end
    end
  end
  sync()
end

function update()
  local now = getMillis()
  if now - lastPing < PING_MS then return end
  lastPing = now
  sendOSC('/glim/ping', CONN)
  local ok = lastPong >= 0 and now - lastPong < LOST_MS
  if ok ~= shown then
    shown = ok
    local text = ok and ('connected: ' .. host) or NOT_CONNECTED
    for _, name in ipairs(STATUS) do setText(name, text) end
  end
end

function onReceiveOSC(message, connections)
  local path = message[1]
  local arg = message[2] and message[2][1]
  local text = arg and tostring(arg.value) or ''
  if path == '/glim/pong' then
    local now = getMillis()
    if lastPong < 0 or now - lastPong >= LOST_MS then
      shown = nil                       -- show "connected" at the next update
      if lastPong >= 0 then sync() end  -- back after a gap: get everything again
    end
    lastPong, host = now, text
    return
  end
  local names = LABELS[path]
  if names then
    for _, name in ipairs(names) do setText(name, text) end
  end
  local slot = SLOTS[path]
  if slot then
    for _, name in ipairs(slot) do
      local c = ctl(name)
      if c then c.properties.visible = text ~= '' end
    end
  end
end
"""


def root_node(lay, name, frame, children):
    return node("GROUP", [
        prop("s", "name", name),
        prop("r", "frame", frame),
        prop("c", "color", BG),
        prop("b", "background", True),
        prop("s", "script", lay.script()),
    ], children=children)


def document(root):
    xml = f"<?xml version='1.0' encoding='UTF-8'?><lexml version='3'>{root}</lexml>"
    return zlib.compress(xml.encode("utf-8"))


# ── Desktop: one landscape page ────────────────────────────────────────────────

def desktop():
    W, H, M, GAP = 1280, 800, 16, 12
    lay = Layout()
    c = [
        lay.label("shader", (M, 14, 820, 54), "GLim", size=28, background=True, align="LEFT",
                  feed="/shader"),
        lay.label("queue", (M + 830, 14, 220, 54), "", size=20, background=True, feed="/queue"),
        lay.label("time", (M + 1060, 14, W - 2 * M - 1060, 54), "", size=20, background=True,
                  feed="/time"),
        lay.status_label("status", (M, 74, W - 2 * M, 28)),
    ]
    x0, x1 = M, 500
    c.append(lay.caption("cap_transport", (x0, 112, 300, 26), "TRANSPORT"))
    play, restart, prev, nxt = row(140, 96, x0, x1, 4, GAP)
    c += [lay.switch("play", play, "PLAY", "/play"),
          lay.push("restart", restart, "RESTART", "/restart"),
          lay.push("prev", prev, "<<  PREV", "/prev"),
          lay.push("next", nxt, "NEXT  >>", "/next")]
    c.append(lay.caption("cap_slideshow", (x0, 252, 300, 26), "SLIDESHOW"))
    auto, down, secs, up = row(280, 80, x0, x1, 4, GAP)
    c += [lay.switch("auto", auto, "AUTO", "/auto"),
          lay.push("auto_down", down, "-", "/auto/seconds/down", size=30),
          lay.label("auto_secs", secs, "10 s", size=22, background=True, feed="/auto/label"),
          lay.push("auto_up", up, "+", "/auto/seconds/up", size=30)]
    c.append(lay.caption("cap_output", (x0, 376, 300, 26), "OUTPUT"))
    out, full = row(404, 80, x0, x1, 2, GAP)
    c += [lay.switch("output", out, "OUTPUT WINDOW", "/output"),
          lay.switch("fullscreen", full, "FULLSCREEN", "/fullscreen")]
    c.append(lay.caption("cap_send", (x0, 500, 300, 26), "SEND"))
    spout, ndi, small = row(528, 80, x0, x1, 3, GAP)
    c += [lay.switch("spout", spout, "Spout", "/spout", feed="/spout/name"),
          lay.switch("ndi", ndi, "NDI", "/ndi"),
          lay.switch("ndi720", small, "NDI 720p", "/ndi/720p")]
    c.append(lay.label("hint", (x0, 640, x1 - x0, 60),
                       f"TouchOSC: any connection, send port {R.PORT}, receive port {R.FEEDBACK_PORT}",
                       size=13, color=DIM, align="LEFT"))

    px0, px1 = 524, W - M
    c.append(lay.caption("cap_params", (px0, 112, 300, 26), "PARAMETERS"))
    c.append(lay.label("params", (px0 + 300, 112, px1 - px0 - 300, 26), "", size=15, color=DIM,
                       align="RIGHT", feed="/params"))
    cols, rows_ = 3, R.SLOTS // 3
    pitch = (H - M - 140) / rows_
    for col, (x, _, w, _) in enumerate(row(0, 0, px0, px1, cols, GAP)):
        for r in range(rows_):
            n = col * rows_ + r + 1
            c.append(lay.slot(n, (x, 140 + r * pitch, w, pitch - 8)))
    return document(root_node(lay, "glim_desktop", (0, 0, W, H), c))


# ── Phone: portrait pages ──────────────────────────────────────────────────────
# 540 x 1110 units: the shape left on a 20:9 phone (Pixel 7a) once the status
# bar, gesture bar and TouchOSC's toolbar are taken off; TouchOSC scales to fit.

def phone():
    W, H, TAB, M, GAP = 540, 1050, 60, 12, 10
    lay = Layout()

    def header(p):
        return [
            lay.label(p + "shader", (M, 10, W - 2 * M, 56), "GLim", size=24, background=True,
                      align="LEFT", feed="/shader"),
            lay.label(p + "queue", (M, 72, 250, 34), "", size=17, background=True, feed="/queue"),
            lay.label(p + "time", (M + 260, 72, W - 2 * M - 260, 34), "", size=17, background=True,
                      feed="/time"),
            lay.status_label(p + "status", (M, H - 40, W - 2 * M, 30), size=12),
        ]

    def page(tab, children):
        return node("GROUP", [
            prop("s", "name", "page_" + tab.replace(" ", "")),
            prop("r", "frame", (0, TAB, W, H)),
            prop("c", "color", BG),
            prop("b", "background", True),
            prop("s", "tabLabel", tab),
            prop("c", "tabColorOff", PANEL),
            prop("c", "tabColorOn", ACCENT),
            prop("c", "textColorOff", DIM),
            prop("c", "textColorOn", TEXT),
        ], children=children)

    x0, x1 = M, W - M
    c = header("c_")
    c.append(lay.caption("cap_transport", (x0, 118, 300, 26), "TRANSPORT"))
    side = 130
    c += [lay.push("prev", (x0, 148, side, 130), "<<\nPREV", "/prev", size=22),
          lay.switch("play", (x0 + side + GAP, 148, x1 - x0 - 2 * (side + GAP), 130), "PLAY", "/play",
                     size=26),
          lay.push("next", (x1 - side, 148, side, 130), "NEXT\n>>", "/next", size=22),
          lay.push("restart", (x0, 288, x1 - x0, 80), "RESTART", "/restart", size=22)]
    c.append(lay.caption("cap_slideshow", (x0, 388, 300, 26), "SLIDESHOW"))
    auto, down, secs, up = row(418, 96, x0, x1, 4, GAP)
    c += [lay.switch("auto", auto, "AUTO", "/auto", size=22),
          lay.push("auto_down", down, "-", "/auto/seconds/down", size=34),
          lay.label("auto_secs", secs, "10 s", size=24, background=True, feed="/auto/label"),
          lay.push("auto_up", up, "+", "/auto/seconds/up", size=34)]
    c.append(lay.caption("cap_output", (x0, 534, 300, 26), "OUTPUT"))
    out, full = row(564, 96, x0, x1, 2, GAP)
    c += [lay.switch("output", out, "OUTPUT\nWINDOW", "/output", size=22),
          lay.switch("fullscreen", full, "FULL\nSCREEN", "/fullscreen", size=22)]
    c.append(lay.caption("cap_send", (x0, 680, 300, 26), "SEND"))
    spout, ndi, small = row(710, 96, x0, x1, 3, GAP)
    c += [lay.switch("spout", spout, "Spout", "/spout", size=22, feed="/spout/name"),
          lay.switch("ndi", ndi, "NDI", "/ndi", size=22),
          lay.switch("ndi720", small, "NDI\n720p", "/ndi/720p", size=22)]
    pages = [page("CONTROL", c)]

    per_page = 8
    for first in range(1, R.SLOTS + 1, per_page):
        p = f"s{first}_"
        last = first + per_page - 1
        c = header(p)
        c.append(lay.caption(p + "cap", (x0, 116, 260, 28), f"PARAMETERS {first}-{last}"))
        c.append(lay.label(p + "params", (x0 + 260, 116, x1 - x0 - 260, 28), "", size=14, color=DIM,
                           align="RIGHT", feed="/params"))
        top, bottom = 150, H - 50
        pitch = (bottom - top) / per_page
        for k in range(per_page):
            c.append(lay.slot(first + k, (x0, top + k * pitch, x1 - x0, pitch - 10), size=18))
        pages.append(page(f"{first}-{last}", c))

    pager = node("PAGER", [
        prop("s", "name", "pages"),
        prop("r", "frame", (0, 0, W, TAB + H)),
        prop("c", "color", BG),
        prop("b", "tabbar", True),
        prop("i", "tabbarSize", TAB),
        prop("b", "tabbarDoubleTap", False),
        prop("b", "tabLabels", True),
        prop("i", "textSizeOff", 18),
        prop("i", "textSizeOn", 20),
    ], [value("page", 0)], children=pages)
    return document(root_node(lay, "glim_phone", (0, 0, W, TAB + H), [pager]))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, data in (("GLim_desktop.tosc", desktop()), ("GLim_phone.tosc", phone())):
        (OUT / name).write_bytes(data)
        print(f"wrote {OUT / name}")

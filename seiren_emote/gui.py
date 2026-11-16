"""GTK4 desktop app for the Razer Seiren Emote LED display."""
import queue
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import images  # noqa: E402
from .device import WIDTH, HEIGHT  # noqa: E402

APP_ID = "io.github.seiren_emote_linux"
SWATCHES = ["ffb400", "ff0028", "00dc3c", "00dcdc",
            "0078ff", "c800ff", "ff66cc", "ffffff", "000000"]


# --------------------------------------------------------------------------
class DeviceWorker(threading.Thread):
    """Talks to the mic off the UI thread. Keeps only the latest frame, so a
    fast drag or animation never builds up a backlog. Retries the connection
    every 2s, which also handles unplug/replug."""

    def __init__(self, on_status):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self.on_status = on_status
        self.dev = None
        self.last_pixels = None
        self.last_brightness = None
        self.rotate, self.flip = 0, False

    def push_pixels(self, px):
        self.q.put(("pixels", [list(r) for r in px]))

    def push_brightness(self, v):
        self.q.put(("brightness", int(v)))

    def push_orientation(self, rotate, flip):
        self.q.put(("orientation", (rotate, flip)))

    def _status(self, text, ok):
        GLib.idle_add(self.on_status, text, ok)

    def _connect(self):
        from .device import Emote, DeviceNotFound, CommandFailed
        import usb.core
        try:
            self.dev = Emote(reconnect_timeout=3, rotate=self.rotate, flip=self.flip)
            fw = self.dev.firmware()
            self._status(f"Connected · fw {fw}", True)
            # re-apply state after (re)connect
            if self.last_brightness is not None:
                self.dev.set_brightness(self.last_brightness)
            if self.last_pixels is not None:
                self.dev.set_pixels(self.last_pixels)
        except DeviceNotFound:
            self.dev = None
            self._status("Mic not found", False)
        except usb.core.USBError as e:
            self.dev = None
            if e.errno == 13:
                self._status("No permission: install udev rule", False)
            else:
                self._status(f"USB error: {e}", False)
        except CommandFailed as e:  # e.g. still busy right after plug-in; retry later
            self.dev = None
            self._status(f"Mic not ready: {e}", False)

    def run(self):
        self._connect()
        while True:
            try:
                items = [self.q.get(timeout=2)]
            except queue.Empty:
                if self.dev is None:
                    self._connect()
                continue
            while not self.q.empty():  # coalesce: newest wins
                items.append(self.q.get_nowait())
            for kind, val in items:
                if kind == "pixels":
                    self.last_pixels = val
                elif kind == "brightness":
                    self.last_brightness = val
                else:
                    self.rotate, self.flip = val
            if self.dev is None:
                self._connect()
                continue
            kinds = {k for k, _ in items}
            try:
                if "brightness" in kinds:
                    self.dev.set_brightness(self.last_brightness)
                if "orientation" in kinds:
                    self.dev.rotate, self.dev.flip = self.rotate, self.flip
                if kinds & {"pixels", "orientation"} and self.last_pixels is not None:
                    self.dev.set_pixels(self.last_pixels)
            except Exception as e:  # unplugged mid-write, etc.
                self.dev = None
                self._status(f"Lost connection ({e.__class__.__name__})", False)


# --------------------------------------------------------------------------
class EmoteWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Seiren Emote")
        self.set_default_size(720, 440)

        state = images.load_state()
        self.pixels = [[tuple(c) for c in row] for row in state.get("pixels", images.blank())]
        self.color = (255, 180, 0)
        self.erasing = False
        self.frames = []
        self.frame_idx = 0
        self.anim_source = None

        self._install_css()

        # header
        header = Gtk.HeaderBar()
        self.status = Gtk.Label(label="Connecting…")
        self.status.add_css_class("dim-label")
        header.pack_end(self.status)
        self.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18,
                       margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        self.set_child(root)

        # canvas
        self.canvas = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.canvas.set_size_request(320, 320)
        self.canvas.set_draw_func(self._draw)
        drag = Gtk.GestureDrag(button=0)
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        self.canvas.add_controller(drag)
        root.append(self.canvas)

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        side.set_size_request(300, -1)
        root.append(side)

        # color
        side.append(self._heading("Color"))
        color_row = Gtk.Box(spacing=6)
        self.color_btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
        self.color_btn.set_rgba(self._rgba(self.color))
        self.color_btn.connect("notify::rgba", self._color_changed)
        color_row.append(self.color_btn)
        for hexc in SWATCHES:
            b = Gtk.Button()
            b.add_css_class("swatch")
            b.set_size_request(24, 24)
            b.set_valign(Gtk.Align.CENTER)
            b.add_css_class(f"sw-{hexc}")
            b.set_tooltip_text(f"#{hexc}")
            b.connect("clicked", lambda _b, h=hexc: self.color_btn.set_rgba(
                self._rgba(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))))
            color_row.append(b)
        side.append(color_row)
        hint = Gtk.Label(label="Left-click to paint, right-click to erase", xalign=0)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        side.append(hint)

        # presets
        side.append(self._heading("Presets"))
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                           max_children_per_line=4, column_spacing=6, row_spacing=6)
        for name in images.PRESETS:
            b = Gtk.Button(label=name.capitalize())
            b.connect("clicked", lambda _b, n=name: self._set_pixels(images.preset(n)))
            flow.append(b)
        side.append(flow)

        # actions
        side.append(self._heading("Image"))
        act = Gtk.Box(spacing=6, homogeneous=True)
        for label, cb in (("Load…", self._load), ("Save…", self._save),
                          ("Fill", self._fill), ("Clear", self._clear)):
            b = Gtk.Button(label=label)
            b.connect("clicked", cb)
            act.append(b)
        side.append(act)

        self.anim_box = Gtk.Box(spacing=6)
        self.anim_label = Gtk.Label(xalign=0, hexpand=True)
        self.play_btn = Gtk.ToggleButton(label="Play")
        self.play_btn.connect("toggled", self._play_toggled)
        self.anim_box.append(self.anim_label)
        self.anim_box.append(self.play_btn)
        self.anim_box.set_visible(False)
        side.append(self.anim_box)

        # brightness
        side.append(self._heading("Brightness"))
        self.bright = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.bright.set_value(state.get("brightness", 255))
        self.bright.set_draw_value(False)
        self.bright.connect("value-changed", self._brightness_changed)
        side.append(self.bright)

        # orientation, e.g. for a mic mounted upside down
        side.append(self._heading("Orientation"))
        orient_row = Gtk.Box(spacing=12)
        orient_row.append(Gtk.Label(label="Rotate"))
        self.rotate_dd = Gtk.DropDown.new_from_strings(["0°", "90°", "180°", "270°"])
        self.rotate_dd.set_selected(state.get("rotate", 0) // 90 % 4)
        self.rotate_dd.connect("notify::selected", self._orientation_changed)
        orient_row.append(self.rotate_dd)
        self.mirror = Gtk.CheckButton(label="Mirror", active=state.get("flip", False))
        self.mirror.connect("toggled", self._orientation_changed)
        orient_row.append(self.mirror)
        side.append(orient_row)

        # device worker
        self.worker = DeviceWorker(self._on_status)
        self.worker.rotate = state.get("rotate", 0)
        self.worker.flip = state.get("flip", False)
        if "brightness" in state:
            self.worker.last_brightness = state["brightness"]
        self.worker.last_pixels = self.pixels
        self.worker.start()

    # ---- helpers --------------------------------------------------------
    def _install_css(self):
        css = ".swatch { min-width: 24px; min-height: 24px; padding: 0; margin: 0; "
        css += "border: 1px solid alpha(currentColor, 0.25); "
        css += "border-radius: 50%; background-image: none; }\n"
        css += "".join(f".sw-{h} {{ background-color: #{h}; }}\n" for h in SWATCHES)
        css += ".heading { font-weight: bold; }"
        prov = Gtk.CssProvider()
        if hasattr(prov, "load_from_string"):
            prov.load_from_string(css)
        else:
            prov.load_from_data(css.encode(), -1)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    @staticmethod
    def _heading(text):
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.add_css_class("heading")
        return lbl

    @staticmethod
    def _rgba(c):
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue, rgba.alpha = c[0] / 255, c[1] / 255, c[2] / 255, 1
        return rgba

    def _on_status(self, text, ok):
        self.status.set_text(text)
        return False

    # ---- canvas ---------------------------------------------------------
    def _geom(self):
        w, h = self.canvas.get_width(), self.canvas.get_height()
        cell = min(w, h) / WIDTH
        return cell, (w - cell * WIDTH) / 2, (h - cell * HEIGHT) / 2

    def _draw(self, _area, cr, _w, _h):
        cell, ox, oy = self._geom()
        cr.set_source_rgb(0.08, 0.08, 0.08)
        cr.rectangle(ox, oy, cell * WIDTH, cell * HEIGHT)
        cr.fill()
        gap = max(1.5, cell * 0.08)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                r, g, b = self.pixels[y][x]
                if (r, g, b) == (0, 0, 0):
                    cr.set_source_rgb(0.16, 0.16, 0.16)
                else:
                    cr.set_source_rgb(r / 255, g / 255, b / 255)
                cr.rectangle(ox + x * cell + gap / 2, oy + y * cell + gap / 2,
                             cell - gap, cell - gap)
                cr.fill()

    def _paint_at(self, px, py):
        cell, ox, oy = self._geom()
        x, y = int((px - ox) // cell), int((py - oy) // cell)
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            c = (0, 0, 0) if self.erasing else self.color
            if self.pixels[y][x] != c:
                self.pixels[y][x] = c
                self._changed()

    def _drag_begin(self, gesture, x, y):
        self._stop_anim()
        self.erasing = gesture.get_current_button() == 3
        self._paint_at(x, y)

    def _drag_update(self, gesture, dx, dy):
        ok, sx, sy = gesture.get_start_point()
        if ok:
            self._paint_at(sx + dx, sy + dy)

    def _changed(self, save=True):
        self.canvas.queue_draw()
        self.worker.push_pixels(self.pixels)
        if save:
            images.save_state(pixels=self.pixels)

    def _set_pixels(self, px):
        self._stop_anim()
        self.frames = []
        self.anim_box.set_visible(False)
        self.pixels = [[tuple(c) for c in row] for row in px]
        self._changed()

    # ---- controls -------------------------------------------------------
    def _color_changed(self, btn, _pspec):
        c = btn.get_rgba()
        self.color = (round(c.red * 255), round(c.green * 255), round(c.blue * 255))

    def _fill(self, _b):
        self._set_pixels([[self.color] * WIDTH for _ in range(HEIGHT)])

    def _clear(self, _b):
        self._set_pixels(images.blank())

    def _brightness_changed(self, scale):
        v = int(scale.get_value())
        self.worker.push_brightness(v)
        images.save_state(brightness=v)

    def _orientation_changed(self, *_):
        rotate, flip = self.rotate_dd.get_selected() * 90, self.mirror.get_active()
        self.worker.push_orientation(rotate, flip)
        images.save_state(rotate=rotate, flip=flip)

    def _file_filter(self):
        f = Gtk.FileFilter(name="Images")
        for pat in ("*.png", "*.gif", "*.jpg", "*.jpeg", "*.webp", "*.bmp"):
            f.add_pattern(pat)
            f.add_pattern(pat.upper())
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(f)
        return store

    def _load(self, _b):
        dlg = Gtk.FileDialog(title="Load image", filters=self._file_filter())
        dlg.open(self, None, self._load_done)

    def _load_done(self, dlg, res):
        try:
            path = dlg.open_finish(res).get_path()
        except GLib.Error:
            return  # cancelled
        try:
            frames = images.load_image(path)
        except Exception as e:
            self._on_status(f"Couldn't load image: {e}", False)
            return
        if len(frames) == 1:
            self._set_pixels(frames[0][0])
            return
        self._set_pixels(frames[0][0])
        self.frames = frames
        images.save_state(image_path=path)
        self.anim_label.set_text(f"Animation · {len(frames)} frames")
        self.anim_box.set_visible(True)
        self.play_btn.set_active(True)

    def _save(self, _b):
        dlg = Gtk.FileDialog(title="Save as PNG", initial_name="emote.png")
        dlg.save(self, None, self._save_done)

    def _save_done(self, dlg, res):
        try:
            path = dlg.save_finish(res).get_path()
        except GLib.Error:
            return
        images.save_png(self.pixels, path)

    # ---- animation ------------------------------------------------------
    def _play_toggled(self, btn):
        if btn.get_active() and self.frames:
            self.play_btn.set_label("Stop")
            self.frame_idx = 0
            self._next_frame()
        else:
            self.play_btn.set_label("Play")
            if self.anim_source:
                GLib.source_remove(self.anim_source)
                self.anim_source = None

    def _next_frame(self):
        px, dur = self.frames[self.frame_idx]
        self.pixels = [[tuple(c) for c in row] for row in px]
        self._changed(save=False)
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        self.anim_source = GLib.timeout_add(int(dur * 1000), self._next_frame)
        return False

    def _stop_anim(self):
        if self.play_btn.get_active():
            self.play_btn.set_active(False)


class EmoteApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = self.props.active_window or EmoteWindow(self)
        win.present()


def main():
    return EmoteApp().run(sys.argv[:1])


if __name__ == "__main__":
    main()

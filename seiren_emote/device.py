"""Low-level driver for the Razer Seiren Emote LED display (USB 1532:0F1B).

The Emote shows up as two USB devices: 1532:0524 (the audio interface, which
works out of the box) and 1532:0F1B (the 8x8 LED display controller). The
display controller speaks the standard 90-byte Razer feature-report protocol
over control transfers. See PROTOCOL.md for details.
"""
import time

import usb.core
import usb.util

VID, PID, IFACE = 0x1532, 0x0F1B, 0
TRANSACTION_ID = 0xFF
DISPLAY_LED = 0x04          # LED zone that drives the 8x8 display
WIDTH = HEIGHT = 8          # physical display
CTRL_ROWS, CTRL_COLS = 4, 16  # how the controller addresses it

STATUS = {0: "new", 1: "busy", 2: "ok", 3: "failure", 4: "timeout", 5: "unsupported"}

Color = tuple  # (r, g, b)


class DeviceNotFound(Exception):
    pass


class CommandFailed(Exception):
    pass


def _find():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is not None:
        try:
            if dev.is_kernel_driver_active(IFACE):
                dev.detach_kernel_driver(IFACE)
        except (NotImplementedError, usb.core.USBError):
            pass
    return dev


def build_report(cls, cid, size, args=b""):
    r = bytearray(90)
    r[1], r[5], r[6], r[7] = TRANSACTION_ID, size, cls, cid
    r[8:8 + len(args)] = bytes(args)
    crc = 0
    for b in r[2:88]:
        crc ^= b
    r[88] = crc
    return r


def grid_to_rows(pixels):
    """8x8 pixels (pixels[y][x], y=0 is the TOP row, like an image) ->
    4 controller rows of 16. LED 0 is bottom-left, filling left->right,
    bottom->top."""
    rows = [[(0, 0, 0)] * CTRL_COLS for _ in range(CTRL_ROWS)]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            idx = (HEIGHT - 1 - y) * WIDTH + x
            rows[idx // CTRL_COLS][idx % CTRL_COLS] = tuple(pixels[y][x])
    return rows


class Emote:
    def __init__(self, reconnect_timeout=10.0):
        self.reconnect_timeout = reconnect_timeout
        self.dev = _find()
        if self.dev is None:
            raise DeviceNotFound("Razer Seiren Emote display (1532:0F1B) not found")

    def close(self):
        if self.dev is not None:
            usb.util.dispose_resources(self.dev)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- transport ---------------------------------------------------------
    def _ctrl(self, *args):
        try:
            return self.dev.ctrl_transfer(*args)
        except usb.core.USBError as e:
            if e.errno not in (19, 5, 32):  # no device / I/O error / pipe
                raise
            self._reconnect()
            return self.dev.ctrl_transfer(*args)

    def _reconnect(self):
        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass
        end = time.time() + self.reconnect_timeout
        while time.time() < end:
            time.sleep(0.25)
            self.dev = _find()
            if self.dev is not None:
                time.sleep(0.5)
                return
        raise DeviceNotFound("display controller disconnected and did not come back")

    def send(self, cls, cid, size, args=b"", check=True):
        self._ctrl(0x21, 0x09, 0x0300, IFACE, build_report(cls, cid, size, args))
        resp = b""
        for _ in range(10):
            time.sleep(0.02)
            resp = bytes(self._ctrl(0xA1, 0x01, 0x0300, IFACE, 90))
            if resp[0] != 0x01:  # not busy
                break
        time.sleep(0.005)
        if check and resp[0] != 0x02:
            raise CommandFailed(f"command {cls:02x}:{cid:02x} -> "
                                f"{STATUS.get(resp[0], hex(resp[0]))}")
        return resp

    # --- queries -----------------------------------------------------------
    def firmware(self):
        r = self.send(0x00, 0x81, 0x02)
        return f"{r[8]}.{r[9]}"

    def serial(self):
        r = self.send(0x00, 0x82, 0x16)
        return r[8:30].split(b"\0")[0].decode(errors="replace")

    def get_brightness(self):
        return self.send(0x0F, 0x84, 0x03, (0x01, DISPLAY_LED, 0))[10]

    # --- commands ----------------------------------------------------------
    def set_brightness(self, value):
        value = max(0, min(255, int(value)))
        self.send(0x0F, 0x04, 0x03, (0x01, DISPLAY_LED, value))

    def set_static(self, color):
        r, g, b = color
        self.send(0x0F, 0x02, 0x09, (0x00, DISPLAY_LED, 0x01, 0, 0, 0x01, r, g, b))

    def set_pixels(self, pixels):
        """Draw an 8x8 image. pixels[y][x] = (r,g,b), y=0 is the top row."""
        for row_idx, row in enumerate(grid_to_rows(pixels)):
            rgb = bytes(c for px in row for c in px)
            self.send(0x0F, 0x03, len(rgb) + 5,
                      bytes((0, 0, row_idx, 0, CTRL_COLS - 1)) + rgb)
        self.send(0x0F, 0x02, 0x0C, (0x00, DISPLAY_LED, 0x08))  # custom-frame effect

    def clear(self):
        self.set_pixels([[(0, 0, 0)] * WIDTH for _ in range(HEIGHT)])

    # --- debug helpers -----------------------------------------------------
    def set_raw_led(self, index, color=(255, 255, 255)):
        """Light one LED by its chain index (0..63), others off."""
        rows = [[(0, 0, 0)] * CTRL_COLS for _ in range(CTRL_ROWS)]
        rows[index // CTRL_COLS][index % CTRL_COLS] = color
        for row_idx, row in enumerate(rows):
            rgb = bytes(c for px in row for c in px)
            self.send(0x0F, 0x03, len(rgb) + 5,
                      bytes((0, 0, row_idx, 0, CTRL_COLS - 1)) + rgb)
        self.send(0x0F, 0x02, 0x0C, (0x00, DISPLAY_LED, 0x08))

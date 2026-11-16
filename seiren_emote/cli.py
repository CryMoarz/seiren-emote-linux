"""Command-line interface: `emote <command>`."""
import argparse
import sys
import time

from . import images
from .device import Emote, DeviceNotFound, CommandFailed

try:
    import usb.core
    _USBError = usb.core.USBError
except ImportError:  # pragma: no cover
    _USBError = OSError


def _rgb(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise argparse.ArgumentTypeError("color must be RRGGBB hex, e.g. ff0000")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def play(dev, frames, loop):
    try:
        while True:
            for px, dur in frames:
                t = time.time()
                dev.set_pixels(px)
                time.sleep(max(0, dur - (time.time() - t)))
            if not loop:
                return
    except KeyboardInterrupt:
        pass


def main(argv=None):
    p = argparse.ArgumentParser(prog="emote",
                                description="Control the Razer Seiren Emote LED display")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="show firmware, serial and brightness")
    pr = sub.add_parser("preset", help="show a built-in emote")
    pr.add_argument("name", choices=sorted(images.PRESETS))
    im = sub.add_parser("image", help="show a PNG/GIF (scaled to 8x8)")
    im.add_argument("file")
    im.add_argument("--loop", action="store_true", help="loop animations forever")
    co = sub.add_parser("color", help="fill the display with one color")
    co.add_argument("hex", type=_rgb, help="RRGGBB, e.g. ff0000")
    br = sub.add_parser("brightness", help="set brightness 0-255")
    br.add_argument("value", type=int)
    sub.add_parser("off", help="turn the display off")
    sub.add_parser("restore", help="re-apply the last saved image and brightness")
    sub.add_parser("gui", help="open the desktop app")
    dbg = sub.add_parser("debug-led", help="light a single LED by chain index (0-63)")
    dbg.add_argument("index", type=int)

    a = p.parse_args(argv)

    if a.cmd == "gui":
        from .gui import main as gui_main
        return gui_main()

    try:
        with Emote() as dev:
            if a.cmd == "info":
                print(f"firmware:   {dev.firmware()}")
                print(f"serial:     {dev.serial()}")
                print(f"brightness: {dev.get_brightness()}")
            elif a.cmd == "preset":
                px = images.preset(a.name)
                dev.set_pixels(px)
                images.save_state(pixels=px)
            elif a.cmd == "image":
                frames = images.load_image(a.file)
                if len(frames) == 1:
                    dev.set_pixels(frames[0][0])
                    images.save_state(pixels=frames[0][0])
                else:
                    images.save_state(image_path=a.file)
                    play(dev, frames, a.loop)
            elif a.cmd == "color":
                px = [[a.hex] * 8 for _ in range(8)]
                dev.set_pixels(px)
                images.save_state(pixels=px)
            elif a.cmd == "brightness":
                dev.set_brightness(a.value)
                images.save_state(brightness=a.value)
            elif a.cmd == "off":
                dev.clear()
                images.save_state(pixels=images.blank())
            elif a.cmd == "restore":
                st = images.load_state()
                if "brightness" in st:
                    dev.set_brightness(st["brightness"])
                if st.get("image_path"):
                    frames = images.load_image(st["image_path"])
                    play(dev, frames, loop=len(frames) > 1)
                elif "pixels" in st:
                    dev.set_pixels(st["pixels"])
            elif a.cmd == "debug-led":
                dev.set_raw_led(a.index)
    except DeviceNotFound as e:
        sys.exit(f"{e}. Is the mic plugged in? (If it is, see README: udev rule.)")
    except _USBError as e:
        if getattr(e, "errno", None) == 13:
            sys.exit("Permission denied. Install the udev rule (see README) or run with sudo.")
        raise
    except CommandFailed as e:
        sys.exit(f"Device rejected a command: {e}")


if __name__ == "__main__":
    main()

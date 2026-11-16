# Razer Seiren Emote for Linux

[![Tests](https://github.com/CryMoarz/seiren-emote-linux/actions/workflows/tests.yml/badge.svg)](https://github.com/CryMoarz/seiren-emote-linux/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platform: Linux](https://img.shields.io/badge/platform-Linux-informational)
![Python 3](https://img.shields.io/badge/python-3-blue)
![GTK 4](https://img.shields.io/badge/GTK-4-green)

**Control the Razer Seiren Emote's 8×8 LED emote display on Linux, without Razer Synapse.** Draw pixel art, show images and animated GIFs, pick a built-in emote, and set the brightness, from a desktop app or the command line. Your emote comes back automatically when you plug the mic in.

Razer only supports the display through Synapse on Windows, and OpenRazer doesn't cover this mic. This is a free, open-source alternative that talks to the mic directly over USB. The installer supports Linux Mint, Ubuntu, Debian, Fedora and Arch.

![Seiren Emote Linux app connected to the mic, with white pixel art drawn on the 8x8 LED display](docs/screenshot.png)

> The microphone audio already works on Linux out of the box. This project only adds control of the LED display.

## Features

- **Desktop app (GTK 4):** paint pixels, pick colors, load PNG/GIF, built-in presets, brightness slider
- **Command line:** `emote preset heart`, `emote image cat.gif --loop`, `emote color ff0000`, `emote off`
- **No sudo:** a udev rule gives your user access
- **Any mounting:** rotate or mirror the picture, e.g. for a mic hanging upside down from a boom arm
- **Restores on plug-in:** your last image (or animation) is re-applied automatically
- Survives a flaky USB cable: reconnects if the display controller drops off the bus

## Install

```bash
git clone https://github.com/CryMoarz/seiren-emote-linux.git
cd seiren-emote-linux
./install.sh
```

The installer puts everything under `~/.local`, installs missing dependencies with your package manager (apt, dnf or pacman), and adds one udev rule (this asks for sudo). **Unplug and replug the mic once afterwards.**

Dependencies, if you'd rather install them yourself: pyusb, Pillow, PyGObject + GTK 4 (and `python3-gi-cairo` on Debian, Ubuntu and Mint).

To remove: `./uninstall.sh`

## Usage

Open **Seiren Emote** from your app menu, or:

```bash
emote gui                     # desktop app
emote preset smile            # smile, wink, sad, heart, star, check, cross, note
emote image heart.png         # any image, scaled to 8x8 (pixel art looks best)
emote image dance.gif --loop  # animated GIF, Ctrl+C to stop
emote color 00ff88            # solid color
emote brightness 120          # 0-255
emote rotate 180              # mic mounted upside down? 0, 90, 180 or 270 (clockwise)
emote flip on                 # mirror left/right (on/off)
emote off
emote info                    # firmware / serial / brightness
```

You get the best results by drawing at exactly 8×8 pixels. Larger images are scaled down.

## Troubleshooting

- **"not found"**: check `lsusb | grep 1532:0f1b`. If only `1532:0524` shows up, replug the mic or try another cable/port.
- **"Permission denied" / "No permission"**: the udev rule isn't active yet. Replug the mic. If it persists on Debian, Ubuntu or Mint, make sure you're in the `plugdev` group (`groups`; add with `sudo usermod -aG plugdev $USER`, then log out and back in). Other distros don't have that group, and the rule gives access to whoever is logged in at the desktop.
- **Display flickers off / random disconnects**: usually the USB cable. The tool reconnects automatically, but a bad cable will make it happen often.
- **Animations are slow**: each frame takes 5 USB packets, so expect roughly 4–5 fps max.

## FAQ

**Does the Razer Seiren Emote work on Linux?**
Yes. The microphone and headphone jack work out of the box as a standard USB audio device. The LED emote display is the part that needs this project.

**Do I need Razer Synapse or Windows?**
No. Everything runs natively on Linux, and you never need Synapse, Windows or a VM.

**Does OpenRazer or Polychromatic support the Seiren Emote?**
Not yet. [PROTOCOL.md](PROTOCOL.md) documents everything needed to add it.

**Can it show animated GIFs?**
Yes: `emote image dance.gif --loop`. Expect about 4–5 frames per second.

**My mic hangs upside down from a boom arm. Can I flip the display?**
Yes: `emote rotate 180`, or use **Orientation** in the app. The setting is saved and applies to everything you show, including after replugging.

**Is the emote saved on the mic?**
Not to the mic's onboard memory yet (help wanted). Instead, a small background service re-applies your last image or animation whenever the mic is plugged in.

## Tested on

| Distro | Mic firmware | Status |
|---|---|---|
| Linux Mint 22.3 Cinnamon (Ubuntu 24.04 base), kernel 7.0, X11 | 1.0 | ✅ desktop app, images, presets |

Got it working on something else? Please [tell us with this short form](https://github.com/CryMoarz/seiren-emote-linux/issues/new?template=works_on_my_setup.yml) so it can be added here.

## How it works

The Emote is two USB devices in one: the audio interface (`1532:0524`) and a separate LED controller (`1532:0F1B`). The controller speaks Razer's standard 90-byte feature-report protocol, so this project talks to it over libusb control transfers, with no kernel module. Full details are in [PROTOCOL.md](PROTOCOL.md). They should make it straightforward to add support to [OpenRazer](https://openrazer.github.io) one day.

## Contributing

Issues and PRs are welcome, especially:

- saving an image to the mic's onboard memory
- OpenRazer / Polychromatic integration
- testing on other distros and firmware versions

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run the tests (no mic needed) and try changes on the real mic.

## Disclaimer

Not affiliated with or endorsed by Razer Inc. "Razer" and "Seiren" are trademarks of Razer Inc. This is an unofficial community tool. Use it at your own risk.

## License

[MIT](LICENSE). You're free to use, copy, modify, share and sell it, in personal or commercial projects. Just keep the license notice.

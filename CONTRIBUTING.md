# Contributing

Thanks for helping out! This is a small project, so the process is simple.

## Reporting a bug, or that it works for you

Use the [issue forms](https://github.com/CryMoarz/seiren-emote-linux/issues/new/choose). They ask for the few things that matter for a USB device: your distro, the mic's firmware (`emote info`) and what `lsusb | grep 1532` shows.

## Running the tests

No mic needed. The tests use a fake USB device:

```bash
python3 -m unittest -v
```

They need pyusb and Pillow, which the installer sets up.

## Trying changes on the real mic

Run straight from your checkout, no reinstall needed:

```bash
python3 -m seiren_emote info
python3 -m seiren_emote gui
```

## Protocol work

Want to explore what's still unknown, like saving to the mic's onboard memory, built-in effects or the mute button? Start with [PROTOCOL.md](PROTOCOL.md) and add what you find there, including commands that come back "unsupported".

Be careful with commands you don't know yet. In Razer's protocol, IDs `0x80` and up are read-only queries, so stick to those until you know what a write command does.

## Pull requests

- Keep each PR to one change.
- Make sure the tests pass.
- By contributing, you agree that your work is released under the [MIT license](LICENSE).

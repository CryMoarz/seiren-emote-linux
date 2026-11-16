# Seiren Emote display protocol notes

Worked out on Linux by probing the device directly. No Synapse captures were needed.

## USB layout

The mic enumerates as **two** USB devices behind an internal hub:

| VID:PID     | What it is | Interfaces |
|-------------|------------|------------|
| `1532:0524` | Audio interface (mic + headphone out) | UAC1 control/streaming + a HID interface (EP 0x87 IN, 16 bytes; buttons/status) |
| `1532:0F1B` | **LED display controller** | One HID interface, **no endpoints** |

`0F1B` has no interrupt endpoint, so Linux's `usbhid` won't bind it and no `/dev/hidraw` node is created. Talk to it with raw control transfers (libusb) instead.

Its 22-byte HID report descriptor:

```
05 0c 09 01 a1 01 06 00 ff 09 02 15 00 25 01 75 08 95 5a b1 01 c0
```

That is a single vendor-defined **90-byte feature report** with no report ID, the standard Razer packet.

## Transport

- SET_REPORT: `bmRequestType=0x21, bRequest=0x09, wValue=0x0300, wIndex=0`, 90 bytes
- GET_REPORT: `bmRequestType=0xA1, bRequest=0x01, wValue=0x0300, wIndex=0`, 90 bytes

## Packet (standard Razer report)

| Byte | Field |
|------|-------|
| 0 | status (0 new, 1 busy, **2 ok**, 3 fail, 4 timeout, 5 unsupported) |
| 1 | transaction id: **0xFF** on this device |
| 2–3 | remaining packets (0) |
| 4 | protocol type (0) |
| 5 | data size |
| 6 | command class |
| 7 | command id |
| 8–87 | arguments |
| 88 | CRC = XOR of bytes 2..87 |
| 89 | reserved |

## Commands confirmed working

| Purpose | Class:ID | Size | Args |
|---|---|---|---|
| Get firmware | `00:81` | 2 | → `args[0].args[1]` (v1.0 on the test unit) |
| Get serial | `00:82` | 0x16 | → ASCII |
| Get device mode | `00:84` | 2 | → `00 00` |
| Get brightness | `0F:84` | 3 | `01, led, 00` → `args[2]` |
| Static colour | `0F:02` | 9 | `00, led, 01, 00, 00, 01, R, G, B` |
| Set frame row | `0F:03` | `n*3+5` | `00, 00, row, start_col, stop_col, RGB…` |
| Apply custom frame | `0F:02` | 0x0C | `00, led, 08` |

This is OpenRazer's "extended matrix" command set. The older "standard matrix" class `03` commands all return *unsupported*.

LED zones: `0x00` and `0x04` answer brightness queries. **`0x04` is the display.** Effects sent to `0x00` show briefly, then the firmware overrides them.

## Display geometry

- The controller accepts **4 rows × 16 columns** (row 4+ and column 16+ are rejected with status 5).
- Physically it's an **8×8 grid**. The 64 LEDs form one chain: LED 0 is bottom-left, filling left→right, then bottom→top.
  - chain index `i` → controller `row = i // 16`, `col = i % 16`
  - image pixel `(x, y)` with `y=0` at the top → `i = (7 - y) * 8 + x`

## Not yet explored

- Saving an image to the mic's onboard memory, so it persists without the host.
- Built-in animations/effects other than static and custom-frame.
- Whether brightness `0F:04` persists across power cycles.
- The HID interface on `0524` (likely mute/button events).

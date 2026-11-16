"""Tests that run without the mic, using a fake USB device."""
import sys, types, unittest
from unittest import mock

from seiren_emote import device, images


class FakeDev:
    """Records SET_REPORTs and answers GET_REPORT with status OK."""
    def __init__(self):
        self.sent = []
        self.last = bytearray(90)

    def is_kernel_driver_active(self, i):
        return False

    def ctrl_transfer(self, bmRequestType, bRequest, wValue, wIndex, data):
        if bmRequestType == 0x21:
            self.sent.append(bytes(data))
            self.last = bytearray(data)
            return len(data)
        resp = bytearray(self.last)
        resp[0] = 0x02
        return resp


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDev()
        p = mock.patch.object(device.usb.core, "find", return_value=self.fake)
        p.start(); self.addCleanup(p.stop)
        q = mock.patch.object(device.time, "sleep"); q.start(); self.addCleanup(q.stop)

    def test_crc(self):
        r = device.build_report(0x00, 0x81, 0x02)
        crc = 0
        for b in r[2:88]:
            crc ^= b
        self.assertEqual(r[88], crc)
        self.assertEqual((r[1], r[5], r[6], r[7]), (0xFF, 0x02, 0x00, 0x81))

    def test_mapping_corners(self):
        px = [[(y * 8 + x, 0, 0) for x in range(8)] for y in range(8)]
        rows = device.grid_to_rows(px)
        flat = [p[0] for row in rows for p in row]
        self.assertEqual(flat[0], 7 * 8 + 0)   # LED 0  = bottom-left
        self.assertEqual(flat[7], 7 * 8 + 7)   # LED 7  = bottom-right
        self.assertEqual(flat[15], 6 * 8 + 7)  # LED 15 = above bottom-right
        self.assertEqual(flat[63], 0 * 8 + 7)  # LED 63 = top-right

    def test_set_pixels_packets(self):
        dev = device.Emote()
        dev.set_pixels(images.preset("heart"))
        frames = self.fake.sent
        self.assertEqual(len(frames), 5)  # 4 rows + apply effect
        for i, f in enumerate(frames[:4]):
            self.assertEqual((f[6], f[7], f[5]), (0x0F, 0x03, 16 * 3 + 5))
            self.assertEqual(tuple(f[8:13]), (0, 0, i, 0, 15))
        self.assertEqual(tuple(frames[4][6:11]), (0x0F, 0x02, 0x00, 0x04, 0x08))

    def test_presets_are_8x8(self):
        for name, rows in images.PRESETS.items():
            self.assertEqual(len(rows), 8, name)
            self.assertTrue(all(len(r) == 8 for r in rows), name)

    def test_image_roundtrip(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.png")
            images.save_png(images.preset("star"), p)
            frames = images.load_image(p)
            self.assertEqual(frames[0][0], images.preset("star"))


if __name__ == "__main__":
    unittest.main()

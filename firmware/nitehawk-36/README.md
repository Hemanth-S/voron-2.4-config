# LDO Nitehawk-36 (Xol toolhead) firmware

Same recipe as the SV08's Nitehawk-36 (`~/sv08/firmware/`), proven there:
RP2040, USB, no bootloader (app at 0x10000100), W25Q080 flash, `INITIAL_PINS=!gpio9`
(hotend heater held low at boot), plus the cold-start patch.

| File | What |
|------|------|
| `nitehawk.config` | minimal Kconfig; `make olddefconfig` expands it |
| `nitehawk-xosc-startup-64ms.patch` | waits 64 ms instead of 1 ms for the crystal. Without it the RP2040 can fail to start on a cold power-up. **Re-apply on every reflash.** |

## Build (on the Pi)

Build from a **patched copy** of Klipper, never in `~/klipper` (its version string and other boards'
builds must stay clean):

```bash
rm -rf ~/klipper-nitehawk && git clone -q ~/klipper ~/klipper-nitehawk && cd ~/klipper-nitehawk
git apply ~/firmware/nitehawk-36/nitehawk-xosc-startup-64ms.patch
cp ~/firmware/nitehawk-36/nitehawk.config .config && make olddefconfig && make -j4   # -> out/klipper.uf2
```

First built and flashed 2026-10-31: v0.13.0-464-g48f0b3cad (same as the host), serial
`usb-Klipper_rp2040_3434343339138651`.

## Flash

The board needs **24 V** (LDO adapter PCB powered from the PSU) for the hub to see it.

- Board already runs this build over USB (no Katapult on it): `make NOSUDO=1 flash
  FLASH_DEVICE=/dev/serial/by-id/usb-Klipper_rp2040_3434343339138651-if00` (in `~/klipper-nitehawk`).
  Klipper reboots it into the RP2040's ROM bootloader, so no button is needed.
- **This board shipped from LDO with Katapult** (unlike the SV08's). A USB flash request then lands in
  Katapult, whose protocol didn't answer our flash tools, and the no-bootloader image doesn't fit
  Katapult's layout anyway. Fix used 2026-10-31: BOOT mode (hold BOOT, tap RESET) and
  `make NOSUDO=1 flash FLASH_DEVICE=2e8a:0003`, which overwrites Katapult. No sudo needed.
- New or unknown firmware: hold BOOT and tap RESET (or hold BOOT while powering up), so it appears
  as `2e8a:0003`, then `make NOSUDO=1 flash FLASH_DEVICE=2e8a:0003`.

Then `ls /dev/serial/by-id/` and put the `usb-Klipper_rp2040_...` path in `config/toolhead-xol.cfg`.

If the board doesn't boot after flashing (no `rp2040` serial device even after RESET), the flash chip
may differ from the SV08's: rebuild with `CONFIG_RP2040_FLASH_GENERIC_03=y` (BTT made the same
change for its RP2040 boards in 2025) and flash again from BOOT mode.

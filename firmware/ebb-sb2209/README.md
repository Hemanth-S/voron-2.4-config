# BTT EBB SB2209 CAN (RP2040) firmware: StealthBurner toolhead

RP2040, Katapult at 16 KiB, CAN on gpio4/gpio5 at 1 Mbit/s, Katapult status LED gpio26.
Katapult uses BTT's May 2025 flash-chip setting (GENERIC_03H, CLKDIV 4), so it boots on both the
older boards and the v1.0.1 board. Klipper doesn't use the setting, because Katapult starts it.
Build dirs on the Pi: `~/firmware/sb2209/`.

## Build (on the Pi)

```bash
F=~/firmware/sb2209
cp katapult.config klipper.config $F/
cd ~/katapult && make KCONFIG_CONFIG=$F/katapult.config OUT=$F/katapult-out/
cd ~/klipper  && make KCONFIG_CONFIG=$F/klipper.config  OUT=$F/klipper-out/
```

## New board

1. Board off the printer, 5V jumper ON, USB-C to the Pi. Hold BOOT and tap RESET; `lsusb` shows `2e8a:0003`.
2. Flash Katapult (no sudo needed as of 2026-10-28):
   ```bash
   cd ~/katapult && make NOSUDO=1 KCONFIG_CONFIG=$F/katapult.config OUT=$F/katapult-out/ flash
   ```
   This writes `katapult.withclear.uf2`, which also clears the application area, so the stock
   Klipper's leftovers can't be started.
3. Unplug the USB and take the 5V jumper OFF (24 V comes over the CAN cable). Copy the old board's
   jumpers by their labels (120R ON) and install the board.
4. Power on, then:
   ```bash
   python3 ~/katapult/scripts/flashtool.py -i can0 -q                                         # new UUID, "Katapult"
   python3 ~/katapult/scripts/flashtool.py -i can0 -u <uuid> -f ~/firmware/sb2209/klipper-out/klipper.bin
   ```
   Put the UUID in `config/toolhead-stealthburner.cfg` under `[mcu EBBCan]`.

If Klipper won't start, double-tap RESET to stay in Katapult.

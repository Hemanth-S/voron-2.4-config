# BTT EBB36 v1.2 (Xol toolhead) firmware

STM32G0B1, 8 MHz crystal, CAN on PB0/PB1 at 1 Mbit/s, Katapult (8 KiB) + Klipper at 0x08002000.
Build dirs on the Pi: `~/firmware/ebb36/` (outside the klipper/katapult repos, so their own
`.config` files for the SB2209 stay untouched).

## Build (on the Pi)

```bash
F=~/firmware/ebb36
cp katapult.config klipper.config $F/          # these files
cd ~/katapult && make KCONFIG_CONFIG=$F/katapult.config OUT=$F/katapult-out/
cd ~/klipper  && make KCONFIG_CONFIG=$F/klipper.config  OUT=$F/klipper-out/
```

Always pass both `KCONFIG_CONFIG` and `OUT`. Running `olddefconfig` without `OUT` repoints the
repo's default `out/board` link. To fix that, run `make create-board-link` in that repo.

## First flash (new board, USB DFU)

1. VUSB jumper ON, 24 V disconnected. Hold BOOT, press RESET, release BOOT. Then USB-C to the Pi.
   `lsusb` shows `0483:df11`.
2. Flash Katapult and then Klipper (needs sudo over SSH; the udev rule only grants a local seat):
   ```bash
   sudo dfu-util -a 0 -d 0483:df11 --dfuse-address 0x08000000:force:mass-erase -D /home/pi/firmware/ebb36/katapult-out/katapult.bin
   sudo dfu-util -a 0 -d 0483:df11 --dfuse-address 0x08002000:leave -D /home/pi/firmware/ebb36/klipper-out/klipper.bin
   ```
   Do not use `mass-erase` on the second command: it would wipe Katapult.
3. Unplug USB to power-cycle the board. On the G0, a plain RESET can drop back into the ROM
   bootloader until the next power-on. Then take the VUSB jumper OFF.

## On the CAN bus

```bash
~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0   # UUID -> config/toolhead-xol.cfg
```

Later Klipper updates go over CAN:
```bash
python3 ~/katapult/scripts/flashtool.py -i can0 -u <uuid> -f ~/firmware/ebb36/klipper-out/klipper.bin
```
If Klipper won't start, double-click RESET to stay in Katapult (status LED PA13 blinks).

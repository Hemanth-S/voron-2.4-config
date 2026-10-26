# BTT Octopus Pro (STM32H723) firmware: USB-to-CAN bridge

H723 at 520 MHz, 25 MHz crystal, BTT stock bootloader (128 KiB, Klipper at 0x08020000),
USB (PA11/PA12) to CAN bridge on PD0/PD1 at 1 Mbit/s. The CAN UUID 8aad5b6575b6 comes from the chip
ID, so it survives a reflash. Based on the October 2025 build (`~/klipper/.config.old` on the Pi).

`CONFIG_INITIAL_PINS="!PG15"` holds the CPAP driver's speed input low from boot. Without it, the
STOP_7 port's pull-up runs the blower flat out until Klipper configures the board, for example
during restarts or when another MCU is missing and Klipper stops with "Unable to connect".

## Build (on the Pi)

```bash
F=~/firmware/octopus
cp klipper.config $F/
cd ~/klipper && make KCONFIG_CONFIG=$F/klipper.config OUT=$F/klipper-out/
```

## Flash

The printer is offline while this runs: the board is the CAN bridge, so the whole bus drops.

- **SD card** (no sudo, leaves the bootloader alone): copy `klipper-out/klipper.bin` to a FAT32
  microSD as `firmware.bin`, insert it into the Octopus, and power-cycle. The bootloader flashes it
  and renames the file to `FIRMWARE.CUR`.
- **DFU**: reboot the board into its ROM bootloader, check that `lsusb` shows `0483:df11`, then run
  ```bash
  sudo dfu-util -a 0 -d 0483:df11 --dfuse-address 0x08020000:leave -D /home/pi/firmware/octopus/klipper-out/klipper.bin
  ```
  Never mass-erase here: that would wipe the BTT bootloader at 0x08000000.

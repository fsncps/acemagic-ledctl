## ACEMAGIC T9 Mini Computer LED Control

[![CI](https://github.com/fsncps/acemagic-ledctl/actions/workflows/ci.yml/badge.svg)](https://github.com/fsncps/acemagic-ledctl/actions/workflows/ci.yml)
[![Bandit](https://github.com/fsncps/acemagic-ledctl/actions/workflows/bandit.yml/badge.svg)](https://github.com/fsncps/acemagic-ledctl/actions/workflows/bandit.yml)
[![GitHub release](https://img.shields.io/github/v/release/fsncps/acemagic-ledctl.svg)](https://github.com/fsncps/acemagic-ledctl/releases)
[![PyPI version](https://img.shields.io/pypi/v/acemagic-ledctl)](https://pypi.org/project/acemagic-ledctl/)

A Linux CLI utility for controlling the LED controller found in some ACEMAGIC mini PCs over a USB-to-UART bridge, usually WCH CH340/CH341, reaplacing  the vendor's Windows-only LED utility with a scriptable CLI and adds extra pattern modes built on top of the observed serial protocol.


## Status

- Current scope: ACEMAGIC T9/T9-class devices and similar variants using a CH34x bridge
- Platform: Linux
- Maturity: experimental but packaged and tested
- Privilege model: root works by default; non-root use normally requires access to the serial device via group membership or udev rules


## Features

When you don't immediately nuke the Windows off one of the ACEMAGIC mini computers, you have a utility to control all the flashy and colourful fadenlights. Luckily, the command sequencesare available online. With my box and I assume with most others, just unplugging the module would be no hassle either – but if you want to set it to rainbow at a certain speed or even make some dynamic use of the modes, then this utility replaces the Windows-only solution by the vendor, adding CLI tool functionality and more lighting patterns. 

- Turn LEDs off: `ledctl off`
- Set built-in LED modes: `ledctl setmode {cycle,rainbow,breathing}`
- Run custom pattern hacks: `ledctl setpattern {stillred,stillblue,breathered,alarm}`
- Launch interactive wizard: `ledctl wiz`
- Auto-detect common CH340/CH341 serial adapters
- Override serial port, baud, DTR, RTS, and inter-byte delay

It should work with any ACEMAGIC box that has LED connected over a CH340 or CH341 bridge, or probably any other UART interface.


## Installation

Install from PyPI:

```bash
pip install acemagic-ledctl
```

For local development:

```bash
git clone https://github.com/fsncps/acemagic-ledctl.git
cd acemagic-ledctl
pip install -e ".[dev]"
```

## Quick start

Try the wizard first:

```bash
ledctl wiz
```

Turn LEDs off:

```bash
ledctl off
```

Run a built-in mode explicitly:

```bash
ledctl setmode cycle -b 1 -s 3
```

Run a custom pattern with a fixed device path:

```bash
ledctl setpattern alarm --port /dev/serial/by-id/usb-...
```

## Device access

On many systems the serial device is owned by a group such as `dialout` or `uucp`. Add your user to the correct group and start a new shell.

Example for Debian-like systems:

```bash
sudo usermod -aG dialout "$USER"
newgrp dialout
```

To discover the actual device and ownership:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
ls -l /dev/serial/by-id/ 2>/dev/null
python3 -m serial.tools.list_ports -v
```

## Detection logic

`ledctl` currently tries the following in order:

1. Known CH34x VID/PIDs
2. First `/dev/ttyUSB*`
3. First `/dev/ttyACM*`

If multiple adapters are connected, or if the device uses CP210x, FTDI, or something else, specify `--port` explicitly.

## Stable udev alias

If auto-detection is unreliable, create a stable symlink:

```bash
sudo tee /etc/udev/rules.d/99-ledctl.rules >/dev/null <<'RULE'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="ledctl", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="5523", SYMLINK+="ledctl", GROUP="dialout", MODE="0660"
RULE

sudo udevadm control --reload
sudo udevadm trigger
```

Then use:

```bash
ledctl setmode breathing -p /dev/ledctl -B 10000 -t -R -d 0.005
```

## Troubleshooting

### Device not found

Check kernel detection while plugging the device:

```bash
dmesg -w
```

Check the driver state:

```bash
lsmod | grep -E 'ch34|usbserial'
sudo modprobe ch341
```

Try a different cable, a different port, and avoid hubs while testing.

### Wrong adapter detected

Use a fixed by-id path:

```bash
ledctl setmode cycle -b 1 -s 3 --port /dev/serial/by-id/usb-...
```

### Timing problems

If the device responds sluggishly or inconsistently, adjust the inter-byte delay:

```bash
ledctl setmode breathing -d 0.002
ledctl setmode breathing -d 0.008
```

## CLI notes

Global pattern controls:

```text
--background / -g
--no-kill-existing
```

Serial controls:

```text
-p, --port PATH
-B, --baud INT
-t, --dtr / -T, --no-dtr
-r, --rts / -R, --no-rts
-d, --delay SEC
```

Pattern-common controls when supported by the pattern implementation:

```text
-b, --brightness 1..5
-s, --speed 1..5
--period SEC
--mode-num BYTE
--hz FLOAT
```

## Security

This is a hardware-control tool, not a sandbox. It writes bytes to a serial device chosen by auto-detection or by explicit path. Review `SECURITY.md` before deploying it on systems where incorrect device selection could matter.

## Documentation

- [Architecture](docs/architecture.md)
- [Release process](docs/release-process.md)
- [Roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [License notes](docs/license-choice.md)

## Attribution

The serial protocol work was informed by public reverse-engineering discussion from the MiniPCs community. The implementation here is an independent Linux CLI around those observations.

## ACEMAGIC T9 Mini Computer LED Control

Rumor has it that when you don't immediately nuke the Windows off one of the ACEMAGIC mini computers, you have a utility to control all the flashy and colourful fadenlights. Luckily, [smart and friendly people](https://www.reddit.com/r/MiniPCs/comments/18icusg/t9_plus_n100_how_to_control_led/) analyzed the serial stream and have posted the command sequences. so we don't need that bit of Windows bloatware to do just as much as switch the LEDs off. With my box and I assume with most others, just unplugging the module would be no hassle either – but if you want to set it to rainbow at a certain speed or even make some dynamic use of the modes, then this utility replaces the Windows-only solution by the vendor, adding CLI tool functionality and more lighting patterns. It should work with any ACEMAGIC box that has LED connected over a CH340 or CH340 bridge, or probably any other UART interface.

### Functionality

You get a CLI tool with commands 
- `ledctl off`
- `ledctl setmode {cycle,rainbow,breathing} [OPTIONS]` (built-in LED controls)
- `ledctl setpattern {stillred,stillblue,breathered,alarm} [OPTIONS]` (hacks for additional lighting modes)
- `ledctl wiz` (a small TUI menu to select or switch between modes quickly to test them)

The built-ins are mostly too colourful and too agitated, so I think the added pattern hacks are quite a plus if you want any LED at all. I wondered why there are no plain colours built in by default, but at least I managed to simulate a still red light (or, the illusion of it) by strobing the cycle mode at a frequency of 50Hz. In a similar manner, I created a blue-and-purple still mode, as well as an uni-coloured breathing mode in red and a blinking "alarm" mode designed to alert, both with adjustable speed. I'm sure more are possible, inputs highly welcome!

I would have just switched them off, but I want to use this box for rsyslogging among other things and this gives me a nice visual status indicator. When some daemon fails somewhere in my LAN and the log is send to the acemagic box, it alerts me of the incident and its gravity by a series of increasingly irritating visual cues. Neat.

---
### Compatibility & Installation

The tool talks to the LED microcontroller over a USB-to-UART bridge. On ACEMAGIC T9 variants this is usually a WCH CH340/CH341. Could work on any similar device with some tweaks. Check compatibilty, then veify you have the right device, then if necessary change UART byte sequence -- but with any ACEMAGIC box with a similar kind of LED module, expect this to Just Work™.

#### **Setup**

1) **Install python module**
It's in PyPI, so you should be able to install directly with pip:
```bash
pip install "acemagic-ledctl[ui]"   # or: pip install acemagic-ledctl
```
Alternatively, in particular when you want to make changes, clone this repo and install from the local dir.

Then try auto-detect with a command like `ledctl wiz` or `ledctl setrainbow` under root privileges. This should work most of the time.

2) **Ensure access**
If you want to enable the tool for a non-root user, add it to the group your distro uses for serial according to udev group rules. Just look at the owner of the terminal `/dev/ttyUSB*` or find it under `/dev/serial/by-id/`. Typically  this is `dialout`, or `uucp` on more traditionally oriented systems like Slackware or Arch. Then start a new shell or reset it with the new group:
```bash
usermod -aG dialout "$USER"        # E.g. for Debian etc.
newgrp dialout                     # To reset your existing shell 
```

#### Troubleshoot

*ledctl* tries to detect the port with your serial adapter as follows
- Tries known **CH34x** VID/PIDs first.
- Falls back to the first `/dev/ttyUSB*`, then `/dev/ttyACM*`.

Reasons for failure could be several simultaneously connected UART/ACM adapters or an LED module that uses a different standard, like CP210x or FTDI, in which case you will have to manually specify the port to connect to. Find a stable path in `/dev/serial/by-id/` which mentions WCH, USB-Serial, CH340 or similar and execute ledctl with the necessary flags:     
```bash
python3 -m serial.tools.list_ports -v
ledctl setmode cycle -b 1 -s 3 \
  --port /dev/serial/by-id/usb-...
```

If this works, you can create a stable alias, e.g. `/dev/ledctl`, for the device in the form of a custom udev rule:
```bash
tee /etc/udev/rules.d/99-ledctl.rules >/dev/null <<'RULE'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="ledctl", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="5523", SYMLINK+="ledctl", GROUP="dialout", MODE="0660"
RULE
#### then reload the udev rules:
udevadm control --reload
udevadm trigger
#### and try again:
ledctl setmode breathing -p /dev/ledctl -B 10000 -t -R -d 0.005
```

If your kernel does not see the device at all, check for hardware and driver issues. Use a different cable/port (no hubs) and check with `dmesg -w` while plugging and ensure driver is loaded using `modprobe`.

#### Serial tuning flags to troubleshoot performance issues
Global (for ledctl setpattern):
```bash
--background (-g) — run pattern detached
--no-kill-existing — don’t terminate existing pattern loops
```
Serial (parsed by ledctl, passed to the pattern runner):
```bash
-p, --port PATH — serial device (by-id path recommended)
-B, --baud INT — baud rate (default from tool)
-t, --dtr / -T, --no-dtr — assert/deassert DTR
-r, --rts / -R, --no-rts — assert/deassert RTS
-d, --delay SEC — inter-byte delay (default **0.005 s**). If it’s sluggish, try 0.002; if unreliable, raise to 0.006–0.010.
```
Pattern-common (only if the pattern’s run() supports them):
```bash
-b, --brightness 1..5
-s, --speed 1..5
--period SEC
--mode-num BYTE (e.g. 0x03)
--hz FLOAT
```

## ACEMAGIC T9 Mini Computer LED Control

Rumor has it that when you don't immediately nuke the Windows off one of the ACEMAGIC mini computers, you have a utility to control all the flashy and colourful fadenlights. Luckily, [smart and friendly people](https://www.reddit.com/r/MiniPCs/comments/18icusg/t9_plus_n100_how_to_control_led/) have analyzed the serial stream and posted the command sequences. so we don't need that bit of Windows bloatware to do just as much as switch the LEDs off. With my box and I assume with most others, just unplugging the module would be no hassle either -- but if you want to set it to rainbow at a certain speed or even make some dynamic use of the modes, then this should probably work with any ACEMAGIC box which has LED lighting that is connected over a CH340 or CH340 bridge, or probably any other UART interface.

### Functionality

You get a CLI tool with commands 
- `ledctl off`
- `ledctl setmode {cycle,rainbow,breathing} [OPTIONS]` (built-in LED controls)
- `ledctl setpattern {stillred,stillblue,breathered,alarm} [OPTIONS]` (some hacks to add a few more, like red breathing of various speeds, and an alarm mode. Be creative and add more)
- `ledctl wiz` (a small TUI menu to select or switch between modes quickly to test them)

I wonder why there are no plain colours built in, but at least we can simulate a still red light by restarting the cycle mode with 50Hz, or the rainbow mode gives us a half blue / half purple light in this way, kind of pretty. The built-ins are mostly too colourful and too agitated, so I think these and the breathing red at different intensities are quite a plus if you want any LED at all. I would have just switched them off, but I want to use this box for rsyslogging among other things, so I have a nice visual status indicator now. Some daemon fails somewhere in my LAN and the log is send to the acemagic box, who informs me of the gravity of recent incidents by a series of increasingly irritating visual cues. Neat.

---
### Compatibility & Installation

The tool talks to the LED microcontroller over a USB-to-UART bridge. On ACEMAGIC T9 variants this is usually a WCH CH340/CH341. Could work on any similar device with some tweaks. Check compatibilty, then veify you have the right device, then if necessary change UART byte sequence -- but with any ACEMAGIC box with a similar kind of LED module, expect this to Just Work™.

1) **Install**
```bash
pip install "acemagic-ledctl[ui]"   # or: pip install acemagic-ledctl
```

2) **(Once) ensure access**
```bash
#### pick the group your distro uses; one of these is typical
sudo usermod -aG dialout "$USER"   # Debian/Ubuntu
#### or
sudo usermod -aG uucp "$USER"      # Arch/Slackware
newgrp dialout || newgrp uucp      # start a new shell with the group
```

3) **Plug the box and try auto-detect**
```bash
ledctl setmode rainbow
#### or
python -m ledctl setmode rainbow
```
If the LEDs change: you’re done.

4) **If auto-detect fails, select the port explicitly**
```bash
#### Find a stable path:
ls -l /dev/serial/by-id/
#### Pick the entry that mentions WCH/USB-Serial/CH340 etc.

ledctl setmode cycle -b 1 -s 3 \
  --port /dev/serial/by-id/usb-... \
  --baud 10000 --dtr --no-rts --delay 0.005
```

5) **(Optional) make a stable alias `/dev/ledctl`**
```bash
sudo tee /etc/udev/rules.d/99-ledctl.rules >/dev/null <<'RULE'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="ledctl", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="5523", SYMLINK+="ledctl", GROUP="dialout", MODE="0660"
RULE
sudo udevadm control --reload
sudo udevadm trigger
#### then:
ledctl setmode breathing -p /dev/ledctl -B 10000 -t -R -d 0.005
```

#### How the tool picks a port
- Tries known **CH34x** VID/PIDs first.
- Falls back to the first `/dev/ttyUSB*`/`/dev/ttyACM*`.
- You can always override with `--port`. Prefer **`/dev/serial/by-id/...`** over `/dev/ttyUSB0`.

#### When you’ll need `--port`
- You have **multiple** USB-UART adapters.
- Your unit uses **CP210x/FTDI/ACM** instead of CH34x.
- Hot-plug order changes across boots (tty index shifts).

#### Minimal verification (optional)
```bash
lsusb | grep -Ei '(1a86:7523|1a86:5523|wch|ch34)'   # CH340/CH341 present?
dmesg | grep -i ch341                                # driver attached? (ttyUSBn)
```

#### Tuning flags you might touch
- `-B/--baud` → **10000** (device default here)
- `-t/--dtr` and `-R/--no-rts` → defaults are **DTR asserted**, **RTS deasserted**
- `-d/--delay` → inter-byte delay (default **0.005 s**). If it’s sluggish, try `0.002`; if unreliable, raise to `0.006–0.010`.



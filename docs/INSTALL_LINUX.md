# Installing Squelch on Debian / Ubuntu / Raspberry Pi

Squelch runs on Debian-based Linux (Debian, Ubuntu, Linux Mint, Raspberry Pi
OS). This is a popular setup for portable and digital-mode stations,
especially on a Raspberry Pi.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git \
    libhamlib-utils \            # rigctld (CAT control)
    rtl-sdr soapysdr-tools \     # RTL-SDR + SoapySDR
    soapysdr-module-rtlsdr \     # SoapySDR RTL plugin
    libportaudio2                # audio (sounddevice backend)
```

Optional, by activity:
```bash
sudo apt install -y wsjtx fldigi            # FT8/FT4/WSPR, PSK/RTTY/CW
sudo apt install -y dump1090-fa             # ADS-B (Local RF / aircraft)
```

Note: VARA HF/FM and RMS Express are Windows programs; on Linux they run
under Wine, or use Pat (`sudo apt install pat` where packaged) for Winlink.

## 2. Serial port permissions (important)

To let Squelch talk to your radio over USB (`/dev/ttyUSB*`, `/dev/ttyACM*`),
add yourself to the `dialout` group:

```bash
sudo usermod -aG dialout $USER
```

Then **log out and back in** (or reboot). Squelch will detect if this is
missing and remind you.

## 3. Squelch itself

```bash
git clone https://github.com/dawardy/squelch.git
cd squelch
python3 installer.py        # add --verbose to see full pip output
```

The installer creates a virtual environment and installs the Python
dependencies. Config and logs are stored per the XDG spec:

- Config:  `~/.config/squelch/`
- Logs:    `~/.config/squelch/logs/` (incl. `network.log`)

## 4. Run

```bash
./run_squelch.sh        # created by the installer
# or
venv/bin/python main.py
```

## Raspberry Pi notes

- Use a 64-bit OS (Raspberry Pi OS 64-bit / Ubuntu) for the best wheel
  availability; PyQt6 wheels exist for `aarch64`.
- A Pi 4 / Pi 5 is recommended for SDR waterfall work; a Pi 3 is fine for
  CAT control and logging.
- For RTL-SDR, blacklist the DVB-T kernel driver so SoapySDR can claim the
  device:
  ```bash
  echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf
  sudo reboot
  ```

## Desktop launcher (optional)

A `squelch.desktop` file is included in `setup/`. Copy it to your
applications directory and fix the `Exec`/`Icon` paths to your install:

```bash
cp setup/squelch.desktop ~/.local/share/applications/
# edit Exec= and Icon= to point at your squelch folder
```

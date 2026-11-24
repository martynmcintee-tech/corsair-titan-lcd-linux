# Corsair TITAN LCD for Linux + Little Computer Person 2026 (`corsair-titan-lcd-linux`)

<p align="center">
  <img src="assets/titan_lcd_real_readme.gif" width="380" height="380" alt="Live camera clip on a physical Corsair TITAN 360 RX LCD on Ubuntu" />&nbsp;&nbsp;<img src="assets/lcp_2026_showcase.gif" width="380" height="380" alt="Direct 480x480 multi-venue feed" />
</p>
<p align="center"><em>Left: Running on the Corsair TITAN 360 RX cooler in my Ubuntu PC &nbsp;·&nbsp; Right: Direct 480x480 pixel feed</em></p>

When I moved my main PC from Windows to Ubuntu, I got my Corsair fans and pump talking to Linux via Nikola Jurkovic's [OpenLinkHub](https://github.com/jurkovic-nikola/OpenLinkHub), then wanted something better than a static JPEG sitting on the circular `480x480` pump screen.

I grew up wasting hours on Activision's 1985 Commodore 64 classic ***Little Computer People*** (*"House-on-a-Disk"*) as a kid and thought the circular cooler glass was the ideal place for the little fella to live. That turned into **LCP 2026**, alongside 12 clock, watch, and hardware gauge faces, plus a standalone GTK4 desktop widget so you can run him on any Linux desktop or laptop even if you don't own a Corsair cooler.

## What LCP 2026 gets up to

In `auto` mode he follows the real wall clock and day of the week rather than looping the same two animations forever:

- Monday to Friday (`09:00 - 17:00`), he walks down the stairs, hops into his silver electric fastback, and drives off to a weekday 9-5 office shift, with the occasional `12:35` lunchtime run to Greggs.
- After `17:00` on weekdays (and Sunday evenings), he drives home to light the fire, sit at his PC, hang out with his girlfriend Chloe and terrier Buddy, or head out for a quick gym session or a pint before bed.
- Saturdays and Sundays are strictly off-duty: lazy morning lie-ins followed by trips around 11 pixel-art locations.
- Whenever he changes location, he actually walks out the front door and drives there, complete with spinning alloys, Buddy sticking his head out the back window with flapping ears, and scrolling green UK road signs.
- Across the 11 scenes (3-storey cutaway house, weekday office, High Street with Greggs, The Red Lion pub, 24/7 gym, IMAX cinema, seaside pier with a 99 Flake van, Club SID, hotel, bistro date, and house party), he pops up 75+ two-line comic thought bubbles complaining about traffic, molten-lava steak bakes, £7.50 pints, leg day, or your GPU heating his living room when a local LLM is running.

If you open the GTK4 app (`lcp-2026`), you can tweak his skin tone, hair colour, outfits, partner's name, simulation speed, and schedule, or click **Mini Widget** (`lcp-2026 --widget`) to keep a `480x480` circular window on your desktop without any Corsair hardware attached.

On a physical TITAN RX LCD, frames render in Pepto's 16-colour C64 VIC-II palette in roughly `0.23 ms` and push to OpenLinkHub (`POST /api/lcd/upload` + `POST /api/lcd/image`) over a persistent HTTP/1.1 keep-alive socket (`~11 ms` round-trip), phase-locked to `floor(time.time()) + 1.006s` so clock second hands tick on time.

## All 13 circular `480x480` faces

| Theme ID | Name | What's on screen |
| :--- | :--- | :--- |
| `c64_lcp` | Little Computer Person 2026 | Cutaway 3-storey house, Chloe, Buddy the terrier, EV commutes, 11 venues, and thought bubbles (~4.6 FPS) |
| `chrono_pulse` | Neon Chrono & Pulse | 60-tick dial, sweeping neon seconds arc, digital clock, and live CPU/GPU/coolant temps (1 Hz) |
| `swiss_tourbillon` | Swiss Skeleton Chrono | Mechanical watch face with crimson lollipop seconds hand and CPU/GPU sub-dials (1 Hz) |
| `cooling_cockpit` | Cryo Dual-Loop Cockpit | Opposing CPU and GPU temperature arcs, large coolant readout, and pump/fan RPMs |
| `ai_fleet` | AI Fleet & VRAM HUD | Shows whichever local model is loaded in `llama-server`, ComfyUI, or Whisper, plus VRAM usage |
| `tensor_reactor` | Tensor Arc Reactor | 24-blade sci-fi turbine ring that scales speed and glow with live GPU wattage and load |
| `motorsport_gt` | Motorsport GT Gauge | 270-degree rev-counter needle with redline zone and digital readout box |
| `stealth_zen` | Stealth Minimal OLED | Plain `#000000` background with `HH:MM` and `CPU · GPU · LIQ` temps for dark rooms |
| `hx1200i_power_grid` | Digital PSU Power Plant | Corsair digital PSU wattage meter, `+12V / 5V / 3.3V` rails, and Zero-RPM fan state |
| `silicon_matrix` | Silicon Compute Matrix | Per-thread CPU bar graph, peak CPU GHz / GPU MHz clocks, and RAM/VRAM arcs |
| `cyber_radar` | Tactical Sonar Sweep | Rotating green phosphor radar line with thermal blips and live network RX/TX speeds (1 Hz) |
| `pip_os_3000` | Amber CRT Terminal | Monochrome amber CRT terminal with scanlines, `HH:MM:SS`, and 12-segment bars (1 Hz) |
| `horizon_avionics` | Jet Glass Cockpit ADI | Artificial horizon that banks and pitches with system load, plus CPU/GPU side tapes (1 Hz) |

## Install

### Option 1: `.deb` package (Ubuntu / Debian / Mint / Pop!_OS)

Grab `corsair-titan-lcd-linux_2.0.0_all.deb` from [Releases](https://github.com/martynmcintee-tech/corsair-titan-lcd-linux/releases/latest) and install it with `apt`:

```bash
sudo apt install ./corsair-titan-lcd-linux_2.0.0_all.deb
```

### Option 2: From source

```bash
# Ubuntu / Debian packages (Pillow + GTK4/Libadwaita for the desktop app and widget)
sudo apt install python3-pil fonts-dejavu-core python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

git clone https://github.com/martynmcintee-tech/corsair-titan-lcd-linux.git
cd corsair-titan-lcd-linux
chmod +x install.sh
./install.sh
```

## Usage

```bash
# Open the GTK4 desktop window (venue picker, wardrobe, schedule, and live preview)
lcp-2026

# Run just the compact circular widget on any Linux desktop (no cooler needed)
lcp-2026 --widget

# Control the physical Corsair AIO screen from the terminal
titan-lcd --list-themes
titan-lcd --set-theme c64_lcp
titan-lcd --set-theme swiss_tourbillon
titan-lcd --brightness 80
```

## Optional environment variables

OpenLinkHub hub serials and LCD channels are picked up automatically from `http://127.0.0.1:27003/api/devices/`, so you normally don't need to touch any of these unless your setup is non-standard:

| Variable | Default | What it overrides |
| :--- | :--- | :--- |
| `OPENLINKHUB_HOST` | `127.0.0.1` | OpenLinkHub HTTP bind address |
| `OPENLINKHUB_PORT` | `27003` | OpenLinkHub HTTP port |
| `OPENLINKHUB_HUB_SERIAL` | *(auto-detected)* | Specific iCUE LINK Hub `deviceId` |
| `OPENLINKHUB_LCD_CHANNEL` | *(auto-detected)* | Specific LCD channel ID (e.g. `17`) |
| `LCP_USER_NAME` | `$USER` | Name used when he knocks on the glass and waves (e.g. `HI MARTYN!`) |
| `LLAMA_MODELS_URL` | `http://127.0.0.1:18436/models` | Optional `llama.cpp` router `/models` URL for the `ai_fleet` face |
| `LLAMA_API_KEY` | *(empty)* | Optional Bearer token if your `llama-server` uses `--api-key` |
| `COMFY_URL` | `http://127.0.0.1:8188` | Optional ComfyUI URL for showing active image/video jobs |

## Notes & Licence

Built for my own Ubuntu 24.04 desktop with AI coding tools helping speed up the procedural Pillow sprite drawing, dial trig, and GTK4 UI boilerplate, and tested day-to-day on a physical Corsair TITAN 360 RX LCD.

Released under the [MIT License](LICENSE). *Little Computer People* (1985) was created by David Crane and Rich Gold at Activision; all code, pixel sprites, and town scenes in this repo are original clean-room procedural Python routines written as a fan tribute.

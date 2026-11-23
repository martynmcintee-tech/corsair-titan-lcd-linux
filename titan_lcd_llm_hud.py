#!/usr/bin/env python3
"""
Corsair iCUE LINK TITAN LCD for Linux — 13-Theme Circular Display Engine (480x480)
Includes an autonomous 1985 Commodore 64 'Little Computer People' cutaway house simulation!

Driven via OpenLinkHub (http://127.0.0.1:27003) with zero-config device auto-discovery,
persistent HTTP/1.1 keep-alive frame swaps (~11ms), 1Hz wall-clock phase-locking,
and ~4.6 FPS pixel-art animation.

Supports 13 selectable live themes persisted in ~/.config/titan-lcd/state.json:
   1. c64_lcp            — Little Computer Person (1985 C64 cutaway house with autonomous pixel resident & dog)
   2. chrono_pulse       — Neon Chrono & System Pulse (60-tick precision dial, sweeping seconds, clock & thermals)
   3. swiss_tourbillon   — Swiss Skeleton Chrono (Luxury analog watch face, live crimson seconds hand & sub-dials)
   4. cooling_cockpit    — Cryo Dual-Loop Cockpit (CPU & GPU opposing gauges, giant Liquid °C, Pump & Fan RPMs)
   5. ai_fleet           — AI Fleet & GPU VRAM HUD (Active GGUF / ComfyUI / Whisper, VRAM & Compute arcs)
   6. tensor_reactor     — Tensor Arc Reactor (Concentric turbine power segments + core compute telemetry)
   7. motorsport_gt      — Motorsport GT Tachometer (270° racing gauge with live needle, redline & digital gear box)
   8. stealth_zen        — Stealth OLED Minimal (Pure #000000 zero-glare studio face with CPU • GPU • LIQ triad)
   9. hx1200i_power_grid — Digital PSU Power Plant (Live PSU wattage rails, +12V/5V/3.3V split, GPU share & Eco mode)
  10. silicon_matrix     — Silicon Compute Matrix (Live per-thread CPU spectrum analyzer, GHz/MHz clocks & RAM/VRAM)
  11. cyber_radar        — Tactical Sonar Sweep (Rotating 360° phosphor radar sweep, thermal blips & live Net I/O)
  12. pip_os_3000        — Amber CRT Terminal (Retro phosphor terminal with scanlines, HH:MM:SS & block bars)
  13. horizon_avionics   — Jet Glass Cockpit ADI (Fighter-jet artificial horizon, pitch ladder & CPU/GPU flight tapes)
"""
import ctypes
import datetime
import glob
import http.client
import io
import json
import math
import os
import re
import sys
import threading
import time
import urllib.request
from PIL import Image, ImageDraw, ImageFont

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from lcp_c64_house import render_theme_c64_lcp

OPENLINKHUB_HOST = os.environ.get("OPENLINKHUB_HOST", "127.0.0.1")
OPENLINKHUB_PORT = int(os.environ.get("OPENLINKHUB_PORT", "27003"))
OPENLINKHUB_URL = f"http://{OPENLINKHUB_HOST}:{OPENLINKHUB_PORT}"
HUB_SERIAL = os.environ.get("OPENLINKHUB_SERIAL", "")
LCD_CHANNEL = int(os.environ.get("OPENLINKHUB_LCD_CHANNEL", "0"))
LLAMA_URL = os.environ.get("LLAMA_MODELS_URL", "http://127.0.0.1:18436/models")
LLAMA_API_KEY = os.environ.get("LLAMA_API_KEY") or os.environ.get("QWEN_API_KEY") or ""
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
COMFY_PORT = int(os.environ.get("COMFY_PORT", "8188"))
PREVIEW_PATH = os.environ.get("TITAN_LCD_PREVIEW", "/dev/shm/titan_lcd_current.png")
MODE_ASSERT_SECS = 120.0

LCD_STATE_DIR = os.path.expanduser("~/.config/titan-lcd")
LCD_STATE_FILE = os.path.join(LCD_STATE_DIR, "state.json")

FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

FAN_CHANNELS: list[int] = []
PSU_CHANNEL: int = 0
_TOPOLOGY_DISCOVERED = False


def discover_openlinkhub_topology(force: bool = False) -> tuple[str, int]:
    """Auto-discover Corsair iCUE LINK Hub serial, AIO LCD channel, fans & PSU from OpenLinkHub."""
    global HUB_SERIAL, LCD_CHANNEL, FAN_CHANNELS, PSU_CHANNEL, _TOPOLOGY_DISCOVERED
    if _TOPOLOGY_DISCOVERED and not force and HUB_SERIAL and LCD_CHANNEL > 0:
        return HUB_SERIAL, LCD_CHANNEL

    env_serial = os.environ.get("OPENLINKHUB_SERIAL", "").strip()
    env_lcd_ch = int(os.environ.get("OPENLINKHUB_LCD_CHANNEL", "0") or 0)

    try:
        req = urllib.request.Request(f"{OPENLINKHUB_URL}/api/devices/")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        devices_root = payload.get("devices") or {}
        for serial_key, entry in devices_root.items():
            if not isinstance(entry, dict) or serial_key == "cluster":
                continue
            if env_serial and serial_key != env_serial:
                continue
            get_dev = entry.get("GetDevice") or {}
            sub_devs = get_dev.get("devices") or {}
            found_lcd = 0
            fans = []
            psu_ch = 0
            for ch_str, info in sub_devs.items():
                if not isinstance(info, dict):
                    continue
                cid = int(info.get("channelId") or ch_str)
                has_lcd = bool(info.get("LCDSerial") or info.get("TitanAIO") or "LCD" in str(info.get("name", "")).upper())
                if has_lcd and found_lcd == 0:
                    found_lcd = cid
                elif info.get("IsPSU") or info.get("watts"):
                    psu_ch = cid
                elif info.get("HasSpeed") and not info.get("AIO"):
                    fans.append(cid)

            if env_lcd_ch > 0:
                found_lcd = env_lcd_ch

            if found_lcd > 0 or env_serial:
                HUB_SERIAL = serial_key
                LCD_CHANNEL = found_lcd or 17
                FAN_CHANNELS = sorted(fans)
                PSU_CHANNEL = psu_ch
                _TOPOLOGY_DISCOVERED = True
                return HUB_SERIAL, LCD_CHANNEL
    except Exception:
        pass

    if env_serial:
        HUB_SERIAL = env_serial
    if env_lcd_ch > 0:
        LCD_CHANNEL = env_lcd_ch
    return HUB_SERIAL, LCD_CHANNEL


LCD_THEMES = [
    ("c64_lcp", "Little Computer Person", "1985 C64 cutaway house with autonomous pixel resident & dog"),
    ("chrono_pulse", "Neon Chrono & Pulse", "Precision 60-tick dial, sweeping seconds arc, clock & live temps"),
    ("swiss_tourbillon", "Swiss Skeleton Chrono", "Luxury analog mechanical watch, ticking seconds hand & CPU/GPU sub-dials"),
    ("cooling_cockpit", "Cryo Dual-Loop Cockpit", "Opposing CPU & GPU thermal gauges, Liquid °C, Pump & Fan RPMs"),
    ("ai_fleet", "AI Fleet & VRAM HUD", "Active GGUF / FLUX / Whisper model, VRAM & compute rings"),
    ("tensor_reactor", "Tensor Arc Reactor", "Segmented sci-fi arc reactor pulsing with wattage, VRAM & load"),
    ("motorsport_gt", "Motorsport GT Gauge", "270° racing tachometer needle, redline zone & digital telemetry box"),
    ("stealth_zen", "Stealth Minimal OLED", "Pitch-black zero-glare night face with crisp CPU • GPU • LIQ triad"),
    ("hx1200i_power_grid", "Digital PSU Power Plant", "Live Platinum PSU wattage, +12V/5V/3.3V rails & GPU split"),
    ("silicon_matrix", "Silicon Compute Matrix", "Live per-thread CPU spectrum analyzer, GHz/MHz clocks & RAM/VRAM"),
    ("cyber_radar", "Tactical Sonar Sweep", "Rotating 360° phosphor radar sweep, thermal targets & live Net I/O"),
    ("pip_os_3000", "Amber CRT Terminal", "Retro phosphor terminal with CRT scanlines, HH:MM:SS & block gauges"),
    ("horizon_avionics", "Jet Glass Cockpit ADI", "Fighter-jet artificial horizon, pitch ladder & CPU/GPU flight tapes"),
]
THEME_IDS = [t[0] for t in LCD_THEMES]
SECOND_TICK_THEMES = {
    "chrono_pulse",
    "swiss_tourbillon",
    "cyber_radar",
    "pip_os_3000",
    "horizon_avionics",
}
FAST_ANIM_THEMES = {
    "c64_lcp": 0.22,
}

QUANT_RE = re.compile(
    r"(?:^|[-_.])((?:UD-)?(?:I?Q[0-9]+(?:_[A-Z0-9]+)*|BF16|F16|FP16|FP8|F32))$",
    re.IGNORECASE,
)
SIZE_SUFFIX_RE = re.compile(
    r"-(\d+(?:\.\d+)?B(?:-A\d+B)?(?:-1M|-IT|-Abl|-Unc)?)$",
    re.IGNORECASE,
)
NVML_VALUE_NOT_AVAILABLE = 0xFFFFFFFFFFFFFFFF

_FONT_CACHE = {}


def load_font(path, size):
    key = (path, size)
    if key not in _FONT_CACHE:
        try:
            _FONT_CACHE[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def read_lcd_state() -> dict:
    defaults = {"theme": "c64_lcp", "auto_cycle": False, "cycle_secs": 15, "brightness": 100}
    try:
        with open(LCD_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("theme") in THEME_IDS:
            defaults["theme"] = data["theme"]
        defaults["auto_cycle"] = bool(data.get("auto_cycle", False))
        defaults["cycle_secs"] = max(5, int(data.get("cycle_secs", 15)))
        defaults["brightness"] = max(0, min(100, int(data.get("brightness", 100))))
    except Exception:
        pass
    return defaults


def write_lcd_state(theme: str | None = None, auto_cycle: bool | None = None, brightness: int | None = None) -> dict:
    st = read_lcd_state()
    if theme is not None and theme in THEME_IDS:
        st["theme"] = theme
    if auto_cycle is not None:
        st["auto_cycle"] = bool(auto_cycle)
    if brightness is not None:
        st["brightness"] = max(0, min(100, int(brightness)))
    os.makedirs(LCD_STATE_DIR, exist_ok=True)
    tmp = f"{LCD_STATE_FILE}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
        f.write("\n")
    os.replace(tmp, LCD_STATE_FILE)
    return st


# NVML structures
class nvmlMemory_t(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


class nvmlUtilization_t(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class nvmlProcessInfo_v2_t(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_ulonglong),
        ("gpuInstanceId", ctypes.c_uint),
        ("computeInstanceId", ctypes.c_uint),
    ]


class NVMLReader:
    def __init__(self):
        self.ok = False
        self.lib = None
        self.dev = ctypes.c_void_p()
        self.gpu_name = "GPU"
        self.short_tag = "GPU"
        try:
            self.lib = ctypes.CDLL("libnvidia-ml.so.1")
            if self.lib.nvmlInit_v2() == 0 and self.lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self.dev)) == 0:
                self.ok = True
                nbuf = ctypes.create_string_buffer(96)
                if self.lib.nvmlDeviceGetName(self.dev, nbuf, 96) == 0:
                    raw = nbuf.value.decode("utf-8", "replace").replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").strip()
                    self.gpu_name = raw[:18] or "GPU"
                    m = re.search(r"(\d{4}(?:\s*Ti)?)", raw, re.IGNORECASE)
                    self.short_tag = m.group(1).replace(" ", "").upper()[:6] if m else self.gpu_name[:6].upper()
        except Exception:
            self.ok = False

    def get_compute_processes(self):
        proc_vram = {}
        if not self.ok:
            return proc_vram
        try:
            count = ctypes.c_uint(0)
            self.lib.nvmlDeviceGetComputeRunningProcesses_v3(self.dev, ctypes.byref(count), None)
            if count.value == 0:
                return proc_vram
            cap = count.value + 16
            arr = (nvmlProcessInfo_v2_t * cap)()
            c2 = ctypes.c_uint(cap)
            if self.lib.nvmlDeviceGetComputeRunningProcesses_v3(self.dev, ctypes.byref(c2), arr) == 0:
                for i in range(c2.value):
                    pid = int(arr[i].pid)
                    mem_b = int(arr[i].usedGpuMemory)
                    if pid > 0 and 0 < mem_b < NVML_VALUE_NOT_AVAILABLE:
                        proc_vram[pid] = proc_vram.get(pid, 0) + mem_b
        except Exception:
            pass
        return proc_vram

    def read(self, include_processes=True):
        if not self.ok:
            return {
                "name": self.gpu_name,
                "short_tag": self.short_tag,
                "vram_used_gb": 0.0,
                "vram_total_gb": 16.0,
                "vram_ratio": 0.0,
                "gpu_util": 0,
                "temp_c": 38,
                "power_w": 25,
                "fan_pct": 0,
                "sm_clock_mhz": 0,
                "mem_clock_mhz": 0,
                "proc_vram": {},
            }
        mem = nvmlMemory_t()
        self.lib.nvmlDeviceGetMemoryInfo(self.dev, ctypes.byref(mem))
        util = nvmlUtilization_t()
        self.lib.nvmlDeviceGetUtilizationRates(self.dev, ctypes.byref(util))
        temp = ctypes.c_uint()
        self.lib.nvmlDeviceGetTemperature(self.dev, 0, ctypes.byref(temp))
        power_mw = ctypes.c_uint()
        self.lib.nvmlDeviceGetPowerUsage(self.dev, ctypes.byref(power_mw))
        fan_pct = ctypes.c_uint()
        self.lib.nvmlDeviceGetFanSpeed_v2(self.dev, 0, ctypes.byref(fan_pct))
        clk_sm = ctypes.c_uint()
        clk_mem = ctypes.c_uint()
        try:
            self.lib.nvmlDeviceGetClockInfo(self.dev, 0, ctypes.byref(clk_sm))
            self.lib.nvmlDeviceGetClockInfo(self.dev, 2, ctypes.byref(clk_mem))
        except Exception:
            pass
        return {
            "name": self.gpu_name,
            "short_tag": self.short_tag,
            "vram_used_gb": mem.used / (1024 ** 3),
            "vram_total_gb": mem.total / (1024 ** 3),
            "vram_ratio": mem.used / max(1, mem.total),
            "gpu_util": int(util.gpu),
            "temp_c": int(temp.value),
            "power_w": int(round(power_mw.value / 1000.0)),
            "fan_pct": int(fan_pct.value),
            "sm_clock_mhz": int(clk_sm.value),
            "mem_clock_mhz": int(clk_mem.value),
            "proc_vram": self.get_compute_processes() if include_processes else {},
        }


class CpuReader:
    def __init__(self):
        self._prev_idle = 0
        self._prev_total = 0
        self._prev_cores = {}
        self._prev_net = None
        self._hwmon_temp = self._find_coretemp()
        self.short_name = self._detect_cpu_short_name()
        self._freq_paths = sorted(
            glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"),
            key=lambda p: int(re.search(r"cpu(\d+)", p).group(1)),
        )
        # Prime baseline counters so first read() produces real instantaneous deltas
        self._read_proc_stat()
        self._read_net_rate()

    @staticmethod
    def _detect_cpu_short_name() -> str:
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        raw = line.split(":", 1)[1].strip()
                        m = re.search(r"(i[3579]-\d{4,5}[A-Z]*|\d{4,5}X3D|\d{4,5}[A-Z]{1,2}|Ultra\s+\d+\s+\w+)", raw)
                        if m:
                            return m.group(1).replace("i3-", "").replace("i5-", "").replace("i7-", "").replace("i9-", "")[:10]
                        return raw[:10]
        except Exception:
            pass
        return "CPU"

    @staticmethod
    def _find_coretemp():
        for h in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                with open(os.path.join(h, "name"), "r", encoding="ascii") as f:
                    if f.read().strip() in ("coretemp", "k10temp", "zenpower"):
                        return os.path.join(h, "temp1_input")
            except OSError:
                continue
        return None

    def _read_proc_stat(self):
        util_pct = 0
        threads = []
        try:
            with open("/proc/stat", "r", encoding="ascii") as f:
                lines = f.readlines()
            for line in lines:
                if not line.startswith("cpu"):
                    break
                toks = line.split()
                tag = toks[0]
                parts = [int(x) for x in toks[1:]]
                idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
                total = sum(parts)
                if tag == "cpu":
                    d_total = total - self._prev_total
                    d_idle = idle - self._prev_idle
                    self._prev_total = total
                    self._prev_idle = idle
                    if d_total > 0:
                        util_pct = max(0, min(100, int(round(100.0 * (1.0 - d_idle / float(d_total))))))
                elif tag[3:].isdigit():
                    cid = int(tag[3:])
                    p_idle, p_tot = self._prev_cores.get(cid, (idle, total))
                    self._prev_cores[cid] = (idle, total)
                    dt = total - p_tot
                    di = idle - p_idle
                    c_pct = max(0, min(100, int(round(100.0 * (1.0 - di / float(dt)))))) if dt > 0 else 0
                    threads.append((cid, c_pct))
            threads.sort(key=lambda x: x[0])
        except Exception:
            pass
        return util_pct, [v for _, v in threads] or [0] * 20

    def _read_net_rate(self):
        now_t = time.monotonic()
        rx_b = 0
        tx_b = 0
        try:
            with open("/proc/net/dev", "r", encoding="ascii") as f:
                for line in f.readlines()[2:]:
                    if ":" not in line:
                        continue
                    iface, rest = line.split(":", 1)
                    iface = iface.strip()
                    if iface == "lo" or iface.startswith(("docker", "br-", "veth")):
                        continue
                    cols = rest.split()
                    if len(cols) >= 9:
                        rx_b += int(cols[0])
                        tx_b += int(cols[8])
        except Exception:
            return 0.0, 0.0
        if self._prev_net is None:
            self._prev_net = (now_t, rx_b, tx_b)
            return 0.0, 0.0
        pt, prx, ptx = self._prev_net
        dt = max(0.05, now_t - pt)
        self._prev_net = (now_t, rx_b, tx_b)
        rx_mbps = max(0.0, (rx_b - prx) * 8.0 / (dt * 1e6))
        tx_mbps = max(0.0, (tx_b - ptx) * 8.0 / (dt * 1e6))
        return rx_mbps, tx_mbps

    def read(self) -> dict:
        temp_c = 35
        if self._hwmon_temp:
            try:
                with open(self._hwmon_temp, "r", encoding="ascii") as f:
                    temp_c = int(round(int(f.read().strip()) / 1000.0))
            except OSError:
                pass

        util_pct, threads = self._read_proc_stat()

        max_ghz = 0.0
        if self._freq_paths:
            freqs = []
            for p in self._freq_paths:
                try:
                    with open(p, "r", encoding="ascii") as f:
                        freqs.append(int(f.read().strip()) / 1e6)
                except OSError:
                    continue
            if freqs:
                max_ghz = max(freqs)

        ram_used_gb = 6.0
        ram_total_gb = 32.0
        try:
            mem_tot_kb = 0
            mem_avail_kb = 0
            with open("/proc/meminfo", "r", encoding="ascii") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_tot_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail_kb = int(line.split()[1])
                    if mem_tot_kb and mem_avail_kb:
                        break
            if mem_tot_kb > 0:
                ram_total_gb = mem_tot_kb / (1024.0 * 1024.0)
                ram_used_gb = max(0.0, (mem_tot_kb - mem_avail_kb) / (1024.0 * 1024.0))
        except Exception:
            pass

        rx_mbps, tx_mbps = self._read_net_rate()
        return {
            "short_name": self.short_name,
            "temp_c": temp_c,
            "util": util_pct,
            "threads": threads,
            "max_ghz": round(max_ghz, 2),
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "ram_ratio": min(1.0, ram_used_gb / max(1.0, ram_total_gb)),
            "net_rx_mbps": rx_mbps,
            "net_tx_mbps": tx_mbps,
        }


def read_cooling_telemetry() -> dict:
    try:
        serial, lcd_ch = discover_openlinkhub_topology()
        if not serial:
            raise RuntimeError("No OpenLinkHub LCD device discovered")
        req = urllib.request.Request(f"{OPENLINKHUB_URL}/api/devices/{serial}")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        devs = ((data.get("device") or {}).get("devices")) or {}
        fan_rpms = [int((devs.get(str(c)) or {}).get("rpm") or 0) for c in FAN_CHANNELS]
        avg_fan_rpm = int(round(sum(fan_rpms) / len(fan_rpms))) if fan_rpms else 0
        pump_info = devs.get(str(lcd_ch)) or {}
        psu_info = (devs.get(str(PSU_CHANNEL)) or {}) if PSU_CHANNEL else {}
        watts_map = psu_info.get("watts") or {}
        w_3v3 = float((watts_map.get("0") or {}).get("Value") or 0.0)
        w_5v = float((watts_map.get("1") or {}).get("Value") or 0.0)
        w_12v = float((watts_map.get("2") or {}).get("Value") or 0.0)
        psu_total = int(round(w_3v3 + w_5v + w_12v))
        return {
            "liquid_c": round(float(pump_info.get("temperature") or 30.0), 1),
            "pump_rpm": int(pump_info.get("rpm") or 0),
            "fan_rpm": avg_fan_rpm,
            "psu_3v3_w": round(w_3v3, 1),
            "psu_5v_w": round(w_5v, 1),
            "psu_12v_w": round(w_12v, 1),
            "psu_total_w": psu_total,
            "psu_temp_c": round(float(psu_info.get("temperature") or 38.0), 1),
            "psu_rpm": int(psu_info.get("rpm") or 0),
        }
    except Exception:
        return {
            "liquid_c": 30.0,
            "pump_rpm": 2300,
            "fan_rpm": 500,
            "psu_3v3_w": 5.8,
            "psu_5v_w": 10.4,
            "psu_12v_w": 100.0,
            "psu_total_w": 116,
            "psu_temp_c": 40.0,
            "psu_rpm": 0,
        }


def read_proc_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read().decode("utf-8", "replace")
        return " ".join(p for p in raw.split("\x00") if p)
    except Exception:
        return ""


def get_port_socket_targets(port):
    target_hex = f":{port:04X}"
    targets = set()
    for net_path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(net_path, "r") as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 10 and parts[3] == "0A" and parts[1].upper().endswith(target_hex):
                        targets.add(f"socket:[{parts[9]}]")
        except Exception:
            pass
    return targets


def pid_owns_socket(pid, socket_targets):
    if not socket_targets:
        return False
    fd_dir = f"/proc/{pid}/fd"
    try:
        for fd in os.listdir(fd_dir):
            try:
                if os.readlink(f"{fd_dir}/{fd}") in socket_targets:
                    return True
            except OSError:
                continue
    except OSError:
        return False
    return False


def get_comfy_pid_vram_bytes(proc_vram):
    if not proc_vram:
        return 0
    sock_targets = get_port_socket_targets(COMFY_PORT)
    total_bytes = 0
    for pid, mem_b in proc_vram.items():
        if pid_owns_socket(pid, sock_targets):
            total_bytes += mem_b
            continue
        cmd = read_proc_cmdline(pid).lower()
        if "comfyui" in cmd and ("main.py" in cmd or str(COMFY_PORT) in cmd):
            total_bytes += mem_b
    return total_bytes


def short_model_name(model_id):
    if not model_id:
        return "STANDBY / READY"
    mapping = {
        "Qwen3.8-27B-UD-Q4_K_M": "Qwen3.8-27B",
        "Qwen3.8-27B-Uncensored": "Qwen3.8-27B-Unc",
        "Qwen2.5-Coder-32B-Instruct": "Qwen2.5-Coder-32B",
        "DeepSeek-R1-Distill-Qwen-32B": "DeepSeek-R1-32B",
        "Qwen2.5-Coder-14B-Instruct": "Qwen2.5-Coder-14B",
        "DeepSeek-R1-Distill-Qwen-14B": "DeepSeek-R1-14B",
        "Qwen2.5-VL-7B-Instruct": "Qwen2.5-VL-7B",
        "sqlcoder-7b-2": "SQLCoder-7B-2",
        "Qwen2.5-Coder-14B-abliterated": "Qwen2.5-Cod-14B-Abl",
        "Hermes-3-Llama-3.1-8B": "Hermes-3-8B",
        "gemma-2-27b-it": "Gemma-2-27B-IT",
        "bge-m3": "BGE-M3-Embed",
        "Qwen3-30B-A3B": "Qwen3-30B-A3B",
        "Qwen2.5-14B-Instruct-1M": "Qwen2.5-14B-1M",
        "Qwen2.5-3B-Instruct-abliterated": "Qwen2.5-3B-Abl",
    }
    if model_id in mapping:
        return mapping[model_id]

    cleaned = QUANT_RE.sub("", model_id)
    for old, new in (
        ("-Instruct-abliterated", "-Abl"),
        ("-abliterated", "-Abl"),
        ("-Uncensored", "-Unc"),
        ("-Instruct", ""),
        ("-Distill-Qwen", ""),
        ("-Distill-Llama", ""),
        ("-it", "-IT"),
    ):
        cleaned = cleaned.replace(old, new)

    if len(cleaned) <= 19:
        return cleaned
    m = SIZE_SUFFIX_RE.search(cleaned)
    if m:
        suffix = m.group(1)
        prefix = cleaned[: m.start()]
        avail = 19 - len(suffix) - 1
        if avail >= 4:
            return f"{prefix[:avail].rstrip('-')}-{suffix}"
    return cleaned[:19]


def parse_gguf_quant(model_path, fallback_meta=None):
    if model_path:
        stem = os.path.splitext(os.path.basename(model_path))[0]
        m = QUANT_RE.search(stem)
        if m:
            return m.group(1).upper()
    if fallback_meta and fallback_meta.get("ftype"):
        return str(fallback_meta["ftype"]).replace(" - Medium", "_M").replace(" - Small", "_S")
    return "GGUF"


_MODEL_SIZE_CACHE = {}


def _cached_file_size(path: str) -> int:
    if not path:
        return 0
    cached = _MODEL_SIZE_CACHE.get(path)
    if cached is not None:
        return cached
    try:
        if os.path.exists(path):
            sz = os.path.getsize(path)
            _MODEL_SIZE_CACHE[path] = sz
            return sz
    except OSError:
        pass
    return 0


def parse_router_model_entry(entry):
    status = entry.get("status") or {}
    args = status.get("args") or []
    meta = entry.get("meta") or {}
    model_path = None
    mmproj_path = None
    ctx_size = None
    ngl = 99

    i = 0
    n = len(args)
    while i < n:
        arg = str(args[i])
        nxt = str(args[i + 1]) if i + 1 < n else None
        if arg in ("-m", "--model") and nxt:
            model_path = nxt
            i += 2
            continue
        if arg == "--mmproj" and nxt:
            mmproj_path = nxt
            i += 2
            continue
        if arg in ("-c", "--ctx-size") and nxt:
            try:
                ctx_size = int(nxt)
            except ValueError:
                pass
            i += 2
            continue
        if arg in ("-ngl", "--n-gpu-layers", "--gpu-layers") and nxt:
            try:
                ngl = int(nxt)
            except ValueError:
                pass
            i += 2
            continue
        i += 1

    size_bytes = _cached_file_size(model_path) + _cached_file_size(mmproj_path)
    if size_bytes <= 0:
        size_bytes = int(meta.get("size") or 0)
    if not ctx_size:
        ctx_size = int(meta.get("n_ctx") or entry.get("context_length") or 0)

    quant = parse_gguf_quant(model_path, fallback_meta=meta)
    return {
        "model_path": model_path,
        "mmproj_path": mmproj_path,
        "size_bytes": size_bytes,
        "size_gb": size_bytes / 1e9,
        "ctx_size": ctx_size,
        "quant": quant,
        "ngl": ngl,
    }


def get_comfy_status(proc_vram):
    comfy_vram_bytes = get_comfy_pid_vram_bytes(proc_vram)
    comfy_vram_gib = comfy_vram_bytes / (1024 ** 3)
    comfy_vram_gb = comfy_vram_bytes / 1e9
    try:
        q_req = urllib.request.Request(f"{COMFY_URL}/queue")
        with urllib.request.urlopen(q_req, timeout=0.6) as q_resp:
            q_data = json.loads(q_resp.read().decode("utf-8"))
    except Exception:
        return None

    running = q_data.get("queue_running") or []
    is_rendering = len(running) > 0
    if not is_rendering and comfy_vram_gib < 1.5:
        return None

    model_label = "FLUX.1-dev-fp8"
    quant_label = "FP8 // DIFFUSION"
    tag_label = "ACTIVE GPU DIFFUSION"

    def inspect_graph(prompt_graph):
        nonlocal model_label, quant_label, tag_label
        if not isinstance(prompt_graph, dict):
            return
        steps_val = None
        for _, node in prompt_graph.items():
            inputs = node.get("inputs") or {}
            if "steps" in inputs and isinstance(inputs["steps"], (int, float)):
                steps_val = int(inputs["steps"])
                break
        for _, node in prompt_graph.items():
            inputs = node.get("inputs") or {}
            raw_ckpt = inputs.get("ckpt_name") or inputs.get("unet_name") or ""
            if not isinstance(raw_ckpt, str) or not raw_ckpt:
                continue
            ckpt = raw_ckpt.lower()
            step_txt = f"{steps_val}-STEP" if steps_val else None
            if "ltx" in ckpt:
                model_label = "LTX-Video-2B"
                quant_label = f"BF16 // {step_txt or '24FPS'} VIDEO"
                tag_label = "ACTIVE GPU VIDEO"
            elif "wan" in ckpt:
                model_label = "Wan2.1-T2V-1.3B"
                quant_label = f"BF16 // {step_txt or 'AI'} VIDEO"
                tag_label = "ACTIVE GPU VIDEO"
            elif "schnell" in ckpt:
                model_label = "FLUX.1-schnell"
                quant_label = f"FP8 // {step_txt or '4-STEP'}"
            elif "dev" in ckpt:
                model_label = "FLUX.1-dev-fp8"
                quant_label = f"FP8 // {step_txt or '24-STEP'}"
            else:
                stem = os.path.splitext(os.path.basename(raw_ckpt))[0]
                model_label = stem[:19]
                quant_label = f"GPU // {step_txt}" if step_txt else "GPU DIFFUSION"
            break

    if is_rendering:
        try:
            inspect_graph(running[0][2])
        except Exception:
            pass
    disp_gb = comfy_vram_gb if comfy_vram_gb > 0.1 else 0.0
    meta_str = f"{quant_label} // {disp_gb:.1f} GB" if disp_gb > 0 else quant_label
    return {
        "loaded": True,
        "tag": tag_label,
        "state_text": "RENDERING..." if is_rendering else "VRAM LOADED",
        "name": model_label,
        "meta": meta_str,
        "size_gb": disp_gb,
    }


def get_whisper_status(proc_vram):
    if not proc_vram:
        return None
    whisper_bytes = 0
    for pid, mem_b in proc_vram.items():
        if mem_b < 100 * 1024 * 1024:
            continue
        cmd = read_proc_cmdline(pid).lower()
        if "whisper_helper" in cmd or "faster_whisper" in cmd or "faster-whisper" in cmd or ("whisper" in cmd and "python" in cmd):
            whisper_bytes += mem_b
    if whisper_bytes <= 0:
        return None
    whisper_gb = whisper_bytes / 1e9
    return {
        "loaded": True,
        "tag": "ACTIVE GPU AUDIO",
        "state_text": "TRANSCRIBING...",
        "name": "Whisper-v3-Turbo",
        "meta": f"INT8_FP16 // CUDA // {whisper_gb:.1f} GB",
        "size_gb": whisper_gb,
    }


def get_loaded_llm(proc_vram=None, gpu_name: str = "GPU"):
    comfy = get_comfy_status(proc_vram)
    whisper = get_whisper_status(proc_vram)
    try:
        hdrs = {"Authorization": f"Bearer {LLAMA_API_KEY}"} if LLAMA_API_KEY else {}
        req = urllib.request.Request(LLAMA_URL, headers=hdrs)
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        all_presets = data.get("data") or []
        total_presets = len(all_presets) or 1
        active = []
        for m in all_presets:
            st = (m.get("status") or {}).get("value", "")
            if st in ("loaded", "loading", "sleeping"):
                parsed = parse_router_model_entry(m)
                active.append((m, st, parsed))

        if not active:
            if comfy:
                return comfy
            if whisper:
                return whisper
            return {
                "loaded": False,
                "tag": "ACTIVE GPU MODEL",
                "state_text": f"{gpu_name} READY",
                "name": "NO MODEL IN VRAM",
                "meta": f"{total_presets} MODELS // READY",
            }

        active.sort(key=lambda item: (1 if item[2]["ngl"] > 0 else 0, item[2]["size_bytes"]), reverse=True)
        top_entry, st_val, top_info = active[0]
        if top_info["ngl"] == 0 and (comfy or whisper):
            return comfy or whisper

        mid = top_entry.get("id", "Local LLM")
        ctx = top_info["ctx_size"]
        if ctx >= 1024 and ctx % 1024 == 0:
            ctx_str = f"{ctx // 1024}K CTX"
        elif ctx >= 1000:
            ctx_str = f"{round(ctx / 1024)}K CTX"
        elif ctx > 0:
            ctx_str = f"{ctx} CTX"
        else:
            ctx_str = "CTX"

        gpu_llm_count = sum(1 for _, _, inf in active if inf["ngl"] > 0)
        extra_gpu = (1 if comfy else 0) + (1 if whisper else 0)

        if top_info["ngl"] == 0:
            tag_text = "ACTIVE CPU EMBED"
            state_text = "LOADING EMBED..." if st_val == "loading" else ("SLEEPING (CPU)" if st_val == "sleeping" else "CPU LOADED")
        else:
            tag_text = "ACTIVE GPU LLM"
            total_gpu_models = gpu_llm_count + extra_gpu
            extra = f" (+{total_gpu_models - 1})" if total_gpu_models > 1 else ""
            state_text = "LOADING MODEL..." if st_val == "loading" else (f"SLEEPING IN VRAM{extra}" if st_val == "sleeping" else f"VRAM LOADED{extra}")

        return {
            "loaded": True,
            "sleeping": st_val == "sleeping",
            "tag": tag_text,
            "state_text": state_text,
            "name": short_model_name(mid),
            "meta": f"{top_info['quant']} // {ctx_str} // {top_info['size_gb']:.1f} GB",
        }
    except Exception:
        return comfy or whisper or {
            "loaded": False,
            "tag": "ACTIVE GPU MODEL",
            "state_text": "SYSTEM STANDBY",
            "name": gpu_name,
            "meta": "LOCAL AI TELEMETRY",
        }


# ===========================================================================
# 6 CIRCULAR 480x480 RENDERERS (2x Supersampled at 960x960 -> LANCZOS)
# ===========================================================================
def render_theme_ai_fleet(gpu, llm, cpu, cooling, now_dt=None):
    S = 960
    img = Image.new("RGB", (S, S), (5, 10, 20))
    draw = ImageDraw.Draw(img)

    draw.ellipse([16, 16, S - 16, S - 16], fill=(6, 12, 24), outline=(22, 48, 82), width=6)
    draw.arc([56, 56, S - 56, S - 56], start=135, end=405, fill=(18, 34, 58), width=26)
    vram_end = 135 + max(4, int(round(270 * min(1.0, gpu["vram_ratio"]))))
    draw.arc([56, 56, S - 56, S - 56], start=135, end=vram_end, fill=(0, 229, 255), width=26)

    draw.arc([94, 94, S - 94, S - 94], start=135, end=405, fill=(14, 32, 44), width=18)
    load_ratio = max(0.02, min(1.0, gpu["gpu_util"] / 100.0))
    load_end = 135 + max(4, int(round(270 * load_ratio)))
    draw.arc([94, 94, S - 94, S - 94], start=135, end=load_end, fill=(16, 185, 129), width=18)

    state_txt = llm["state_text"]
    f_pill = load_font(FONT_BOLD_PATH, 23 if len(state_txt) > 15 else 26)
    f_tag = load_font(FONT_BOLD_PATH, 24)
    f_title = load_font(FONT_BOLD_PATH, 50)
    f_meta = load_font(FONT_BOLD_PATH, 26)
    f_vram = load_font(FONT_BOLD_PATH, 30)
    f_mlbl = load_font(FONT_BOLD_PATH, 22)
    f_mval = load_font(FONT_BOLD_PATH, 36)

    pill_w = 376 if len(state_txt) > 15 else 330
    pill_h = 52
    pill_x = (S - pill_w) // 2
    pill_y = 165
    dot_color = (251, 191, 36) if llm.get("sleeping") else ((16, 185, 129) if llm["loaded"] else (0, 229, 255))
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=26, fill=(10, 25, 42), outline=dot_color, width=3)
    draw.ellipse([pill_x + 22, pill_y + 16, pill_x + 42, pill_y + 36], fill=dot_color)
    draw.text((pill_x + pill_w // 2 + 12, pill_y + pill_h // 2), state_txt, font=f_pill, fill=(240, 249, 255), anchor="mm")

    draw.text((S // 2, 258), llm.get("tag", "ACTIVE GPU LLM"), font=f_tag, fill=(0, 210, 255), anchor="mm")
    title_text = llm["name"]
    title_font = f_title if len(title_text) <= 16 else load_font(FONT_BOLD_PATH, 44)
    draw.text((S // 2, 318), title_text, font=title_font, fill=(248, 250, 252), anchor="mm")
    draw.text((S // 2, 374), llm["meta"], font=f_meta, fill=(148, 163, 184), anchor="mm")

    bar_w, bar_h = 540, 26
    bar_x, bar_y = (S - bar_w) // 2, 430
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=13, fill=(15, 28, 48), outline=(35, 65, 100), width=2)
    fill_w = max(20, int(round(bar_w * min(1.0, gpu["vram_ratio"]))))
    draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=13, fill=(0, 215, 255))

    vram_pct = int(round(gpu["vram_ratio"] * 100))
    draw.text((S // 2, 492), f"VRAM  {gpu['vram_used_gb']:.1f} / {gpu['vram_total_gb']:.1f} GB  ({vram_pct}%)", font=f_vram, fill=(226, 232, 240), anchor="mm")

    box_w, box_h, gap = 172, 112, 20
    start_x = (S - (3 * box_w + 2 * gap)) // 2
    box_y = 548
    cards = [
        ("GPU USE", f"{gpu['gpu_util']}%", (16, 185, 129) if gpu["gpu_util"] > 5 else (248, 250, 252)),
        ("POWER", f"{gpu['power_w']}W", (56, 189, 248)),
        ("TEMP", f"{gpu['temp_c']}°C", (251, 191, 36) if gpu["temp_c"] >= 70 else (248, 250, 252)),
    ]
    for i, (lbl, val, col) in enumerate(cards):
        bx = start_x + i * (box_w + gap)
        draw.rounded_rectangle([bx, box_y, bx + box_w, box_y + box_h], radius=18, fill=(10, 20, 36), outline=(28, 52, 84), width=3)
        draw.text((bx + box_w // 2, box_y + 34), lbl, font=f_mlbl, fill=(148, 163, 184), anchor="mm")
        draw.text((bx + box_w // 2, box_y + 78), val, font=f_mval, fill=col, anchor="mm")

    g_label = gpu.get("name", "GPU")
    draw.text((S // 2, 720), f"{g_label} // AI COMPUTE", font=f_mlbl, fill=(0, 180, 255), anchor="mm")
    return img.resize((480, 480), Image.Resampling.LANCZOS)


def render_theme_cooling_cockpit(gpu, llm, cpu, cooling, now_dt=None):
    """Cryo Dual-Loop Cockpit: Left arc = CPU °C, Right arc = GPU °C, Center = Liquid °C + Pump/Fan RPMs."""
    S = 960
    img = Image.new("RGB", (S, S), (4, 11, 22))
    draw = ImageDraw.Draw(img)
    draw.ellipse([18, 18, S - 18, S - 18], fill=(6, 15, 28), outline=(20, 60, 95), width=6)

    # Left Gauge Track (CPU: 120° -> 240°)
    draw.arc([58, 58, S - 58, S - 58], start=120, end=240, fill=(18, 36, 58), width=32)
    cpu_ratio = max(0.05, min(1.0, (cpu["temp_c"] - 20) / 70.0))
    cpu_col = (56, 189, 248) if cpu["temp_c"] < 65 else ((251, 191, 36) if cpu["temp_c"] < 80 else (239, 68, 68))
    draw.arc([58, 58, S - 58, S - 58], start=120, end=120 + int(120 * cpu_ratio), fill=cpu_col, width=32)

    # Right Gauge Track (GPU: 300° -> 420°)
    draw.arc([58, 58, S - 58, S - 58], start=300, end=420, fill=(18, 36, 58), width=32)
    gpu_ratio = max(0.05, min(1.0, (gpu["temp_c"] - 20) / 68.0))
    gpu_col = (16, 185, 129) if gpu["temp_c"] < 62 else ((251, 191, 36) if gpu["temp_c"] < 78 else (239, 68, 68))
    draw.arc([58, 58, S - 58, S - 58], start=300, end=300 + int(120 * gpu_ratio), fill=gpu_col, width=32)

    # Inner liquid halo arc (cleanly framing upper dome above bottom cards)
    draw.arc([195, 195, S - 195, S - 195], start=192, end=348, fill=(14, 116, 144), width=4)

    f_hdr = load_font(FONT_BOLD_PATH, 24)
    f_big = load_font(FONT_BOLD_PATH, 108)
    f_unit = load_font(FONT_BOLD_PATH, 32)
    f_side_lbl = load_font(FONT_BOLD_PATH, 24)
    f_side_val = load_font(FONT_BOLD_PATH, 52)
    f_card_l = load_font(FONT_BOLD_PATH, 20)
    f_card_v = load_font(FONT_BOLD_PATH, 34)

    draw.text((S // 2, 145), "CRYO THERMAL COCKPIT", font=f_hdr, fill=(56, 189, 248), anchor="mm")

    # Center Liquid Temp
    draw.text((S // 2, 265), "COOLANT LOOP", font=f_side_lbl, fill=(125, 211, 252), anchor="mm")
    draw.text((S // 2, 365), f"{cooling['liquid_c']:.1f}°", font=f_big, fill=(240, 249, 255), anchor="mm")
    draw.text((S // 2, 442), f"PUMP {cooling['pump_rpm']} RPM", font=f_unit, fill=(0, 229, 255), anchor="mm")

    # Left CPU & Right GPU readouts
    draw.text((205, 420), "CPU", font=f_side_lbl, fill=(148, 163, 184), anchor="mm")
    draw.text((205, 475), f"{cpu['temp_c']}°", font=f_side_val, fill=cpu_col, anchor="mm")

    draw.text((S - 205, 420), "GPU", font=f_side_lbl, fill=(148, 163, 184), anchor="mm")
    draw.text((S - 205, 475), f"{gpu['temp_c']}°", font=f_side_val, fill=gpu_col, anchor="mm")

    # Bottom 3 cooling pills: CASE FANS / GPU FANS / POWER
    g_tag = gpu.get("short_tag", "GPU")
    cards = [
        ("CASE FANS", f"{cooling['fan_rpm']} RPM", (125, 211, 252)),
        (f"{g_tag} FANS", f"{gpu['fan_pct']}%", (52, 211, 153)),
        ("GPU DRAW", f"{gpu['power_w']}W", (248, 250, 252)),
    ]
    bw, bh, gap = 186, 108, 18
    sx = (S - (3 * bw + 2 * gap)) // 2
    by = 568
    for i, (l_txt, v_txt, col) in enumerate(cards):
        bx = sx + i * (bw + gap)
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=18, fill=(9, 22, 38), outline=(26, 58, 92), width=3)
        draw.text((bx + bw // 2, by + 32), l_txt, font=f_card_l, fill=(148, 163, 184), anchor="mm")
        draw.text((bx + bw // 2, by + 74), v_txt, font=f_card_v, fill=col, anchor="mm")

    draw.text((S // 2, 742), "TITAN 360 RX // 8× CORSAIR RX", font=f_card_l, fill=(56, 189, 248), anchor="mm")
    return img.resize((480, 480), Image.Resampling.LANCZOS)


def render_theme_chrono_pulse(gpu, llm, cpu, cooling, now_dt=None):
    """Neon Chrono & System Pulse: Watchmaker 60-tick dial, sweeping seconds arc, giant HH:MM & live temps."""
    S = 960
    if now_dt is None:
        now_dt = datetime.datetime.now()
    img = Image.new("RGB", (S, S), (6, 9, 18))
    draw = ImageDraw.Draw(img)
    cx, cy = S // 2, S // 2

    draw.ellipse([20, 20, S - 20, S - 20], fill=(8, 12, 24), outline=(30, 41, 59), width=5)

    # 60 precision radial tick marks
    sec_now = now_dt.second
    for s in range(60):
        ang = math.radians(s * 6 - 90)
        is_major = (s % 5) == 0
        r_outer = 432
        r_inner = 396 if is_major else 412
        x1, y1 = cx + r_inner * math.cos(ang), cy + r_inner * math.sin(ang)
        x2, y2 = cx + r_outer * math.cos(ang), cy + r_outer * math.sin(ang)
        if s <= sec_now:
            col = (56, 189, 248) if is_major else (14, 165, 233)
        else:
            col = (51, 65, 85) if is_major else (30, 41, 59)
        draw.line([(x1, y1), (x2, y2)], fill=col, width=7 if is_major else 3)

    # Sweeping seconds inner neon ring
    sec_deg = -90 + max(3, int(round((sec_now / 60.0) * 360)))
    draw.arc([108, 108, S - 108, S - 108], start=-90, end=sec_deg, fill=(168, 85, 247), width=10)

    f_date = load_font(FONT_BOLD_PATH, 28)
    f_time = load_font(FONT_BOLD_PATH, 148)
    f_sec = load_font(FONT_BOLD_PATH, 40)
    f_pill = load_font(FONT_BOLD_PATH, 26)
    f_sub = load_font(FONT_BOLD_PATH, 22)

    date_str = now_dt.strftime("%a • %d %b %Y").upper()
    draw.text((cx, 250), date_str, font=f_date, fill=(168, 85, 247), anchor="mm")

    time_str = now_dt.strftime("%H:%M")
    draw.text((cx - 24, 395), time_str, font=f_time, fill=(248, 250, 252), anchor="mm")
    draw.text((cx + 255, 362), now_dt.strftime(":%S"), font=f_sec, fill=(56, 189, 248), anchor="mm")

    # Model / Status banner
    banner = f"AI: {llm['name']}" if llm.get("loaded") else f"PUMP {cooling['pump_rpm']} RPM • FANS {cooling['fan_rpm']} RPM"
    draw.text((cx, 512), banner, font=f_sub, fill=(148, 163, 184), anchor="mm")

    # Bottom 3 sleek telemetry badges
    badges = [
        (f"CPU {cpu['temp_c']}°C", (56, 189, 248)),
        (f"GPU {gpu['temp_c']}°C", (16, 185, 129)),
        (f"LIQ {cooling['liquid_c']:.0f}°C", (192, 132, 252)),
    ]
    pw, ph, gap = 178, 64, 16
    sx = (S - (3 * pw + 2 * gap)) // 2
    py = 576
    for i, (txt, col) in enumerate(badges):
        bx = sx + i * (pw + gap)
        draw.rounded_rectangle([bx, py, bx + pw, py + ph], radius=32, fill=(15, 23, 42), outline=col, width=3)
        draw.text((bx + pw // 2, py + ph // 2), txt, font=f_pill, fill=(241, 245, 249), anchor="mm")

    return img.resize((480, 480), Image.Resampling.LANCZOS)


def render_theme_tensor_reactor(gpu, llm, cpu, cooling, now_dt=None):
    """GA102 Tensor Arc Reactor: 24 segmented power blades + concentric glowing core."""
    S = 960
    img = Image.new("RGB", (S, S), (3, 8, 16))
    draw = ImageDraw.Draw(img)
    cx, cy = S // 2, S // 2

    draw.ellipse([18, 18, S - 18, S - 18], fill=(4, 10, 22), outline=(0, 190, 255), width=5)

    # 24 segmented arc reactor blades tracking GPU Power (0..360W)
    pwr_ratio = min(1.0, max(0.08, gpu["power_w"] / 360.0))
    lit_segs = max(2, int(round(pwr_ratio * 24)))
    for i in range(24):
        a0 = -90 + i * 15 + 2
        a1 = a0 + 11
        col = (0, 229, 255) if i < lit_segs else (14, 30, 52)
        if i < lit_segs and i >= 18:
            col = (251, 191, 36)
        draw.arc([58, 58, S - 58, S - 58], start=a0, end=a1, fill=col, width=38)

    # Inner VRAM ring
    draw.arc([118, 118, S - 118, S - 118], start=0, end=360, fill=(12, 26, 46), width=14)
    v_deg = int(round(360 * min(1.0, gpu["vram_ratio"])))
    if v_deg > 0:
        draw.arc([118, 118, S - 118, S - 118], start=-90, end=-90 + v_deg, fill=(56, 189, 248), width=14)

    # Glowing Reactor Core Circle
    draw.ellipse([195, 195, S - 195, S - 195], fill=(7, 18, 36), outline=(0, 229, 255), width=6)
    draw.ellipse([218, 218, S - 218, S - 218], outline=(14, 116, 144), width=2)

    f_top = load_font(FONT_BOLD_PATH, 24)
    f_big = load_font(FONT_BOLD_PATH, 96)
    f_mid = load_font(FONT_BOLD_PATH, 30)
    f_bot = load_font(FONT_BOLD_PATH, 25)

    draw.text((cx, 285), "GA102 // TENSOR CORE", font=f_top, fill=(56, 189, 248), anchor="mm")
    draw.text((cx, 392), f"{gpu['power_w']}W", font=f_big, fill=(240, 249, 255), anchor="mm")
    draw.text(
        (cx, 478),
        f"GPU {gpu['temp_c']}°C  •  LOAD {gpu['gpu_util']}%",
        font=f_mid,
        fill=(52, 211, 153),
        anchor="mm",
    )
    sub_line = llm["name"] if llm.get("loaded") else f"VRAM {gpu['vram_used_gb']:.1f}G / 24G • CPU {cpu['temp_c']}°C"
    draw.text((cx, 545), sub_line, font=f_bot, fill=(148, 163, 184), anchor="mm")
    draw.text((cx, 618), f"BF16 UNLOCKED • FAN {gpu['fan_pct']}%", font=f_top, fill=(0, 200, 255), anchor="mm")

    return img.resize((480, 480), Image.Resampling.LANCZOS)


def render_theme_motorsport_gt(gpu, llm, cpu, cooling, now_dt=None):
    """Motorsport GT Gauge: 270° racing tachometer needle + redline arc + digital gear-style telemetry."""
    S = 960
    img = Image.new("RGB", (S, S), (10, 10, 14))
    draw = ImageDraw.Draw(img)
    cx, cy = S // 2, S // 2

    draw.ellipse([18, 18, S - 18, S - 18], fill=(14, 15, 20), outline=(60, 64, 78), width=6)

    # Background scale arc (135° to 405°, with redline from 350° to 405°)
    draw.arc([64, 64, S - 64, S - 64], start=135, end=350, fill=(32, 36, 46), width=30)
    draw.arc([64, 64, S - 64, S - 64], start=350, end=405, fill=(127, 29, 29), width=30)

    # Combined performance index: max of GPU util, CPU util, or power%
    perf_pct = max(gpu["gpu_util"], cpu["util"], int(round((gpu["power_w"] / 360.0) * 100)))
    perf_pct = max(3, min(100, perf_pct))
    active_end = 135 + int(round(2.7 * perf_pct))
    trail_col = (245, 158, 11) if perf_pct < 80 else (239, 68, 68)
    draw.arc([64, 64, S - 64, S - 64], start=135, end=active_end, fill=trail_col, width=30)

    # Major scale numbers 0..10 (x10%)
    f_num = load_font(FONT_BOLD_PATH, 30)
    for step in range(11):
        deg = 135 + step * 27
        rad = math.radians(deg)
        tx = cx + 345 * math.cos(rad)
        ty = cy + 345 * math.sin(rad)
        ncol = (239, 68, 68) if step >= 8 else (226, 232, 240)
        draw.text((tx, ty), str(step), font=f_num, fill=ncol, anchor="mm")

    # Racing Needle
    n_rad = math.radians(active_end)
    nx = cx + 315 * math.cos(n_rad)
    ny = cy + 315 * math.sin(n_rad)
    draw.line([(cx, cy), (nx, ny)], fill=(239, 68, 68), width=10)
    draw.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=(30, 32, 40), outline=(245, 158, 11), width=5)

    # Lower digital GT readout box (clear of 0 and 10 scale numbers)
    draw.rounded_rectangle([272, 525, S - 272, 708], radius=22, fill=(20, 22, 30), outline=(245, 158, 11), width=3)
    f_gt_big = load_font(FONT_BOLD_PATH, 48)
    f_gt_sub = load_font(FONT_BOLD_PATH, 21)
    draw.text((cx, 578), f"{gpu['temp_c']}°C  |  {gpu['power_w']}W", font=f_gt_big, fill=(248, 250, 252), anchor="mm")
    draw.text(
        (cx, 638),
        f"CPU {cpu['temp_c']}°C • {cooling['fan_rpm']} RPM",
        font=f_gt_sub,
        fill=(251, 191, 36),
        anchor="mm",
    )
    draw.text((cx, 676), f"LOAD INDEX {perf_pct}%", font=f_gt_sub, fill=(148, 163, 184), anchor="mm")
    draw.text((cx, 255), "GT TELEMETRY", font=f_gt_sub, fill=(245, 158, 11), anchor="mm")

    return img.resize((480, 480), Image.Resampling.LANCZOS)


def render_theme_stealth_zen(gpu, llm, cpu, cooling, now_dt=None):
    """Stealth Minimal OLED: Pitch-black #000000 zero-glare face with crisp monochrome telemetry."""
    S = 960
    if now_dt is None:
        now_dt = datetime.datetime.now()
    img = Image.new("RGB", (S, S), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = S // 2, S // 2

    draw.ellipse([36, 36, S - 36, S - 36], outline=(38, 42, 52), width=3)

    f_clock = load_font(FONT_REG_PATH, 124)
    f_lbl = load_font(FONT_BOLD_PATH, 22)
    f_val = load_font(FONT_BOLD_PATH, 46)
    f_foot = load_font(FONT_REG_PATH, 24)

    now_str = now_dt.strftime("%H:%M")
    draw.text((cx, 330), now_str, font=f_clock, fill=(226, 232, 240), anchor="mm")

    draw.line([(240, 445), (S - 240, 445)], fill=(38, 42, 52), width=2)

    cols = [
        (270, "CPU", f"{cpu['temp_c']}°"),
        (480, "GPU", f"{gpu['temp_c']}°"),
        (690, "LIQ", f"{cooling['liquid_c']:.0f}°"),
    ]
    for x_pos, l_txt, v_txt in cols:
        draw.text((x_pos, 515), l_txt, font=f_lbl, fill=(100, 116, 139), anchor="mm")
        draw.text((x_pos, 575), v_txt, font=f_val, fill=(203, 213, 225), anchor="mm")

    sub = llm["name"] if llm.get("loaded") else f"{cooling['fan_rpm']} RPM  •  {gpu['power_w']}W"
    draw.text((cx, 690), sub, font=f_foot, fill=(71, 85, 105), anchor="mm")

    return img.resize((480, 480), Image.Resampling.LANCZOS)


_CRT_SCANLINE_CACHE = None
_ADI_MASK_CACHE = None


def _draw_tapered_hand(draw, cx, cy, angle_deg, length, tail, w_base, w_tip, fill_col, lume_col=None):
    rad = math.radians(angle_deg)
    perp = rad + math.pi / 2.0
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    cos_p, sin_p = math.cos(perp), math.sin(perp)

    bx, by = cx - tail * cos_r, cy - tail * sin_r
    tx, ty = cx + length * cos_r, cy + length * sin_r
    pts = [
        (bx + w_base * cos_p, by + w_base * sin_p),
        (tx + w_tip * cos_p, ty + w_tip * sin_p),
        (tx + 12 * cos_r, ty + 12 * sin_r),
        (tx - w_tip * cos_p, ty - w_tip * sin_p),
        (bx - w_base * cos_p, by - w_base * sin_p),
    ]
    draw.polygon(pts, fill=fill_col)
    if lume_col is not None:
        lx1, ly1 = cx + 38 * cos_r, cy + 38 * sin_r
        lx2, ly2 = cx + (length - 22) * cos_r, cy + (length - 22) * sin_r
        draw.line([(lx1, ly1), (lx2, ly2)], fill=lume_col, width=max(3, int(w_tip * 1.3)))


def render_theme_swiss_tourbillon(gpu, llm, cpu, cooling, now_dt=None):
    """Swiss Skeleton Chrono: Luxury mechanical watch face with ticking crimson seconds & CPU/GPU sub-dials."""
    S = 960
    if now_dt is None:
        now_dt = datetime.datetime.now()
    img = Image.new("RGB", (S, S), (7, 9, 14))
    draw = ImageDraw.Draw(img)
    cx, cy = S // 2, S // 2

    # Champagne-gold case & chapter rings
    draw.ellipse([18, 18, S - 18, S - 18], fill=(9, 12, 18), outline=(196, 154, 78), width=6)
    draw.ellipse([42, 42, S - 42, S - 42], outline=(82, 66, 38), width=2)
    draw.ellipse([162, 162, S - 162, S - 162], outline=(22, 28, 40), width=2)

    # 60 chapter ticks + 12 applied gold/Super-LumiNova baton markers
    for i in range(60):
        ang = math.radians(i * 6 - 90)
        ca, sa = math.cos(ang), math.sin(ang)
        if i == 0:
            # Signature Swiss double baton at 12 o'clock
            px, py = -sa * 9.0, ca * 9.0
            for sign in (-1, 1):
                x1, y1 = cx + 384 * ca + sign * px, cy + 384 * sa + sign * py
                x2, y2 = cx + 432 * ca + sign * px, cy + 432 * sa + sign * py
                draw.line([(x1, y1), (x2, y2)], fill=(218, 172, 82), width=10)
                draw.line([(x1 + 4 * ca, y1 + 4 * sa), (x2 - 4 * ca, y2 - 4 * sa)], fill=(248, 250, 252), width=4)
        elif i % 5 == 0:
            x1, y1 = cx + 388 * ca, cy + 388 * sa
            x2, y2 = cx + 432 * ca, cy + 432 * sa
            draw.line([(x1, y1), (x2, y2)], fill=(218, 172, 82), width=11)
            draw.line([(x1 + 5 * ca, y1 + 5 * sa), (x2 - 5 * ca, y2 - 5 * sa)], fill=(248, 250, 252), width=5)
        else:
            x1, y1 = cx + 414 * ca, cy + 414 * sa
            x2, y2 = cx + 432 * ca, cy + 432 * sa
            draw.line([(x1, y1), (x2, y2)], fill=(120, 100, 64), width=3)

    f_brand = load_font(FONT_BOLD_PATH, 24)
    f_sub = load_font(FONT_BOLD_PATH, 18)
    f_slbl = load_font(FONT_BOLD_PATH, 20)
    f_sval = load_font(FONT_BOLD_PATH, 26)
    f_comp = load_font(FONT_BOLD_PATH, 23)

    # 12H Crown Crest & Dial Branding
    draw.polygon([(cx, 138), (cx + 12, 154), (cx, 170), (cx - 12, 154)], fill=(234, 179, 8))
    draw.text((cx, 202), "CHRONOMETRE", font=f_brand, fill=(234, 179, 8), anchor="mm")
    draw.text((cx, 232), "TITAN 360  •  SWISS", font=f_sub, fill=(148, 163, 184), anchor="mm")

    # Recessed Horological Sub-Dials at 9H (CPU °C) & 3H (GPU °C)
    g_tag = gpu.get("short_tag", "GPU")
    subdials = [
        (248, 480, "CPU", cpu["temp_c"], 20, 95, (56, 189, 248)),
        (712, 480, g_tag, gpu["temp_c"], 20, 90, (52, 211, 153)),
    ]
    for sx, sy, slbl, val_c, vmin, vmax, scol in subdials:
        sr = 102
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(14, 18, 27), outline=(168, 130, 62), width=3)
        draw.arc([sx - 84, sy - 84, sx + 84, sy + 84], start=135, end=405, fill=(32, 40, 56), width=6)
        ratio = max(0.03, min(1.0, (val_c - vmin) / float(vmax - vmin)))
        s_end = 135 + int(round(270 * ratio))
        draw.arc([sx - 84, sy - 84, sx + 84, sy + 84], start=135, end=s_end, fill=scol, width=6)
        for st in range(9):
            sa_rad = math.radians(135 + st * 33.75)
            draw.line(
                [(sx + 74 * math.cos(sa_rad), sy + 74 * math.sin(sa_rad)), (sx + 88 * math.cos(sa_rad), sy + 88 * math.sin(sa_rad))],
                fill=(140, 114, 64),
                width=2,
            )
        draw.text((sx, sy - 42), slbl, font=f_slbl, fill=(196, 164, 104), anchor="mm")
        draw.text((sx, sy + 52), f"{val_c}°C", font=f_sval, fill=(248, 250, 252), anchor="mm")
        hand_r = math.radians(s_end)
        draw.line([(sx, sy), (sx + 68 * math.cos(hand_r), sy + 68 * math.sin(hand_r))], fill=(234, 179, 8), width=5)
        draw.ellipse([sx - 8, sy - 8, sx + 8, sy + 8], fill=(234, 179, 8))

    # 6H Beveled Date & Coolant Aperture
    psu_w = cooling.get("psu_total_w") or (gpu["power_w"] + 75)
    draw.rounded_rectangle([322, 648, 638, 714], radius=16, fill=(14, 18, 27), outline=(180, 140, 68), width=3)
    date_lbl = now_dt.strftime("%a %d").upper()
    draw.text((cx, 681), f"{date_lbl}   •   LIQ {cooling['liquid_c']:.1f}°C", font=f_comp, fill=(248, 250, 252), anchor="mm")
    draw.text((cx, 748), f"HX1200i {psu_w}W  •  {cooling['pump_rpm']} RPM", font=f_sub, fill=(180, 148, 88), anchor="mm")

    # Main Analog Hands (Hour, Minute, Ticking Crimson Seconds)
    sec_val = now_dt.second
    min_deg = (now_dt.minute + sec_val / 60.0) * 6.0 - 90.0
    hr_deg = ((now_dt.hour % 12) + now_dt.minute / 60.0) * 30.0 - 90.0
    sec_deg = sec_val * 6.0 - 90.0

    _draw_tapered_hand(draw, cx, cy, hr_deg, length=230, tail=42, w_base=12, w_tip=5.5, fill_col=(222, 178, 88), lume_col=(248, 250, 252))
    _draw_tapered_hand(draw, cx, cy, min_deg, length=344, tail=52, w_base=9.5, w_tip=4.0, fill_col=(238, 198, 112), lume_col=(248, 250, 252))

    sr_rad = math.radians(sec_deg)
    sc, ss = math.cos(sr_rad), math.sin(sr_rad)
    draw.line([(cx - 92 * sc, cy - 92 * ss), (cx + 390 * sc, cy + 390 * ss)], fill=(239, 68, 68), width=5)
    lx, ly = cx + 305 * sc, cy + 305 * ss
    draw.ellipse([lx - 9, ly - 9, lx + 9, ly + 9], fill=(248, 250, 252), outline=(239, 68, 68), width=4)
    draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(222, 178, 88), outline=(20, 24, 34), width=4)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(239, 68, 68))

    return img.resize((480, 480), Image.Resampling.LANCZOS)


def render_theme_hx1200i_power_grid(gpu, llm, cpu, cooling, now_dt=None):
    """HX1200i Power Plant: Live 1200W Platinum PSU wattage, +12V/5V/3.3V rails, GPU share & Eco status."""
    S = 960
    img = Image.new("RGB", (S, S), (6, 12, 16))
    draw = ImageDraw.Draw(img)
    cx = S // 2

    draw.ellipse([18, 18, S - 18, S - 18], fill=(8, 15, 20), outline=(77, 124, 15), width=6)

    w_12v = float(cooling.get("psu_12v_w") or 0.0)
    w_5v = float(cooling.get("psu_5v_w") or 0.0)
    w_3v3 = float(cooling.get("psu_3v3_w") or 0.0)
    psu_w = int(cooling.get("psu_total_w") or 0)
    if psu_w <= 0:
        w_3v3, w_5v = 5.8, 10.4
        w_12v = float(gpu["power_w"] + 68)
        psu_w = int(round(w_12v + w_5v + w_3v3))

    psu_rpm = int(cooling.get("psu_rpm") or 0)
    psu_temp = float(cooling.get("psu_temp_c") or 40.0)

    # 30-segment 270° 1200W Load Meter
    lit = max(2, min(30, int(round((psu_w / 1200.0) * 30))))
    for i in range(30):
        a0 = 135 + i * 9 + 1
        a1 = a0 + 6.8
        if i < lit:
            col = (163, 230, 53) if i < 16 else ((250, 204, 21) if i < 24 else (239, 68, 68))
        else:
            col = (24, 42, 36)
        draw.arc([56, 56, S - 56, S - 56], start=a0, end=a1, fill=col, width=32)

    f_pill = load_font(FONT_BOLD_PATH, 22)
    f_lbl = load_font(FONT_BOLD_PATH, 21)
    f_big = load_font(FONT_BOLD_PATH, 108)
    f_sub = load_font(FONT_BOLD_PATH, 23)
    f_card_l = load_font(FONT_BOLD_PATH, 20)
    f_card_v = load_font(FONT_BOLD_PATH, 34)

    eco_txt = "HX1200i  •  ZERO-RPM ECO" if psu_rpm == 0 else f"HX1200i  •  FAN {psu_rpm} RPM"
    draw.rounded_rectangle([282, 134, 678, 184], radius=25, fill=(13, 28, 22), outline=(163, 230, 53), width=3)
    draw.text((cx, 159), eco_txt, font=f_pill, fill=(217, 249, 157), anchor="mm")

    draw.text((cx, 226), "TOTAL DC SYSTEM OUTPUT", font=f_lbl, fill=(148, 163, 184), anchor="mm")
    draw.text((cx, 316), f"{psu_w}W", font=f_big, fill=(248, 250, 252), anchor="mm")
    cap_pct = min(100, int(round((psu_w / 1200.0) * 100)))
    draw.text((cx, 392), f"{cap_pct}% OF 1200W PLATINUM", font=f_sub, fill=(163, 230, 53), anchor="mm")

    # Stacked Rail Breakdown Bar (RTX 3090 vs CPU/Sys +12V vs 5V+3.3V)
    w_minor = max(1.0, w_3v3 + w_5v)
    gpu_share = min(max(w_12v, float(gpu["power_w"])), float(gpu["power_w"]))
    sys_12v = max(4.0, w_12v - gpu_share)
    tot_split = max(1.0, gpu_share + sys_12v + w_minor)

    bx0, by0, bw, bh = 180, 434, 600, 28
    draw.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=14, fill=(18, 30, 36))
    w_g = max(24, int(round(bw * (gpu_share / tot_split))))
    w_s = max(24, int(round(bw * (sys_12v / tot_split))))
    w_g = min(bw - 48, w_g)
    w_s = min(bw - w_g - 20, w_s)
    draw.rounded_rectangle([bx0, by0, bx0 + w_g, by0 + bh], radius=12, fill=(56, 189, 248))
    draw.rectangle([bx0 + w_g, by0, bx0 + w_g + w_s, by0 + bh], fill=(163, 230, 53))
    draw.rounded_rectangle([bx0 + w_g + w_s, by0, bx0 + bw, by0 + bh], radius=12, fill=(250, 204, 21))
    draw.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=14, outline=(52, 82, 66), width=2)

    g_tag = gpu.get("short_tag", "GPU")
    draw.text(
        (cx, 496),
        f"{g_tag} {int(round(gpu_share))}W   •   SYS 12V {int(round(sys_12v))}W   •   5V/3.3V {w_minor:.0f}W",
        font=f_lbl,
        fill=(203, 213, 225),
        anchor="mm",
    )

    cards = [
        ("+12V RAIL", f"{w_12v:.0f}W", (163, 230, 53)),
        (f"{g_tag} GPU", f"{gpu['power_w']}W", (56, 189, 248)),
        ("PSU TEMP", f"{psu_temp:.0f}°C", (250, 204, 21)),
    ]
    cw, ch, gap = 180, 104, 18
    sx = (S - (3 * cw + 2 * gap)) // 2
    cy_card = 542
    for i, (clbl, cval, ccol) in enumerate(cards):
        x = sx + i * (cw + gap)
        draw.rounded_rectangle([x, cy_card, x + cw, cy_card + ch], radius=18, fill=(11, 22, 28), outline=(38, 72, 52), width=3)
        draw.text((x + cw // 2, cy_card + 32), clbl, font=f_card_l, fill=(148, 163, 184), anchor="mm")
        draw.text((x + cw // 2, cy_card + 72), cval, font=f_card_v, fill=ccol, anchor="mm")

    draw.text((cx, 716), "CORSAIR HX1200i // DIGITAL RAILS", font=f_card_l, fill=(132, 204, 22), anchor="mm")
    return img.resize((480, 480), Image.Resampling.LANCZOS)


def render_theme_silicon_matrix(gpu, llm, cpu, cooling, now_dt=None):
    """14600K x GA102 Matrix: Live 20-thread CPU spectrum analyzer, GHz/MHz clocks, 32GB RAM & 24GB VRAM."""
    S = 960
    img = Image.new("RGB", (S, S), (6, 8, 20))
    draw = ImageDraw.Draw(img)
    cx = S // 2

    draw.ellipse([18, 18, S - 18, S - 18], fill=(8, 10, 26), outline=(99, 102, 241), width=5)

    # Left Outer Arc = System RAM, Right Outer Arc = RTX 3090 VRAM
    ram_ratio = float(cpu.get("ram_ratio", 0.2))
    draw.arc([56, 56, S - 56, S - 56], start=122, end=238, fill=(24, 22, 52), width=26)
    draw.arc([56, 56, S - 56, S - 56], start=122, end=122 + max(4, int(round(116 * ram_ratio))), fill=(168, 85, 247), width=26)

    draw.arc([56, 56, S - 56, S - 56], start=302, end=418, fill=(18, 32, 56), width=26)
    vram_arc_deg = max(4, int(round(116 * min(1.0, gpu["vram_ratio"]))))
    draw.arc([56, 56, S - 56, S - 56], start=418 - vram_arc_deg, end=418, fill=(56, 189, 248), width=26)

    f_hdr = load_font(FONT_BOLD_PATH, 22)
    f_clk = load_font(FONT_BOLD_PATH, 26)
    f_mono = load_font(FONT_MONO_PATH, 18)
    f_mem = load_font(FONT_BOLD_PATH, 25)
    f_card_l = load_font(FONT_BOLD_PATH, 19)
    f_card_v = load_font(FONT_BOLD_PATH, 30)

    draw.text((cx, 148), "SILICON COMPUTE MATRIX", font=f_hdr, fill=(192, 132, 252), anchor="mm")
    cpu_ghz = float(cpu.get("max_ghz") or 5.0)
    sm_mhz = int(gpu.get("sm_clock_mhz") or 0)
    cpu_tag = cpu.get("short_name", "CPU")
    g_tag = gpu.get("short_tag", "GPU")
    draw.text((cx, 198), f"{cpu_tag} {cpu_ghz:.2f} GHz  •  {g_tag} {sm_mhz} MHz", font=f_clk, fill=(248, 250, 252), anchor="mm")

    # 20-Thread Logic Analyzer Box
    fx0, fy0, fx1, fy1 = 148, 240, 812, 474
    draw.rounded_rectangle([fx0, fy0, fx1, fy1], radius=20, fill=(10, 14, 34), outline=(79, 70, 229), width=3)
    for gy in (290, 340, 390):
        draw.line([(fx0 + 18, gy), (fx1 - 18, gy)], fill=(24, 30, 62), width=2)

    raw_threads = list(cpu.get("threads") or [])
    if len(raw_threads) < 20:
        raw_threads.extend([cpu["util"]] * (20 - len(raw_threads)))
    threads = raw_threads[:20]

    bar_w, gap = 22, 9
    sx = (S - (20 * bar_w + 19 * gap)) // 2
    y_base = 436
    max_h = 174
    for idx, t_pct in enumerate(threads):
        bx = sx + idx * (bar_w + gap)
        h = max(10, int(round(max_h * (t_pct / 100.0))))
        if idx < 12:
            bcol = (56, 189, 248) if t_pct < 70 else (168, 85, 247)
            cap = (186, 230, 253)
        else:
            bcol = (52, 211, 153) if t_pct < 70 else (236, 72, 153)
            cap = (251, 207, 232)
        draw.rounded_rectangle([bx, y_base - h, bx + bar_w, y_base], radius=5, fill=bcol)
        draw.rectangle([bx, max(fy0 + 12, y_base - h - 6), bx + bar_w, max(fy0 + 16, y_base - h - 2)], fill=cap)

    draw.text((cx, 456), "P-THREADS 0–11            •            E-THREADS 12–19", font=f_mono, fill=(148, 163, 184), anchor="mm")

    ram_u = float(cpu.get("ram_used_gb", 5.5))
    ram_t = float(cpu.get("ram_total_gb", 32.0))
    vram_t = float(gpu.get("vram_total_gb", 24.0))
    draw.text(
        (cx, 514),
        f"RAM {ram_u:.1f}/{ram_t:.0f}G   •   VRAM {gpu['vram_used_gb']:.1f}/{vram_t:.0f}G",
        font=f_mem,
        fill=(226, 232, 240),
        anchor="mm",
    )

    cards = [
        ("CPU", f"{cpu['util']}% • {cpu['temp_c']}°", (168, 85, 247)),
        (g_tag, f"{gpu['gpu_util']}% • {gpu['temp_c']}°", (56, 189, 248)),
        ("LIQUID", f"{cooling['liquid_c']:.1f}°C", (52, 211, 153)),
    ]
    cw, ch, cgap = 180, 98, 16
    csx = (S - (3 * cw + 2 * cgap)) // 2
    cy_c = 556
    for i, (clbl, cval, ccol) in enumerate(cards):
        x = csx + i * (cw + cgap)
        draw.rounded_rectangle([x, cy_c, x + cw, cy_c + ch], radius=18, fill=(12, 16, 38), outline=ccol, width=3)
        draw.text((x + cw // 2, cy_c + 28), clbl, font=f_card_l, fill=(148, 163, 184), anchor="mm")
        draw.text((x + cw // 2, cy_c + 66), cval, font=f_card_v, fill=(248, 250, 252), anchor="mm")

    draw.text((cx, 714), f"{len(cpu.get('threads') or threads)} THREADS  //  {gpu.get('name', 'GPU')}", font=f_card_l, fill=(129, 140, 248), anchor="mm")
    return img.resize((480, 480), Image.Resampling.LANCZOS)


def _fmt_net_mbps(mbps: float) -> str:
    if mbps >= 1000.0:
        return f"{mbps / 1000.0:.2f}G"
    if mbps >= 10.0:
        return f"{mbps:.0f}M"
    if mbps >= 0.1:
        return f"{mbps:.1f}M"
    kbps = mbps * 1000.0
    return f"{kbps:.0f}K"


def render_theme_cyber_radar(gpu, llm, cpu, cooling, now_dt=None):
    """Tactical Sonar Sweep: Rotating 360° phosphor radar sweep, thermal targets & live Net I/O."""
    S = 960
    if now_dt is None:
        now_dt = datetime.datetime.now()
    img = Image.new("RGB", (S, S), (3, 12, 8))
    draw = ImageDraw.Draw(img)
    cx, cy = S // 2, S // 2

    draw.ellipse([22, 22, S - 22, S - 22], fill=(4, 15, 10), outline=(16, 185, 129), width=5)

    # Phosphor trailing sweep wedge (42° trail behind live second angle)
    sweep_deg = now_dt.second * 6.0 - 90.0
    for step in range(21):
        a0 = sweep_deg - (21 - step) * 2.0
        a1 = a0 + 2.2
        frac = (step + 1) / 21.0
        g_val = int(18 + 115 * (frac ** 1.7))
        b_val = int(12 + 72 * (frac ** 1.7))
        draw.pieslice([68, 68, S - 68, S - 68], start=a0, end=a1, fill=(6, g_val, b_val))

    # Compass perimeter ticks & concentric range rings
    for i in range(72):
        ang = math.radians(i * 5 - 90)
        is_maj = (i % 6) == 0
        r_in = 420 if is_maj else 434
        r_out = 448
        col = (52, 211, 153) if is_maj else (16, 92, 64)
        draw.line(
            [(cx + r_in * math.cos(ang), cy + r_in * math.sin(ang)), (cx + r_out * math.cos(ang), cy + r_out * math.sin(ang))],
            fill=col,
            width=4 if is_maj else 2,
        )

    for rr in (110, 210, 310, 412):
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(14, 74, 50), width=2)
    draw.line([(cx - 412, cy), (cx + 412, cy)], fill=(14, 74, 50), width=2)
    draw.line([(cx, cy - 412), (cx, cy + 412)], fill=(14, 74, 50), width=2)

    # Leading laser sweep line
    s_rad = math.radians(sweep_deg)
    draw.line([(cx, cy), (cx + 412 * math.cos(s_rad), cy + 412 * math.sin(s_rad))], fill=(110, 255, 196), width=5)
    draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(52, 211, 153), outline=(4, 15, 10), width=3)

    f_top = load_font(FONT_MONO_PATH, 26)
    f_tag = load_font(FONT_MONO_PATH, 22)
    f_net = load_font(FONT_MONO_PATH, 25)
    f_sub = load_font(FONT_MONO_PATH, 21)

    # Top Chrono Transponder
    draw.rounded_rectangle([282, 118, 678, 174], radius=28, fill=(5, 24, 16), outline=(16, 185, 129), width=3)
    draw.text((cx, 146), f"SONAR // {now_dt.strftime('%H:%M:%S')}", font=f_top, fill=(110, 231, 183), anchor="mm")

    # 4 Quadrant Tactical Blips & Callout Tags
    targets = [
        (280, 295, f"CPU {cpu['temp_c']}°C [{cpu['util']}%]"),
        (680, 295, f"GPU {gpu['temp_c']}°C [{gpu['power_w']}W]"),
        (280, 535, f"LIQ {cooling['liquid_c']:.1f}°C"),
        (680, 535, f"VRAM {gpu['vram_used_gb']:.1f}G"),
    ]
    for tx, ty, ttxt in targets:
        draw.ellipse([tx - 16, ty - 46, tx + 16, ty - 14], outline=(52, 211, 153), width=2)
        draw.ellipse([tx - 7, ty - 37, tx + 7, ty - 23], fill=(110, 255, 196))
        tw = 268 if len(ttxt) > 13 else 216
        draw.rounded_rectangle([tx - tw // 2, ty - 4, tx + tw // 2, ty + 42], radius=12, fill=(5, 24, 16), outline=(20, 128, 88), width=2)
        draw.text((tx, ty + 19), ttxt, font=f_tag, fill=(209, 250, 229), anchor="mm")

    # Bottom Network & AI Node Transponder
    rx_str = _fmt_net_mbps(float(cpu.get("net_rx_mbps", 0.0)))
    tx_str = _fmt_net_mbps(float(cpu.get("net_tx_mbps", 0.0)))
    draw.rounded_rectangle([210, 624, 750, 742], radius=20, fill=(5, 24, 16), outline=(16, 185, 129), width=3)
    draw.text((cx, 658), f"NET ↓ {rx_str}bps  •  ↑ {tx_str}bps", font=f_net, fill=(52, 211, 153), anchor="mm")
    draw.text((cx, 706), f"NODE: {llm['name']}", font=f_sub, fill=(167, 243, 208), anchor="mm")

    return img.resize((480, 480), Image.Resampling.LANCZOS)


def _get_crt_scanline_overlay(size: int):
    global _CRT_SCANLINE_CACHE
    if _CRT_SCANLINE_CACHE is None:
        ov = Image.new("RGB", (size, size), (0, 0, 0))
        od = ImageDraw.Draw(ov)
        for y in range(0, size, 6):
            od.line([(0, y), (size, y)], fill=(255, 255, 255), width=3)
        _CRT_SCANLINE_CACHE = ov
    return _CRT_SCANLINE_CACHE


def render_theme_pip_os_3000(gpu, llm, cpu, cooling, now_dt=None):
    """Amber CRT Terminal: Retro phosphor terminal with CRT scanlines, HH:MM:SS & block gauges."""
    S = 960
    if now_dt is None:
        now_dt = datetime.datetime.now()
    img = Image.new("RGB", (S, S), (18, 11, 2))
    draw = ImageDraw.Draw(img)
    cx = S // 2

    draw.ellipse([22, 22, S - 22, S - 22], fill=(22, 13, 3), outline=(245, 158, 11), width=6)
    draw.ellipse([40, 40, S - 40, S - 40], outline=(120, 70, 8), width=2)

    f_hdr = load_font(FONT_MONO_PATH, 22)
    f_clk = load_font(FONT_MONO_PATH, 76)
    f_tab = load_font(FONT_MONO_PATH, 21)
    f_row = load_font(FONT_MONO_PATH, 25)
    f_box = load_font(FONT_MONO_PATH, 23)

    draw.text((cx, 152), "══ PIP-OS v3.90 // TERMINAL ══", font=f_hdr, fill=(245, 158, 11), anchor="mm")
    draw.text((cx, 228), now_dt.strftime("%H:%M:%S"), font=f_clk, fill=(254, 243, 199), anchor="mm")

    # Retro CRT Tab Strip
    draw.rounded_rectangle([244, 282, 362, 318], radius=8, fill=(245, 158, 11))
    draw.text((303, 300), "STAT", font=f_tab, fill=(22, 13, 3), anchor="mm")
    draw.text((545, 300), "FLEET   COOL   PWR", font=f_tab, fill=(180, 112, 14), anchor="mm")
    draw.line([(165, 330), (795, 330)], fill=(146, 86, 10), width=3)

    ram_u = float(cpu.get("ram_used_gb", 5.5))
    ram_t = float(cpu.get("ram_total_gb", 32.0))
    vram_t = float(gpu.get("vram_total_gb", 24.0))
    g_tag = gpu.get("short_tag", "GPU")[:4]
    rows = [
        ("CPU", cpu["util"] / 100.0, f"{cpu['temp_c']:>2}°C {cpu['util']:>3}%"),
        (g_tag, gpu["gpu_util"] / 100.0, f"{gpu['temp_c']:>2}°C {gpu['gpu_util']:>3}%"),
        ("VRAM", gpu["vram_ratio"], f"{gpu['vram_used_gb']:>4.1f}/{vram_t:.0f}G"),
        ("RAM", float(cpu.get("ram_ratio", 0.2)), f"{ram_u:>4.1f}/{ram_t:.0f}G"),
    ]
    n_blocks = 12
    bx_start = 264
    bw, bh, bgap = 20, 28, 5
    for r_idx, (rlbl, r_ratio, r_txt) in enumerate(rows):
        ry = 374 + r_idx * 58
        draw.text((162, ry), rlbl, font=f_row, fill=(251, 191, 36), anchor="lm")
        lit_n = max(1, min(n_blocks, int(round(r_ratio * n_blocks)))) if r_ratio > 0.02 else 0
        for b in range(n_blocks):
            bx = bx_start + b * (bw + bgap)
            if b < lit_n:
                bcol = (251, 191, 36) if b < 9 else (249, 115, 22)
            else:
                bcol = (56, 34, 6)
            draw.rectangle([bx, ry - bh // 2, bx + bw, ry + bh // 2], fill=bcol)
        draw.text((798, ry), r_txt, font=f_row, fill=(254, 243, 199), anchor="rm")

    psu_w = cooling.get("psu_total_w") or (gpu["power_w"] + 75)
    draw.rounded_rectangle([205, 598, 755, 724], radius=14, fill=(30, 18, 4), outline=(217, 119, 6), width=3)
    draw.text((cx, 636), f"> {llm['name']}", font=f_box, fill=(253, 224, 71), anchor="mm")
    draw.text((cx, 686), f"> LIQ {cooling['liquid_c']:.1f}°C • PSU {psu_w}W", font=f_box, fill=(245, 158, 11), anchor="mm")

    # Apply subtle CRT phosphor scanline pass
    darkened = Image.eval(img, lambda px: int(px * 0.84))
    img = Image.composite(img, darkened, _get_crt_scanline_overlay(S).convert("L"))
    return img.resize((480, 480), Image.Resampling.LANCZOS)


def _get_adi_mask(diam: int):
    global _ADI_MASK_CACHE
    if _ADI_MASK_CACHE is None or _ADI_MASK_CACHE.size != (diam, diam):
        m = Image.new("L", (diam, diam), 0)
        ImageDraw.Draw(m).ellipse([0, 0, diam - 1, diam - 1], fill=255)
        _ADI_MASK_CACHE = m
    return _ADI_MASK_CACHE


def render_theme_horizon_avionics(gpu, llm, cpu, cooling, now_dt=None):
    """Jet Glass Cockpit ADI: Fighter-jet artificial horizon, pitch ladder & CPU/3090 flight tapes."""
    S = 960
    if now_dt is None:
        now_dt = datetime.datetime.now()
    img = Image.new("RGB", (S, S), (10, 15, 24))
    draw = ImageDraw.Draw(img)
    cx, cy = S // 2, S // 2

    draw.ellipse([20, 20, S - 20, S - 20], fill=(12, 18, 29), outline=(71, 85, 105), width=6)

    # Attitude Sphere (468x468 centered at 480,480 -> x=246..714)
    diam = 468
    canvas_sz = 620
    ball = Image.new("RGB", (canvas_sz, canvas_sz), (12, 82, 128))
    bdraw = ImageDraw.Draw(ball)
    mc = canvas_sz // 2

    perf_load = max(gpu["gpu_util"], cpu["util"])
    pitch_px = int(round((perf_load - 20) * 0.45))
    pitch_px = max(-18, min(36, pitch_px))
    roll_deg = max(-16.0, min(16.0, (gpu["gpu_util"] - cpu["util"]) * 0.16))

    horizon_y = mc + pitch_px
    bdraw.rectangle([0, horizon_y, canvas_sz, canvas_sz], fill=(74, 45, 24))
    bdraw.line([(0, horizon_y), (canvas_sz, horizon_y)], fill=(248, 250, 252), width=4)

    f_pitch = load_font(FONT_MONO_PATH, 16)
    for step_deg, dy in ((20, -96), (10, -48), (-10, 48), (-20, 96)):
        ly = horizon_y + dy
        half_l = 68 if abs(step_deg) == 20 else 46
        bdraw.line([(mc - half_l, ly), (mc - 18, ly)], fill=(241, 245, 249), width=3)
        bdraw.line([(mc + 18, ly), (mc + half_l, ly)], fill=(241, 245, 249), width=3)
        bdraw.text((mc - half_l - 22, ly), f"{abs(step_deg)}", font=f_pitch, fill=(226, 232, 240), anchor="mm")
        bdraw.text((mc + half_l + 22, ly), f"{abs(step_deg)}", font=f_pitch, fill=(226, 232, 240), anchor="mm")

    if abs(roll_deg) > 0.2:
        ball = ball.rotate(roll_deg, resample=Image.Resampling.BILINEAR)

    crop_off = (canvas_sz - diam) // 2
    ball_crop = ball.crop((crop_off, crop_off, crop_off + diam, crop_off + diam))
    sx0, sy0 = cx - diam // 2, cy - diam // 2
    img.paste(ball_crop, (sx0, sy0), _get_adi_mask(diam))

    # Fixed Aviation Yellow Fighter-Jet Wings Reticle & Roll Scale
    draw.line([(cx - 92, cy), (cx - 28, cy)], fill=(250, 204, 21), width=7)
    draw.line([(cx - 28, cy), (cx - 14, cy + 16)], fill=(250, 204, 21), width=7)
    draw.line([(cx + 28, cy), (cx + 92, cy)], fill=(250, 204, 21), width=7)
    draw.line([(cx + 28, cy), (cx + 14, cy + 16)], fill=(250, 204, 21), width=7)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(250, 204, 21))

    draw.ellipse([sx0 - 2, sy0 - 2, sx0 + diam + 2, sy0 + diam + 2], outline=(148, 163, 184), width=6)
    for b_deg in (-45, -30, -15, 0, 15, 30, 45):
        brad = math.radians(b_deg - 90)
        r1 = diam // 2 + 6
        r2 = r1 + (20 if b_deg == 0 else 13)
        draw.line(
            [(cx + r1 * math.cos(brad), cy + r1 * math.sin(brad)), (cx + r2 * math.cos(brad), cy + r2 * math.sin(brad))],
            fill=(250, 204, 21) if b_deg == 0 else (203, 213, 225),
            width=4 if b_deg == 0 else 3,
        )

    f_top = load_font(FONT_MONO_PATH, 27)
    f_tlbl = load_font(FONT_BOLD_PATH, 20)
    f_tval = load_font(FONT_BOLD_PATH, 42)
    f_tsub = load_font(FONT_MONO_PATH, 22)
    f_bot = load_font(FONT_BOLD_PATH, 22)

    # Top Flight Chronometer Tape
    draw.rounded_rectangle([292, 112, 668, 174], radius=16, fill=(15, 23, 38), outline=(56, 189, 248), width=3)
    draw.text((cx, 143), f"FLT  {now_dt.strftime('%H:%M:%S')}", font=f_top, fill=(125, 211, 252), anchor="mm")

    # Left Airspeed-Style Tape (CPU) & Right Altitude-Style Tape (3090)
    draw.rounded_rectangle([86, 360, 220, 600], radius=16, fill=(15, 23, 38), outline=(56, 189, 248), width=3)
    for ty in range(384, 588, 28):
        draw.line([(206, ty), (218, ty)], fill=(56, 189, 248), width=2)
    draw.text((148, 392), "CPU", font=f_tlbl, fill=(148, 163, 184), anchor="mm")
    draw.text((148, 450), f"{cpu['temp_c']}°", font=f_tval, fill=(56, 189, 248), anchor="mm")
    draw.text((148, 512), f"{cpu.get('max_ghz', 5.3):.1f}G", font=f_tsub, fill=(241, 245, 249), anchor="mm")
    draw.text((148, 562), f"{cpu['util']}%", font=f_tsub, fill=(52, 211, 153), anchor="mm")

    draw.rounded_rectangle([740, 360, 874, 600], radius=16, fill=(15, 23, 38), outline=(52, 211, 153), width=3)
    for ty in range(384, 588, 28):
        draw.line([(742, ty), (754, ty)], fill=(52, 211, 153), width=2)
    draw.text((812, 392), gpu.get("short_tag", "GPU"), font=f_tlbl, fill=(148, 163, 184), anchor="mm")
    draw.text((812, 450), f"{gpu['temp_c']}°", font=f_tval, fill=(52, 211, 153), anchor="mm")
    draw.text((812, 512), f"{gpu['power_w']}W", font=f_tsub, fill=(250, 204, 21), anchor="mm")
    draw.text((812, 562), f"{gpu['gpu_util']}%", font=f_tsub, fill=(56, 189, 248), anchor="mm")

    # Bottom Avionics Flight Director Readout
    draw.rounded_rectangle([268, 744, 692, 806], radius=16, fill=(15, 23, 38), outline=(250, 204, 21), width=3)
    draw.text((cx, 775), f"LIQ {cooling['liquid_c']:.1f}°C  •  PUMP {cooling['pump_rpm']} RPM", font=f_bot, fill=(250, 204, 21), anchor="mm")

    return img.resize((480, 480), Image.Resampling.LANCZOS)


RENDERERS = {
    "ai_fleet": render_theme_ai_fleet,
    "cooling_cockpit": render_theme_cooling_cockpit,
    "chrono_pulse": render_theme_chrono_pulse,
    "tensor_reactor": render_theme_tensor_reactor,
    "motorsport_gt": render_theme_motorsport_gt,
    "stealth_zen": render_theme_stealth_zen,
    "swiss_tourbillon": render_theme_swiss_tourbillon,
    "hx1200i_power_grid": render_theme_hx1200i_power_grid,
    "silicon_matrix": render_theme_silicon_matrix,
    "cyber_radar": render_theme_cyber_radar,
    "pip_os_3000": render_theme_pip_os_3000,
    "horizon_avionics": render_theme_horizon_avionics,
    "c64_lcp": render_theme_c64_lcp,
}


class OpenLinkHubClient:
    """Persistent HTTP/1.1 keep-alive client for OpenLinkHub LCD updates (~11ms/frame)."""

    BOUNDARY = "----OpenLinkHubBoundaryTitanLCD"
    PART_PREFIX = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="animationFile"; filename="llmhud.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8")
    PART_SUFFIX = f"\r\n--{BOUNDARY}--\r\n".encode("utf-8")

    def __init__(self):
        self._conn = None

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _target(self) -> tuple[str, int]:
        serial, lcd_ch = discover_openlinkhub_topology()
        if not serial or lcd_ch <= 0:
            raise RuntimeError(
                "Could not auto-discover a Corsair LCD AIO on OpenLinkHub. "
                "Ensure OpenLinkHub is running on 127.0.0.1:27003 or set OPENLINKHUB_SERIAL and OPENLINKHUB_LCD_CHANNEL."
            )
        return serial, lcd_ch

    def _request(self, method: str, path: str, body: bytes, content_type: str) -> bytes:
        headers = {"Content-Type": content_type, "Connection": "keep-alive"}
        last_exc = None
        for _ in range(2):
            try:
                if self._conn is None:
                    self._conn = http.client.HTTPConnection(OPENLINKHUB_HOST, OPENLINKHUB_PORT, timeout=1.8)
                self._conn.request(method, path, body=body, headers=headers)
                resp = self._conn.getresponse()
                data = resp.read()
                if resp.status >= 400:
                    raise RuntimeError(f"OpenLinkHub HTTP {resp.status} on {path}: {data[:120]!r}")
                return data
            except (OSError, http.client.HTTPException, ConnectionError) as exc:
                last_exc = exc
                self.close()
        raise last_exc

    def ensure_mode(self):
        serial, lcd_ch = self._target()
        payload = json.dumps({"deviceId": serial, "channelId": lcd_ch, "mode": 10}).encode("utf-8")
        self._request("POST", "/api/lcd", payload, "application/json")

    def activate_image(self):
        # OpenLinkHub's lsh.Device caches a heap copy in d.lcdImage[ch] and only swaps it
        # to the newly uploaded buffer when POST /api/lcd/image is called (~0.7ms).
        serial, lcd_ch = self._target()
        payload = json.dumps({"deviceId": serial, "channelId": lcd_ch, "image": "llmhud"}).encode("utf-8")
        self._request("POST", "/api/lcd/image", payload, "application/json")

    def set_brightness(self, brightness: int):
        serial, lcd_ch = self._target()
        payload = json.dumps(
            {"deviceId": serial, "channelId": lcd_ch, "brightness": max(0, min(100, int(brightness)))}
        ).encode("utf-8")
        self._request("POST", "/api/lcd/brightness", payload, "application/json")

    def push_frame(self, img_480, ensure_mode: bool = False):
        buf = io.BytesIO()
        img_480.save(buf, format="JPEG", quality=90)
        body = self.PART_PREFIX + buf.getvalue() + self.PART_SUFFIX
        self._request("POST", "/api/lcd/upload", body, f"multipart/form-data; boundary={self.BOUNDARY}")
        if ensure_mode:
            self.ensure_mode()
        self.activate_image()


_DEFAULT_OLH_CLIENT = OpenLinkHubClient()


def assert_openlinkhub_lcd_mode():
    _DEFAULT_OLH_CLIENT.ensure_mode()
    _DEFAULT_OLH_CLIENT.activate_image()


def set_lcd_brightness(brightness: int):
    _DEFAULT_OLH_CLIENT.set_brightness(brightness)


def push_to_openlinkhub(img_480, ensure_mode=False):
    _DEFAULT_OLH_CLIENT.push_frame(img_480, ensure_mode=ensure_mode)


class TelemetryPoller:
    """Background telemetry poller so HTTP/NVML/router checks never stall the 1Hz LCD clock."""

    def __init__(self, nvml: NVMLReader, cpu_reader: CpuReader):
        self.nvml = nvml
        self.cpu_reader = cpu_reader
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._last_slow_mono = 0.0
        self._cooling = {"liquid_c": 30.0, "pump_rpm": 2350, "fan_rpm": 500}
        self._llm = {
            "loaded": False,
            "tag": "ACTIVE GPU MODEL",
            "state_text": f"{nvml.gpu_name} READY",
            "name": "NO MODEL IN VRAM",
            "meta": "LOCAL AI TELEMETRY",
        }
        self._gpu = {
            "name": nvml.gpu_name,
            "short_tag": nvml.short_tag,
            "vram_used_gb": 0.0,
            "vram_total_gb": 24.0,
            "vram_ratio": 0.0,
            "gpu_util": 0,
            "temp_c": 35,
            "power_w": 20,
            "fan_pct": 30,
            "proc_vram": {},
        }
        self._cpu = {"short_name": cpu_reader.short_name, "temp_c": 35, "util": 0}
        self._thread = None

    def poll_once(self, force_slow: bool = False):
        now_m = time.monotonic()
        do_slow = force_slow or ((now_m - self._last_slow_mono) >= 1.5)
        try:
            gpu = self.nvml.read(include_processes=do_slow)
        except Exception:
            gpu = None
        try:
            cpu = self.cpu_reader.read()
        except Exception:
            cpu = None

        cooling = None
        llm = None
        if do_slow:
            self._last_slow_mono = now_m
            cooling = read_cooling_telemetry()
            proc_vram = (gpu or self._gpu).get("proc_vram")
            llm = get_loaded_llm(proc_vram, gpu_name=self.nvml.gpu_name)

        with self._lock:
            if gpu is not None:
                if not do_slow:
                    gpu["proc_vram"] = self._gpu.get("proc_vram", {})
                self._gpu = gpu
            if cpu is not None:
                self._cpu = cpu
            if cooling is not None:
                self._cooling = cooling
            if llm is not None:
                self._llm = llm

    def start(self):
        self.poll_once(force_slow=True)
        self._thread = threading.Thread(target=self._run, name="titan-lcd-telemetry", daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.wait(0.85):
            self.poll_once(force_slow=False)

    def snapshot(self):
        with self._lock:
            return self._gpu, self._llm, self._cpu, self._cooling


def _file_mtime_ns(path: str):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def sync_saved_case_rgb():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        import case_rgb_control

        case_rgb_control.apply_saved_rgb_state(notify=False)
    except Exception:
        pass


def main():
    if "--list-themes" in sys.argv:
        cur = read_lcd_state()
        for tid, tname, tdesc in LCD_THEMES:
            mark = "*" if tid == cur.get("theme") and not cur.get("auto_cycle") else " "
            print(f" {mark} {tid:20s} — {tname}: {tdesc}")
        return

    if "--brightness" in sys.argv:
        idx = sys.argv.index("--brightness")
        if idx + 1 < len(sys.argv):
            st = write_lcd_state(brightness=int(sys.argv[idx + 1]))
            print(json.dumps(st, indent=2))
            if "--set-theme" not in sys.argv and "--once" not in sys.argv:
                return

    if "--set-theme" in sys.argv:
        idx = sys.argv.index("--set-theme")
        if idx + 1 < len(sys.argv):
            t_name = sys.argv[idx + 1]
            if t_name == "cycle":
                st = write_lcd_state(auto_cycle=True)
            elif t_name == "next":
                cur = read_lcd_state()["theme"]
                nxt = THEME_IDS[(THEME_IDS.index(cur) + 1) % len(THEME_IDS)]
                st = write_lcd_state(theme=nxt, auto_cycle=False)
            elif t_name in THEME_IDS:
                st = write_lcd_state(theme=t_name, auto_cycle=False)
            else:
                print(f"Unknown theme '{t_name}'. Valid themes: {', '.join(THEME_IDS + ['next', 'cycle'])}", file=sys.stderr)
                sys.exit(1)
            print(json.dumps(st, indent=2))
            return

    once = "--once" in sys.argv
    nvml = NVMLReader()
    cpu_reader = CpuReader()
    poller = TelemetryPoller(nvml, cpu_reader)
    olh = OpenLinkHubClient()

    last_sig = None
    last_frame = None
    last_mode_assert = 0.0
    last_state_mtime_ns = None
    lcd_state = read_lcd_state()
    last_brightness = None
    active_theme = lcd_state["theme"]

    if once:
        poller.poll_once(force_slow=True)
    else:
        poller.start()
        sync_saved_case_rgb()

    while True:
        try:
            now_mono = time.monotonic()
            mtime_ns = _file_mtime_ns(LCD_STATE_FILE)

            if mtime_ns != last_state_mtime_ns:
                lcd_state = read_lcd_state()
                last_state_mtime_ns = mtime_ns
                last_sig = None  # Force immediate redraw on state/theme switch

            if lcd_state["brightness"] != last_brightness:
                try:
                    olh.set_brightness(lcd_state["brightness"])
                    last_brightness = lcd_state["brightness"]
                except Exception:
                    pass

            now_wall = time.time()
            active_theme = lcd_state["theme"]
            if lcd_state.get("auto_cycle"):
                cycle_secs = lcd_state.get("cycle_secs", 15)
                slot = int(now_wall // cycle_secs) % len(THEME_IDS)
                active_theme = THEME_IDS[slot]

            gpu, llm, cpu, cooling = poller.snapshot()
            now_dt = datetime.datetime.fromtimestamp(now_wall)
            if active_theme in FAST_ANIM_THEMES:
                time_bucket = int(now_wall / FAST_ANIM_THEMES[active_theme])
            elif active_theme in SECOND_TICK_THEMES:
                time_bucket = now_dt.hour * 3600 + now_dt.minute * 60 + now_dt.second
            else:
                time_bucket = now_dt.hour * 60 + now_dt.minute
            thread_sig = tuple(t // 10 for t in (cpu.get("threads") or ())[:20]) if active_theme == "silicon_matrix" else ()

            sig = (
                active_theme,
                time_bucket,
                llm["state_text"],
                llm.get("tag", ""),
                llm["name"],
                llm["meta"],
                round(gpu["vram_used_gb"], 1),
                gpu["gpu_util"] // 3,
                gpu["power_w"] // 5,
                gpu["temp_c"] // 2,
                gpu["fan_pct"] // 2,
                gpu.get("sm_clock_mhz", 0) // 50,
                cpu["temp_c"] // 2,
                cpu["util"] // 3,
                round(cpu.get("max_ghz", 0.0), 1),
                round(cpu.get("ram_used_gb", 0.0), 1),
                cooling.get("psu_total_w", 0) // 4,
                cooling.get("psu_rpm", 0) // 50,
                round(cooling["liquid_c"] * 2) / 2.0,
                cooling["fan_rpm"] // 35,
                thread_sig,
            )
            need_mode_assert = (last_mode_assert == 0.0) or ((now_mono - last_mode_assert) >= MODE_ASSERT_SECS)

            if sig != last_sig or once or last_frame is None:
                renderer = RENDERERS.get(active_theme, render_theme_ai_fleet)
                frame = renderer(gpu, llm, cpu, cooling, now_dt=now_dt)
                try:
                    tmp_prev = f"{PREVIEW_PATH}.tmp"
                    frame.save(tmp_prev, format="PNG", compress_level=1)
                    os.replace(tmp_prev, PREVIEW_PATH)
                except Exception:
                    pass
                olh.push_frame(frame, ensure_mode=need_mode_assert)
                last_frame = frame
                last_sig = sig
                if need_mode_assert:
                    last_mode_assert = now_mono
                if once:
                    print(f"Rendered theme '{active_theme}' -> {PREVIEW_PATH}")
                    return
            elif need_mode_assert and last_frame is not None:
                olh.push_frame(last_frame, ensure_mode=True)
                last_mode_assert = now_mono
        except Exception as exc:
            olh.close()
            last_mode_assert = 0.0
            last_brightness = None
            last_sig = None
            if once:
                raise
            print(f"[titan-lcd] Warning: {exc}", file=sys.stderr, flush=True)
            time.sleep(0.8)
            continue

        # Phase-lock wakeup to sub-second step for FAST_ANIM_THEMES or wall-clock second
        # boundary (+6ms guard) for 1Hz themes, while watching state.json every 40ms.
        if active_theme in FAST_ANIM_THEMES:
            step = FAST_ANIM_THEMES[active_theme]
            deadline_wall = (math.floor(now_wall / step) + 1.0) * step + 0.002
        elif active_theme in SECOND_TICK_THEMES:
            deadline_wall = math.floor(now_wall) + 1.006
        else:
            deadline_wall = time.time() + 0.5
            if active_theme == "stealth_zen":
                next_min = (math.floor(now_wall / 60.0) + 1.0) * 60.0 + 0.006
                deadline_wall = min(deadline_wall, next_min)

        if lcd_state.get("auto_cycle"):
            cycle_secs = lcd_state.get("cycle_secs", 15)
            next_cycle = (math.floor(now_wall / cycle_secs) + 1.0) * cycle_secs + 0.006
            deadline_wall = min(deadline_wall, next_cycle)

        while True:
            rem = deadline_wall - time.time()
            if rem <= 0.0 or rem > 2.0:
                break
            if _file_mtime_ns(LCD_STATE_FILE) != last_state_mtime_ns:
                break
            time.sleep(min(0.04, rem))


if __name__ == "__main__":
    main()

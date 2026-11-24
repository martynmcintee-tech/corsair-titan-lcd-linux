#!/usr/bin/env python3
"""
LCP 2026 — Standalone Desktop Companion & Studio Application (GTK4 + Libadwaita)

Runs anywhere on Linux (with or without a Corsair cooler!):
  • Syncs seamlessly with titan-lcd.service (/dev/shm/titan_lcd_current.png) when active on c64_lcp
  • Otherwise renders LCP 2026 directly in-process at ~5 FPS so you ALWAYS have your Little Computer
    Person living on your desktop even on laptops, future PCs, or while the cooler shows another dial!
  • Supports both Full Studio mode and a sleek Compact Circular Widget mode (--widget).
"""
from __future__ import annotations

import argparse
import ctypes
import glob
import io
import json
import os
import sys
import time

_PKG_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

import lcp_c64_house as lcp_engine
import lcp_world_scenes as lcp_world

TITAN_PREVIEW_PNG = "/dev/shm/titan_lcd_current.png"
TITAN_STATE_JSON = os.path.expanduser("~/.config/titan-lcd/state.json")


class LightTelemetry:
    """Zero-crash optional CPU/GPU telemetry reader for standalone desktop rendering."""

    def __init__(self) -> None:
        self.nvml = None
        self.dev = ctypes.c_void_p()
        self.nvml_ok = False
        try:
            self.nvml = ctypes.CDLL("libnvidia-ml.so.1")
            if self.nvml.nvmlInit_v2() == 0:
                if self.nvml.nvmlDeviceGetHandleByIndex_v2(ctypes.c_uint(0), ctypes.byref(self.dev)) == 0:
                    self.nvml_ok = True
        except Exception:
            self.nvml_ok = False
        self._last_poll = 0.0
        self._cache = ({"gpu_util": 0, "temp_c": 36}, {"loaded": False, "name": ""}, {"temp_c": 38}, {"liquid_c": 30.0})

    def read(self):
        now = time.monotonic()
        if (now - self._last_poll) < 2.0:
            return self._cache
        self._last_poll = now

        cpu_t = 38
        for h in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                with open(os.path.join(h, "name"), "r", encoding="ascii") as f:
                    nm = f.read().strip()
                if nm in ("coretemp", "k10temp", "zenpower", "cpu_thermal"):
                    with open(os.path.join(h, "temp1_input"), "r", encoding="ascii") as f:
                        cpu_t = int(round(int(f.read().strip()) / 1000.0))
                    break
            except OSError:
                continue

        gpu_t, gpu_u = 36, 0
        if self.nvml_ok:
            try:
                t_val = ctypes.c_uint()
                if self.nvml.nvmlDeviceGetTemperature(self.dev, ctypes.c_uint(0), ctypes.byref(t_val)) == 0:
                    gpu_t = int(t_val.value)

                class _Util(ctypes.Structure):
                    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

                u_val = _Util()
                if self.nvml.nvmlDeviceGetUtilizationRates(self.dev, ctypes.byref(u_val)) == 0:
                    gpu_u = int(u_val.gpu)
            except Exception:
                pass

        self._cache = (
            {"gpu_util": gpu_u, "temp_c": gpu_t},
            {"loaded": gpu_u > 18, "name": "LOCAL-AI"},
            {"temp_c": cpu_t},
            {"liquid_c": 30.0},
        )
        return self._cache


def _titan_cooler_showing_lcp() -> bool:
    try:
        if (time.time() - os.path.getmtime(TITAN_PREVIEW_PNG)) > 2.0:
            return False
        with open(TITAN_STATE_JSON, "r", encoding="utf-8") as f:
            st = json.load(f)
        return st.get("theme") == "c64_lcp" and not st.get("auto_cycle", False)
    except Exception:
        return False


def _activate_on_cooler_lcd() -> bool:
    try:
        st = {"theme": "c64_lcp", "auto_cycle": False, "cycle_secs": 15, "brightness": 100}
        if os.path.exists(TITAN_STATE_JSON):
            with open(TITAN_STATE_JSON, "r", encoding="utf-8") as f:
                st.update(json.load(f))
        st["theme"] = "c64_lcp"
        st["auto_cycle"] = False
        os.makedirs(os.path.dirname(TITAN_STATE_JSON), exist_ok=True)
        tmp = f"{TITAN_STATE_JSON}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=2)
            f.write("\n")
        os.replace(tmp, TITAN_STATE_JSON)
        return True
    except Exception:
        return False


def run_app(start_widget_mode: bool = False) -> int:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gdk, GLib, Gtk

    CSS = b"""
    window { background-color: #0b0f17; }
    .master-card {
        background: linear-gradient(145deg, #132238, #0f172a);
        border: 1px solid rgba(56, 189, 248, 0.40);
        border-radius: 16px;
        padding: 16px;
    }
    .zone-card {
        background-color: #141a24;
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 14px;
        padding: 14px 16px;
    }
    .theme-card {
        background-color: #141a24;
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 14px;
        padding: 10px 12px;
    }
    .theme-card-active {
        background: linear-gradient(145deg, #132842, #0f1b2d);
        border: 2px solid #38bdf8;
        border-radius: 14px;
        padding: 10px 12px;
    }
    .preset-active {
        background: linear-gradient(135deg, #0284c7, #0369a1);
        color: #ffffff;
        font-weight: 700;
    }
    .lcd-bezel {
        background: radial-gradient(circle, #0b1324 60%, #050811 100%);
        border: 3px solid rgba(56, 189, 248, 0.55);
        border-radius: 999px;
        padding: 6px;
    }
    .pct-pill {
        background-color: rgba(56, 189, 248, 0.16);
        color: #7dd3fc;
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 999px;
        padding: 3px 12px;
        font-weight: 800;
        font-size: 13px;
    }
    .hero-btn {
        background: linear-gradient(135deg, #e0f2fe, #bae6fd);
        color: #0f172a;
        font-weight: 800;
        border-radius: 10px;
        padding: 8px 12px;
    }
    .sec-btn {
        background-color: #1e293b;
        color: #e2e8f0;
        font-weight: 700;
        border-radius: 10px;
        padding: 8px 12px;
    }
    """

    class Lcp2026App(Adw.Application):
        def __init__(self):
            super().__init__(application_id="io.github.corsair_titan_lcd.Lcp2026")
            self.telemetry = LightTelemetry()
            self.state = lcp_world.read_lcp_settings(force=True)
            self.widget_mode = start_widget_mode
            self._last_png_mtime = None
            self._spd_debounce = None
            self.win = None

        def do_activate(self):
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            provider = Gtk.CssProvider()
            provider.load_from_data(CSS)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            if self.win is not None:
                self.win.present()
                return

            self.win = Adw.ApplicationWindow(application=self, title="Little Computer Person 2026")
            self.root_stack = Gtk.Stack()
            self.root_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

            # Root layout with headerbar
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.header = Adw.HeaderBar()
            self.btn_mode_toggle = Gtk.Button(label="🪟 Mini Widget")
            self.btn_mode_toggle.connect("clicked", self._toggle_window_mode)
            self.header.pack_end(self.btn_mode_toggle)

            if os.path.exists(os.path.dirname(TITAN_STATE_JSON)):
                btn_sync_cooler = Gtk.Button(label="🖥 Show on Cooler LCD")
                btn_sync_cooler.connect("clicked", lambda _b: _activate_on_cooler_lcd())
                self.header.pack_start(btn_sync_cooler)

            outer.append(self.header)
            outer.append(self.root_stack)
            self.win.set_content(outer)

            self.root_stack.add_named(self._build_studio_view(), "studio")
            self.root_stack.add_named(self._build_widget_view(), "widget")

            self._apply_window_mode()
            self._refresh_ui()
            self._tick_frame()
            GLib.timeout_add(200, self._tick_frame)
            self.win.present()

        def _build_widget_view(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_margin_top(12)
            box.set_margin_bottom(14)
            box.set_margin_start(14)
            box.set_margin_end(14)
            box.set_valign(Gtk.Align.CENTER)
            box.set_halign(Gtk.Align.CENTER)

            self.pic_widget = Gtk.Picture()
            self.pic_widget.set_size_request(256, 256)
            self.pic_widget.set_can_shrink(True)
            bezel = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            bezel.set_overflow(Gtk.Overflow.HIDDEN)
            bezel.add_css_class("lcd-bezel")
            bezel.append(self.pic_widget)
            box.append(bezel)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, homogeneous=True)
            for lbl, cmd in (("👋 Knock", "knock"), ("💭 Thought", "thought"), ("🚗 Drive", "next_venue")):
                b = Gtk.Button(label=lbl)
                b.add_css_class("sec-btn")
                b.connect("clicked", self._on_action, cmd)
                row.append(b)
            box.append(row)
            return box

        def _build_studio_view(self) -> Gtk.Widget:
            scroll = Gtk.ScrolledWindow(vexpand=True)
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            content.set_margin_top(12)
            content.set_margin_bottom(18)
            content.set_margin_start(18)
            content.set_margin_end(18)
            scroll.set_child(content)

            hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
            hero.add_css_class("master-card")
            content.append(hero)

            self.pic_studio = Gtk.Picture()
            self.pic_studio.set_size_request(216, 216)
            self.pic_studio.set_can_shrink(True)
            bezel = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            bezel.set_overflow(Gtk.Overflow.HIDDEN)
            bezel.add_css_class("lcd-bezel")
            bezel.append(self.pic_studio)
            hero.append(bezel)

            hcol = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, valign=Gtk.Align.CENTER)
            hero.append(hcol)
            t_lbl = Gtk.Label(label="Little Computer Person 2026", xalign=0)
            t_lbl.add_css_class("title-2")
            self.lbl_status = Gtk.Label(label="", xalign=0, wrap=True)
            self.lbl_status.add_css_class("accent")
            hcol.append(t_lbl)
            hcol.append(self.lbl_status)

            act_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
            b_k = Gtk.Button(label="👋 Knock Glass")
            b_k.add_css_class("hero-btn")
            b_k.connect("clicked", self._on_action, "knock")
            b_t = Gtk.Button(label="💭 Funny Thought!")
            b_t.add_css_class("sec-btn")
            b_t.connect("clicked", self._on_action, "thought")
            b_n = Gtk.Button(label="🚗 Drive Next Place")
            b_n.add_css_class("sec-btn")
            b_n.connect("clicked", self._on_action, "next_venue")
            act_row.append(b_k)
            act_row.append(b_t)
            act_row.append(b_n)
            hcol.append(act_row)

            spd_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            spd_lbl = Gtk.Label(label="Simulation Speed", xalign=0, hexpand=True)
            init_spd = float(self.state.get("sim_speed", 1.0))
            self.lbl_spd = Gtk.Label(label=f"{init_spd:.1f}×")
            self.lbl_spd.add_css_class("pct-pill")
            spd_head.append(spd_lbl)
            spd_head.append(self.lbl_spd)
            hcol.append(spd_head)

            self.scale_spd = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.5, 0.1)
            self.scale_spd.set_draw_value(False)
            self.scale_spd.set_value(init_spd)
            self.scale_spd.connect("value-changed", self._on_speed)
            hcol.append(self.scale_spd)

            v_hdr = Gtk.Label(label="Life Schedule & Town Destinations", xalign=0)
            v_hdr.add_css_class("heading")
            content.append(v_hdr)

            v_grid = Gtk.Grid(column_spacing=10, row_spacing=10, column_homogeneous=True)
            content.append(v_grid)
            self.venue_btns = {}
            for idx, (mid, mtitle, mdesc) in enumerate(lcp_world.SCENE_MODES):
                btn = Gtk.Button()
                bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                nt = Gtk.Label(label=mtitle, xalign=0)
                nt.add_css_class("heading")
                dt = Gtk.Label(label=mdesc, xalign=0, wrap=True)
                dt.add_css_class("caption")
                dt.add_css_class("dim-label")
                bx.append(nt)
                bx.append(dt)
                btn.set_child(bx)
                btn.add_css_class("theme-card")
                btn.connect("clicked", self._on_venue, mid)
                v_grid.attach(btn, idx % 2, idx // 2, 1, 1)
                self.venue_btns[mid] = btn

            app_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            app_card.add_css_class("zone-card")
            content.append(app_card)
            app_hdr = Gtk.Label(label="Appearance & Life Settings", xalign=0)
            app_hdr.add_css_class("heading")
            app_card.append(app_hdr)

            sk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
            app_card.append(sk_box)
            self.skin_btns = {}
            for k, info in lcp_world.SKIN_STYLES.items():
                b = Gtk.Button(label=info[0])
                b.connect("clicked", self._on_style, "skin_tone", k)
                sk_box.append(b)
                self.skin_btns[k] = b

            hr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
            app_card.append(hr_box)
            self.hair_btns = {}
            for k, info in lcp_world.HAIR_STYLES.items():
                b = Gtk.Button(label=info[0])
                b.connect("clicked", self._on_style, "hair_style", k)
                hr_box.append(b)
                self.hair_btns[k] = b

            out_grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
            app_card.append(out_grid)
            self.outfit_btns = {}
            for idx, (k, info) in enumerate(lcp_world.OUTFIT_STYLES.items()):
                b = Gtk.Button(label=info[0])
                b.connect("clicked", self._on_style, "outfit", k)
                out_grid.attach(b, idx % 3, idx // 3, 1, 1)
                self.outfit_btns[k] = b

            gf_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            gf_lbl = Gtk.Label(label="Girlfriend's Name", xalign=0, hexpand=True)
            self.entry_gf = Gtk.Entry()
            self.entry_gf.set_max_length(10)
            self.entry_gf.set_text(self.state.get("girlfriend_name", "CHLOE"))
            b_gf = Gtk.Button(label="Save")
            b_gf.connect("clicked", self._on_save_gf)
            gf_row.append(gf_lbl)
            gf_row.append(self.entry_gf)
            gf_row.append(b_gf)
            app_card.append(gf_row)

            for label_txt, key in (
                ("Funny 2026 Thought Bubbles", "thought_bubbles"),
                ("Autonomous Town Trips & EV Car Commutes", "auto_town_trips"),
                ("Weekday 9–5 Work Shifts (Never on Weekends)", "work_shifts_enabled"),
                ("Girlfriend Visits & Dates", "girlfriend_enabled"),
            ):
                r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                l = Gtk.Label(label=label_txt, xalign=0, hexpand=True)
                sw = Gtk.Switch(valign=Gtk.Align.CENTER)
                sw.set_active(bool(self.state.get(key, True)))
                sw.connect("notify::active", lambda s, _p, k=key: lcp_world.write_lcp_settings(**{k: bool(s.get_active())}))
                r.append(l)
                r.append(sw)
                app_card.append(r)

            return scroll

        def _toggle_window_mode(self, _btn):
            self.widget_mode = not self.widget_mode
            self._apply_window_mode()

        def _apply_window_mode(self):
            if self.widget_mode:
                self.root_stack.set_visible_child_name("widget")
                self.btn_mode_toggle.set_label("🎛 Full Studio")
                self.win.set_default_size(310, 375)
                self.win.set_size_request(295, 360)
            else:
                self.root_stack.set_visible_child_name("studio")
                self.btn_mode_toggle.set_label("🪟 Mini Widget")
                self.win.set_size_request(680, 560)
                self.win.set_default_size(880, 860)

        def _refresh_ui(self):
            self.state = lcp_world.read_lcp_settings(force=True)
            mode = self.state.get("mode", "auto")
            sk = self.state.get("skin_tone", "caucasian")
            hr = self.state.get("hair_style", "brown")
            out = self.state.get("outfit", "cyan")
            m_map = {m[0]: m[1] for m in lcp_world.SCENE_MODES}
            self.lbl_status.set_label(
                f"{m_map.get(mode, mode)}  •  {lcp_world.SKIN_STYLES[sk][0]}  •  {lcp_world.HAIR_STYLES[hr][0]}"
            )
            for mid, b in self.venue_btns.items():
                b.remove_css_class("theme-card-active" if mid != mode else "theme-card")
                b.add_css_class("theme-card-active" if mid == mode else "theme-card")
            for k, b in self.skin_btns.items():
                (b.add_css_class if k == sk else b.remove_css_class)("preset-active")
            for k, b in self.hair_btns.items():
                (b.add_css_class if k == hr else b.remove_css_class)("preset-active")
            for k, b in self.outfit_btns.items():
                (b.add_css_class if k == out else b.remove_css_class)("preset-active")

        def _on_venue(self, _b, mid: str):
            _activate_on_cooler_lcd()
            lcp_world.write_lcp_settings(mode=mid)
            self._refresh_ui()

        def _on_action(self, _b, cmd: str):
            _activate_on_cooler_lcd()
            upd = {"action_cmd": cmd}
            if cmd == "knock":
                upd["mode"] = "home"
            elif cmd == "next_venue":
                upd["mode"] = "tour"
            lcp_world.write_lcp_settings(**upd)
            self._refresh_ui()

        def _on_style(self, _b, field: str, val: str):
            _activate_on_cooler_lcd()
            lcp_world.write_lcp_settings(**{field: val})
            self._refresh_ui()

        def _on_save_gf(self, _b):
            nm = (self.entry_gf.get_text() or "CHLOE").strip().upper()[:10] or "CHLOE"
            self.entry_gf.set_text(nm)
            lcp_world.write_lcp_settings(girlfriend_name=nm)
            self._refresh_ui()

        def _on_speed(self, scale):
            val = round(float(scale.get_value()), 1)
            self.lbl_spd.set_label(f"{val:.1f}×")
            if self._spd_debounce:
                GLib.source_remove(self._spd_debounce)

            def apply_spd():
                self._spd_debounce = None
                lcp_world.write_lcp_settings(sim_speed=val)
                return False

            self._spd_debounce = GLib.timeout_add(150, apply_spd)

        def _tick_frame(self):
            try:
                if _titan_cooler_showing_lcp():
                    st = os.stat(TITAN_PREVIEW_PNG)
                    if st.st_mtime_ns != self._last_png_mtime:
                        self._last_png_mtime = st.st_mtime_ns
                        tex = Gdk.Texture.new_from_filename(TITAN_PREVIEW_PNG)
                        self.pic_studio.set_paintable(tex)
                        self.pic_widget.set_paintable(tex)
                else:
                    # Render standalone right inside the desktop app!
                    gpu, llm, cpu, cooling = self.telemetry.read()
                    im = lcp_engine.render_theme_c64_lcp(gpu, llm, cpu, cooling)
                    buf = io.BytesIO()
                    im.save(buf, format="PNG")
                    tex = Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))
                    self.pic_studio.set_paintable(tex)
                    self.pic_widget.set_paintable(tex)
            except Exception:
                pass
            return True

    app = Lcp2026App()
    return app.run(None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Little Computer Person 2026 — Desktop Companion & Studio")
    parser.add_argument("--widget", action="store_true", help="Open directly in compact circular desktop widget mode")
    parser.add_argument("--cooler", action="store_true", help="Activate LCP 2026 on the Corsair TITAN LCD and exit")
    args = parser.parse_args()
    if args.cooler:
        _activate_on_cooler_lcd()
        print("Activated LCP 2026 on Corsair TITAN LCD.")
        return 0
    return run_app(start_widget_mode=args.widget)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
LCP 2026 — Modern Edition World, Realistic Life Schedule, Car Commutes,
Funny Thought Bubbles & Town Venues for the Circular 480x480 Pump LCD.

Features:
- Realistic Wall-Clock & Calendar Schedule:
    * Mon - Fri 09:00-17:00: Works at Metro Fleet & Tech (with morning/evening car commutes & lunch run)
    * Mon - Thu & Sun Evenings: Cozy evenings at Home (with occasional quick gym/shop/pub/cinema errands)
    * Sat - Sun: Strictly ZERO work — weekend adventures (Pub, Beach, Shops, Gym, Cinema, Bistro, Hotel, Parties)
- Animated Car Commute Transition ("LCP 26" 2026 Arctic EV Fastback) between every venue!
- Context-aware 2-line comic Thought Bubbles with 75+ funny British/2026/hardware quips
- 11 Full 240x240 Pixel-Art Venues + Car Scene (upscaled 2x NEAREST to 480x480)
"""
from __future__ import annotations

import datetime
import json
import math
import os
import random
import time
from PIL import Image, ImageDraw

LCP_SETTINGS_DIR = os.path.expanduser("~/.config/titan-lcd")
LCP_SETTINGS_FILE = os.path.join(LCP_SETTINGS_DIR, "lcp_settings.json")

SCENE_MODES = [
    ("auto", "Realistic 2026 Schedule", "Mon–Fri 9–5 work shift, evenings at Home, weekends off-duty + car drives"),
    ("tour", "Fast Town Tour (Demo)", "Drives his car around every venue every ~30s so you can watch them all"),
    ("home", "At Home (3-Story House)", "Modern 3-story cutaway home with rig, fireplace, piano, Chloe & Buddy"),
    ("work_hub", "9–5 Fleet & Tech Shift", "Metro Fleet & Tech depot yard, RCV PMI walkaround & compliance office"),
    ("shops", "High Street (Greggs & Tech)", "Pop into Greggs, CEX/Tech Store & Fresh Supermarket with carrier bags"),
    ("pub", "The Red Lion UK Pub", "Real ale pumps, Sunday roast, dartboard & big-screen match with mates"),
    ("gym", "Pulse 24/7 Fitness Gym", "Bench press, neon treadmills, dumbbells & post-workout protein shake"),
    ("cinema", "IMAX Cinema & Arcade", "Giant sci-fi movie screen, plush tiered seats & popcorn with Chloe"),
    ("park_beach", "Seaside Pier & Dog Walk", "Sunny promenade, waves, 99 Flake ice-cream van & Buddy chasing balls"),
    ("nightclub", "Nightclub (Club SID)", "Mirrored disco ball, sweeping lasers, DJ turntables & lit dancefloor"),
    ("hotel", "Grand Boutique Hotel", "Marble concierge lobby, brass luggage cart & panoramic skyline suite"),
    ("girlfriend", "Starlight Bistro Date", "Candlelit waterfront bistro dinner & moonlit stroll with Chloe"),
    ("house_party", "3-Story House Party", "Fairy lights, balloons, pizza boxes, booming vinyl & dancing friends"),
    ("driving", "Cruising in His EV Car", "Out for a spin in his Arctic 2026 EV fastback ('LCP 26') with Buddy"),
]
SCENE_MODE_IDS = [m[0] for m in SCENE_MODES]

VENUE_SHORT_NAMES = {
    "home": "HOME",
    "work_hub": "WORK HUB",
    "shops": "HIGH ST",
    "pub": "RED LION",
    "gym": "PULSE GYM",
    "cinema": "CINEMA",
    "park_beach": "SEASIDE",
    "nightclub": "CLUB SID",
    "hotel": "HOTEL",
    "girlfriend": "BISTRO",
    "house_party": "PARTY",
    "driving": "CRUISING",
}

HAIR_STYLES = {
    "brown": ("Chestnut Brown", (104, 64, 34)),
    "blonde": ("Golden Blonde", (230, 194, 88)),
    "black": ("Raven Black", (30, 34, 44)),
    "auburn": ("Warm Auburn", (166, 68, 34)),
}

OUTFIT_STYLES = {
    "cyan": ("Classic Cyan Tee", (64, 168, 196), (48, 72, 136)),
    "navy": ("Smart Navy Jacket", (42, 74, 138), (58, 64, 78)),
    "emerald": ("Forest Hoodie", (46, 152, 84), (48, 72, 136)),
    "crimson": ("Crimson Jumper", (196, 48, 58), (46, 52, 68)),
    "hivis_vest": ("Safety Hi-Vis Vest", (228, 244, 28), (28, 52, 104)),
}

SKIN_STYLES = {
    "caucasian": ("Fair Caucasian", (248, 210, 182), (222, 174, 144)),
    "warm_tan": ("Warm Olive / Tan", (218, 168, 128), (188, 138, 98)),
    "classic_c64": ("Retro 1985 C64", (154, 103, 89), (124, 78, 66)),
}

DEFAULT_LCP_SETTINGS = {
    "mode": "auto",
    "skin_tone": "caucasian",
    "hair_style": "brown",
    "outfit": "cyan",
    "resident_name": "JAY",
    "girlfriend_name": "CHLOE",
    "thought_bubbles": True,
    "auto_town_trips": True,
    "work_shifts_enabled": True,
    "girlfriend_enabled": True,
    "sim_speed": 1.0,
    "action_nonce": 0,
    "action_cmd": "",
}

_SETTINGS_CACHE: dict = dict(DEFAULT_LCP_SETTINGS)
_SETTINGS_MTIME_NS: int | None = None
_LAST_STAT_MONO: float = 0.0


def read_lcp_settings(force: bool = False) -> dict:
    global _SETTINGS_CACHE, _SETTINGS_MTIME_NS, _LAST_STAT_MONO
    now_m = time.monotonic()
    if not force and (now_m - _LAST_STAT_MONO) < 0.25:
        return _SETTINGS_CACHE
    _LAST_STAT_MONO = now_m
    try:
        st = os.stat(LCP_SETTINGS_FILE)
        if not force and st.st_mtime_ns == _SETTINGS_MTIME_NS:
            return _SETTINGS_CACHE
        with open(LCP_SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        merged = dict(DEFAULT_LCP_SETTINGS)
        if raw.get("mode") in SCENE_MODE_IDS:
            merged["mode"] = raw["mode"]
        if raw.get("skin_tone") in SKIN_STYLES:
            merged["skin_tone"] = raw["skin_tone"]
        if raw.get("hair_style") in HAIR_STYLES:
            merged["hair_style"] = raw["hair_style"]
        if raw.get("outfit") in OUTFIT_STYLES:
            merged["outfit"] = raw["outfit"]
        rname = str(raw.get("resident_name") or "JAY").strip().upper()[:10]
        gname = str(raw.get("girlfriend_name") or "CHLOE").strip().upper()[:10]
        merged["resident_name"] = rname or "JAY"
        merged["girlfriend_name"] = gname or "CHLOE"
        merged["thought_bubbles"] = bool(raw.get("thought_bubbles", True))
        merged["auto_town_trips"] = bool(raw.get("auto_town_trips", True))
        merged["work_shifts_enabled"] = bool(raw.get("work_shifts_enabled", True))
        merged["girlfriend_enabled"] = bool(raw.get("girlfriend_enabled", True))
        merged["sim_speed"] = max(0.4, min(2.5, float(raw.get("sim_speed", 1.0))))
        merged["action_nonce"] = int(raw.get("action_nonce", 0))
        merged["action_cmd"] = str(raw.get("action_cmd") or "")
        _SETTINGS_CACHE = merged
        _SETTINGS_MTIME_NS = st.st_mtime_ns
    except FileNotFoundError:
        _SETTINGS_CACHE = dict(DEFAULT_LCP_SETTINGS)
        _SETTINGS_MTIME_NS = None
    except Exception:
        pass
    return _SETTINGS_CACHE


def write_lcp_settings(**updates) -> dict:
    cur = dict(read_lcp_settings(force=True))
    for k, v in updates.items():
        if v is not None and k in DEFAULT_LCP_SETTINGS:
            cur[k] = v
    if "action_cmd" in updates and updates["action_cmd"]:
        cur["action_nonce"] = int(cur.get("action_nonce", 0)) + 1
    os.makedirs(LCP_SETTINGS_DIR, exist_ok=True)
    tmp = f"{LCP_SETTINGS_FILE}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2)
        f.write("\n")
    os.replace(tmp, LCP_SETTINGS_FILE)
    read_lcp_settings(force=True)
    return cur


# ===========================================================================
# Palette Constants
# ===========================================================================
C_BLK = (0, 0, 0)
C_WHT = (255, 255, 255)
C_RED = (188, 52, 48)
C_CYN = (112, 164, 178)
C_PUR = (126, 64, 164)
C_GRN = (88, 141, 67)
C_BLU = (53, 40, 121)
C_YEL = (234, 214, 92)
C_ORG = (168, 102, 44)
C_BRN = (82, 56, 28)
C_DGY = (58, 64, 74)
C_MGY = (108, 114, 124)
C_LGN = (142, 214, 122)
C_LBL = (108, 94, 181)
C_LGY = (164, 170, 178)

CORP_BLUE = (34, 74, 145)     # #224A91
CORP_NAVY = (20, 46, 94)      # #142E5E
CORP_GREEN = (0, 150, 57)     # #009639
SAFETY_HIVIS = (234, 250, 32)

NEON_PINK = (244, 62, 158)
PASTEL_PINK = (252, 156, 204)
NEON_CYAN = (32, 218, 236)
GOLD_TRIM = (224, 182, 74)
SKY_NIGHT = (12, 18, 36)
CLUB_DARK = (16, 10, 28)
GREGGS_BLUE = (0, 85, 165)
GREGGS_GOLD = (250, 182, 24)


# ===========================================================================
# Funny Context-Aware 2-Line Thought Bubbles (Max 18 chars per line!)
# ===========================================================================
THOUGHT_POOLS: dict[str, tuple[tuple[str, str], ...]] = {
    "work_hub": (
        ("WHO TICKED NIL", "DEFECTS IN 3 SEC?"),
        ("ANOTHER WHEEL NUT", "POINTER TWISTED!"),
        ("TEAMS CALL COULD", "HAVE BEEN EMAIL"),
        ("NEED COFFEE BEFORE", "THE DVSA AUDIT!"),
        ("SHAREPOINT BLOCKED", "MY SCRIPT AGAIN"),
        ("COUNTING DOWN TO", "5 O'CLOCK ALREADY"),
        ("TACHO DOWNLOAD", "DAY... SEND TEA"),
        ("ADBLUE LIGHT IS", "FLASHING AGAIN!"),
        ("AT LEAST HI-VIS", "HIDES COFFEE STAIN"),
    ),
    "driving": (
        ("WHY DO 38 MPH IN", "A 60 ZONE MATE?!"),
        ("INDICATORS COME", "FREE WITH BMWs!"),
        ("POTHOLE JUST ATE", "MY FRONT WISHBONE"),
        ("SATNAV SAYS TURN", "INTO THAT HEDGE"),
        ("TEMP TRAFFIC LIGHT", "STUCK ON RED AGAIN"),
        ("GREGGS DRIVE-THRU", "CALLING MY NAME..."),
        ("REGENERATIVE BRAKE", "MODE: MAXIMUM!"),
        ("BUDDY LOVES THE", "WINDOW DOWN!"),
    ),
    "home_day": (
        ("OPENED FRIDGE 4X", "STILL NOTHING NEW"),
        ("I LIVE INSIDE A", "WATERBLOCK. WILD."),
        ("BUDDY JUST STOLE", "MY WARM SPOT!"),
        ("NO WINDOWS 11", "ADS IN MY HOUSE!"),
        ("SHOULD TIDY UP...", "NAH, C64 TIME"),
        ("KETTLE'S ON!", "PROPER BREW TIME"),
        ("WONDER WHAT WE'RE", "BUILDING NEXT!"),
    ),
    "home_evening": (
        ("5PM! HI-VIS OFF,", "SLIPPERS ON!"),
        ("40 MINS SCROLLING", "0 MINS WATCHING"),
        ("FANCY A CURRY OR", "BE GOOD TONIGHT?"),
        ("NOTHING BEATS AN", "OPEN PIXEL FIRE"),
        ("HOME SWEET 480PX", "CIRCULAR HOME!"),
        ("DO NOT EMAIL ME", "TILL 9AM MONDAY"),
    ),
    "home_late": (
        ("DOES MY HUMAN", "EVER SLEEP?!"),
        ("1 MORE VIDEO...", "WAIT IT'S 1:30AM"),
        ("MIDNIGHT CHEESE", "DOESN'T COUNT"),
        ("EVEN BUDDY WENT", "TO BED HOURS AGO"),
    ),
    "home_ai_hot": (
        ("GPU IS HEATING", "MY ENTIRE HOUSE!"),
        ("24GB VRAM FULL!", "BRAIN AT MAX RPM"),
        ("LOCAL GPU RUNNING", "ANOTHER AI SWARM!"),
        ("COOLANT WARMING", "MY RADIATORS NICE"),
    ),
    "shops": (
        ("STEAK BAKE IS", "MOLTEN LAVA TEMP!"),
        ("CAME IN FOR MILK", "BOUGHT A NEW SSD"),
        ("HOW IS LURPAK", "SEVEN QUID NOW?!"),
        ("UNEXPECTED ITEM", "IN BAGGING AREA!"),
        ("FORGOT MY BAGS", "FOR LIFE AGAIN..."),
        ("OOOH SAUSAGE ROLL", "FRESH OUT OVEN!"),
    ),
    "pub": (
        ("JUST ONE PINT...", "FAMOUS LAST WORDS"),
        ("SEVEN POUND FIFTY", "FOR A LAGER?!"),
        ("WE'RE WINNING THE", "PUB QUIZ TONIGHT!"),
        ("CRISPS COUNT AS", "DINNER, RIGHT?"),
        ("SUNDAY ROAST &", "YORKSHIRE PUD!"),
        ("REF NEEDS SPECS!", "NEVER OFFSIDE!"),
    ),
    "gym": (
        ("DID 3 REPS. TIME", "TO CHECK MY PHONE"),
        ("LEG DAY? THOUGHT", "YOU SAID GREGGS!"),
        ("EARNING MY FRIDAY", "TAKEAWAY RIGHT NOW"),
        ("WHO LEFT 140KG ON", "THE BENCH BAR?!"),
        ("PROTEIN SHAKE =", "90% OF WORKING OUT"),
    ),
    "cinema": (
        ("ATE ALL POPCORN", "DURING TRAILERS!"),
        ("25 MINS OF ADS", "BEFORE THE FILM?!"),
        ("ACT COOL... DON'T", "MENTION LINUX"),
        ("IMAX BASS SHAKING", "MY PIXELS LOOSE!"),
    ),
    "park_beach": (
        ("GUARD YOUR CHIPS!", "SEAGULL INBOUND!"),
        ("99 FLAKE USED TO", "ACTUALLY COST 99P"),
        ("BRITISH SUMMER:", "14 DEGREES, SUNNY!"),
        ("BUDDY'S HAVING THE", "BEST DAY EVER!"),
    ),
    "nightclub": (
        ("MY KNEES WERE", "DESIGNED IN 1985"),
        ("DJ DROP SOME", "PRODIGY ALREADY!"),
        ("EARS RINGING AT", "120 DECIBELS!"),
        ("STILL GOT THE", "8-BIT MOVES!"),
    ),
    "hotel": (
        ("MINI-BAR PRINGLES", "COST A MORTGAGE!"),
        ("TAKING ALL THE", "TINY SHAMPOOS HOME"),
        ("FLUFFY ROBE LIFE", "SUITS ME WELL"),
        ("PENTHOUSE VIEW", "OVER PIXEL CITY!"),
    ),
    "girlfriend": (
        ("PUNCHING WELL", "ABOVE MY WEIGHT!"),
        ("DON'T SPILL SAUCE", "ON CLEAN SHIRT..."),
        ("SHE LAUGHED AT MY", "DAD JOKE! RESULT!"),
        ("SPLITTING DESSERT?", "GET TWO SPOONS!"),
    ),
    "house_party": (
        ("USE A COASTER ON", "THE PIANO PLEASE!"),
        ("NEIGHBOURS LOVE", "SYNTHWAVE, RIGHT?"),
        ("BUDDY JUST ATE A", "FLOOR PEPPERONI!"),
        ("BEST HOUSE PARTY", "INSIDE A PC CASE!"),
    ),
}


def pick_funny_thought(
    venue: str,
    hour: int,
    ai_busy: bool,
    gpu_temp: int,
    rng: random.Random,
    recent: list[tuple[str, str]],
) -> tuple[str, str]:
    if venue == "home":
        if ai_busy or gpu_temp >= 62:
            pool_key = "home_ai_hot"
        elif hour >= 23 or hour < 6:
            pool_key = "home_late"
        elif hour >= 17:
            pool_key = "home_evening"
        else:
            pool_key = "home_day"
    else:
        pool_key = venue if venue in THOUGHT_POOLS else "home_day"

    pool = list(THOUGHT_POOLS[pool_key])
    # Mix in AI quips occasionally if GPU is working hard at home
    if venue == "home" and ai_busy:
        pool.extend(THOUGHT_POOLS["home_ai_hot"])

    candidates = [p for p in pool if p not in recent] or pool
    chosen = rng.choice(candidates)
    recent.append(chosen)
    if len(recent) > 6:
        del recent[0]
    return chosen


def draw_thought_bubble(
    canvas: Image.Image,
    anchor_x: int,
    anchor_y: int,
    lines: tuple[str, str],
    draw_text_fn,
) -> None:
    """Draws a crisp 2-line pixel comic thought cloud safely clamped inside R_WORLD."""
    l1, l2 = lines[0][:18], lines[1][:18]
    max_chars = max(len(l1), len(l2))
    bw = max(68, max_chars * 6 + 12)
    bh = 21 if l2 else 13

    # Clamp safely within circular chord at y=36..72
    by0 = max(34, min(124, anchor_y - bh - 10))
    by1 = by0 + bh
    # Compute safe horizontal margin at by0 inside circle of radius 108
    dy_top = abs(by0 - 120)
    max_half_w = int(math.sqrt(max(400, 108 * 108 - dy_top * dy_top))) - 4
    bx_center = max(120 - max_half_w + bw // 2, min(120 + max_half_w - bw // 2, anchor_x))
    bx0 = bx_center - bw // 2
    bx1 = bx_center + bw // 2

    d = ImageDraw.Draw(canvas)
    # Thought trail bubbles rising from character's head to cloud!
    tx_mid = int(round((anchor_x + bx_center) * 0.5))
    ty_mid = int(round((anchor_y + by1) * 0.5))
    d.ellipse([anchor_x - 2, anchor_y - 3, anchor_x + 2, anchor_y + 1], fill=C_WHT, outline=C_BLK)
    d.ellipse([tx_mid - 3, ty_mid - 3, tx_mid + 3, ty_mid + 3], fill=C_WHT, outline=C_BLK)

    # Rounded cloud box
    d.rectangle([bx0 + 2, by0, bx1 - 2, by1], fill=C_WHT)
    d.rectangle([bx0, by0 + 2, bx1, by1 - 2], fill=C_WHT)
    # Crisp pixel outline
    d.line([(bx0 + 2, by0), (bx1 - 2, by0)], fill=C_BLK)
    d.line([(bx0 + 2, by1), (bx1 - 2, by1)], fill=C_BLK)
    d.line([(bx0, by0 + 2), (bx0, by1 - 2)], fill=C_BLK)
    d.line([(bx1, by0 + 2), (bx1, by1 - 2)], fill=C_BLK)
    for cx_c, cy_c in ((bx0 + 1, by0 + 1), (bx1 - 1, by0 + 1), (bx0 + 1, by1 - 1), (bx1 - 1, by1 - 1)):
        d.point((cx_c, cy_c), fill=C_BLK)
    # Subtle inner light-blue accent top bar
    d.line([(bx0 + 3, by0 + 1), (bx1 - 3, by0 + 1)], fill=C_CYN)

    if l2:
        draw_text_fn(canvas, bx_center, by0 + 3, l1, color=CORP_NAVY, center_x=True)
        draw_text_fn(canvas, bx_center, by0 + 12, l2, color=C_BLK, center_x=True)
    else:
        draw_text_fn(canvas, bx_center, by0 + 3, l1, color=CORP_NAVY, center_x=True)


# ===========================================================================
# Realistic 2026 Life Schedule Resolver (Mon-Fri 9-5 FCC, Sat-Sun Never Work!)
# ===========================================================================
def compute_realistic_venue(
    now_dt: datetime.datetime,
    settings: dict,
    slot_seed: int,
) -> str:
    """
    Determines where Jay realistically is right now in 'auto' mode:
      - Mon-Fri (weekday 0..4) 09:00..16:59 -> FCC Work (with optional quick 12:35-13:05 lunch nip to Greggs/Shops)
      - Mon-Thu & Sun Evenings (17:00..23:15) -> Primarily At Home (with occasional short evening gym/shop/pub/cinema trip)
      - Friday Night (18:30..00:59) -> Pub, Bistro Date, Cinema, Nightclub, or House Party
      - Sat & Sun (weekday 5..6) -> NEVER Work! Daytime adventures (Shops, Seaside, Gym, Pub Roast, Cinema, Hotel)
      - Overnight (23:15..08:45) -> At Home!
    """
    if not settings.get("auto_town_trips", True):
        return "home"

    wk = now_dt.weekday()  # 0=Mon .. 4=Fri, 5=Sat, 6=Sun
    mins = now_dt.hour * 60 + now_dt.minute
    r = random.Random(slot_seed)
    gf_ok = bool(settings.get("girlfriend_enabled", True))
    work_ok = bool(settings.get("work_shifts_enabled", True))
    is_weekend = wk >= 5

    # 1. Overnight Sleep / Late Night at Home
    # Allow Friday night & Saturday night late-out till 01:00 (i.e. Sat 00:00..00:59 & Sun 00:00..00:59)
    if mins < 60 and wk in (5, 6):
        late_choices = ["nightclub", "house_party", "pub", "home"]
        return r.choice(late_choices)
    if mins < 8 * 60 + 50 or mins >= 23 * 60 + 15:
        return "home"

    # 2. MONDAY - FRIDAY WORKDAY (09:00 - 17:00)
    if not is_weekend and (9 * 60 <= mins < 17 * 60):
        if work_ok:
            # Quick lunchtime Greggs / Cafe nip-out window (12:35 - 13:05)
            if 12 * 60 + 35 <= mins < 13 * 60 + 5 and r.random() < 0.65:
                return "shops"
            return "work_hub"
        # If user toggled FCC shifts off, normal daytime errands/home
        return r.choice(["home", "shops", "gym", "park_beach"])

    # 3. WEEKDAY EVENINGS (Mon - Thu 17:00 - 23:15) -> Evenings at Home!
    if not is_weekend and wk < 4 and mins >= 17 * 60:
        # 78% cozy evening at Home; 22% quick early-evening gym/shops/pub/cinema before 21:00
        if mins < 21 * 60 and r.random() < 0.22:
            errands = ["gym", "shops", "pub"] + (["cinema", "girlfriend"] if gf_ok else [])
            return r.choice(errands)
        return "home"

    # 4. FRIDAY EVENING (Fri 17:00 - 23:15)
    if wk == 4 and mins >= 17 * 60:
        if mins < 18 * 60 + 30:
            return "home"  # Getting changed after work!
        fri_pool = ["pub", "nightclub", "house_party", "home"]
        if gf_ok:
            fri_pool.extend(["girlfriend", "cinema"])
        return r.choice(fri_pool)

    # 5. SATURDAY & SUNDAY (STRICTLY ZERO WORK!)
    # Weekend Daytime (08:50 - 18:30)
    if mins < 18 * 60 + 30:
        if mins < 10 * 60:
            return "home"  # Lazy weekend morning brew!
        wknd_day = ["home", "shops", "park_beach", "gym", "pub", "hotel"]
        if gf_ok:
            wknd_day.extend(["cinema", "girlfriend"])
        return r.choice(wknd_day)

    # Sunday Evening (18:30 - 23:15) -> Cozy evening at home before Monday!
    if wk == 6:
        if mins < 20 * 60 and r.random() < 0.35:
            return "pub" if not gf_ok else r.choice(["pub", "girlfriend"])
        return "home"

    # Saturday Night (18:30 - 23:15) -> Big night out or House Party!
    sat_night = ["nightclub", "house_party", "pub", "hotel", "home"]
    if gf_ok:
        sat_night.extend(["girlfriend", "cinema"])
    return r.choice(sat_night)


# ===========================================================================
# Character Sprite Grid Templates (13w x 21h)
# ===========================================================================
_CHAR_WALK_0 = (
    "....00000....",
    "...0HHHHH0...",
    "..0HHSSSSHH0.",
    "..0HHS10S10..",
    "..0HSSSSS00..",
    "...0SS22S0...",
    "....0SSS0....",
    "...0TTTTT0...",
    "..0TTTTTTT0..",
    ".0TTTTTTTTT0.",
    ".0S0TTTTT0S0.",
    "..0.0TTTTT0..",
    "....0PPPPP0..",
    "...0PP00PP0..",
    "..0PP0..0PP0.",
    "..0PP0...0PP0",
    "..0P0....0PP0",
    ".0880....0880",
    ".08880...0888",
    ".00000...0000",
    ".............",
)

_CHAR_WALK_1 = (
    ".............",
    "....00000....",
    "...0HHHHH0...",
    "..0HHSSSSHH0.",
    "..0HHS10S10..",
    "..0HSSSSS00..",
    "...0SS22S0...",
    "....0SSS0....",
    "...0TTTTT0...",
    "..0TTTTTTT0..",
    "..0TTTTTTT0..",
    "..0STTTTTS0..",
    "...0TTTTT0...",
    "...0PPPPP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0880880...",
    "...08888880..",
    "...00000000..",
)

_CHAR_DANCE_0 = (
    ".0S0.00000...",
    ".0T00HHHHH0..",
    "..0T0HHSSSS0.",
    "..0T0HS10S10.",
    "...00HSSSSS0.",
    "....0SS22S0..",
    ".....0SSS0...",
    "....0TTTTT00.",
    "...0TTTTTTT0S",
    "...0TTTTTTT00",
    "...0TTTTT0...",
    "...0PPPPP0...",
    "..0PP0.0PP0..",
    ".0PP0...0PP0.",
    ".0PP0....0PP0",
    "..0880...0880",
    "..0000...0000",
    ".............",
    ".............",
    ".............",
    ".............",
)

_CHAR_DANCE_1 = (
    "...00000.0S0.",
    "..0HHHHH00T0.",
    ".0HHSSSS0T0..",
    ".0HHS10S10T0.",
    ".0HSSSSS00...",
    "..0SS22S0....",
    "...0SSS0.....",
    ".00TTTTT0....",
    "S0TTTTTTT0...",
    "00TTTTTTT0...",
    "...0TTTTT0...",
    "...0PPPPP0...",
    "..0PP0.0PP0..",
    "..0PP0..0PP0.",
    ".0PP0...0PP0.",
    ".0880...0880.",
    ".0000...0000.",
    ".............",
    ".............",
    ".............",
    ".............",
)

_CHAR_SHOP_0 = (
    "....00000....",
    "...0HHHHH0...",
    "..0HHSSSSHH0.",
    "..0HHS10S10..",
    "..0HSSSSS00..",
    "...0SS22S0...",
    "....0SSS0....",
    "...0TTTTT0...",
    "..0TTTTTTT0..",
    ".0TTTTTTTTT0.",
    ".0STTTTTTTS0.",
    ".0220TTTT0770",
    "022220PPP0777",
    "021220P0P0717",
    "022220P0P0777",
    ".00000P0P0000",
    "....0PP0PP0..",
    "...0880.0880.",
    "...0888.0888.",
    "...0000.0000.",
    ".............",
)

# Pint / Mug Toast Pose (for Pub & Party!)
_CHAR_PINT_0 = (
    "....00000....",
    "...0HHHHH0...",
    "..0HHSSSSHH0.",
    "..0HHS10S10..",
    "..0HSSSSS00..",
    "...0SS22S0...",
    "....0SSS0.111",
    "...0TTTTT0777",
    "..0TTTTTTTS77",
    "..0TTTTTTTS00",
    "..0STTTTT0...",
    "...0TTTTT0...",
    "...0PPPPP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0880880...",
    "...08888880..",
    "...00000000..",
    ".............",
)

# Gym Barbell Overhead Lift Pose!
_CHAR_LIFT_0 = (
    "00.0000000.00",
    "0000000000000",
    "00.0S000S0.00",
    "...0HHHHH0...",
    "..0HHSSSSHH0.",
    "..0HHS10S10..",
    "...0SS22S0...",
    "..0STTTTTS0..",
    "...0TTTTT0...",
    "...0TTTTT0...",
    "...0PPPPP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0SS0SS0...",
    "...0880880...",
    "...0000000...",
    ".............",
    ".............",
    ".............",
    ".............",
    ".............",
)

_HIVIS_WORKER_0 = (
    "...0111110...",
    "..011111110..",
    "..000000000..",
    "..0HHSSSSS0..",
    "..0HHS10S10..",
    "..0HSSSSS00..",
    "...0SS22S0...",
    "....0SSS0....",
    "...0VVVVV0...",
    "..0VV111VV00.",
    "..0VVVVVVV110",
    "..0SV111VS170",
    "...0VVVVV000.",
    "...0PPPPP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0PP0PP0...",
    "...0880880...",
    "...08888880..",
    "...00000000..",
)

_HIVIS_WORKER_WALK = (
    "...0111110...",
    "..011111110..",
    "..000000000..",
    "..0HHSSSSS0..",
    "..0HHS10S10..",
    "..0HSSSSS00..",
    "...0SS22S0...",
    "....0SSS0....",
    "...0VVVVV0...",
    "..0VV111VV0..",
    ".0VVVVVVVVV0.",
    ".0S0V111V0S0.",
    "..0.0VVVV0...",
    "...0PPPPP0...",
    "..0PP0.0PP0..",
    ".0PP0...0PP0.",
    ".0PP0....0P0.",
    ".0880....0880",
    ".08880...0888",
    ".00000...0000",
    ".............",
)

_GF_WALK_0 = (
    "...0000000...",
    "..0HHHHHHH0..",
    ".0HHHSSSSHH0.",
    ".0HHHS10S1H0.",
    ".0HHHSSSSSH0.",
    "..0HSS22SH0..",
    "...0HSSSH0...",
    "...0TTTTT0...",
    "..0TTTTTTT0..",
    ".0STTTTTTTS0.",
    "..0TTTTTTT0..",
    "..0PPPPPPP0..",
    ".0PPPPPPPPP0.",
    ".0PPPPPPPPP0.",
    "...0SS0.0SS0.",
    "...0SS0..0SS0",
    "...0880..0880",
    "...0888..0888",
    "...0000..0000",
    ".............",
    ".............",
)

_GF_WALK_1 = (
    ".............",
    "...0000000...",
    "..0HHHHHHH0..",
    ".0HHHSSSSHH0.",
    ".0HHHS10S1H0.",
    ".0HHHSSSSSH0.",
    "..0HSS22SH0..",
    "...0HSSSH0...",
    "...0TTTTT0...",
    "..0TTTTTTT0..",
    "..0STTTTTS0..",
    "..0PPPPPPP0..",
    ".0PPPPPPPPP0.",
    ".0PPPPPPPPP0.",
    "...0SS0SS0...",
    "...0SS0SS0...",
    "...0SS0SS0...",
    "...0880880...",
    "...08888880..",
    "...00000000..",
    ".............",
)

_GF_DANCE_0 = (
    ".0S0000000...",
    ".0T0HHHHHHH0.",
    "..0HHHSSSSHH0",
    "..0HHHS10S1H0",
    "..0HHHSSSSSH0",
    "...0HSS22SH0.",
    "....0TTTTT00.",
    "...0TTTTTTT0S",
    "...0PPPPPPP00",
    "..0PPPPPPPPP0",
    "..0PPPPPPPPP0",
    "...0SS0..0SS0",
    "..0SS0....0SS",
    "..0880....088",
    "..0000....000",
    ".............",
    ".............",
    ".............",
    ".............",
    ".............",
    ".............",
)

_GF_DANCE_1 = (
    "...00000000S0",
    ".0HHHHHHH0T0.",
    "0HHHSSSSHH0..",
    "0HHHS10S1H0..",
    "0HHHSSSSSH0..",
    ".0HSS22SH0...",
    ".00TTTTT0....",
    "S0TTTTTTT0...",
    "00PPPPPPP0...",
    "0PPPPPPPPP0..",
    "0PPPPPPPPP0..",
    "0SS0..0SS0...",
    "SS0....0SS0..",
    "880....0880..",
    "000....0000..",
    ".............",
    ".............",
    ".............",
    ".............",
    ".............",
    ".............",
)

_DYN_SPRITE_CACHE: dict[tuple, Image.Image] = {}


def get_custom_char_sprite(
    pose: str,
    skin_rgb: tuple[int, int, int],
    hair_rgb: tuple[int, int, int],
    top_rgb: tuple[int, int, int],
    pants_rgb: tuple[int, int, int],
    flip_x: bool = False,
) -> Image.Image:
    key = (pose, skin_rgb, hair_rgb, top_rgb, pants_rgb, flip_x)
    cached = _DYN_SPRITE_CACHE.get(key)
    if cached is not None:
        return cached

    grids = {
        "walk_0": _CHAR_WALK_0,
        "walk_1": _CHAR_WALK_1,
        "dance_0": _CHAR_DANCE_0,
        "dance_1": _CHAR_DANCE_1,
        "shop_0": _CHAR_SHOP_0,
        "pint_0": _CHAR_PINT_0,
        "lift_0": _CHAR_LIFT_0,
        "hivis_stand": _HIVIS_WORKER_0,
        "hivis_walk": _HIVIS_WORKER_WALK,
        "gf_walk_0": _GF_WALK_0,
        "gf_walk_1": _GF_WALK_1,
        "gf_dance_0": _GF_DANCE_0,
        "gf_dance_1": _GF_DANCE_1,
    }
    rows = grids[pose]
    h = len(rows)
    w = len(rows[0])
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = im.load()

    cmap = {
        "0": C_BLK,
        "1": C_WHT,
        "2": (214, 92, 92),
        "7": C_YEL,
        "8": (74, 48, 28),
        "S": skin_rgb,
        "H": hair_rgb,
        "T": top_rgb,
        "P": pants_rgb,
        "V": SAFETY_HIVIS,
    }
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            rgb = cmap.get(ch, C_WHT)
            tx = (w - 1 - x) if flip_x else x
            px[tx, y] = rgb + (255,)

    if len(_DYN_SPRITE_CACHE) > 768:
        _DYN_SPRITE_CACHE.clear()
    _DYN_SPRITE_CACHE[key] = im
    return im


def resolve_appearance(settings: dict) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    skin = SKIN_STYLES.get(settings.get("skin_tone", "caucasian"), SKIN_STYLES["caucasian"])[1]
    hair = HAIR_STYLES.get(settings.get("hair_style", "brown"), HAIR_STYLES["brown"])[1]
    _, top, pants = OUTFIT_STYLES.get(settings.get("outfit", "cyan"), OUTFIT_STYLES["cyan"])
    return skin, hair, top, pants


# ===========================================================================
# Cached Venue Static Backdrops (240x240)
# ===========================================================================
_VENUE_BG_CACHE: dict[tuple[str, str], Image.Image] = {}


def _get_work_hub_bg(day_phase: str) -> Image.Image:
    key = ("work_hub", day_phase)
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), C_BLK)
    d = ImageDraw.Draw(im)

    sky_top = (128, 178, 226) if day_phase == "day" else (24, 38, 72)
    sky_bot = (176, 212, 242) if day_phase == "day" else (42, 62, 108)
    d.rectangle([0, 0, 240, 95], fill=sky_top)
    d.rectangle([0, 95, 240, 148], fill=sky_bot)
    d.rectangle([0, 148, 240, 240], fill=(52, 56, 64))
    d.line([(0, 148), (240, 148)], fill=C_LGY)
    for lx in range(34, 206, 16):
        d.rectangle([lx, 189, lx + 9, 191], fill=SAFETY_HIVIS)

    d.rectangle([30, 46, 198, 61], fill=CORP_BLUE, outline=C_BLK)
    d.rectangle([30, 59, 198, 62], fill=CORP_GREEN)
    d.rectangle([32, 62, 148, 118], fill=(228, 234, 242), outline=C_BLK)
    d.rectangle([32, 110, 148, 118], fill=(182, 192, 206))

    d.rectangle([38, 68, 58, 92], fill=C_WHT, outline=CORP_NAVY)
    d.polygon([(44, 72), (50, 71), (53, 80), (49, 88), (43, 86)], fill=CORP_GREEN)
    d.point((48, 78), fill=C_RED)
    d.point((46, 83), fill=CORP_BLUE)

    d.rectangle([66, 101, 108, 104], fill=C_ORG, outline=C_BLK)
    d.line([(69, 104), (69, 116)], fill=C_DGY, width=2)
    d.line([(104, 104), (104, 116)], fill=C_DGY, width=2)
    for mx in (70, 88):
        d.rectangle([mx, 89, mx + 14, 100], fill=CORP_NAVY, outline=C_BLK)
        d.rectangle([mx + 2, 91, mx + 12, 98], fill=(20, 32, 54))
        d.line([(mx + 3, 93), (mx + 10, 93)], fill=CORP_GREEN)
        d.line([(mx + 3, 96), (mx + 11, 96)], fill=NEON_CYAN)
    d.rectangle([118, 92, 126, 116], fill=C_WHT, outline=C_BLK)
    d.rectangle([119, 84, 125, 92], fill=NEON_CYAN, outline=CORP_BLUE)
    d.line([(132, 116), (144, 184)], fill=C_DGY, width=3)

    d.rectangle([32, 119, 88, 185], fill=(74, 80, 90), outline=C_BLK)
    for bx in (38, 54):
        d.rectangle([bx, 164, bx + 11, 184], fill=CORP_GREEN, outline=C_BLK)
        d.rectangle([bx - 1, 162, bx + 12, 165], fill=CORP_BLUE, outline=C_BLK)
        d.ellipse([bx + 1, 182, bx + 5, 186], fill=C_BLK)
        d.ellipse([bx + 7, 182, bx + 11, 186], fill=C_BLK)
    for cx_cone in (74, 84):
        d.polygon([(cx_cone, 185), (cx_cone + 3, 175), (cx_cone + 6, 185)], fill=(244, 112, 24), outline=C_BLK)
        d.line([(cx_cone + 2, 180), (cx_cone + 4, 180)], fill=C_WHT)

    # Metro Fleet Utility Truck
    d.rectangle([128, 134, 202, 174], fill=CORP_BLUE, outline=C_BLK)
    for rx in (142, 158, 174, 190):
        d.line([(rx, 136), (rx, 172)], fill=CORP_NAVY)
    d.rectangle([134, 150, 196, 157], fill=C_WHT)
    d.rectangle([134, 157, 196, 160], fill=CORP_GREEN)
    # Mini "ECO" fleet mark
    for ox, segs in ((154, ((0, 0, 0, 4), (0, 0, 3, 0), (0, 2, 2, 2), (0, 4, 3, 4))), (159, ((0, 0, 3, 0), (0, 0, 0, 4), (0, 4, 3, 4))), (164, ((0, 0, 3, 0), (0, 0, 0, 4), (3, 0, 3, 4), (0, 4, 3, 4)))):
        for x0, y0, x1, y1 in segs:
            d.line([(ox + x0, 151 + y0), (ox + x1, 151 + y1)], fill=CORP_BLUE)

    d.rectangle([202, 140, 207, 174], fill=C_MGY, outline=C_BLK)
    d.rectangle([204, 154, 209, 170], fill=SAFETY_HIVIS, outline=C_BLK)

    d.polygon([(98, 154), (104, 140), (127, 140), (127, 174), (98, 174)], fill=C_WHT, outline=C_BLK)
    d.polygon([(100, 154), (105, 143), (116, 143), (116, 156)], fill=(120, 188, 224), outline=C_BLK)
    d.rectangle([118, 144, 125, 155], fill=(120, 188, 224), outline=C_BLK)
    d.rectangle([110, 160, 122, 165], fill=CORP_BLUE)
    d.line([(110, 165), (122, 165)], fill=CORP_GREEN)
    d.rectangle([98, 166, 101, 170], fill=C_YEL)
    d.rectangle([102, 174, 200, 178], fill=C_DGY, outline=C_BLK)

    for wx in (112, 168, 186):
        d.ellipse([wx - 8, 170, wx + 8, 186], fill=C_BLK, outline=C_DGY)
        d.ellipse([wx - 4, 174, wx + 4, 182], fill=C_LGY)
        for ang in (0, 90, 180, 270):
            nx = int(round(wx + math.cos(math.radians(ang)) * 3))
            ny = int(round(178 + math.sin(math.radians(ang)) * 3))
            d.point((nx, ny), fill=SAFETY_HIVIS)

    _VENUE_BG_CACHE[key] = im
    return im


def _get_shops_bg(day_phase: str) -> Image.Image:
    key = ("shops_2026", day_phase)
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), C_BLK)
    d = ImageDraw.Draw(im)

    sky = (116, 176, 232) if day_phase == "day" else (24, 30, 62)
    d.rectangle([0, 0, 240, 184], fill=sky)
    d.rectangle([0, 184, 240, 240], fill=(132, 136, 144))
    d.rectangle([0, 184, 240, 188], fill=(178, 182, 190))
    for cx_p in range(16, 224, 12):
        d.line([(cx_p, 188), (cx_p - 4, 202)], fill=C_DGY)

    # Storefront 1: TECH & GPU STORE (x=28..86)
    d.rectangle([28, 82, 86, 184], fill=(42, 48, 72), outline=C_BLK)
    d.rectangle([26, 74, 88, 83], fill=C_DGY, outline=C_BLK)
    d.rectangle([30, 118, 84, 132], fill=(18, 24, 48), outline=NEON_CYAN)
    d.rectangle([33, 138, 66, 172], fill=(14, 20, 38), outline=C_WHT)
    # GPU box & curved monitor in window
    d.rectangle([37, 150, 51, 162], fill=C_BLK, outline=C_LGN)
    d.rectangle([54, 146, 63, 168], fill=CORP_GREEN)
    d.rectangle([69, 142, 82, 184], fill=C_DGY, outline=C_BLK)
    d.rectangle([71, 146, 80, 162], fill=NEON_CYAN)

    # Storefront 2: GREGGS BAKERY! (x=87..152 — Iconic Blue & Gold!)
    d.rectangle([87, 76, 152, 184], fill=(228, 220, 206), outline=C_BLK)
    d.rectangle([85, 68, 154, 77], fill=GREGGS_BLUE, outline=C_BLK)
    d.rectangle([89, 118, 150, 133], fill=GREGGS_BLUE, outline=C_WHT)
    # Four-square gold bakery emblem on left of sign
    d.rectangle([92, 122, 95, 125], fill=GREGGS_GOLD)
    d.rectangle([96, 122, 99, 125], fill=GREGGS_GOLD)
    d.rectangle([92, 126, 95, 129], fill=GREGGS_GOLD)
    d.rectangle([96, 126, 99, 129], fill=GREGGS_GOLD)
    # Warm golden pastry display counter!
    d.rectangle([92, 140, 128, 170], fill=(252, 228, 164), outline=GREGGS_BLUE)
    for px_s in range(96, 124, 7):
        d.rectangle([px_s, 156, px_s + 5, 160], fill=(208, 142, 62))
        d.rectangle([px_s, 163, px_s + 5, 167], fill=(208, 142, 62))
    d.rectangle([131, 140, 148, 184], fill=GREGGS_BLUE, outline=C_BLK)
    d.rectangle([133, 144, 146, 168], fill=(180, 224, 248))

    # Storefront 3: SUPERMARKET (x=153..212)
    d.rectangle([153, 84, 212, 184], fill=(198, 204, 210), outline=C_BLK)
    d.rectangle([151, 76, 214, 85], fill=CORP_GREEN, outline=C_BLK)
    d.rectangle([155, 118, 210, 132], fill=CORP_GREEN, outline=C_WHT)
    d.rectangle([158, 140, 192, 170], fill=(238, 248, 242), outline=C_DGY)
    for fx, fc in ((163, C_RED), (170, C_YEL), (177, C_LGN), (184, C_ORG)):
        d.rectangle([fx, 158, fx + 5, 166], fill=fc)
    d.rectangle([194, 142, 208, 184], fill=C_DGY, outline=C_BLK)

    for wx in (38, 62, 98, 126, 164, 188):
        d.rectangle([wx, 90, wx + 14, 106], fill=C_YEL if day_phase != "day" else (164, 214, 244), outline=C_DGY)

    _VENUE_BG_CACHE[key] = im
    return im


def _get_pub_bg() -> Image.Image:
    key = ("pub", "cozy")
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), (28, 18, 14))
    d = ImageDraw.Draw(im)

    # Warm Traditional UK Pub Interior ("THE RED LION")
    d.rectangle([26, 44, 214, 188], fill=(92, 42, 34), outline=GOLD_TRIM)
    d.rectangle([26, 44, 214, 58], fill=(48, 22, 18), outline=GOLD_TRIM)
    # Wood-panelled dado & pub carpet
    d.rectangle([28, 146, 212, 182], fill=(68, 38, 22))
    d.rectangle([28, 180, 212, 188], fill=(118, 32, 38))

    # Oak Back-Bar & Brass Hand-Pull Ale Pumps (x=36..114, y=96..182)
    d.rectangle([38, 92, 108, 138], fill=(46, 26, 16), outline=GOLD_TRIM)
    for bx, bc in ((44, C_GRN), (52, C_ORG), (60, NEON_CYAN), (68, C_RED), (76, GOLD_TRIM), (84, C_LGN), (94, C_YEL)):
        d.rectangle([bx, 102, bx + 4, 114], fill=bc)
        d.rectangle([bx, 120, bx + 4, 132], fill=bc)
    # Mahogany Bar Counter
    d.rectangle([34, 154, 116, 182], fill=(78, 42, 20), outline=C_BLK)
    d.rectangle([32, 151, 118, 155], fill=(124, 72, 34), outline=C_BLK)
    # 4 Brass Real-Ale Hand Pumps!
    for px_p in (52, 66, 80, 94):
        d.line([(px_p, 141), (px_p, 151)], fill=GOLD_TRIM, width=2)
        d.line([(px_p, 138), (px_p + 2, 143)], fill=C_WHT, width=2)

    # Big-Screen Live Football Match TV on Pub Wall (x=126..166, y=76..102)
    d.rectangle([126, 76, 166, 102], fill=C_BLK, outline=C_DGY)
    d.rectangle([129, 79, 163, 99], fill=CORP_GREEN)
    d.rectangle([138, 83, 154, 95], fill=CORP_GREEN, outline=C_WHT)
    d.line([(146, 79), (146, 99)], fill=C_WHT)

    # Classic Bristle Dartboard on Right Wall (x=180..198, y=82..100)
    d.ellipse([180, 82, 198, 100], fill=C_BLK, outline=GOLD_TRIM)
    d.ellipse([183, 85, 195, 97], fill=C_GRN, outline=C_RED)
    d.ellipse([187, 89, 191, 93], fill=C_RED)

    # Booth Table with Sunday Roast & Pint Glasses (x=144..186, y=164..182)
    d.rectangle([144, 166, 186, 170], fill=(112, 66, 32), outline=C_BLK)
    d.line([(152, 170), (152, 182)], fill=C_BLK, width=2)
    d.line([(178, 170), (178, 182)], fill=C_BLK, width=2)
    d.rectangle([154, 160, 158, 166], fill=GOLD_TRIM, outline=C_WHT)  # pint 1
    d.rectangle([172, 160, 176, 166], fill=GOLD_TRIM, outline=C_WHT)  # pint 2

    _VENUE_BG_CACHE[key] = im
    return im


def _get_gym_bg() -> Image.Image:
    key = ("gym", "neon")
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), (18, 22, 30))
    d = ImageDraw.Draw(im)

    # Modern 2026 Neon Fitness Studio ("PULSE 24/7 GYM")
    d.rectangle([26, 44, 214, 188], fill=(32, 38, 50), outline=NEON_CYAN)
    d.rectangle([26, 44, 214, 58], fill=(16, 22, 34), outline=NEON_CYAN)
    # Rubberized gym mat floor
    d.rectangle([28, 176, 212, 188], fill=(44, 48, 58))
    d.line([(28, 176), (212, 176)], fill=NEON_CYAN)

    # Panoramic Wall Mirrors + Neon Motivational Strip (x=36..204, y=72..126)
    d.rectangle([38, 72, 142, 124], fill=(56, 72, 92), outline=C_LGY)
    d.line([(48, 78), (68, 118)], fill=(96, 118, 142), width=2)
    d.line([(98, 78), (118, 118)], fill=(96, 118, 142), width=2)
    d.line([(38, 66), (202, 66)], fill=NEON_PINK, width=2)

    # Dumbbell Rack (Left x=38..74, y=152..176)
    d.rectangle([38, 156, 74, 176], fill=C_BLK, outline=C_MGY)
    for dx_w in range(42, 72, 7):
        d.rectangle([dx_w, 152, dx_w + 4, 156], fill=C_LGY)
        d.rectangle([dx_w, 163, dx_w + 5, 167], fill=C_MGY)

    # Squat / Power Rack (Center x=96..132, y=128..176)
    d.line([(98, 128), (98, 176)], fill=C_RED, width=3)
    d.line([(130, 128), (130, 176)], fill=C_RED, width=3)
    d.line([(96, 128), (132, 128)], fill=C_RED, width=3)

    # Treadmills (Right x=152..202, y=144..176)
    for tx_m in (154, 180):
        d.line([(tx_m + 14, 144), (tx_m + 18, 174)], fill=C_LGY, width=2)
        d.rectangle([tx_m + 10, 141, tx_m + 19, 146], fill=C_BLK, outline=NEON_CYAN)
        d.rectangle([tx_m, 172, tx_m + 18, 176], fill=C_BLK, outline=C_MGY)

    _VENUE_BG_CACHE[key] = im
    return im


def _get_cinema_bg() -> Image.Image:
    key = ("cinema", "imax")
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), (8, 8, 16))
    d = ImageDraw.Draw(im)

    # Dark Velvet Auditorium & Giant Glowing IMAX Screen
    d.rectangle([28, 44, 212, 190], fill=(16, 12, 26), outline=(92, 24, 42))
    # Crimson stage curtains left & right
    d.rectangle([32, 52, 46, 134], fill=(138, 22, 38))
    d.rectangle([194, 52, 208, 134], fill=(138, 22, 38))

    # Giant Widescreen Movie Frame (x=48..192, y=54..126)
    d.rectangle([48, 54, 192, 126], fill=(10, 18, 38), outline=C_LGY)

    # Tiered Plush Red Cinema Seats (2 rows: y=148..164 and y=166..186)
    for row_y in (148, 168):
        for sx in range(44, 192, 20):
            d.rectangle([sx, row_y, sx + 15, row_y + 14], fill=(156, 28, 44), outline=C_BLK)
    # Aisle floor lights
    for ly in (156, 168, 180):
        d.point((38, ly), fill=NEON_CYAN)
        d.point((202, ly), fill=NEON_CYAN)

    _VENUE_BG_CACHE[key] = im
    return im


def _get_beach_bg(day_phase: str) -> Image.Image:
    key = ("park_beach", day_phase)
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), C_BLK)
    d = ImageDraw.Draw(im)

    sky = (98, 182, 244) if day_phase == "day" else (38, 52, 98)
    d.rectangle([0, 0, 240, 118], fill=sky)
    if day_phase == "day":
        d.ellipse([170, 42, 186, 58], fill=C_YEL)

    # Turquoise Ocean Horizon (y=118..148)
    d.rectangle([0, 118, 240, 148], fill=(24, 132, 188))
    # Golden Sandy Beach & Promenade Walk (y=148..240)
    d.rectangle([0, 148, 240, 174], fill=(238, 208, 138))
    d.rectangle([0, 174, 240, 240], fill=(148, 154, 162))
    d.line([(0, 174), (240, 174)], fill=C_WHT, width=2)

    # Classic Pastel Pink & White Ice-Cream Van ("99 FLAKE", x=36..88, y=146..176)
    d.rectangle([38, 150, 84, 174], fill=C_WHT, outline=C_BLK)
    d.rectangle([38, 163, 84, 174], fill=PASTEL_PINK, outline=C_BLK)
    d.rectangle([48, 153, 68, 162], fill=(42, 58, 78), outline=C_BLK)  # serving hatch
    # Giant pixel 99 ice-cream cone on roof!
    d.polygon([(58, 142), (64, 142), (61, 150)], fill=C_ORG, outline=C_BLK)
    d.ellipse([57, 136, 65, 143], fill=C_WHT, outline=C_BLK)
    d.line([(63, 134), (65, 139)], fill=C_BRN, width=2)  # chocolate flake!
    d.ellipse([44, 170, 52, 178], fill=C_BLK)
    d.ellipse([70, 170, 78, 178], fill=C_BLK)

    # Striped Beach Parasol (x=176..198, y=138..168)
    d.line([(187, 144), (187, 168)], fill=C_BRN, width=2)
    d.pieslice([174, 136, 200, 154], start=180, end=360, fill=C_RED, outline=C_WHT)

    _VENUE_BG_CACHE[key] = im
    return im


def _get_nightclub_bg() -> Image.Image:
    key = ("nightclub", "night")
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), CLUB_DARK)
    d = ImageDraw.Draw(im)

    d.rectangle([24, 42, 216, 192], fill=(20, 12, 38), outline=NEON_PINK)
    d.rectangle([28, 105, 168, 108], fill=(48, 28, 84), outline=NEON_CYAN)
    d.line([(28, 96), (168, 96)], fill=NEON_PINK)
    for rx in range(36, 168, 16):
        d.line([(rx, 96), (rx, 105)], fill=C_PUR)

    for spx in (42, 136):
        d.rectangle([spx, 76, spx + 16, 105], fill=(28, 30, 40), outline=C_BLK)
        d.ellipse([spx + 3, 79, spx + 13, 89], fill=C_DGY, outline=NEON_CYAN)
        d.ellipse([spx + 2, 91, spx + 14, 103], fill=C_DGY, outline=NEON_PINK)

    d.rectangle([76, 91, 120, 105], fill=(34, 22, 62), outline=NEON_CYAN)
    d.ellipse([80, 88, 92, 92], fill=C_LGY, outline=C_BLK)
    d.ellipse([104, 88, 116, 92], fill=C_LGY, outline=C_BLK)

    for i in range(10):
        t = i / 9.0
        sx = int(round(196 - 26 * t))
        sy = int(round(185 - 80 * t))
        d.rectangle([sx - 5, sy - 2, sx + 5, sy], fill=(64, 34, 108), outline=NEON_CYAN)

    d.rectangle([32, 138, 72, 162], fill=(32, 18, 58), outline=NEON_PINK)
    for bx, bc in ((36, NEON_CYAN), (42, NEON_PINK), (48, C_LGN), (54, C_YEL), (60, NEON_CYAN), (66, NEON_PINK)):
        d.rectangle([bx, 143, bx + 3, 150], fill=bc)
        d.rectangle([bx, 153, bx + 3, 160], fill=bc)
    d.rectangle([30, 168, 76, 185], fill=(48, 24, 78), outline=C_BLK)
    d.rectangle([29, 166, 77, 169], fill=NEON_CYAN)

    _VENUE_BG_CACHE[key] = im
    return im


def _get_hotel_bg(day_phase: str) -> Image.Image:
    key = ("hotel", day_phase)
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), SKY_NIGHT)
    d = ImageDraw.Draw(im)

    sky_c = (94, 156, 218) if day_phase == "day" else (14, 22, 48)
    d.rectangle([0, 0, 240, 195], fill=sky_c)
    d.polygon([(52, 36), (188, 36), (204, 54), (36, 54)], fill=(44, 32, 58), outline=GOLD_TRIM)

    d.rectangle([38, 55, 178, 122], fill=(238, 228, 212), outline=GOLD_TRIM)
    d.rectangle([38, 115, 178, 122], fill=(148, 42, 58))
    d.rectangle([88, 62, 152, 98], fill=(18, 28, 62) if day_phase != "day" else (140, 198, 242), outline=GOLD_TRIM)
    for skx, skh in ((92, 18), (103, 26), (116, 22), (128, 30), (141, 19)):
        d.rectangle([skx, 97 - skh, skx + 9, 97], fill=(32, 44, 78))
        for wy in range(99 - skh, 95, 4):
            d.point((skx + 3, wy), fill=C_YEL)
            d.point((skx + 6, wy), fill=NEON_CYAN if wy % 8 == 0 else C_YEL)

    d.rectangle([44, 84, 48, 116], fill=C_BRN, outline=C_BLK)
    d.rectangle([48, 100, 82, 115], fill=C_WHT, outline=GOLD_TRIM)
    d.rectangle([50, 96, 60, 101], fill=C_WHT, outline=C_LGY)
    d.rectangle([60, 99, 81, 112], fill=(168, 44, 68), outline=C_BLK)

    d.rectangle([156, 105, 172, 113], fill=C_WHT, outline=C_MGY)
    d.pieslice([159, 98, 169, 108], start=180, end=360, fill=C_LGY, outline=C_BLK)
    d.ellipse([157, 113, 161, 117], fill=C_BLK)
    d.ellipse([167, 113, 171, 117], fill=C_BLK)

    d.rectangle([179, 116, 208, 122], fill=C_LGY, outline=C_BLK)
    d.line([(179, 104), (208, 104)], fill=GOLD_TRIM, width=2)
    for bx in range(183, 208, 5):
        d.line([(bx, 104), (bx, 116)], fill=GOLD_TRIM)

    d.rectangle([38, 123, 204, 188], fill=(244, 238, 226), outline=GOLD_TRIM)
    d.rectangle([40, 182, 202, 188], fill=(168, 32, 44))
    d.line([(40, 182), (202, 182)], fill=GOLD_TRIM)

    d.line([(121, 123), (121, 130)], fill=GOLD_TRIM)
    d.polygon([(113, 134), (121, 129), (129, 134), (121, 138)], fill=C_YEL, outline=GOLD_TRIM)

    d.rectangle([54, 136, 86, 154], fill=C_BRN, outline=GOLD_TRIM)
    for kx in range(58, 84, 6):
        d.point((kx, 142), fill=GOLD_TRIM)
        d.point((kx, 148), fill=GOLD_TRIM)
    d.rectangle([50, 165, 92, 183], fill=(82, 48, 34), outline=GOLD_TRIM)
    d.rectangle([48, 163, 94, 166], fill=C_WHT, outline=C_LGY)

    d.rectangle([136, 144, 158, 183], fill=GOLD_TRIM, outline=C_BLK)
    d.line([(147, 144), (147, 183)], fill=C_BLK)
    d.pieslice([140, 136, 154, 148], start=180, end=360, fill=C_BLK, outline=GOLD_TRIM)

    d.arc([172, 154, 190, 182], start=180, end=360, fill=GOLD_TRIM, width=2)
    d.line([(172, 168), (172, 181)], fill=GOLD_TRIM)
    d.line([(190, 168), (190, 181)], fill=GOLD_TRIM)
    d.rectangle([170, 180, 192, 182], fill=GOLD_TRIM)
    d.rectangle([175, 171, 187, 180], fill=C_RED, outline=C_BLK)
    d.rectangle([177, 164, 185, 171], fill=CORP_BLUE, outline=C_BLK)

    _VENUE_BG_CACHE[key] = im
    return im


def _get_girlfriend_bistro_bg() -> Image.Image:
    key = ("girlfriend", "evening")
    if key in _VENUE_BG_CACHE:
        return _VENUE_BG_CACHE[key]

    im = Image.new("RGB", (240, 240), (14, 18, 42))
    d = ImageDraw.Draw(im)

    d.rectangle([0, 0, 240, 92], fill=(16, 20, 48))
    d.rectangle([0, 92, 240, 142], fill=(44, 32, 78))
    d.rectangle([0, 142, 240, 176], fill=(22, 34, 64))
    d.ellipse([166, 42, 180, 56], fill=C_YEL)
    d.ellipse([171, 40, 183, 53], fill=(16, 20, 48))
    for wy in range(148, 172, 4):
        w_half = 8 - (wy - 148) // 4
        d.line([(172 - w_half, wy), (172 + w_half, wy)], fill=C_YEL)

    d.rectangle([0, 176, 240, 240], fill=(78, 72, 86))
    d.line([(20, 162), (220, 162)], fill=C_BLK, width=2)
    for rx in range(26, 218, 10):
        d.line([(rx, 162), (rx, 176)], fill=C_BLK)

    d.polygon([(28, 78), (112, 78), (120, 94), (24, 94)], fill=(156, 36, 58), outline=GOLD_TRIM)
    d.line([(36, 94), (36, 185)], fill=C_BRN, width=3)
    d.line([(198, 94), (198, 185)], fill=C_BRN, width=3)
    d.line([(36, 94), (198, 94)], fill=C_BRN, width=2)

    d.line([(120, 172), (120, 185)], fill=C_BLK, width=3)
    d.line([(113, 185), (127, 185)], fill=C_BLK, width=2)
    d.polygon([(104, 168), (136, 168), (139, 175), (101, 175)], fill=C_WHT, outline=C_BLK)
    for tx in range(106, 136, 6):
        d.rectangle([tx, 169, tx + 2, 174], fill=C_RED)
    d.line([(120, 163), (120, 168)], fill=C_WHT, width=2)
    d.rectangle([110, 164, 113, 168], fill=NEON_PINK)
    d.rectangle([127, 164, 130, 168], fill=NEON_PINK)

    _VENUE_BG_CACHE[key] = im
    return im


# ===========================================================================
# Dynamic Scene Renderers — Returns (canvas, status_str, status_col, jay_head_xy)
# ===========================================================================
def draw_driving_scene(
    t: float,
    tick: int,
    day_phase: str,
    settings: dict,
    route_from: str,
    route_to: str,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    """Animated parallax UK road trip in Jay's Arctic 2026 EV Fastback ('LCP 26')!"""
    im = Image.new("RGB", (240, 240), C_BLK)
    d = ImageDraw.Draw(im)
    skin, hair, top, _ = resolve_appearance(settings)

    # 1. Sky + Scrolling Distant Hills & City Silhouette
    if day_phase == "day":
        d.rectangle([0, 0, 240, 112], fill=(104, 172, 234))
        d.rectangle([0, 112, 240, 148], fill=(166, 210, 246))
        d.ellipse([172, 42, 186, 56], fill=C_YEL)
    elif day_phase == "dusk":
        d.rectangle([0, 0, 240, 100], fill=(44, 34, 88))
        d.rectangle([0, 100, 240, 148], fill=(186, 84, 72))
    else:
        d.rectangle([0, 0, 240, 112], fill=(12, 18, 38))
        d.rectangle([0, 112, 240, 148], fill=(24, 36, 68))
        for idx, (sx, sy) in enumerate(((52, 46), (88, 38), (144, 44), (186, 54))):
            d.point((sx, sy), fill=C_WHT if (tick + idx) % 3 else C_YEL)

    # Rolling green UK hills & scrolling roadside trees/signs
    d.rectangle([0, 138, 240, 158], fill=(56, 118, 64) if day_phase == "day" else (24, 52, 38))
    tree_scroll = int(t * 58.0) % 64
    for tx_base in range(-32, 272, 64):
        tx = tx_base - tree_scroll
        d.rectangle([tx + 2, 132, tx + 5, 154], fill=C_BRN)
        d.ellipse([tx - 5, 118, tx + 12, 136], fill=CORP_GREEN if day_phase == "day" else (28, 78, 44), outline=C_BLK)

    # Scrolling UK Green Motorway / A-Road Sign!
    sign_x = 230 - (int(t * 76.0) % 260)
    d.line([(sign_x + 8, 128), (sign_x + 8, 156)], fill=C_LGY, width=2)
    d.line([(sign_x + 34, 128), (sign_x + 34, 156)], fill=C_LGY, width=2)
    d.rectangle([sign_x, 110, sign_x + 44, 129], fill=(0, 112, 60), outline=C_WHT)
    dest_lbl = VENUE_SHORT_NAMES.get(route_to, "TOWN")[:6]
    draw_text_fn(im, sign_x + 22, 116, dest_lbl, color=C_WHT, center_x=True)

    # 2. Scrolling Dual-Carriageway Tarmac & Dashed Center Line (y=156..204)
    d.rectangle([0, 156, 240, 240], fill=(46, 50, 58))
    d.line([(0, 156), (240, 156)], fill=C_WHT)
    dash_off = int(t * 140.0) % 28
    for lx in range(-28, 260, 28):
        dx0 = lx - dash_off
        d.rectangle([dx0, 178, dx0 + 14, 181], fill=C_WHT)

    # 3. Sleek 2026 Arctic-Silver EV Fastback ("Polestar" inspired!) at Center (x=68..176)
    bob = tick % 2  # subtle 1px road vibration!
    cy = 148 + bob

    # Matrix LED Headlight Beam at Dusk/Night!
    if day_phase != "day":
        d.polygon([(174, cy + 16), (226, cy + 8), (226, cy + 28), (174, cy + 22)], fill=(210, 238, 255))

    # Ground shadow under EV
    d.ellipse([70, 179, 176, 186], fill=(22, 24, 30))

    # Aerodynamic Fastback Cabin & Glasshouse
    d.polygon([(82, cy + 12), (98, cy + 1), (144, cy + 1), (162, cy + 12)], fill=(30, 38, 52), outline=C_BLK)
    # Panoramic tinted windows showing Jay at the steering wheel (+ Buddy in back!)
    d.polygon([(87, cy + 12), (100, cy + 3), (120, cy + 3), (120, cy + 12)], fill=(116, 176, 214), outline=C_BLK)
    d.polygon([(123, cy + 12), (123, cy + 3), (142, cy + 3), (156, cy + 12)], fill=(116, 176, 214), outline=C_BLK)

    # Buddy's golden terrier head poking happily out the rear window!
    d.rectangle([94, cy + 6, 100, cy + 11], fill=C_YEL, outline=C_BLK)
    d.point((99, cy + 8), fill=C_BLK)
    d.line([(92, cy + 7 - (tick % 2)), (94, cy + 8)], fill=C_BRN)  # flapping ear!

    # Jay in the driver's seat holding steering wheel!
    d.rectangle([131, cy + 4, 138, cy + 10], fill=skin, outline=C_BLK)
    d.line([(131, cy + 4), (137, cy + 4)], fill=hair, width=2)
    d.point((136, cy + 6), fill=C_BLK)
    d.rectangle([130, cy + 10, 138, cy + 12], fill=SAFETY_HIVIS if route_to == "work_hub" or route_from == "work_hub" else top)
    d.line([(143, cy + 8), (140, cy + 12)], fill=C_BLK, width=2)  # steering wheel

    # Sculpted Arctic-White EV Bodywork + Performance Gold Brake Calipers!
    d.polygon(
        [(68, cy + 15), (74, cy + 12), (164, cy + 12), (176, cy + 16), (176, cy + 25), (68, cy + 25)],
        fill=(236, 242, 248),
        outline=C_BLK,
    )
    # Lower gloss-black aero sill
    d.rectangle([72, cy + 23, 172, cy + 25], fill=(24, 28, 34))
    # Rear crimson LED lightbar & front Thor's-Hammer DRL
    d.rectangle([68, cy + 14, 72, cy + 18], fill=(238, 38, 48))
    d.rectangle([170, cy + 15, 176, cy + 18], fill=NEON_CYAN if day_phase == "day" else C_WHT)
    # Flush door handles
    d.line([(104, cy + 16), (108, cy + 16)], fill=C_DGY)
    d.line([(130, cy + 16), (134, cy + 16)], fill=C_DGY)

    # Spinning Diamond-Cut Alloy Wheels + Gold Calipers!
    for wx in (88, 154):
        d.ellipse([wx - 9, cy + 17, wx + 9, cy + 35], fill=C_BLK, outline=C_DGY)
        d.ellipse([wx - 5, cy + 21, wx + 5, cy + 31], fill=C_LGY)
        d.point((wx - 3, cy + 25), fill=GOLD_TRIM)  # performance gold caliper!
        ang = (tick * 45) % 180
        rx_s = int(round(math.cos(math.radians(ang)) * 4))
        ry_s = int(round(math.sin(math.radians(ang)) * 4))
        d.line([(wx - rx_s, cy + 26 - ry_s), (wx + rx_s, cy + 26 + ry_s)], fill=C_BLK)

    f_short = VENUE_SHORT_NAMES.get(route_from, "HOME")
    t_short = VENUE_SHORT_NAMES.get(route_to, "TOWN")
    if route_to == "driving" or route_from == route_to:
        status = "CRUISING IN EV"
    else:
        status = f"EV -> {t_short}"[:17]

    return im, status, NEON_CYAN, (135, cy - 2)


def draw_work_hub_scene(
    t: float,
    tick: int,
    day_phase: str,
    settings: dict,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_work_hub_bg(day_phase).copy()
    d = ImageDraw.Draw(canvas)
    skin, hair, _, _ = resolve_appearance(settings)

    draw_text_fn(canvas, 36, 50, "METRO FLEET & TECH", color=C_WHT, shadow=C_BLK)

    beacon_on = (tick % 4) < 2
    d.rectangle([107, 136, 112, 140], fill=(255, 190, 0) if beacon_on else C_ORG, outline=C_BLK)
    if beacon_on:
        for bx, by in ((104, 135), (115, 135), (109, 132)):
            d.point((bx, by), fill=SAFETY_HIVIS)

    col_spr = get_custom_char_sprite("walk_1", SKIN_STYLES["caucasian"][1], HAIR_STYLES["blonde"][1], CORP_BLUE, C_DGY, flip_x=True)
    canvas.paste(col_spr, (84, 96), col_spr)

    cycle = t % 26.0
    if cycle < 16.0:
        phase = cycle / 16.0
        if phase < 0.35:
            jx = int(round(92 + (190 - 92) * (phase / 0.35)))
            pose = "hivis_walk" if (tick % 2 == 0) else "hivis_stand"
            flip = False
            status = "FLEET WALKAROUND"
        elif phase < 0.65:
            jx = 194
            pose = "hivis_stand"
            flip = True
            status = "CHECKING BIN LIFT"
            if (tick % 6) < 4:
                d.rectangle([182, 144, 206, 154], fill=CORP_GREEN, outline=C_BLK)
                draw_text_fn(canvas, 194, 146, "OK!", color=C_WHT, center_x=True)
        else:
            jx = int(round(190 - (190 - 108) * ((phase - 0.65) / 0.35)))
            pose = "hivis_walk" if (tick % 2 == 0) else "hivis_stand"
            flip = True
            status = "LOGGING PMI CHECK"

        spr = get_custom_char_sprite(pose, skin, hair, CORP_BLUE, (28, 42, 78), flip_x=flip)
        canvas.paste(spr, (jx - 6, 165), spr)
        head_xy = (jx, 162)
    else:
        jx = int(round(58 + math.sin(t * 0.9) * 12))
        spr = get_custom_char_sprite("hivis_stand", skin, hair, CORP_BLUE, (28, 42, 78), flip_x=False)
        canvas.paste(spr, (jx - 6, 96), spr)
        status = "9-5 TECH OFFICE"
        head_xy = (jx, 94)

    return canvas, status, SAFETY_HIVIS, head_xy


def draw_shops_scene(
    t: float,
    tick: int,
    day_phase: str,
    settings: dict,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_shops_bg(day_phase).copy()
    skin, hair, top, pants = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]

    draw_text_fn(canvas, 57, 122, "TECH", color=NEON_CYAN, center_x=True)
    draw_text_fn(canvas, 124, 122, "GREGGS", color=C_WHT, center_x=True)
    draw_text_fn(canvas, 182, 122, "MART", color=C_WHT, center_x=True)

    sx = int((40 + (t * 14.0) % 165))
    shopper = get_custom_char_sprite(f"walk_{tick % 2}", gf_skin, HAIR_STYLES["black"][1], C_PUR, C_DGY, flip_x=False)
    canvas.paste(shopper, (sx - 6, 166), shopper)

    phs = t % 24.0
    if phs < 8.0:
        jx = int(round(48 + (118 - 48) * (phs / 8.0)))
        pose = "walk_0" if (tick % 2 == 0) else "shop_0"
        flip = False
        status = "GREGGS SAUSAGE ROL"
    elif phs < 16.0:
        jx = int(round(118 + (176 - 118) * ((phs - 8.0) / 8.0)))
        pose = "shop_0"
        flip = False
        status = "WEEKLY FOOD SHOP"
    else:
        jx = int(round(176 - (176 - 54) * ((phs - 16.0) / 8.0)))
        pose = "shop_0" if (tick % 2 == 0) else "walk_1"
        flip = True
        status = "BROWSING PC PARTS"

    jay_spr = get_custom_char_sprite(pose, skin, hair, top, pants, flip_x=flip)
    canvas.paste(jay_spr, (jx - 6, 168), jay_spr)

    if settings.get("girlfriend_enabled", True):
        gfx = max(36, min(198, jx + (14 if flip else -14)))
        gf_spr = get_custom_char_sprite(f"gf_walk_{tick % 2}", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, CORP_BLUE, flip_x=flip)
        canvas.paste(gf_spr, (gfx - 6, 169), gf_spr)

    return canvas, status, GREGGS_GOLD, (jx, 166)


def draw_pub_scene(
    t: float,
    tick: int,
    settings: dict,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_pub_bg().copy()
    d = ImageDraw.Draw(canvas)
    skin, hair, top, pants = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]

    draw_text_fn(canvas, 120, 48, "THE RED LION PUB", color=GOLD_TRIM, shadow=C_BLK, center_x=True)

    # Tiny animated football moving across the pub TV pitch!
    ball_x = 134 + int(round((math.sin(t * 2.4) * 0.5 + 0.5) * 24))
    ball_y = 85 + int(round(math.cos(t * 3.1) * 4))
    d.point((ball_x, ball_y), fill=C_WHT)

    # Landlord behind mahogany bar + mate near dartboard
    landlord = get_custom_char_sprite("walk_1", gf_skin, HAIR_STYLES["auburn"][1], C_WHT, C_BLK)
    mate = get_custom_char_sprite("pint_0", gf_skin, HAIR_STYLES["black"][1], CORP_GREEN, C_DGY, flip_x=True)
    canvas.paste(landlord, (72, 134), landlord)
    canvas.paste(mate, (176, 162), mate)

    # Jay enjoying a pint at the bar & chatting at the table!
    jx = int(round(108 + (136 - 108) * (0.5 + 0.5 * math.sin(t * 0.5))))
    pose = "pint_0" if (tick // 3) % 2 == 0 else f"walk_{tick % 2}"
    jay_s = get_custom_char_sprite(pose, skin, hair, top, pants, flip_x=False)
    canvas.paste(jay_s, (jx - 6, 162), jay_s)

    if settings.get("girlfriend_enabled", True):
        gf_s = get_custom_char_sprite("gf_walk_1", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, CORP_BLUE, flip_x=True)
        canvas.paste(gf_s, (158, 163), gf_s)

    return canvas, "PINT @ RED LION", GOLD_TRIM, (jx, 160)


def draw_gym_scene(
    t: float,
    tick: int,
    settings: dict,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_gym_bg().copy()
    skin, hair, top, _ = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]

    draw_text_fn(canvas, 120, 48, "PULSE 24/7 GYM", color=NEON_CYAN, shadow=C_BLK, center_x=True)

    # Gym member jogging on right treadmill
    runner = get_custom_char_sprite(f"walk_{tick % 2}", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, C_BLK)
    canvas.paste(runner, (180, 154), runner)

    cycle = t % 18.0
    if cycle < 10.0:
        # Overhead barbell press in the power rack!
        jx = 114
        pose = "lift_0" if (tick // 2) % 2 == 0 else "walk_1"
        jay_s = get_custom_char_sprite(pose, skin, hair, top, C_BLK)
        canvas.paste(jay_s, (jx - 6, 156), jay_s)
        status = "PUMPING IRON!"
    else:
        # Running sprints on treadmill 1!
        jx = 160
        jay_s = get_custom_char_sprite(f"walk_{tick % 2}", skin, hair, top, C_BLK)
        canvas.paste(jay_s, (jx - 6, 154), jay_s)
        status = "CARDIO SPRINT"

    return canvas, status, NEON_CYAN, (jx, 152)


def draw_cinema_scene(
    t: float,
    tick: int,
    settings: dict,
    heart_icon: Image.Image,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_cinema_bg().copy()
    d = ImageDraw.Draw(canvas)
    skin, hair, top, pants = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]

    # Animated Sci-Fi Space Battle on the Giant IMAX Screen (x=50..190, y=56..124)!
    for si in range(14):
        sx = 52 + ((si * 19 + tick * 4) % 136)
        sy = 58 + ((si * 13) % 62)
        d.point((sx, sy), fill=C_WHT)
    # ringed planet
    d.ellipse([146, 68, 168, 90], fill=(188, 92, 58), outline=GOLD_TRIM)
    d.line([(140, 82), (174, 76)], fill=C_YEL, width=2)
    # Hero starfighter firing cyan laser bolts!
    ship_y = 88 + int(round(math.sin(t * 2.6) * 12))
    d.polygon([(68, ship_y), (82, ship_y + 4), (68, ship_y + 8)], fill=C_WHT, outline=NEON_CYAN)
    lx_laser = 84 + ((tick * 16) % 72)
    d.line([(lx_laser, ship_y + 4), (min(186, lx_laser + 14), ship_y + 4)], fill=NEON_CYAN, width=2)

    # Jay & Chloe seated center-row with a striped Popcorn Tub!
    jay_s = get_custom_char_sprite("walk_1", skin, hair, top, pants)
    canvas.paste(jay_s, (104, 152), jay_s)
    # Popcorn bucket between them
    d.rectangle([118, 162, 124, 169], fill=C_RED, outline=C_WHT)
    d.line([(119, 161), (123, 161)], fill=C_YEL, width=2)

    if settings.get("girlfriend_enabled", True):
        gf_s = get_custom_char_sprite("gf_walk_1", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, PASTEL_PINK, flip_x=True)
        canvas.paste(gf_s, (124, 153), gf_s)
        if (tick % 8) < 4:
            canvas.paste(heart_icon, (117, 142 - (tick % 3)), heart_icon)

    return canvas, "IMAX MOVIE NIGHT", PASTEL_PINK, (110, 150)


def draw_beach_scene(
    t: float,
    tick: int,
    day_phase: str,
    settings: dict,
    dog_sprite: Image.Image,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_beach_bg(day_phase).copy()
    d = ImageDraw.Draw(canvas)
    skin, hair, top, pants = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]

    # Animated white surf waves rolling onto the sand!
    wave_y = 145 + int(round(math.sin(t * 2.0) * 2))
    for wx in range(18, 222, 18):
        d.arc([wx, wave_y - 2, wx + 14, wave_y + 3], start=0, end=180, fill=C_WHT)

    # Flying pixel seagulls in sky
    gx = 60 + (int(t * 18.0) % 120)
    gy = 64 + int(round(math.sin(t * 3.5) * 3))
    d.line([(gx - 3, gy), (gx, gy + 2), (gx + 3, gy)], fill=C_WHT)

    # Jay strolling the promenade throwing ball for Buddy!
    jx = int(round(92 + (164 - 92) * (0.5 + 0.5 * math.sin(t * 0.7))))
    flip = math.cos(t * 0.7) < 0
    jay_s = get_custom_char_sprite(f"walk_{tick % 2}", skin, hair, top, pants, flip_x=flip)
    canvas.paste(jay_s, (jx - 6, 160), jay_s)

    # Buddy bounding ahead on the golden sand!
    bx = max(44, min(196, jx + (-22 if flip else 22)))
    canvas.paste(dog_sprite, (bx - 6, 164), dog_sprite)

    if settings.get("girlfriend_enabled", True):
        gf_s = get_custom_char_sprite(f"gf_walk_{tick % 2}", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, C_WHT, flip_x=flip)
        canvas.paste(gf_s, (jx + (12 if flip else -12) - 6, 161), gf_s)

    draw_text_fn(canvas, 61, 144, "99 ICE", color=NEON_PINK, center_x=True)
    return canvas, "SEASIDE DOG WALK", C_YEL, (jx, 158)


def draw_nightclub_scene(
    t: float,
    tick: int,
    settings: dict,
    heart_icon: Image.Image,
    note_a: Image.Image,
    note_b: Image.Image,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_nightclub_bg().copy()
    d = ImageDraw.Draw(canvas)
    skin, hair, top, pants = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]

    draw_text_fn(canvas, 120, 48, "CLUB SID 2026", color=NEON_PINK, shadow=C_BLK, center_x=True)

    beam_cols = (NEON_CYAN, NEON_PINK, C_LGN, C_YEL)
    for bi in range(4):
        ang = t * 1.8 + bi * (math.pi / 2.0)
        ex = max(32, min(206, int(round(120 + math.cos(ang) * 78))))
        ey = max(110, min(186, int(round(145 + math.sin(ang) * 34))))
        d.line([(120, 118), (ex, ey)], fill=beam_cols[(bi + tick) % 4], width=1)

    d.line([(120, 108), (120, 113)], fill=C_LGY)
    d.ellipse([114, 113, 126, 125], fill=C_LGY, outline=C_WHT)
    for dx_b in (-3, 0, 3):
        for dy_b in (-3, 0, 3):
            d.point((120 + dx_b, 119 + dy_b), fill=C_WHT if ((dx_b + dy_b + tick) % 2 == 0) else NEON_CYAN)

    tile_palette = (NEON_PINK, NEON_CYAN, C_PUR, C_YEL, C_LGN, CORP_BLUE)
    for ti in range(8):
        tx0 = 82 + ti * 12
        d.rectangle([tx0, 183, tx0 + 11, 188], fill=tile_palette[(ti + tick) % len(tile_palette)], outline=C_BLK)

    for ei in range(10):
        ex0 = 64 + ei * 7
        eh = 4 + ((tick * 3 + ei * 5) % 16)
        ecol = NEON_CYAN if eh < 10 else (C_YEL if eh < 15 else NEON_PINK)
        d.rectangle([ex0, 86 - eh, ex0 + 4, 86], fill=ecol)

    dj_spr = get_custom_char_sprite(f"dance_{tick % 2}", gf_skin, HAIR_STYLES["black"][1], NEON_CYAN, C_BLK)
    canvas.paste(dj_spr, (92, 74), dj_spr)

    bar_spr = get_custom_char_sprite("walk_1", gf_skin, HAIR_STYLES["auburn"][1], C_WHT, C_BLK)
    canvas.paste(bar_spr, (48, 150), bar_spr)

    c1 = get_custom_char_sprite(f"dance_{(tick + 1) % 2}", SKIN_STYLES["warm_tan"][1], HAIR_STYLES["black"][1], C_YEL, C_BLU)
    c2 = get_custom_char_sprite(f"gf_dance_{(tick + 1) % 2}", gf_skin, HAIR_STYLES["auburn"][1], NEON_CYAN, C_PUR, flip_x=True)
    canvas.paste(c1, (86, 165), c1)
    canvas.paste(c2, (158, 166), c2)

    jx = 116 + int(round(math.sin(t * 2.2) * 6))
    jay_dance = get_custom_char_sprite(f"dance_{tick % 2}", skin, hair, top, pants, flip_x=False)
    canvas.paste(jay_dance, (jx - 6, 165), jay_dance)

    if settings.get("girlfriend_enabled", True):
        gf_dance = get_custom_char_sprite(f"gf_dance_{tick % 2}", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, PASTEL_PINK, flip_x=True)
        canvas.paste(gf_dance, (jx + 12, 166), gf_dance)
        if (tick % 6) < 3:
            canvas.paste(heart_icon, (jx + 5, 154 - (tick % 3)), heart_icon)

    canvas.paste(note_a, (72, 72 - (tick % 5)), note_a)
    canvas.paste(note_b, (124, 70 - ((tick + 2) % 5)), note_b)

    return canvas, "DANCING AT SID 85", NEON_PINK, (jx, 162)


def draw_hotel_scene(
    t: float,
    tick: int,
    day_phase: str,
    settings: dict,
    heart_icon: Image.Image,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_hotel_bg(day_phase).copy()
    d = ImageDraw.Draw(canvas)
    skin, hair, top, pants = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]

    draw_text_fn(canvas, 120, 42, "GRAND BOUTIQUE", color=GOLD_TRIM, shadow=C_BLK, center_x=True)

    for idx, (sx, sy) in enumerate(((186, 66), (198, 74), (206, 86), (192, 88))):
        d.point((sx, sy), fill=C_YEL if (tick + idx) % 4 == 0 else C_WHT)

    conc = get_custom_char_sprite("walk_1", gf_skin, HAIR_STYLES["black"][1], (140, 28, 44), C_BLK)
    canvas.paste(conc, (66, 146), conc)

    cycle = t % 22.0
    if cycle < 9.0:
        jx = int(round(88 + (142 - 88) * (cycle / 9.0)))
        jay_s = get_custom_char_sprite(f"walk_{tick % 2}", skin, hair, top, pants, flip_x=False)
        canvas.paste(jay_s, (jx - 6, 164), jay_s)
        if settings.get("girlfriend_enabled", True):
            gf_s = get_custom_char_sprite(f"gf_walk_{tick % 2}", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, C_WHT)
            canvas.paste(gf_s, (jx - 20, 165), gf_s)
        status = "HOTEL CHECK-IN"
        head_xy = (jx, 161)
    else:
        jx = int(round(112 + (188 - 112) * (0.5 + 0.5 * math.sin(t * 0.6))))
        jay_s = get_custom_char_sprite("walk_1", skin, hair, top, pants, flip_x=jx > 165)
        canvas.paste(jay_s, (jx - 6, 97), jay_s)
        if settings.get("girlfriend_enabled", True):
            gfx = min(198, jx + 13)
            gf_s = get_custom_char_sprite("gf_walk_1", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, C_WHT, flip_x=True)
            canvas.paste(gf_s, (gfx - 6, 98), gf_s)
            if jx > 165:
                canvas.paste(heart_icon, (jx + 2, 86 - (tick % 3)), heart_icon)
        status = "PENTHOUSE SUITE"
        head_xy = (jx, 95)

    return canvas, status, GOLD_TRIM, head_xy


def draw_girlfriend_scene(
    t: float,
    tick: int,
    settings: dict,
    heart_icon: Image.Image,
    note_a: Image.Image,
    draw_text_fn,
) -> tuple[Image.Image, str, tuple[int, int, int], tuple[int, int]]:
    canvas = _get_girlfriend_bistro_bg().copy()
    d = ImageDraw.Draw(canvas)
    skin, hair, top, pants = resolve_appearance(settings)
    gf_skin = SKIN_STYLES["caucasian"][1]
    gname = settings.get("girlfriend_name", "CHLOE")

    bulb_cols = (C_YEL, PASTEL_PINK, C_WHT, GOLD_TRIM)
    for bi, bx in enumerate(range(42, 196, 12)):
        by = 96 + int(round(math.sin((bx - 42) / 24.0) * 3))
        d.ellipse([bx - 1, by - 1, bx + 1, by + 1], fill=bulb_cols[(bi + tick) % 4])

    d.point((120, 161 - (tick % 2)), fill=C_YEL)
    d.point((120, 162), fill=C_ORG)

    cycle = t % 20.0
    if cycle < 12.0:
        jay_s = get_custom_char_sprite("walk_1", skin, hair, top, pants, flip_x=False)
        gf_s = get_custom_char_sprite("gf_walk_1", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, PASTEL_PINK, flip_x=True)
        canvas.paste(jay_s, (91, 165), jay_s)
        canvas.paste(gf_s, (136, 166), gf_s)
        canvas.paste(heart_icon, (116, 152 - (tick % 6)), heart_icon)
        canvas.paste(note_a, (64, 134 - (tick % 5)), note_a)
        status = f"DATE WITH {gname}"[:17]
        head_xy = (97, 162)
    else:
        wx = int(round(56 + (168 - 56) * ((cycle - 12.0) / 8.0)))
        jay_s = get_custom_char_sprite(f"walk_{tick % 2}", skin, hair, top, pants, flip_x=False)
        gf_s = get_custom_char_sprite(f"gf_walk_{tick % 2}", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, PASTEL_PINK, flip_x=False)
        canvas.paste(jay_s, (wx - 6, 165), jay_s)
        canvas.paste(gf_s, (wx + 7, 166), gf_s)
        canvas.paste(heart_icon, (wx + 2, 152 - (tick % 4)), heart_icon)
        status = f"WALK WITH {gname}"[:17]
        head_xy = (wx, 162)

    draw_text_fn(canvas, 72, 83, "STARLIGHT BISTRO", color=GOLD_TRIM, center_x=True)
    return canvas, status, PASTEL_PINK, head_xy


def draw_house_party_overlay(
    canvas: Image.Image,
    t: float,
    tick: int,
    settings: dict,
    heart_icon: Image.Image,
    note_a: Image.Image,
    note_b: Image.Image,
) -> None:
    d = ImageDraw.Draw(canvas)
    gf_skin = SKIN_STYLES["caucasian"][1]

    fairy_cols = (NEON_PINK, NEON_CYAN, C_YEL, C_LGN, GOLD_TRIM)
    for floor_y_ceil, x_start, x_end in ((61, 48, 192), (103, 32, 208), (147, 44, 196)):
        d.line([(x_start, floor_y_ceil), (x_end, floor_y_ceil)], fill=C_DGY)
        for idx, lx in enumerate(range(x_start + 6, x_end - 4, 12)):
            c = fairy_cols[(idx + tick) % len(fairy_cols)]
            d.rectangle([lx - 1, floor_y_ceil + 1, lx + 1, floor_y_ceil + 3], fill=c)

    balloons = (
        (56, 158, NEON_PINK),
        (124, 156, NEON_CYAN),
        (144, 112, C_YEL),
        (174, 114, C_LGN),
        (118, 69, NEON_PINK),
    )
    for bi, (bx, by_base, bcol) in enumerate(balloons):
        by = by_base + int(round(math.sin(t * 2.5 + bi) * 2))
        d.line([(bx, by + 5), (bx, by + 13)], fill=C_LGY)
        d.ellipse([bx - 3, by - 4, bx + 3, by + 4], fill=bcol, outline=C_BLK)
        d.point((bx - 1, by - 2), fill=C_WHT)

    d.rectangle([152, 169, 161, 171], fill=C_WHT, outline=C_RED)
    d.rectangle([165, 167, 172, 171], fill=NEON_CYAN, outline=C_WHT)
    d.line([(166, 168), (171, 168)], fill=NEON_PINK)

    chloe = get_custom_char_sprite(f"gf_dance_{tick % 2}", gf_skin, HAIR_STYLES["blonde"][1], NEON_PINK, PASTEL_PINK, flip_x=False)
    canvas.paste(chloe, (108, 122), chloe)

    g1 = get_custom_char_sprite(f"dance_{(tick + 1) % 2}", SKIN_STYLES["warm_tan"][1], HAIR_STYLES["black"][1], NEON_CYAN, C_BLU, flip_x=True)
    canvas.paste(g1, (158, 121), g1)

    g2 = get_custom_char_sprite(f"dance_{tick % 2}", gf_skin, HAIR_STYLES["auburn"][1], C_YEL, C_DGY, flip_x=False)
    g3 = get_custom_char_sprite(f"gf_dance_{(tick + 1) % 2}", gf_skin, HAIR_STYLES["brown"][1], C_LGN, CORP_BLUE, flip_x=True)
    canvas.paste(g2, (84, 165), g2)
    canvas.paste(g3, (148, 166), g3)

    canvas.paste(note_a, (88, 114 - (tick % 6)), note_a)
    canvas.paste(note_b, (96, 112 - ((tick + 3) % 6)), note_b)
    canvas.paste(heart_icon, (112, 112 - (tick % 4)), heart_icon)

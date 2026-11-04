#!/usr/bin/env python3
"""Rendu d'une vidéo TikTok « Astuce Excel du jour » (1080x1920, ~30 s) à partir d'un fichier JSON.
Usage : python3 render.py spec.json sortie.mp4

Champs de variété (tous facultatifs ; sans eux on retrouve le look « classique » d'origine) :
  "theme"  : nom d'un thème de THEMES (palette, fond, disposition, police, animations, musique)
  "music"  : force une ambiance musicale de MUSIC (sinon celle du thème)
  "layout" : classic | banner | card | laptop (sinon celle du thème)
  "cta_style" : pulse | card | bar (sinon celui du thème)
Deux modes :
  "mode": "formula" (défaut) – une formule tapée dans la barre fx + cellule résultat (anciennes specs)
  "mode": "steps"   – astuces sans formule (raccourcis, menus, mise en forme) :
     "steps": [{"at": 7.5, "text": "...", "keys": ["Ctrl","E"] | "path": ["Accueil","..."], "fx": "texte tapé"}]
     "select": [{"at": 7.5, "cell": [ligne, col]} | {"at": .., "range": [l1, c1, l2, c2]}]  (lignes Excel, col 0 = A)
     "fills":  [{"at": 9.0, "cells": [[ligne, col, "valeur"], ...], "stagger": 0.12}]
     "paints": [{"at": 14.0, "rows": [3, 5], "cols": [0,1,2] (défaut : toutes), "fill": [r,g,b], "color": [r,g,b], "stagger": 0.2}]
     "dropdowns": [{"at": 12.6, "until": 14.0, "cell": [2, 2], "items": ["A","B"], "pick": 0, "arrow_from": 12.0, "arrow_rows": [2,3]}]
       (liste déroulante ouverte sous une cellule ; flèche ▼ affichée sur arrow_rows à partir de arrow_from)
"""
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 24

# ---------------------------------------------------------------- polices
FONTS = {
    "dejavu": ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    "inter": ("/usr/share/fonts/opentype/inter/Inter-Medium.otf", "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"),
    "poppins": ("/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf", "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"),
    "carlito": ("/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf", "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf"),
    "serif": ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
}
MONO = ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")
_FC = {}
def _load(path, size, fallback):
    key = (path, size)
    if key not in _FC:
        try: _FC[key] = ImageFont.truetype(path, size)
        except OSError: _FC[key] = ImageFont.truetype(fallback, size)
    return _FC[key]
DISPLAY = "dejavu"  # police des titres/légendes (changée par le thème)
def font(size, bold=False, mono=False, family=None):
    if mono: return _load(MONO[1 if bold else 0], size, MONO[0])
    fam = FONTS.get(family or "dejavu", FONTS["dejavu"])
    return _load(fam[1 if bold else 0], size, FONTS["dejavu"][1 if bold else 0])
def dfont(size, bold=True):  # police d'affichage du thème
    return font(size, bold, family=DISPLAY)

# ---------------------------------------------------------------- thèmes
BASE = dict(
    bg=("vgrad", (20, 64, 42), (10, 36, 24)), pattern=None, pattern_color=(255, 255, 255, 18),
    badge_bg=(255, 214, 0), badge_fg=(20, 20, 20), badge_text="ASTUCE EXCEL DU JOUR",
    font="dejavu", cap_fg=(255, 255, 255), accent=(255, 214, 0), accent2=(120, 180, 255), accent3=(140, 230, 160),
    cap_style="box", cap_box=(0, 0, 0, 170), cap_anim="fade",
    win_bar=(33, 115, 70), win_bar_fg=(255, 255, 255), cell=(255, 255, 255), hdr=(238, 238, 238), hdr_fg=(90, 90, 90),
    grid=(214, 214, 214), txt=(30, 30, 30), row1=(226, 239, 218), crit_hl=(255, 236, 150), sum_hl=(205, 228, 255),
    res_fill=(198, 239, 206), res_txt=(0, 97, 0), sel=(33, 115, 70), fx_txt=(30, 30, 30), win_bg=(255, 255, 255),
    key_bg=(255, 255, 255), key_fg=(25, 25, 25), key_shadow=(150, 150, 150), path_bg=(33, 115, 70), path_fg=(255, 255, 255),
    layout="classic", entry="slide_up", result_style="fill", cta_style="pulse", music="lofi",
    cta_bg=(0, 0, 0), cta_btn=(254, 44, 85), sig_fg=(255, 255, 255, 200), sig_style="plain",
)
THEMES = {
    "classique": {},
    "neon": dict(
        bg=("vgrad", (8, 6, 26), (2, 2, 10)), pattern="neon_grid", pattern_color=(0, 255, 230, 40),
        badge_bg=(255, 0, 170), badge_fg=(255, 255, 255), badge_text="EXCEL HACK //", font="inter",
        cap_fg=(235, 245, 255), accent=(0, 255, 230), accent2=(255, 80, 200), accent3=(170, 255, 90),
        cap_style="glow", cap_anim="typewriter",
        win_bar=(30, 26, 60), win_bar_fg=(0, 255, 230), cell=(18, 18, 36), hdr=(32, 30, 58), hdr_fg=(150, 150, 200),
        grid=(55, 52, 95), txt=(230, 230, 255), row1=(45, 30, 80), crit_hl=(90, 30, 110), sum_hl=(20, 70, 110),
        res_fill=(0, 90, 80), res_txt=(0, 255, 230), sel=(0, 255, 230), fx_txt=(0, 255, 230), win_bg=(24, 22, 46),
        key_bg=(25, 25, 50), key_fg=(0, 255, 230), key_shadow=(255, 0, 170), path_bg=(255, 0, 170), path_fg=(255, 255, 255),
        layout="laptop", entry="zoom", result_style="glow", cta_style="bar", music="electro",
        cta_bg=(5, 3, 20), cta_btn=(255, 0, 170), sig_fg=(0, 255, 230, 220), sig_style="glow"),
    "epure": dict(
        bg=("vgrad", (250, 250, 252), (232, 236, 243)), pattern="dots", pattern_color=(0, 0, 0, 14),
        badge_bg=(30, 30, 30), badge_fg=(255, 255, 255), badge_text="Astuce Excel", font="inter",
        cap_fg=(25, 25, 35), accent=(37, 99, 235), accent2=(220, 38, 38), accent3=(5, 150, 105),
        cap_style="underline", cap_anim="slide",
        win_bar=(245, 245, 245), win_bar_fg=(40, 40, 40), sel=(37, 99, 235), res_fill=(219, 234, 254), res_txt=(29, 78, 216),
        key_bg=(255, 255, 255), key_fg=(25, 25, 35), key_shadow=(190, 195, 205), path_bg=(37, 99, 235),
        layout="banner", entry="fade", result_style="marker", cta_style="card", music="piano",
        cta_bg=(250, 250, 252), cta_btn=(37, 99, 235), sig_fg=(60, 60, 70, 220)),
    "vert_excel": dict(
        bg=("vgrad", (33, 115, 70), (16, 80, 46)), pattern="cells", pattern_color=(255, 255, 255, 22),
        badge_bg=(255, 255, 255), badge_fg=(33, 115, 70), badge_text="EXCEL EN 30 SECONDES", font="carlito",
        accent=(255, 255, 255), accent2=(200, 255, 210), accent3=(255, 230, 120), cap_style="pill", cap_box=(0, 60, 30, 200),
        cap_anim="slide", win_bar=(16, 80, 46), layout="laptop", entry="drop", result_style="stamp",
        cta_style="card", music="marimba", cta_bg=(16, 80, 46)),
    "bleu_nuit": dict(
        bg=("radial", (30, 50, 110), (5, 10, 35)), pattern="stars", pattern_color=(255, 255, 255, 120),
        badge_bg=(255, 196, 60), badge_fg=(10, 20, 50), badge_text="ASTUCE DU SOIR", font="serif",
        accent=(255, 196, 60), accent2=(140, 190, 255), accent3=(150, 240, 200), cap_style="plain", cap_anim="typewriter",
        win_bar=(20, 40, 95), sel=(255, 160, 0), res_fill=(255, 236, 179), res_txt=(150, 80, 0),
        layout="card", entry="zoom", result_style="glow", cta_style="pulse", music="lofi_nuit", cta_bg=(5, 10, 35),
        cta_btn=(255, 196, 60)),
    "soleil": dict(
        bg=("vgrad", (255, 183, 77), (244, 81, 30)), pattern="sunrays", pattern_color=(255, 255, 255, 30),
        badge_bg=(120, 30, 0), badge_fg=(255, 230, 160), badge_text="ASTUCE DU MATIN", font="poppins",
        cap_fg=(60, 20, 0), accent=(120, 30, 0), accent2=(0, 80, 160), accent3=(0, 110, 60),
        cap_style="pill", cap_box=(255, 255, 255, 225), cap_anim="slide",
        win_bar=(230, 81, 0), sel=(230, 81, 0), row1=(255, 236, 210), res_fill=(255, 224, 178), res_txt=(150, 50, 0),
        key_bg=(255, 255, 255), key_fg=(120, 30, 0), key_shadow=(180, 70, 20), path_bg=(120, 30, 0), path_fg=(255, 230, 160),
        layout="card", entry="drop", result_style="stamp", cta_style="card", music="rumba",
        cta_bg=(244, 81, 30), cta_btn=(120, 30, 0), sig_fg=(80, 25, 0, 230)),
    "violet": dict(
        bg=("vgrad", (88, 28, 135), (40, 10, 70)), pattern="stripes", pattern_color=(255, 255, 255, 16),
        badge_bg=(244, 114, 182), badge_fg=(50, 10, 60), badge_text="EXCEL • ASTUCE", font="poppins",
        accent=(244, 114, 182), accent2=(196, 181, 253), accent3=(134, 239, 172), cap_style="box", cap_box=(30, 5, 50, 190),
        cap_anim="fade", win_bar=(109, 40, 217), sel=(168, 85, 247), row1=(237, 233, 254), res_fill=(250, 232, 255),
        res_txt=(134, 25, 143), layout="banner", entry="slide_up", result_style="marker", cta_style="bar",
        music="percussions", cta_bg=(40, 10, 70), cta_btn=(244, 114, 182)),
    "degrade": dict(
        bg=("dgrad", (255, 94, 98), (118, 40, 180)), pattern=None,
        badge_bg=(255, 255, 255), badge_fg=(150, 40, 120), badge_text="ASTUCE EXCEL •", font="inter",
        accent=(255, 240, 120), accent2=(255, 255, 255), accent3=(170, 255, 220), cap_style="glow", cap_anim="slide",
        win_bar=(150, 40, 120), sel=(200, 40, 140), layout="card", entry="zoom", result_style="glow",
        cta_style="pulse", music="electro", cta_bg=(70, 20, 110), cta_btn=(255, 94, 98)),
    "papier": dict(
        bg=("vgrad", (250, 244, 228), (236, 226, 200)), pattern="graph", pattern_color=(90, 140, 200, 45),
        badge_bg=(200, 60, 40), badge_fg=(255, 250, 240), badge_text="Le carnet Excel", font="serif",
        cap_fg=(40, 35, 30), accent=(200, 60, 40), accent2=(30, 90, 170), accent3=(30, 120, 60),
        cap_style="underline", cap_anim="typewriter", win_bar=(80, 70, 60), sel=(200, 60, 40),
        key_shadow=(170, 160, 140), path_bg=(80, 70, 60), layout="classic", entry="drop", result_style="marker",
        cta_style="card", music="piano", cta_bg=(250, 244, 228), cta_btn=(200, 60, 40), sig_fg=(60, 50, 40, 220)),
    "terre": dict(
        bg=("vgrad", (110, 52, 20), (60, 25, 8)), pattern="kente", pattern_color=(255, 190, 60, 40),
        badge_bg=(255, 190, 60), badge_fg=(60, 25, 8), badge_text="ASTUCE EXCEL DU JOUR", font="poppins",
        accent=(255, 190, 60), accent2=(120, 220, 200), accent3=(190, 240, 120), cap_style="box", cap_box=(40, 15, 0, 190),
        cap_anim="slide", win_bar=(150, 70, 20), sel=(200, 100, 20), row1=(255, 240, 215), layout="laptop",
        entry="slide_up", result_style="stamp", cta_style="bar", music="likembe", cta_bg=(60, 25, 8),
        cta_btn=(255, 190, 60)),
}

def get_theme(name):
    th = dict(BASE); th.update(THEMES.get(name or "classique", {})); return th

# ---------------------------------------------------------------- utilitaires
def ease(t): t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3
def rgba(c, a=1.0):
    c = tuple(int(v) for v in c)
    return c[:3] + (int((c[3] if len(c) > 3 else 255) * a),)
def wrap(d, text, f, maxw):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for w in words:
            test = (cur + " " + w).strip()
            if d.textlength(test, font=f) <= maxw: cur = test
            else: lines.append(cur); cur = w
        lines.append(cur)
    return lines

TH = get_theme(None)
def safe(text):  # remplace les glyphes absents de la police du thème
    if DISPLAY == "poppins": text = text.replace("→", "»").replace("\u202f", "\u00a0")
    return text
def caption(d, text, y, size=64, color=None, alpha=1.0, box=True, prog=1.0):
    """Légende centrée. prog (0→1) sert à l'animation du thème (machine à écrire / glissement)."""
    text = safe(text)
    color = TH["cap_fg"] if color is None else color
    f = dfont(size)
    lines = wrap(d, text, f, W - 150)
    lh = int(size * 1.28)
    if alpha <= 0: return y + len(lines) * lh
    anim, style = TH["cap_anim"], (TH["cap_style"] if box else "bare")
    total = sum(len(l) for l in lines); shown = int(total * ease(prog) + 0.999) if anim == "typewriter" else 10 ** 6
    dx = int((1 - ease(prog)) * -120) if anim == "slide" else 0
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        x = (W - tw) / 2 + dx; yy = y + i * lh
        vis = ln[:max(0, shown)]; shown -= len(ln)
        if style == "box":
            d.rounded_rectangle([x - 22, yy - 8, x + tw + 22, yy + lh - 4], 18, fill=rgba(TH["cap_box"], alpha))
        elif style == "pill":
            d.rounded_rectangle([x - 30, yy - 6, x + tw + 30, yy + lh - 6], (lh - 2) // 2, fill=rgba(TH["cap_box"], alpha))
        elif style == "underline" and vis:
            uw = d.textlength(vis, font=f)
            d.rectangle([x, yy + lh - 22, x + uw, yy + lh - 10], fill=rgba(TH["accent"], 0.35 * alpha))
        c = rgba(color, alpha)
        if style in ("plain", "bare") and sum(color[:3]) > 380:
            d.text((x, yy), vis, font=f, fill=c, stroke_width=4, stroke_fill=(0, 0, 0, int(200 * alpha)))
        elif style == "glow":
            for r in (8, 5):
                d.text((x, yy), vis, font=f, fill=rgba(color, 0.18 * alpha), stroke_width=r, stroke_fill=rgba(color, 0.12 * alpha))
            d.text((x, yy), vis, font=f, fill=c)
        else:
            d.text((x, yy), vis, font=f, fill=c)
    return y + len(lines) * lh

def chips(d, items, y, kind="keys", alpha=1.0):
    """Touches du clavier (keys) ou chemin de menu (path), centrées, sur plusieurs lignes si besoin."""
    if kind == "keys": f, ph, pw, sep, gap = dfont(52), 104, 34, "+", 26
    else: f, ph, pw, sep, gap = dfont(34), 70, 22, "›", 16
    items = [safe(x) for x in items]
    sw = d.textlength(sep, font=f)
    widths = [d.textlength(it, font=f) + 2 * pw for it in items]
    rows, cur, curw = [], [], 0
    for i, w in enumerate(widths):
        add = w + (sw + 2 * gap if cur else 0)
        if cur and curw + add > W - 120: rows.append(cur); cur, curw = [], 0; add = w
        cur.append(i); curw += add
    rows.append(cur)
    for r in rows:
        tot = sum(widths[i] for i in r) + (len(r) - 1) * (sw + 2 * gap); x = (W - tot) / 2
        for j, i in enumerate(r):
            if j: d.text((x + gap, y + (ph - f.size) / 2 - 6), sep, font=f, fill=rgba(TH["cap_fg"], alpha)); x += sw + 2 * gap
            w = widths[i]
            if kind == "keys":
                d.rounded_rectangle([x, y + 10, x + w, y + ph + 10], 18, fill=rgba(TH["key_shadow"], alpha))
                d.rounded_rectangle([x, y, x + w, y + ph], 18, fill=rgba(TH["key_bg"], alpha), outline=rgba(TH["key_shadow"], alpha), width=3)
                d.text((x + pw, y + (ph - f.size) / 2 - 6), items[i], font=f, fill=rgba(TH["key_fg"], alpha))
            else:
                d.rounded_rectangle([x, y, x + w, y + ph], ph // 2, fill=rgba(TH["path_bg"], alpha))
                d.text((x + pw, y + (ph - f.size) / 2 - 5), items[i], font=f, fill=rgba(TH["path_fg"], alpha))
            x += w
        y += ph + 26
    return y

# ---------------------------------------------------------------- fonds
def build_background(th):
    kind = th["bg"][0]; c1, c2 = np.array(th["bg"][1], float), np.array(th["bg"][2], float)
    yy, xx = np.mgrid[0:H, 0:W]
    if kind == "radial":
        r = np.sqrt((xx - W / 2) ** 2 + (yy - H * 0.35) ** 2) / (H * 0.75); k = np.clip(r, 0, 1)
    elif kind == "dgrad":
        k = np.clip((xx / W * 0.45 + yy / H * 0.85) / 1.3, 0, 1)
    else:
        k = yy / (H - 1)
    arr = (c1[None, None, :] * (1 - k[..., None]) + c2[None, None, :] * k[..., None]).astype(np.uint8)
    bg = Image.fromarray(arr).convert("RGBA")
    p = th["pattern"]
    if p:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); pc = th["pattern_color"]
        rng = np.random.default_rng(7)
        if p == "dots":
            for y in range(20, H, 48):
                for x in range(20 + (24 if (y // 48) % 2 else 0), W, 48): d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=pc)
        elif p == "graph":
            for x in range(0, W, 36): d.line([x, 0, x, H], fill=pc, width=1 if x % 180 else 2)
            for y in range(0, H, 36): d.line([0, y, W, y], fill=pc, width=1 if y % 180 else 2)
        elif p == "cells":
            for x in range(0, W, 120): d.line([x, 0, x, H], fill=pc, width=2)
            for y in range(0, H, 50): d.line([0, y, W, y], fill=pc, width=2)
        elif p == "stripes":
            for x in range(-H, W, 70): d.line([x, H, x + H, 0], fill=pc, width=22)
        elif p == "stars":
            for _ in range(160):
                x, y = rng.integers(0, W), rng.integers(0, H); r = rng.choice([1, 1, 2, 3])
                d.ellipse([x - r, y - r, x + r, y + r], fill=pc[:3] + (int(rng.integers(40, pc[3] + 1)),))
        elif p == "neon_grid":
            hz_y = int(H * 0.62)
            for i in range(-12, 13):
                d.line([W / 2 + i * 40, hz_y, W / 2 + i * 260, H], fill=pc, width=2)
            for j in range(14):
                y = hz_y + int((H - hz_y) * (j / 14) ** 1.8); d.line([0, y, W, y], fill=pc, width=2)
        elif p == "sunrays":
            cx, cy = W / 2, -200
            for a in range(0, 180, 12):
                a0, a1 = math.radians(a), math.radians(a + 6); R = 3000
                d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=pc)
        elif p == "kente":
            for y in range(0, H, 160):
                d.rectangle([0, y, W, y + 18], fill=pc)
                for x in range(0, W, 80):
                    d.polygon([(x, y + 40), (x + 40, y + 80), (x + 80, y + 40), (x + 40, y + 120)], outline=pc, width=3)
        bg = Image.alpha_composite(bg, ov)
    return bg

# ---------------------------------------------------------------- musique originale (synthèse, libre de droits)
SR = 44100
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def tone(kind, f, dur):
    L = int(dur * SR); t = np.arange(L) / SR
    if kind == "pluck":   # guitare légère (type sebene)
        w = sum((0.6 ** k) * np.sin(2 * np.pi * f * (k + 1) * t) for k in range(5)); env = np.exp(-t * 7)
    elif kind == "marimba":
        w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 30); env = np.exp(-t * 9)
    elif kind == "likembe":  # lamellophone : partiel inharmonique + petit « buzz »
        w = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 20) + 0.08 * np.sign(np.sin(2 * np.pi * f * t))
        env = np.exp(-t * 5)
    elif kind == "piano":
        w = sum((0.5 ** k) * np.sin(2 * np.pi * f * (k + 1) * t) for k in range(6)); env = np.exp(-t * 2.2) * np.minimum(1, t / 0.005)
    elif kind == "rhodes":
        w = np.sin(2 * np.pi * f * t + 0.8 * np.sin(2 * np.pi * f * t) * np.exp(-t * 3)); env = np.exp(-t * 1.8) * np.minimum(1, t / 0.01)
    elif kind == "saw":
        w = sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, 9)); env = np.exp(-t * 4) * np.minimum(1, t / 0.005)
    elif kind == "pad":
        w = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 1.005 * t) + 0.2 * np.sin(2 * np.pi * f * 2 * t)
        env = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.4)
    else:
        w = np.sin(2 * np.pi * f * t); env = np.exp(-t * 3)
    return w * env
def drum(kind, rng):
    if kind == "kick":
        L = int(0.25 * SR); t = np.arange(L) / SR; return np.exp(-t * 18) * np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 30)) * t)
    if kind == "snare":
        L = int(0.18 * SR); t = np.arange(L) / SR; return np.exp(-t * 22) * (0.7 * rng.standard_normal(L) + 0.5 * np.sin(2 * np.pi * 190 * t))
    if kind == "clap":
        L = int(0.2 * SR); t = np.arange(L) / SR; n = rng.standard_normal(L); return n * (np.exp(-t * 30) + 0.5 * np.exp(-((t - 0.012) ** 2) / 1e-5))
    if kind == "hat":
        L = int(0.05 * SR); n = np.diff(rng.standard_normal(L + 1)); return 0.5 * n * np.exp(-np.arange(L) / SR * 90)
    if kind == "shaker":
        L = int(0.07 * SR); n = np.diff(rng.standard_normal(L + 1)); t = np.arange(L) / SR; return 0.35 * n * np.minimum(1, t / 0.01) * np.exp(-t * 40)
    if kind in ("conga", "conga_hi"):
        f0 = 200 if kind == "conga" else 300; L = int(0.2 * SR); t = np.arange(L) / SR
        return np.exp(-t * 16) * np.sin(2 * np.pi * (f0 + 60 * np.exp(-t * 40)) * t)
    if kind == "bell":
        L = int(0.3 * SR); t = np.arange(L) / SR; return 0.5 * np.exp(-t * 10) * (np.sin(2 * np.pi * 900 * t) + 0.6 * np.sin(2 * np.pi * 1350 * t))
    return np.zeros(1)
def put(buf, start_s, sig, amp):
    s0 = int(start_s * SR)
    if s0 >= len(buf): return
    L = min(len(sig), len(buf) - s0); buf[s0:s0 + L] += amp * sig[:L]

def music_lofi(T, rng, night=False):
    n = int(T * SR); tt = np.arange(n) / SR; audio = np.zeros(n)
    bpm = 76 if night else 88; beat = 60 / bpm; bar = beat * 4
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]] if not night else [[50, 53, 57, 60], [55, 58, 62, 65], [48, 52, 55, 59], [53, 57, 60, 64]]
    for b in range(int(T / bar) + 1):
        chord = prog[b % 4]; st = int(b * bar * SR); en = min(n, int((b + 1) * bar * SR))
        if st >= n: break
        if night:
            for m in chord: put(audio, b * bar, tone("rhodes", hz(m), bar), 0.07)
            put(audio, b * bar, tone("sine", hz(chord[0] - 12), bar), 0.12)
            for j in (0, 3, 5):
                put(audio, b * bar + j * beat / 2, tone("piano", hz(chord[(j + b) % len(chord)] + 12), 1.0), 0.04)
            continue
        seg = tt[st:en] - b * bar
        env = np.minimum(1, seg / 0.3) * np.exp(-seg * 0.35)
        for m in chord:
            audio[st:en] += 0.08 * env * (np.sin(2 * np.pi * hz(m) * seg) + 0.3 * np.sin(2 * np.pi * hz(m) * 2 * seg))
        audio[st:en] += 0.12 * env * np.sin(2 * np.pi * hz(chord[0] - 12) * seg)
        for j in range(8):
            a0 = st + int(j * beat / 2 * SR); a1 = min(en, a0 + int(beat / 2 * SR))
            if a0 >= en: break
            sg = tt[a0:a1] - tt[a0]; m = chord[j % 3] + 12
            audio[a0:a1] += 0.05 * np.exp(-sg * 6) * np.sin(2 * np.pi * hz(m) * sg)
    for k in range(int(T / beat)):
        if k % 2 == 0: put(audio, k * beat, drum("kick", rng), 0.35)
        elif night: put(audio, k * beat, drum("snare", rng), 0.08)
        put(audio, k * beat + beat / 2, drum("hat", rng), 0.08)
    if night: audio += 0.004 * rng.standard_normal(n) * (rng.random(n) > 0.9993) * 30  # craquements de vinyle
    return audio

def music_rumba(T, rng):  # rumba / sebene léger, majeur, guitare en arpèges
    n = int(T * SR); audio = np.zeros(n); bpm = 114; b = 60 / bpm; bar = 4 * b
    prog = [[60, 64, 67], [65, 69, 72], [60, 64, 67], [67, 71, 74]]  # C F C G
    for i in range(int(T / bar) + 1):
        ch = prog[i % 4]; t0 = i * bar
        for j in range(16):
            m = ch[[0, 1, 2, 1, 2, 0, 1, 2][j % 8]] + 12 + (12 if j in (6, 14) else 0)
            put(audio, t0 + j * b / 4, tone("pluck", hz(m), 0.35), 0.05 if j % 2 else 0.07)
        for (off, m) in ((0, ch[0] - 24), (1.5, ch[0] - 24), (2.5, ch[2] - 24), (3.5, ch[1] - 24)):
            put(audio, t0 + off * b, tone("sine", hz(m), 0.45), 0.22)
    for k in range(int(T / b) * 4):
        put(audio, k * b / 4, drum("shaker", rng), 0.10 if k % 2 else 0.05)
    for k in range(int(T / b)):
        if k % 2 == 0: put(audio, k * b, drum("kick", rng), 0.28)
        put(audio, k * b + b / 2, drum("conga_hi" if k % 2 else "conga", rng), 0.10)
        if k % 4 == 3: put(audio, k * b + 0.75 * b, drum("conga", rng), 0.09)
    return audio

def music_electro(T, rng):
    n = int(T * SR); audio = np.zeros(n); bpm = 124; b = 60 / bpm; bar = 4 * b
    prog = [50, 46, 53, 48]  # D Bb F C
    for i in range(int(T / bar) + 1):
        r = prog[i % 4]; t0 = i * bar
        for j in range(8):
            put(audio, t0 + j * b / 2 + b / 4, tone("saw", hz(r - 12), 0.2), 0.10)
        minor = r in (50,)
        tri = [r + 12, r + 15 if minor else r + 16, r + 19]
        for j in range(16):
            if j % 3 != 2: put(audio, t0 + j * b / 4, tone("pluck", hz(tri[j % 3] + 12), 0.15), 0.035)
        put(audio, t0, tone("pad", hz(r + 12), bar), 0.04)
    for k in range(int(T / b)):
        put(audio, k * b, drum("kick", rng), 0.40)
        if k % 2: put(audio, k * b, drum("clap", rng), 0.09)
        put(audio, k * b + b / 2, drum("hat", rng), 0.12)
    return audio

def music_piano(T, rng):
    n = int(T * SR); audio = np.zeros(n); bpm = 72; b = 60 / bpm; bar = 4 * b
    prog = [[48, 55, 59, 64], [45, 52, 55, 60], [41, 48, 52, 57], [43, 50, 55, 59]]  # Cmaj7 Am7 Fmaj7 G
    mel = [76, 74, 72, 71, 72, 67, 69, 71]
    for i in range(int(T / bar) + 1):
        ch = prog[i % 4]; t0 = i * bar
        put(audio, t0, tone("piano", hz(ch[0] - 12), bar), 0.10)
        for j, m in enumerate(ch[1:]): put(audio, t0 + 0.02 * j, tone("piano", hz(m), bar), 0.05)
        for j in range(2):
            put(audio, t0 + (j * 2 + 1) * b, tone("piano", hz(mel[(2 * i + j) % len(mel)]), 1.5), 0.05)
    return audio

def music_mallet(T, rng, kind="marimba"):  # marimba ou likembe, pentatonique
    n = int(T * SR); audio = np.zeros(n); bpm = 100 if kind == "marimba" else 108; b = 60 / bpm; bar = 4 * b
    penta = [60, 62, 64, 67, 69, 72, 74, 76]
    pats = [[0, 2, 4, 2, 5, 4, 2, 3], [1, 3, 5, 3, 6, 5, 3, 4], [0, 2, 4, 5, 7, 5, 4, 2], [3, 4, 2, 0, 1, 2, 4, 3]]
    roots = [48, 45, 41, 43]
    for i in range(int(T / bar) + 1):
        t0 = i * bar; p = pats[i % 4]
        for j, idx in enumerate(p):
            put(audio, t0 + j * b / 2, tone(kind, hz(penta[idx] + (0 if kind == "marimba" else -12)), 0.6), 0.10)
        put(audio, t0, tone("sine", hz(roots[i % 4]), 1.2), 0.18); put(audio, t0 + 2.5 * b, tone("sine", hz(roots[i % 4]), 0.8), 0.14)
    for k in range(int(T / b) * 2):
        put(audio, k * b / 2, drum("shaker", rng), 0.07)
    for k in range(int(T / b)):
        if k % 4 in (0, 2): put(audio, k * b, drum("kick", rng), 0.22)
        if kind == "likembe" and k % 4 == 3: put(audio, k * b + b / 2, drum("conga_hi", rng), 0.08)
    return audio

def music_percussions(T, rng):
    n = int(T * SR); audio = np.zeros(n); bpm = 96; b = 60 / bpm; bar = 4 * b
    for i in range(int(T / bar) + 1):
        t0 = i * bar
        put(audio, t0, tone("pad", hz(43), bar), 0.10); put(audio, t0, tone("pad", hz(50), bar), 0.05)
        for off in (0, 1.5, 2, 3, 3.5): put(audio, t0 + off * b, drum("conga", rng), 0.16)
        for off in (0.5, 1, 2.5, 2.75): put(audio, t0 + off * b, drum("conga_hi", rng), 0.12)
        for off in (0, 1, 1.5, 2.5, 3): put(audio, t0 + off * b, drum("bell", rng), 0.05)
    for k in range(int(T / b)):
        put(audio, k * b, drum("kick", rng), 0.30 if k % 2 == 0 else 0.15)
        put(audio, k * b + b / 2, drum("shaker", rng), 0.09)
    return audio

MUSIC = {
    "lofi": lambda T, r: music_lofi(T, r), "lofi_nuit": lambda T, r: music_lofi(T, r, night=True),
    "rumba": music_rumba, "electro": music_electro, "piano": music_piano,
    "marimba": lambda T, r: music_mallet(T, r, "marimba"), "likembe": lambda T, r: music_mallet(T, r, "likembe"),
    "percussions": music_percussions,
}

# ---------------------------------------------------------------- rendu
def main(spec_path, out_path):
    global TH, DISPLAY
    s = json.load(open(spec_path, encoding="utf-8"))
    TH = get_theme(s.get("theme")); DISPLAY = TH["font"]
    layout = s.get("layout", TH["layout"]); cta_style = s.get("cta_style", TH["cta_style"])
    mode = s.get("mode", "formula")
    headers, rows = s["headers"], [list(r) for r in s["rows"]]
    ncols = len(headers)
    T = s.get("duration", 30)
    t_hook, t_q, t_type, t_res, t_exp, t_cta = 0, 3.5, 7.5, 15.5, 18.5, 25.5
    formula = s.get("formula", "")
    t_hl = t_res if s.get("highlight_at") == "result" else t_q
    bg = build_background(TH)

    # géométrie selon la disposition
    wx, ww = 50, W - 100
    wy = {"classic": 560, "banner": 590, "card": 600, "laptop": 620}.get(layout, 560)
    if layout in ("card", "laptop"): wx, ww = 70, W - 140
    rowh, rown_w = 64, 60
    colw = [(ww - rown_w) * c for c in s.get("col_ratio", [1 / ncols] * ncols)]
    nrows_total = len(rows) + (3 if mode == "formula" else 1)
    grid_top = wy + 80 + 70
    wh = 80 + 70 + rowh * (nrows_total + 1) + 10
    res_row = len(rows) + 3
    res_col = s.get("result_col", ncols - 1)
    hl_col, hl_val, sum_col = s.get("criteria_col"), s.get("criteria_value"), s.get("sum_col")
    crit = s.get("criteria") or ([[hl_col, hl_val]] if hl_col is not None else [])
    crit_cols = {c for c, _ in crit}
    sum_cols = set(sum_col) if isinstance(sum_col, list) else {sum_col}
    steps = s.get("steps", []); fills = s.get("fills", []); paints = s.get("paints", []); selects = s.get("select", [])

    def as_date(v):
        p = str(v).strip().split("/")
        if len(p) == 3 and all(x.isdigit() for x in p): return (int(p[2]), int(p[1]), int(p[0]))
        return None
    def match(cell, vv):
        if isinstance(vv, str):
            if vv == "<>": return str(cell).strip() != ""
            for op in (">=", "<=", "<>", ">", "<"):
                if vv.startswith(op):
                    da, db = as_date(cell), as_date(vv[len(op):])
                    if da and db: return {">=": da >= db, "<=": da <= db, "<>": da != db, ">": da > db, "<": da < db}[op]
                    try:
                        a = float(str(cell).replace(" ", "").replace(" ", "").replace(",", "."))
                        b = float(vv[len(op):].replace(" ", "").replace(",", "."))
                    except ValueError: return False
                    return {">=": a >= b, "<=": a <= b, "<>": a != b, ">": a > b, "<": a < b}[op]
        return cell == vv
    def cell_xy(col, row):
        x = wx + rown_w + sum(colw[:col]); y = grid_top + row * rowh
        return x, y, x + colw[col], y + rowh

    fcell, fbold, fsmall = font(30), font(30, True), font(24)
    _tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    fx_texts = [formula] + [st.get("fx", "") for st in steps]
    fsz = 34
    while fsz > 20 and max(_tmp.textlength(x + "|", font=font(fsz, mono=True)) for x in fx_texts) > ww - 85 - 30: fsz -= 1
    ffx = font(fsz, mono=True)

    # ombre portée (dispositions carte / ordinateur)
    shadow = None
    if layout in ("card", "laptop"):
        pad = 40 if layout == "laptop" else 0
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle([wx - pad + 10, wy - pad + 30, wx + ww + pad + 10, wy + wh + pad + 30], 30, fill=(0, 0, 0, 120))
        shadow = sh.filter(ImageFilter.GaussianBlur(24))

    # valeurs de cellules dans le temps (mode étapes)
    def cell_value(r_excel, c, t):
        v = None; ta = None
        for fl in fills:
            for k, (rr, cc, val) in enumerate(fl["cells"]):
                at = fl["at"] + k * fl.get("stagger", 0)
                if rr == r_excel and cc == c and t >= at: v, ta = val, at
        if v is None: return str(rows[r_excel - 2][c]), None
        return str(v), ta
    def paint_of(r_excel, c, t):
        res = None
        for p in paints:
            cols = p.get("cols", list(range(ncols)))
            if c not in cols: continue
            for k, rr in enumerate(p["rows"]):
                at = p["at"] + k * p.get("stagger", 0)
                if rr == r_excel and t >= at: res = (p, ease((t - at) / 0.4))
        return res
    def current_step(t):
        cur = None
        for st in steps:
            if t >= st["at"]: cur = st
        return cur

    def draw_window(t):
        L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
        TL = Image.new("RGBA", (W, H), (0, 0, 0, 0)); td = ImageDraw.Draw(TL)  # calque translucide (fusionné à la fin)
        if layout == "laptop":
            d.rounded_rectangle([wx - 34, wy - 40, wx + ww + 34, wy + wh + 34], 34, fill=(28, 28, 32))
            d.ellipse([W / 2 - 6, wy - 26, W / 2 + 6, wy - 14], fill=(70, 70, 80))
            by = wy + wh + 34
            d.polygon([(wx - 70, by), (wx + ww + 70, by), (wx + ww + 120, by + 46), (wx - 120, by + 46)], fill=(70, 72, 80))
            d.rounded_rectangle([W / 2 - 90, by + 4, W / 2 + 90, by + 16], 6, fill=(50, 52, 58))
        d.rounded_rectangle([wx, wy, wx + ww, wy + wh], 20, fill=TH["win_bg"])
        d.rounded_rectangle([wx, wy, wx + ww, wy + 80], 20, fill=TH["win_bar"])
        d.rectangle([wx, wy + 60, wx + ww, wy + 80], fill=TH["win_bar"])
        for i, cdot in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)] if layout in ("laptop", "card") else []):
            d.ellipse([wx + ww - 150 + i * 42, wy + 28, wx + ww - 124 + i * 42, wy + 54], fill=cdot)
        d.text((wx + 30, wy + 20), s.get("file", "Ventes.xlsx") + " - Excel", font=font(32, True), fill=TH["win_bar_fg"])
        fy = wy + 80
        d.rectangle([wx + 10, fy + 10, wx + ww - 10, fy + 60], outline=TH["grid"], width=2)
        d.text((wx + 25, fy + 17), "fx", font=font(30, True), fill=(110, 110, 110))
        typed, cursor = "", ""
        if mode == "formula":
            if t >= t_type:
                k = int(min(len(formula), (t - t_type) / 6.0 * len(formula) + 1)); typed = formula[:k]
            cursor = "|" if (t_type <= t < t_res and int(t * 3) % 2 == 0) else ""
        else:
            st = current_step(t)
            if st and st.get("fx"):
                dur = st.get("fx_dur", 2.5); k = int(min(len(st["fx"]), (t - st["at"]) / dur * len(st["fx"]) + 1))
                typed = st["fx"][:k]; cursor = "|" if (k < len(st["fx"]) and int(t * 3) % 2 == 0) else ""
            elif st is None or not st.get("fx"):
                # affiche le contenu de la cellule sélectionnée
                sel = None
                for sl in selects:
                    if t >= sl["at"] and "cell" in sl: sel = sl["cell"]
                if sel and sel[0] >= 2: typed = cell_value(sel[0], sel[1], t)[0]
        d.text((wx + 85, fy + 16 + (34 - fsz) // 2), typed + cursor, font=ffx, fill=TH["fx_txt"])
        for r in range(nrows_total + 1):
            for c in range(ncols):
                x0, y0, x1, y1 = cell_xy(c, r)
                fill = TH["hdr"] if r == 0 else TH["cell"]
                if r == 1: fill = TH["row1"]
                data_i = r - 2; tcol = TH["txt"]
                if mode == "formula" and t_hl <= t < t_exp + 6 and crit and 0 <= data_i < len(rows):
                    if all(match(rows[data_i][cc], vv) for cc, vv in crit):
                        a = ease((t - t_hl) / 0.6)
                        if c in crit_cols: fill = tuple(int(b0 + (h - b0) * a) for b0, h in zip(TH["cell"], TH["crit_hl"]))
                        if c in sum_cols and t >= t_exp: fill = TH["sum_hl"]
                if mode == "steps" and 0 <= data_i < len(rows):
                    pt = paint_of(r, c, t)
                    if pt:
                        p, a = pt; pf = tuple(p.get("fill", TH["crit_hl"]))
                        fill = tuple(int(b0 + (h - b0) * a) for b0, h in zip(TH["cell"], pf))
                        if p.get("color"): tcol = tuple(p["color"])
                d.rectangle([x0, y0, x1, y1], fill=fill, outline=TH["grid"])
                if r == 0:
                    Lt = chr(65 + c); d.text((x0 + (x1 - x0 - d.textlength(Lt, font=fsmall)) / 2, y0 + 18), Lt, font=fsmall, fill=TH["hdr_fg"])
                elif r == 1:
                    d.text((x0 + 10, y0 + 15), headers[c], font=fbold, fill=TH["txt"])
                elif 0 <= data_i < len(rows):
                    if mode == "steps":
                        v, ta = cell_value(r, c, t)
                        if ta is not None and t - ta < 0.35:  # apparition
                            a = ease((t - ta) / 0.35); tcol = tuple(int(cv * a + bv * (1 - a)) for cv, bv in zip(tcol, fill))
                    else:
                        v = str(rows[data_i][c])
                    if c in s.get("right_cols", []): d.text((x1 - 12 - d.textlength(v, font=fcell), y0 + 15), v, font=fcell, fill=tcol)
                    else: d.text((x0 + 10, y0 + 15), v, font=fcell, fill=tcol)
            if r > 0:
                y0 = grid_top + r * rowh
                d.rectangle([wx, y0, wx + rown_w, y0 + rowh], fill=TH["hdr"], outline=TH["grid"])
                num = str(r); d.text((wx + (rown_w - d.textlength(num, font=fsmall)) / 2, y0 + 18), num, font=fsmall, fill=TH["hdr_fg"])
            else:
                d.rectangle([wx, grid_top, wx + rown_w, grid_top + rowh], fill=TH["hdr"], outline=TH["grid"])
        if mode == "formula":
            lab_c = s.get("label_col", 0)
            x0, y0, x1, y1 = cell_xy(lab_c, res_row)
            d.text((x0 + 10, y0 + 15), s.get("result_label", "Total"), font=fbold, fill=TH["txt"])
            x0, y0, x1, y1 = cell_xy(res_col, res_row)
            if t >= t_type: d.rectangle([x0, y0, x1, y1], outline=TH["sel"], width=5)
            if t >= t_res:
                a = ease((t - t_res) / 0.5); rs = TH["result_style"]
                if rs == "marker":
                    d.rectangle([x0 + 3, y0 + 3, x0 + 3 + (x1 - x0 - 6) * a, y1 - 3], fill=TH["res_fill"])
                else:
                    d.rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], fill=TH["res_fill"])
                if rs == "glow":
                    g = 0.5 + 0.5 * math.sin((t - t_res) * 5)
                    for k in range(3): td.rectangle([x0 - 6 - 4 * k, y0 - 6 - 4 * k, x1 + 6 + 4 * k, y1 + 6 + 4 * k], outline=rgba(TH["sel"], (0.5 - 0.15 * k) * g), width=3)
                fr = font(int(30 + 10 * (1 - a) * math.sin(a * math.pi)), True)
                v = s["result"]; d.text((x1 - 14 - d.textlength(v, font=fr), y0 + 13), v, font=fr, fill=TH["res_txt"])
                if rs == "stamp" and t < t_exp:
                    sf = dfont(44); txt = "= " + v; tw = d.textlength(txt, font=sf); sx = min(W - 70 - tw - 40, x1 - tw - 40); sy = y0 - 110 + int((1 - a) * -40)
                    d.rounded_rectangle([sx, sy, sx + tw + 40, sy + 78], 39, fill=rgba(TH["sel"], a))
                    d.polygon([(x1 - 80, sy + 78), (x1 - 50, sy + 78), (x1 - 65, sy + 100)], fill=rgba(TH["sel"], a))
                    d.text((sx + 20, sy + 12), txt, font=sf, fill=(255, 255, 255, int(255 * a)))
            elif t >= t_type:
                v = typed[-14:]; d.text((x0 + 8, y0 + 17), v, font=font(24, mono=True), fill=TH["txt"])
        else:
            for sl in selects:  # sélection (cellule ou plage)
                end = sl.get("until", 1e9)
                if not (sl["at"] <= t < end): continue
                if "cell" in sl: r1, c1 = sl["cell"]; r2, c2 = r1, c1
                else: r1, c1, r2, c2 = sl["range"]
                if sl is not [x for x in selects if x["at"] <= t][-1]: continue
                x0, y0, _, _ = cell_xy(c1, r1); _, _, x1, y1 = cell_xy(c2, r2)
                if "range" in sl:
                    a = ease((t - sl["at"]) / 0.6); x1 = x0 + (x1 - x0) * a; y1 = y0 + (y1 - y0) * a
                    td.rectangle([x0, y0, x1, y1], fill=rgba(TH["sel"], 0.16))
                d.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], outline=TH["sel"], width=5)
                d.rectangle([x1 - 7, y1 - 7, x1 + 7, y1 + 7], fill=TH["sel"])
            for dd in s.get("dropdowns", []):  # liste déroulante ouverte sous une cellule
                if dd.get("arrow_from") is not None and t >= dd["arrow_from"]:
                    for rr in dd.get("arrow_rows", [dd["cell"][0]]):
                        ax0, ay0, ax1, ay1 = cell_xy(dd["cell"][1], rr)
                        d.rectangle([ax1 - 40, ay0 + 6, ax1 - 6, ay1 - 6], fill=TH["hdr"], outline=TH["grid"])
                        d.polygon([(ax1 - 33, ay0 + 26), (ax1 - 13, ay0 + 26), (ax1 - 23, ay0 + 38)], fill=TH["hdr_fg"])
                if not (dd["at"] <= t < dd.get("until", dd["at"] + 1.5)): continue
                rr, cc = dd["cell"]; x0, y0, x1, y1 = cell_xy(cc, rr)
                a = ease((t - dd["at"]) / 0.3); items = dd["items"]; ih = 58
                bh = int(len(items) * ih * a) + 8
                d.rectangle([x0 + 6, y1 + 8, x1 + 8, y1 + 10 + bh], fill=TH["key_shadow"])
                d.rectangle([x0, y1, x1, y1 + bh], fill=TH["cell"], outline=TH["sel"], width=3)
                pick = dd.get("pick", 0); hov = t >= dd["at"] + dd.get("hover_after", 0.6)
                for k, it in enumerate(items):
                    iy = y1 + 4 + k * ih
                    if iy + ih > y1 + bh: break
                    if hov and k == pick: d.rectangle([x0 + 4, iy, x1 - 4, iy + ih - 2], fill=TH["sel"])
                    d.text((x0 + 14, iy + 12), it, font=fcell, fill=(255, 255, 255) if (hov and k == pick) else TH["txt"])
        return Image.alpha_composite(L, TL)

    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-pix_fmt", "yuv420p", "-crf", "20", "silent.mp4"], stdin=subprocess.PIPE)
    explain_cols = {"yellow": TH["accent"], "blue": TH["accent2"], "green": TH["accent3"], "white": TH["cap_fg"]}
    cap_y = 200 if layout != "card" else 210
    # taille des explications : réduite automatiquement pour ne jamais chevaucher la fenêtre
    top_win = wy - (50 if layout == "laptop" else 25)
    exp_size = 44
    while exp_size > 30:
        hh = sum(len(wrap(_tmp, safe(txt), dfont(exp_size), W - 150)) * int(exp_size * 1.28) + 8 for txt, _ in s["explain"])
        if cap_y + hh <= top_win: break
        exp_size -= 2
    for fi in range(int(T * FPS)):
        t = fi / FPS
        im = bg.copy()
        # fenêtre + animation d'entrée
        win = draw_window(t); k = ease(t / 0.8); entry = TH["entry"]
        if shadow is not None and k >= 0.999: im = Image.alpha_composite(im, shadow)
        if k < 1:
            if entry == "zoom":
                sc = 0.6 + 0.4 * k; cx, cy = W / 2, wy + wh / 2
                ws = win.resize((int(W * sc), int(H * sc)), Image.BILINEAR)
                tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0)); tmp.paste(ws, (int(cx - cx * sc), int(cy - cy * sc)))
                win = tmp
            elif entry == "fade":
                win.putalpha(win.getchannel("A").point(lambda v: int(v * k)))
            else:
                oy = int((1 - k) * (300 if entry == "slide_up" else -500))
                tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0)); tmp.paste(win, (0, oy)); win = tmp
        im = Image.alpha_composite(im, win)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        # en-tête
        bt = s.get("badge", TH["badge_text"]); bfont = dfont(44)
        if layout == "banner":
            d.rectangle([0, 0, W, 520], fill=rgba(TH["win_bar"], 0.92)); d.rectangle([0, 520, W, 532], fill=TH["badge_bg"])
            d.text(((W - d.textlength(bt, font=bfont)) / 2, 70), bt, font=bfont, fill=TH["win_bar_fg"] if TH["win_bar_fg"] != TH["win_bar"] else (255, 255, 255))
        elif layout == "card":
            tw = d.textlength(bt, font=dfont(38)); d.rounded_rectangle([60, 80, 60 + tw + 60, 146], 33, fill=TH["badge_bg"])
            d.text((90, 88), bt, font=dfont(38), fill=TH["badge_fg"])
        else:
            tw = d.textlength(bt, font=bfont); d.rounded_rectangle([W / 2 - tw / 2 - 50, 70, W / 2 + tw / 2 + 50, 150], 40, fill=TH["badge_bg"])
            d.text(((W - tw) / 2, 82), bt, font=bfont, fill=TH["badge_fg"])
        # légendes
        if t < t_q:
            caption(d, s["hook"], cap_y, 70, TH["accent"], ease(t / 0.4), prog=t / 1.2)
        elif t < t_type:
            caption(d, s["question"], cap_y, 60, TH["cap_fg"], ease((t - t_q) / 0.4), prog=(t - t_q) / 1.2)
        elif t < t_res:
            if mode == "steps" and current_step(t):
                st = current_step(t); a = ease((t - st["at"]) / 0.4)
                yy = caption(d, st["text"], cap_y, 54, TH["cap_fg"], a, prog=(t - st["at"]) / 0.9)
                if st.get("keys"): chips(d, st["keys"], yy + 24, "keys", a)
                elif st.get("path"): chips(d, st["path"], yy + 20, "path", a)
            else:
                caption(d, s.get("typing_caption", "Tape cette formule :"), cap_y, 60, TH["cap_fg"], 1, prog=(t - t_type) / 1.0)
        elif t < t_exp:
            caption(d, s.get("result_caption", "Et voilà ! Résultat instantané"), cap_y, 64, TH["accent"], ease((t - t_res) / 0.4), prog=(t - t_res) / 1.0)
        elif t < t_cta:
            yy = cap_y
            for i, (txt, col) in enumerate(s["explain"]):
                a = ease((t - t_exp - i * 1.4) / 0.5)
                yy = caption(d, txt, yy, exp_size, explain_cols.get(col, TH["cap_fg"]), a, prog=(t - t_exp - i * 1.4) / 0.8) + 8 if a > 0 else yy + 70
        else:
            a = ease((t - t_cta) / 0.5)
            im = Image.alpha_composite(im, ov)
            ov = Image.new("RGBA", (W, H), rgba(TH["cta_bg"], 0.94 * a)); d = ImageDraw.Draw(ov)
            draw_cta(d, s, cta_style, t - t_cta, a)
        # signature
        sig = "Ingénieur Van MUFWAR"; fs = dfont(34)
        sx = (W - d.textlength(sig, font=fs)) / 2
        if TH["sig_style"] == "glow": d.text((sx, H - 200), sig, font=fs, fill=rgba(TH["sig_fg"], 0.3), stroke_width=5, stroke_fill=rgba(TH["sig_fg"], 0.15))
        d.text((sx, H - 200), sig, font=fs, fill=TH["sig_fg"])
        im = Image.alpha_composite(im, ov).convert("RGB")
        proc.stdin.write(im.tobytes())
    proc.stdin.close(); proc.wait()

    # musique
    rng = np.random.default_rng(1)
    audio = MUSIC.get(s.get("music", TH["music"]), MUSIC["lofi"])(T, rng)
    n = int(T * SR); audio = np.resize(audio, n) if len(audio) != n else audio
    fade = np.ones(n); fl = int(1.5 * SR); fade[:fl] = np.linspace(0, 1, fl); fade[-fl:] = np.linspace(1, 0, fl)
    audio = audio * fade; audio = audio / (np.max(np.abs(audio)) + 1e-9) * 0.5
    vpath = s.get("voice")
    if vpath:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vpath = vpath if os.path.isabs(vpath) else os.path.join(root, vpath)
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", vpath, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
        v = np.frombuffer(raw, np.int16).astype(float) / 32768
        v = v / (np.max(np.abs(v)) + 1e-9) * 0.9
        v0 = int((t_cta + s.get("voice_delay", 0.4)) * SR); v1 = min(n, v0 + len(v))
        duck = np.ones(n); r = int(0.25 * SR)
        duck[max(0, v0 - r):v0] = np.linspace(1, 0.3, v0 - max(0, v0 - r)); duck[v0:v1] = 0.3
        e2 = min(n, v1 + r); duck[v1:e2] = np.linspace(0.3, 1, e2 - v1)
        audio = audio * duck; audio[v0:v1] += v[:v1 - v0]
        audio = np.clip(audio, -0.98, 0.98)
    pcm = (audio * 32767).astype(np.int16)
    with wave.open("music.wav", "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "silent.mp4", "-i", "music.wav", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path], check=True)
    for f in ("silent.mp4", "music.wav"):
        try: os.remove(f)
        except OSError: pass

def draw_cta(d, s, style, dt, a):
    cta = s.get("cta", "Abonne-toi pour ne rater aucune astuce !")
    nxt = s.get("next", "Prochaine astuce demain à 6h")
    q = s.get("comment_cta", "Quelle formule veux-tu demain ?\nÉcris-la en commentaire !")
    p = 1 + 0.06 * math.sin(dt * 6)
    if style == "card":
        cy0, cy1 = 520, 1470
        d.rounded_rectangle([90, cy0, W - 90, cy1], 46, fill=(255, 255, 255, int(245 * a)))
        d.ellipse([W / 2 - 85, cy0 + 50, W / 2 + 85, cy0 + 220], fill=rgba(TH["cta_btn"], a))
        f = dfont(90); d.text((W / 2 - d.textlength("V", font=f) / 2, cy0 + 72), "V", font=f, fill=(255, 255, 255, int(255 * a)))
        y = cy0 + 250
        for txt, sz, col in ((cta, 58, (30, 30, 30)), ("@bleuddymufwar", 56, TH["cta_btn"]), (nxt, 40, (90, 90, 90))):
            f = dfont(sz)
            for ln in wrap(d, txt, f, W - 280):
                d.text((W / 2 - d.textlength(ln, font=f) / 2, y), ln, font=f, fill=rgba(col, a)); y += int(sz * 1.25)
            y += 18
        bw, bh = 400 * p, 100 * p; by = y + 70
        d.rounded_rectangle([W / 2 - bw / 2, by - bh / 2, W / 2 + bw / 2, by + bh / 2], 50, fill=rgba(TH["cta_btn"], a))
        fb = dfont(int(46 * p)); tx = "Suivre"; d.text((W / 2 - d.textlength(tx, font=fb) / 2, by - 30 * p), tx, font=fb, fill=(255, 255, 255, int(255 * a)))
        if q:
            yq = by + 90; f = dfont(38)
            for ln in wrap(d, q, f, W - 280):
                if yq > cy1 - 50: break
                d.text((W / 2 - d.textlength(ln, font=f) / 2, yq), ln, font=f, fill=rgba((60, 60, 60), a)); yq += 48
    elif style == "bar":
        yy = caption(d, cta, 560, 70, TH["accent"], a, box=False)
        sl = ease(dt / 0.6); bx = -W + (W) * sl
        d.rectangle([bx, yy + 50, bx + W, yy + 200], fill=rgba(TH["cta_btn"], a))
        f = dfont(70); hnd = "@bleuddymufwar"
        d.text((bx + (W - d.textlength(hnd, font=f)) / 2, yy + 82), hnd, font=f, fill=(255, 255, 255, int(255 * a)))
        y2 = caption(d, nxt, yy + 250, 46, TH["cap_fg"] if sum(TH["cta_bg"][:3]) < 300 else (30, 30, 30), a, box=False)
        bw, bh = 420 * p, 110 * p; by = y2 + 110
        d.rounded_rectangle([W / 2 - bw / 2, by - bh / 2, W / 2 + bw / 2, by + bh / 2], 55, outline=(255, 255, 255, int(255 * a)), width=6)
        fb = dfont(int(50 * p)); tx = "+ S'abonner"
        d.text((W / 2 - d.textlength(tx, font=fb) / 2, by - 32 * p), tx, font=fb, fill=(255, 255, 255, int(255 * a)))
        if q: caption(d, q, by + 110, 44, TH["accent"], a, box=False)
    else:  # pulse (style d'origine)
        light = sum(TH["cta_bg"][:3]) > 500
        yy = caption(d, cta, 700, 72, TH["accent"], a, box=False)
        caption(d, "@bleuddymufwar", yy + 40, 64, (30, 30, 30) if light else (255, 255, 255), a, box=False)
        caption(d, nxt, yy + 150, 46, (30, 30, 30) if light else (255, 255, 255), a, box=False)
        bw, bh = 420 * p, 110 * p
        d.rounded_rectangle([W / 2 - bw / 2, 1250 - bh / 2, W / 2 + bw / 2, 1250 + bh / 2], 55, fill=rgba(TH["cta_btn"], a))
        fb = dfont(int(50 * p)); tx = "+ S'abonner"
        d.text((W / 2 - d.textlength(tx, font=fb) / 2, 1250 - 30 * p), tx, font=fb, fill=(255, 255, 255, int(255 * a)))
        if q: caption(d, q, 1380, 46, TH["accent"], a, box=False)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

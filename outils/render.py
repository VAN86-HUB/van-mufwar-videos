#!/usr/bin/env python3
"""Rendu d'une vidéo TikTok « Astuce Excel du jour » (1080x1920, ~30 s) à partir d'un fichier JSON.
Usage : python3 render.py spec.json sortie.mp4
"""
import json, math, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 24
F = "/usr/share/fonts/truetype/dejavu/"
def font(size, bold=False, mono=False):
    name = "DejaVuSansMono.ttf" if mono else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    if mono and bold: name = "DejaVuSansMono-Bold.ttf"
    return ImageFont.truetype(F + name, size)

GREEN, DARK1, DARK2 = (33, 115, 70), (10, 36, 24), (20, 64, 42)
YELLOW, WHITE, GRID = (255, 214, 0), (255, 255, 255), (214, 214, 214)
HDR, TXT, BLUE, ORANGE, PINK = (238, 238, 238), (30, 30, 30), (52, 120, 246), (240, 140, 30), (220, 60, 120)

def ease(t): t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3
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
def caption(d, text, y, size=64, color=WHITE, alpha=1.0, box=True):
    f = font(size, bold=True)
    lines = wrap(d, text, f, W - 140)
    lh = int(size * 1.25)
    if alpha <= 0: return y + len(lines) * lh
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        x = (W - tw) / 2; yy = y + i * lh
        if box:
            d.rounded_rectangle([x - 22, yy - 10, x + tw + 22, yy + lh - 4], 18, fill=(0, 0, 0, int(170 * alpha)))
        c = tuple(int(v) for v in color) + (int(255 * alpha),)
        d.text((x, yy), ln, font=f, fill=c)
    return y + len(lines) * lh

def build_background():
    bg = Image.new("RGB", (W, H))
    arr = np.zeros((H, W, 3), np.uint8)
    for i in range(3):
        arr[:, :, i] = np.linspace(DARK2[i], DARK1[i], H)[:, None]
    return Image.fromarray(arr)

def main(spec_path, out_path):
    s = json.load(open(spec_path, encoding="utf-8"))
    headers, rows = s["headers"], s["rows"]
    ncols = len(headers)
    T = s.get("duration", 30)
    # repères temporels
    t_hook, t_q, t_type, t_res, t_exp, t_cta = 0, 3.5, 7.5, 15.5, 18.5, 25.5
    formula = s["formula"]
    bg = build_background()

    # géométrie de la feuille
    wx, wy, ww = 50, 560, W - 100
    rowh, rown_w = 64, 60
    colw = [(ww - rown_w) * c for c in s.get("col_ratio", [1 / ncols] * ncols)]
    nrows_total = len(rows) + 3  # en-têtes + lignes + ligne vide + total
    grid_top = wy + 80 + 70  # barre titre + barre formule
    wh = 80 + 70 + rowh * (nrows_total + 1) + 10
    res_row = len(rows) + 3          # numéro de ligne Excel de la cellule résultat
    res_col = s.get("result_col", ncols - 1)
    hl_col, hl_val, sum_col = s.get("criteria_col"), s.get("criteria_value"), s.get("sum_col")

    def cell_xy(col, row):  # row : 0 = ligne des lettres
        x = wx + rown_w + sum(colw[:col]); y = grid_top + row * rowh
        return x, y, x + colw[col], y + rowh

    fcell, fbold, fsmall = font(30), font(30, True), font(24)
    ffx = font(34, mono=True)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-pix_fmt", "yuv420p", "-crf", "20", "silent.mp4"], stdin=subprocess.PIPE)
    nframes = int(T * FPS)
    for fi in range(nframes):
        t = fi / FPS
        im = bg.copy().convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        # bandeau du haut
        d.rounded_rectangle([W/2 - 330, 70, W/2 + 330, 150], 40, fill=YELLOW)
        tt = "ASTUCE EXCEL DU JOUR"; ft = font(44, True)
        d.text(((W - d.textlength(tt, font=ft)) / 2, 84), tt, font=ft, fill=(20, 20, 20))
        # fenêtre Excel (glisse depuis le bas)
        k = ease(t / 0.8); oy = int((1 - k) * 300)
        d.rounded_rectangle([wx, wy + oy, wx + ww, wy + wh + oy], 20, fill=WHITE)
        d.rounded_rectangle([wx, wy + oy, wx + ww, wy + 80 + oy], 20, fill=GREEN)
        d.rectangle([wx, wy + 60 + oy, wx + ww, wy + 80 + oy], fill=GREEN)
        d.text((wx + 30, wy + 20 + oy), s.get("file", "Ventes.xlsx") + " - Excel", font=font(32, True), fill=WHITE)
        # barre de formule
        fy = wy + 80 + oy
        d.rectangle([wx + 10, fy + 10, wx + ww - 10, fy + 60], outline=GRID, width=2)
        d.text((wx + 25, fy + 17), "fx", font=font(30, True), fill=(110, 110, 110))
        typed = ""
        if t >= t_type:
            n = int(min(len(formula), (t - t_type) / 6.0 * len(formula) + 1))
            typed = formula[:n]
        cursor = "|" if (t >= t_type and t < t_res and int(t * 3) % 2 == 0) else ""
        d.text((wx + 85, fy + 16), typed + cursor, font=ffx, fill=TXT)
        # grille
        for r in range(nrows_total + 1):
            for c in range(ncols):
                x0, y0, x1, y1 = cell_xy(c, r); y0 += oy; y1 += oy
                fill = HDR if r == 0 else WHITE
                if r == 1: fill = (226, 239, 218)
                excel_row = r
                data_i = r - 2
                if t_q <= t < t_exp + 6 and hl_col is not None and 0 <= data_i < len(rows):
                    if rows[data_i][hl_col] == hl_val:
                        a = ease((t - t_q) / 0.6)
                        if c == hl_col: fill = tuple(int(255 - (255 - v) * a) for v in (255, 236, 150))
                        if c == sum_col and t >= t_exp: fill = (205, 228, 255)
                d.rectangle([x0, y0, x1, y1], fill=fill, outline=GRID)
                if r == 0:
                    L = chr(65 + c); d.text((x0 + (x1 - x0 - d.textlength(L, font=fsmall)) / 2, y0 + 18), L, font=fsmall, fill=(90, 90, 90))
                elif r == 1:
                    d.text((x0 + 10, y0 + 15), headers[c], font=fbold, fill=TXT)
                elif 0 <= data_i < len(rows):
                    v = str(rows[data_i][c]); ff = fcell
                    if c in s.get("right_cols", []):
                        d.text((x1 - 12 - d.textlength(v, font=ff), y0 + 15), v, font=ff, fill=TXT)
                    else:
                        d.text((x0 + 10, y0 + 15), v, font=ff, fill=TXT)
            # numéros de ligne
            if r > 0:
                x0 = wx; y0 = grid_top + r * rowh + oy
                d.rectangle([x0, y0, x0 + rown_w, y0 + rowh], fill=HDR, outline=GRID)
                num = str(r); d.text((x0 + (rown_w - d.textlength(num, font=fsmall)) / 2, y0 + 18), num, font=fsmall, fill=(90, 90, 90))
            else:
                d.rectangle([wx, grid_top + oy, wx + rown_w, grid_top + rowh + oy], fill=HDR, outline=GRID)
        # libellé + cellule résultat
        lab_c = s.get("label_col", 0)
        x0, y0, x1, y1 = cell_xy(lab_c, res_row); y0 += oy
        d.text((x0 + 10, y0 + 15), s.get("result_label", "Total"), font=fbold, fill=TXT)
        x0, y0, x1, y1 = cell_xy(res_col, res_row); y0 += oy; y1 += oy
        if t >= t_type:
            d.rectangle([x0, y0, x1, y1], outline=GREEN, width=5)
        if t >= t_res:
            a = ease((t - t_res) / 0.5)
            d.rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], fill=(198, 239, 206))
            fr = font(int(30 + 10 * (1 - a) * math.sin(a * math.pi)), True)
            v = s["result"]; d.text((x1 - 14 - d.textlength(v, font=fr), y0 + 13), v, font=fr, fill=(0, 97, 0))
        elif t >= t_type:
            v = typed[-14:]; d.text((x0 + 8, y0 + 17), v, font=font(24, mono=True), fill=TXT)
        # légendes selon la scène
        cap_y = 200
        if t < t_q:
            caption(d, s["hook"], cap_y, 70, YELLOW, ease(t / 0.4))
        elif t < t_type:
            caption(d, s["question"], cap_y, 60, WHITE, ease((t - t_q) / 0.4))
        elif t < t_res:
            caption(d, s.get("typing_caption", "Tape cette formule :"), cap_y, 60, WHITE, 1)
        elif t < t_exp:
            caption(d, s.get("result_caption", "Et voilà ! Résultat instantané"), cap_y, 64, YELLOW, ease((t - t_res) / 0.4))
        elif t < t_cta:
            yy = cap_y
            for i, (txt, col) in enumerate(s["explain"]):
                a = ease((t - t_exp - i * 1.4) / 0.5)
                col = {"yellow": YELLOW, "blue": (120, 180, 255), "green": (140, 230, 160), "white": WHITE}.get(col, WHITE)
                yy = caption(d, txt, yy, 44, col, a) + 8 if a > 0 else yy + 70
        else:
            a = ease((t - t_cta) / 0.5)
            im = Image.alpha_composite(im, ov)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, int(238 * a))); d = ImageDraw.Draw(ov)
            yy = caption(d, s.get("cta", "Abonne-toi pour ne rater aucune astuce !"), 700, 72, YELLOW, a, box=False)
            caption(d, "@bleuddymufwar", yy + 40, 64, WHITE, a, box=False)
            caption(d, s.get("next", "Prochaine astuce demain à 6h"), yy + 150, 46, WHITE, a, box=False)
            # bouton abonnement qui pulse
            p = 1 + 0.06 * math.sin((t - t_cta) * 6)
            bw, bh = 420 * p, 110 * p
            d.rounded_rectangle([W/2 - bw/2, 1250 - bh/2, W/2 + bw/2, 1250 + bh/2], 55, fill=(254, 44, 85, int(255 * a)))
            fb = font(int(50 * p), True); tx = "+ S'abonner"
            d.text((W/2 - d.textlength(tx, font=fb)/2, 1250 - 30 * p), tx, font=fb, fill=(255, 255, 255, int(255 * a)))
        # signature
        sig = "Ingénieur Van MUFWAR"; fs = font(34, True)
        d.text(((W - d.textlength(sig, font=fs)) / 2, H - 200), sig, font=fs, fill=(255, 255, 255, 200))
        im = Image.alpha_composite(im, ov).convert("RGB")
        proc.stdin.write(im.tobytes())
    proc.stdin.close(); proc.wait()

    # musique de fond originale (synthèse lo-fi, libre de droits)
    sr = 44100; n = int(T * sr); tt = np.arange(n) / sr
    bpm = 88; beat = 60 / bpm
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    audio = np.zeros(n)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    bar = beat * 4
    for b in range(int(T / bar) + 1):
        chord = prog[b % 4]; st = int(b * bar * sr); en = min(n, int((b + 1) * bar * sr))
        if st >= n: break
        seg = tt[st:en] - b * bar
        env = np.minimum(1, seg / 0.3) * np.exp(-seg * 0.35)
        for m in chord:
            audio[st:en] += 0.08 * env * (np.sin(2 * np.pi * hz(m) * seg) + 0.3 * np.sin(2 * np.pi * hz(m) * 2 * seg))
        audio[st:en] += 0.12 * env * np.sin(2 * np.pi * hz(chord[0] - 12) * seg)
        # arpège
        for j in range(8):
            a0 = st + int(j * beat / 2 * sr); a1 = min(en, a0 + int(beat / 2 * sr))
            if a0 >= en: break
            sg = tt[a0:a1] - tt[a0]; m = chord[j % 3] + 12
            audio[a0:a1] += 0.05 * np.exp(-sg * 6) * np.sin(2 * np.pi * hz(m) * sg)
    rng = np.random.default_rng(1)
    for k in range(int(T / beat)):
        s0 = int(k * beat * sr)
        if s0 >= n: break
        if k % 2 == 0:  # kick
            L = min(n - s0, int(0.25 * sr)); sg = np.arange(L) / sr
            audio[s0:s0 + L] += 0.35 * np.exp(-sg * 18) * np.sin(2 * np.pi * (50 + 80 * np.exp(-sg * 30)) * sg)
        h0 = s0 + int(beat / 2 * sr); L = min(max(0, n - h0), int(0.05 * sr))
        if L > 0: audio[h0:h0 + L] += 0.04 * rng.standard_normal(L) * np.exp(-np.arange(L) / sr * 80)
    fade = np.ones(n); fl = int(1.5 * sr); fade[:fl] = np.linspace(0, 1, fl); fade[-fl:] = np.linspace(1, 0, fl)
    audio = audio * fade; audio = audio / (np.max(np.abs(audio)) + 1e-9) * 0.5
    pcm = (audio * 32767).astype(np.int16)
    with wave.open("music.wav", "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "silent.mp4", "-i", "music.wav", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path], check=True)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

# -*- coding: utf-8 -*-
"""出「平面 + 前场横断面」一张图。全部坐标从布局文件读，剖面按 x=1200 竖切自动推导。

用法： python _t_plan2.py <布局.json> <输出.png> [标题]
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "_layout_oconnor.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "OC_平面.png")
TITLE = sys.argv[3] if len(sys.argv) > 3 else "CatMansion 街角"

d = json.load(open(SRC, encoding="utf-8"))
bld = d["building"]["box"]
corr = d["building"]["corr"]


def F(sz=14, bold=False):
    for p in ("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
              "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


f_t, f_m, f, f_s, f_xs = F(23, True), F(16, True), F(14), F(13), F(12)

X0, X1 = -280.0, 4300.0
Y0 = -300.0
Y1 = max(b["y1"] for b in d["bands"] if "对侧人行道" in b["name"]) + 70.0
S = 1600.0 / (X1 - X0)
PW, PH = int((X1 - X0) * S), int((Y1 - Y0) * S)
L, RGT, TOP, GAP, SEC_H = 34, 320, 62, 30, 250
W, H = L + PW + RGT, TOP + PH + GAP + SEC_H + 60
img = Image.new("RGB", (W, H), (249, 248, 245))
dr = ImageDraw.Draw(img)
pl = Image.new("RGB", (PW, PH), (249, 248, 245))
pd = ImageDraw.Draw(pl)


def Q(x, y):
    return ((x - X0) * S, (y - Y0) * S)


COL = {"walk": (232, 228, 216), "lot": (176, 175, 170), "verge": (152, 178, 134),
       "curb": (112, 112, 110), "road": (98, 100, 104), "far": (208, 206, 202)}
LANE_COL = (140, 143, 146)
CROSS_COL = (196, 190, 178)

for b in d["bands"]:
    pd.rectangle([Q(b["x0"], b["y0"]), Q(b["x1"], b["y1"])], fill=COL[b["kind"]])
for g in d["grass"]:
    pd.rectangle([Q(g["x0"], g["y0"]), Q(g["x1"], g["y1"])], fill=(168, 186, 146))
for b in d["bands"]:
    if b["name"] == "内部车道":
        pd.rectangle([Q(b["x0"], b["y0"]), Q(b["x1"], b["y1"])], fill=LANE_COL)
    if b["name"] == "车道出入口":
        pd.rectangle([Q(b["x0"], b["y0"]), Q(b["x1"], b["y1"])], fill=CROSS_COL)
for b in d["bands"]:
    if b["kind"] == "walk":
        pd.rectangle([Q(b["x0"], b["y0"]), Q(b["x1"], b["y1"])],
                     fill=(240, 236, 224), outline=(206, 124, 92), width=2)

pd.rectangle([Q(bld["x0"], bld["y0"]), Q(bld["x1"], bld["y1"])],
             fill=(208, 192, 174), outline=(92, 82, 72), width=2)
u = bld["x1"] / 8.0
for i in range(1, 8):
    pd.line([Q(i * u, bld["y0"]), Q(i * u, bld["y1"])], fill=(146, 132, 116), width=1)
pd.rectangle([Q(bld["x0"], corr["y0"]), Q(bld["x1"], corr["y1"])], fill=(186, 172, 156))

for b in d["bands"]:
    if b.get("pitch"):
        n = int((b["x1"] - b["x0"]) // b["pitch"]) + 1
        for i in range(n + 1):
            xx = b["x0"] + i * b["pitch"]
            if xx > b["x1"]:
                break
            pd.line([Q(xx, b["y0"]), Q(xx, b["y1"])], fill=(238, 238, 234), width=1)

for cc in d["cars"]:
    pd.rectangle([Q(cc["x"], cc["y"]), Q(cc["x"] + 160, cc["y"] + cc["len"])],
                 fill=(120, 132, 144), outline=(72, 82, 94))
    pd.rectangle([Q(cc["x"] + 14, cc["y"] + 70), Q(cc["x"] + 146, cc["y"] + cc["len"] - 80)],
                 fill=(88, 100, 112))

for t in d["trees"]:
    r = max(55.0, 170.0 * t.get("scale", 0.6) * 0.9)
    pd.ellipse([Q(t["x"] - r, t["y"] - r), Q(t["x"] + r, t["y"] + r)],
               fill=(98, 122, 86), outline=(72, 94, 64))

for p in d["poles"]:
    pd.ellipse([Q(p["x"] - 70, p["y"] - 70), Q(p["x"] + 70, p["y"] + 70)],
               outline=(206, 60, 60), width=2)
    pd.ellipse([Q(p["x"] - 20, p["y"] - 20), Q(p["x"] + 20, p["y"] + 20)], fill=(56, 56, 60))
for lp in d["lamps"]:
    x, y = Q(lp["x"], lp["y"])
    pd.line([(x, y), (x + 30, y - 26)], fill=(36, 36, 40), width=3)
    pd.ellipse([x + 24, y - 34, x + 40, y - 18], fill=(252, 248, 214), outline=(36, 36, 40))

# ---------- 人的动线：沿步道，不穿车道；过街用虚线 ----------
paths = [b for b in d["bands"] if "步道" in b["name"]]
ns = [b for b in d["bands"] if "南北" in b["name"]]
sw = [b for b in d["bands"] if "临街人行道" in b["name"]]
if paths and ns and sw:
    main = max(paths, key=lambda b: b["x1"] - b["x0"])
    mid = (main["y0"] + main["y1"]) / 2.0
    nx = (ns[0]["x0"] + ns[0]["x1"]) / 2.0
    sy = (sw[0]["y0"] + sw[0]["y1"]) / 2.0
    dwx = 4030.0
    corner_y = sw[0]["y1"]
    pts = [(700, bld["y1"] - 70), (700, mid), (nx, mid), (nx, sy), (dwx - 130, sy), (dwx, sy)]
    for a, b in zip(pts[:-1], pts[1:]):
        pd.line([Q(*a), Q(*b)], fill=(206, 52, 52), width=3)
    q = Q(*pts[0])
    pd.ellipse([q[0] - 7, q[1] - 7, q[0] + 7, q[1] + 7], fill=(206, 52, 52))
    far_walk = [b for b in d["bands"] if "对侧人行道" in b["name"]]
    if far_walk:
        ty = (far_walk[0]["y0"] + far_walk[0]["y1"]) / 2.0
        yy = corner_y + 20
        while yy < ty:
            pd.line([Q(dwx, yy), Q(dwx, min(yy + 70, ty))], fill=(206, 52, 52), width=3)
            yy += 130
        q = Q(dwx, ty + 26)
        pd.polygon([(q[0] - 8, q[1] + 12), (q[0] + 8, q[1] + 12), (q[0], q[1] - 2)], fill=(206, 52, 52))
    q = Q(dwx, corner_y)
    pd.ellipse([q[0] - 9, q[1] - 9, q[0] + 9, q[1] + 9], fill=(255, 255, 255), outline=(206, 52, 52), width=3)

img.paste(pl, (L, TOP))

PLAN = d.get("_plan", "")
dr.text((L, 12), ("%s · 方案 %s" % (TITLE, PLAN)) if PLAN else TITLE,
        font=f_t, fill=(28, 28, 32))
dr.text((L + 300, 20), d.get("_note", ""), font=f, fill=(112, 112, 118))


def T(x, y, s, cc=(58, 58, 64), ft=None):
    dr.text((L + (x - X0) * S, TOP + (y - Y0) * S), s, font=ft or f_xs, fill=cc,
            stroke_width=3, stroke_fill=(250, 249, 246))


T(40, 300, "外廊 / 各户门", (74, 62, 50))
T(-190, -170, "后院草地", (52, 76, 44))
for b in d["bands"]:
    if b.get("pitch"):
        # ⚠️ 2026-10-31 修：原来这里两个 %d 都填 len(d["cars"])，
        #    8 台车时恰好等于 8 车位 / 8 户 ⇒ 看不出错。
        #    改成「停 2 台」以后立刻暴露成「2 个车位（2 户）」—— 车数 ≠ 车位数 ≠ 户数。
        #    车位从地块尺寸和 pitch 算，户数从 building.units 读，只有「停几台」看 cars。
        _bays = int(round((b["x1"] - b["x0"]) / float(b["pitch"])))
        _units = int((d.get("building") or {}).get("units") or 0)
        T(b["x0"] + 200, b["y0"] + 200,
          "%d 个 90° 车位 · 停 %d 台 · 车头朝楼（%d 户）" % (_bays, len(d["cars"]), _units),
          (44, 44, 50))
    if b["name"] == "内部车道":
        T(b["x0"] + 420, (b["y0"] + b["y1"]) / 2 - 18, "内部车道 %.0f" % (b["y1"] - b["y0"]), (30, 30, 34))
        T(b["x0"] + 2150, (b["y0"] + b["y1"]) / 2 - 18, "车从这倒进车位", (58, 58, 64))
    if b["name"] == "车道出入口":
        cx, cy = Q((b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2)
        dr.text((L + cx - 30, TOP + cy - 8), "车道口", font=f_xs, fill=(150, 40, 40),
                stroke_width=3, stroke_fill=(250, 249, 246))
    if b["name"].startswith("临街绿化带"):
        T(b["x0"] + 70, (b["y0"] + b["y1"]) / 2 - 24, "绿化带 %.0f" % (b["y1"] - b["y0"]), (52, 84, 40))
    if b["name"].startswith("临街人行道-西"):
        T(b["x0"] + 70, (b["y0"] + b["y1"]) / 2 + 4, "临街人行道 %.0f" % (b["y1"] - b["y0"]), (150, 70, 44))
    if b["name"] == "主街 车行道":
        T(760, (b["y0"] + b["y1"]) / 2, "主街 车行道 1094", (30, 30, 36), f_s)
    if b["name"] == "主街 对侧人行道":
        T(760, b["y0"] + 90, "主街 对侧人行道", (58, 58, 64))
    if b["name"] == "侧街 人行道":
        T(b["x0"] + 40, -170, "侧街 人行道", (58, 58, 64))
    if b["name"] == "入户步道（南北）":
        T(b["x1"] + 34, (b["y0"] + b["y1"]) / 2 - 60, "入户步道 200", (150, 70, 44))

dr.text((L + 8, TOP + PH - 22),
        "红线 = 人的动线：楼门 → 建筑前步道 → 入户步道 → 临街人行道 → 街角（过街段虚线）",
        font=f_xs, fill=(176, 32, 32))

# ---------- 右侧分层标注（短名 + 防重叠） ----------
SHORT = {"建筑前步道": "步道", "楼前停车位": "车位", "内部车道": "内部车道",
         "临街绿化带-西": "绿化带", "临街人行道-西": "临街人行道",
         "主街 路缘": "路缘", "主街 车行道": "主街 车行道",
         "主街 对侧人行道": "对侧人行道"}
cut = [b for b in d["bands"] if b["x0"] <= 1200 <= b["x1"] and b["kind"] != "far"]
cut.sort(key=lambda b: b["y0"])
marks = [("外廊", 540)]
for b in cut:
    marks.append((SHORT.get(b["name"], b["name"]), b["y1"]))
ax = L + PW + 14
prev = -99.0
for t, yy in marks:
    py = max(TOP + (yy - Y0) * S, prev + 17)
    prev = py
    dr.line([(L + PW + 2, py), (ax, py)], fill=(126, 124, 120), width=1)
    dr.text((ax + 5, py - 9), "%s  %.0f" % (t, yy), font=f_xs, fill=(72, 72, 78))

# ---------- 横断面 ----------
SY = TOP + PH + GAP
dr.line([(L, SY - 6), (W - 16, SY - 6)], fill=(212, 210, 206), width=1)
dr.text((L, SY + 2), "前场横断面（x=1200 处竖切，自楼向外）", font=f_m, fill=(30, 30, 36))

stack = [("楼", 150, (188, 174, 158), "楼")]
for b in cut:
    stack.append((SHORT.get(b["name"], b["name"]), b["y1"] - b["y0"], COL[b["kind"]],
                  "%s %.0f" % (b["kind"], b["y1"] - b["y0"])))
sx, SW = L + 6, W - L - 30
total = sum(s[1] for s in stack)
sy0, bh = SY + 46, 84
thin = []
for name, val, cc, short in stack:
    w = max(3, int(val / float(total) * SW))
    dr.rectangle([sx, sy0, sx + w, sy0 + bh], fill=cc, outline=(150, 148, 144))
    if w >= 54:
        dr.text((sx + 4, sy0 + bh + 5), short, font=f_xs, fill=(60, 60, 66))
        dr.text((sx + 6, sy0 + 6), name, font=f_xs,
                fill=(248, 248, 248) if cc in (COL["road"], COL["curb"]) else (44, 44, 50))
    else:
        thin.append((sx, short))
    sx += w
for i, (sx, short) in enumerate(thin):
    yy = sy0 - 8 - i * 17
    dr.line([(sx + 1, yy + 2), (sx + 1, sy0)], fill=(120, 118, 114), width=2)
    dr.text((sx + 5, yy - 12), short, font=f_xs, fill=(60, 60, 66))
dr.text((L + 6, sy0 - 18), "↑ 楼", font=f_xs, fill=(92, 82, 72))
tot = sum(s[1] for s in stack[1:])
dr.text((L + 6, sy0 + bh + 48),
        "真实尺寸（cm），条形宽度按尺寸线性压缩非等比；外廊→对侧人行道合计 %.0f cm" % tot,
        font=f_xs, fill=(126, 126, 132))
print("SEC      total=%.0f  segs=%d" % (tot, len(stack) - 1))
for nm, v, _c, _s in stack[1:]:
    print("   %-12s %5.0f" % (nm, v))

img.save(OUT)
print("saved", OUT, img.size)

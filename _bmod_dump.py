# -*- coding: utf-8 -*-
"""把 _gmod 的几何 + 机位表导出成 JSON，供 Blender 侧构建。

⭐ 单一事实源：几何只从 _gmod.build_scene() 取，不在 Blender 侧重写一遍。
⭐ 3D 只出「人真能站进去的机位」——A/B/C 那种「贴脸 48mm / 悬空 85mm」在 3D 里
   只是一块橙色板子占满画面，什么也证明不了。空间限制改用 2D 剖面图（_bmod_section.py）。
⭐ grading 块只出数字，喂剖面图与规格书。
"""
import json
import os

import numpy as np

from _gmod import (build_scene, build_details, build_env, build_back, SHOT_LENS, K_TABLE, BODY_CM, SENSOR_H,
                   W, H, unit_center, FULL_X, F2_Z, ROOF_Z, COR_Y0, COR_Y1, ROOM_Y)

ROOT = r"D:\mv\pierce_wide"
OUT = os.path.join(ROOT, "_bmod")
os.makedirs(OUT, exist_ok=True)

EYE = 140.0       # 相机眼高 cm（角色 152cm）
CHEST = 100.0     # 看向高度（门中段 / 人胸腹）


def lens_for(name, dist_cm):
    """已知景别 + 可用物距 ⇒ 需要的焦距(mm)。与 _gmod_shots.lens_for 同式。"""
    k = K_TABLE[name]
    fpx = (k * H) * dist_cm / BODY_CM
    return SENSOR_H * fpx / float(H)


def fpx_of_mm(f):
    return (H / 2.0) / np.tan(np.arctan(SENSOR_H / 2.0 / f))


def dist_of(name):
    """景别 → 需要的物距（cm），由 k 表反算"""
    f = SHOT_LENS[name]
    return float(fpx_of_mm(f) * BODY_CM / (K_TABLE[name] * H))


# ---------------- ① 几何 ----------------
B = build_scene()
boxes = []
for p0, p1, c in B:
    boxes.append([float(p0[0]), float(p0[1]), float(p0[2]),
                  float(p1[0]), float(p1[1]), float(p1[2]),
                  [int(c[0]), int(c[1]), int(c[2])],
                  1 if float(p0[2]) >= ROOF_Z - 1.0 else 0])   # grp: 1=屋顶层
n_arch = len(boxes)

# ⭐ 2026-10-30：生活痕迹层（grp=3）—— 白天才看得见的那些东西
DET = build_details()
for p0, p1, c in DET:
    boxes.append([float(p0[0]), float(p0[1]), float(p0[2]),
                  float(p1[0]), float(p1[1]), float(p1[2]),
                  [int(c[0]), int(c[1]), int(c[2])], 3])
n_det = len(DET)

# ⭐ 2026-10-30：背面（y=0 侧）的后窗 / 排水管 —— grp=3，跟走廊侧细节同一层
BK = build_back()
for p0, p1, c in BK:
    boxes.append([float(p0[0]), float(p0[1]), float(p0[2]),
                  float(p1[0]), float(p1[1]), float(p1[2]),
                  [int(c[0]), int(c[1]), int(c[2])], 3])
n_det += len(BK)

# ⭐ 环境层 L2（grp=4）
ENV = build_env()
for p0, p1, c in ENV:
    boxes.append([float(p0[0]), float(p0[1]), float(p0[2]),
                  float(p1[0]), float(p1[1]), float(p1[2]),
                  [int(c[0]), int(c[1]), int(c[2])], 4])
n_env = len(ENV)

# ---------------- ② 尺度人（152cm 含耳，三段三色，好认） ----------------
C_HEAD = [240, 176, 128]
C_BODY = [222, 138, 86]
C_LEG = [190, 104, 62]


def figure(fx, fy, fz):
    """152cm 含耳。一块块拼，但分腿 + 收腰 + 脖子，才读得出是人不是柱子。"""
    return [
        [fx - 11, fy - 8, fz, fx - 2, fy + 8, fz + 78, C_LEG],
        [fx + 2, fy - 8, fz, fx + 11, fy + 8, fz + 78, C_LEG],
        [fx - 13, fy - 9, fz + 78, fx + 13, fy + 9, fz + 98, C_LEG],
        [fx - 15, fy - 10, fz + 98, fx + 15, fy + 10, fz + 128, C_BODY],
        [fx - 5, fy - 6, fz + 128, fx + 5, fy + 6, fz + 134, C_BODY],
        [fx - 9, fy - 10, fz + 134, fx + 9, fy + 10, fz + 152, C_HEAD],
    ]


c208 = unit_center(208)
c203 = unit_center(203)

SHOTS = []


def add(tag, pos, look, lens, note, fig=None, ortho=None):
    SHOTS.append(dict(tag=tag, pos=[float(v) for v in pos],
                      look=[float(v) for v in look], lens=float(lens),
                      note=note, fig=fig, ortho=ortho))


# ---------------- ③ 八个人站得进去的实用机位 ----------------
add("E1_corr_east", (200, 470, F2_Z + EYE), (FULL_X, 470, F2_Z + 90),
    32.0, "外廊纵望 · 向东，一头看到东端铁梯", fig=[1100, 470, F2_Z])
add("E2_corr_west", (1300, 470, F2_Z + EYE), (0, 470, F2_Z + 90),
    32.0, "外廊纵望 · 向西，八户门连成一排", fig=[520, 470, F2_Z])
add("E3_d208_34", (c208 + 140, COR_Y1 - 12, F2_Z + EYE), (c208, 430, F2_Z + 78),
    18.0, "208 门前 3/4（斜纵深处，24mm 装不下走廊+门，退到 18mm）", fig=[c208 - 6, 432, F2_Z])
add("E4_d208_inside", (c208, 250, F2_Z + EYE), (c208, 520, F2_Z + 85),
    32.0, "208 屋内朝外拍 · 纵深换来的替代机位", fig=[c208 - 6, 432, F2_Z])
add("E5_d203_34", (c203 - 140, COR_Y1 - 12, F2_Z + EYE), (c203, 430, F2_Z + 78),
    18.0, "203 门前 3/4（Koko 家，同上机位规律）", fig=[c203 + 6, 432, F2_Z])
add("E6_corr_low", (600, 478, F2_Z + 50), (FULL_X, 470, F2_Z + 200),
    18.0, "走廊低角度仰拍 · 天花板压顶", fig=[1100, 470, F2_Z])
add("E7_roof", (300, 250, ROOF_Z + EYE), (300, 540, ROOF_Z + 30),
    24.0, "天台 · 看向女儿墙", fig=[300, 505, ROOF_Z])
add("E8_stair", (FULL_X - 40, 470, F2_Z + EYE), (FULL_X + 390, 470, F2_Z + 230),
    24.0, "东端露天铁梯 · 从走廊尽头仰视上梯")

# ---------------- ④ 两张正投影（分镜画机位用） ----------------

# ---------------- ⑤ 拼人形进几何 ----------------
figs_seen = set()
for s in SHOTS:
    if s["fig"]:
        key = tuple(round(v, 1) for v in s["fig"])
        if key not in figs_seen:
            figs_seen.add(key)
            boxes.extend([b + [2] for b in figure(*s["fig"])])   # grp 2 = 人形

for s in SHOTS:
    p = np.array(s["pos"], float)
    if s["fig"]:
        tgt = np.array([s["fig"][0], s["fig"][1], s["fig"][2] + BODY_CM / 2.0])
        s["subject_cm"] = float(np.linalg.norm(tgt - p))
    else:
        s["subject_cm"] = float(np.linalg.norm(np.array(s["look"], float) - p))
    fpx = fpx_of_mm(s["lens"])
    s["body_px"] = float(fpx * BODY_CM / s["subject_cm"])
    s["body_k"] = float(s["body_px"] / H)
    s["has_fig"] = 1 if s["fig"] else 0

# ---------------- ⑥ 景别能退多远（喂剖面图） ----------------
grading = []
for name in ("全景", "中景", "中近", "近景"):
    need = dist_of(name)
    grading.append(dict(
        shot=name,
        lens_mm=SHOT_LENS[name],
        k=K_TABLE[name],
        need_cm=round(need, 1),
        have_cm=110.0,
        short_cm=round(need - 110.0, 1),
        lens_at_110=round(lens_for(name, 110.0), 2),
        cover_v_cm=round(BODY_CM / K_TABLE[name], 1),
    ))

data = dict(
    units="cm",
    body_cm=BODY_CM,
    sensor_h_mm=SENSOR_H,
    res=[W, H],
    eye_cm=EYE,
    arch_box_count=n_arch, detail_box_count=n_det, env_box_count=n_env,
    total_box_count=len(boxes),
    door_y=ROOM_Y,
    rail_in=COR_Y1 - 8,
    rail_out=COR_Y1,
    fig_y=440.0,
    boxes=boxes,
    shots=[dict(tag=s["tag"], pos=s["pos"], look=s["look"],
                lens=round(s["lens"], 3), note=s["note"], ortho=s["ortho"],
                subject_cm=round(s["subject_cm"], 1),
                body_px=round(s["body_px"], 1), body_k=round(s["body_k"], 3),
                has_fig=s["has_fig"]) for s in SHOTS],
    grading=grading,
)

p = os.path.join(OUT, "scene.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

print("boxes: arch=%d  det=%d  env=%d  fig=%d  all=%d" % (n_arch, n_det, n_env, len(boxes)-n_arch-n_det-n_env, len(boxes)))
print()
print("%-16s %7s %8s %8s %6s %5s  %s"
      % ("tag", "焦距mm", "主体cm", "身高px", "k", "正投", "说明"))
for s in data["shots"]:
    print("%-16s %7.2f %8.1f %8.1f %6.3f %5s  %s"
          % (s["tag"], s["lens"], s["subject_cm"], s["body_px"], s["body_k"],
             ("%.0fm" % s["ortho"]) if s["ortho"] else "-", s["note"]))
print()
print("=" * 78)
print("景别 → 需要多远（走廊实有 110cm）")
print("=" * 78)
print("%-6s %8s %6s %9s %9s %10s %9s"
      % ("景别", "焦距mm", "k", "需要cm", "实有cm", "缺口cm", "110cm处焦距"))
for g in grading:
    print("%-6s %8.0f %6.2f %9.0f %9.0f %10.0f %9.1f"
          % (g["shot"], g["lens_mm"], g["k"], g["need_cm"], g["have_cm"],
             g["short_cm"], g["lens_at_110"]))
print("->", p, os.path.getsize(p), "B")

# -*- coding: utf-8 -*-
"""灰模：针孔相机 + 线框/面填充，替 Blender 做的事。
单位一律 cm。坐标右手系：x=沿走廊(西0→东+), y=进深(屋内侧0→走廊+), z=高(一层地面0)
"""
import math
import os
import json
import numpy as np
import cv2

ROOT = r"D:\mv\pierce_wide"
OUT = os.path.join(ROOT, "_gmod")

W, H = 1920, 1080
SENSOR_H = 20.25          # 全画幅 36x24 裁 16:9 ⇒ 高 20.25 mm

# ============================================================
# ① 景别 → (焦距, 物距)  —— 由规格书 §二 的 k 值反推
# ============================================================
BODY_CM = 152.0           # 拟人角色身高（含耳）

def fpx_of(f_mm):
    """焦距(mm) → 像素焦距。垂直 FOV = 2*atan(SENSOR_H/2 / f)"""
    fv = 2.0 * math.atan((SENSOR_H / 2.0) / f_mm)   # rad
    return (H / 2.0) / math.tan(fv / 2.0), math.degrees(fv)

SHOT_LENS = {
    "全景": 32.0,
    "中景": 50.0,
    "中近": 70.0,
    "近景": 85.0,
}
K_TABLE = {"全景": 0.95, "中景": 1.70, "中近": 2.40, "近景": 3.30}

def lens_and_dist(name):
    """给定景别，返回 (焦距mm, 垂直fov°, 物距cm)"""
    f = SHOT_LENS[name]
    k = K_TABLE[name]
    fpx, fvd = fpx_of(f)
    target_px = k * H
    dist = fpx * BODY_CM / target_px
    return f, fvd, dist

# ============================================================
# ② 场景几何（全部来自规格书，单位 cm）
# ============================================================
# 楼层
F1_Z = 0.0        # 一层地面
F2_Z = 240.0      # 二层地面（层高 240）
ROOF_Z = 480.0    # 屋顶面

# ⭐ 2026-10-30 改：真实日本木造 1K アパート 的住戸開間 = 2間 = 3640mm（910mm 模数的整数倍）
#    来源：建筑基准法体系 + 木造在来軸組 910 模数（见 [设计端]研究-真实日本小公寓-20261030.md）
#    ⛔ 之前写的 180 是"门间距"，450 是"开间"，两个都错。
UNIT_X = 364.0    # 每户开间（含户界墙）
N_UNIT = 8        # 8 户
FULL_X = UNIT_X * N_UNIT          # 1440
ROOM_Y = 420.0                    # 户进深
COR_Y0, COR_Y1 = ROOM_Y, ROOM_Y + 120.0   # 外廊 420..540
SLAB_T = 12.0
RAIL_H = 110.0
DOOR_W, DOOR_H = 80.0, 200.0

def unit_x_range(no):
    """房号 201..208 → (x0,x1)。201 最东（靠楼梯），208 最西"""
    i = N_UNIT - (no - 200)        # 201→7, 208→0
    x0 = i * UNIT_X
    return x0, x0 + UNIT_X

def unit_center(no):
    x0, x1 = unit_x_range(no)
    return 0.5 * (x0 + x1)


def box(x0, y0, z0, x1, y1, z1, c):
    return (np.array([x0, y0, z0], float),
            np.array([x1, y1, z1], float), c)


# 灰阶配色：不同构件不同灰度，能读出前后关系
C_FLOOR = (168, 162, 150)
C_WALL  = (190, 184, 173)
C_PARTY = (150, 145, 136)
C_RAIL  = (96, 92, 86)
C_COPING = (206, 200, 188)   # 栏杆压顶（2026-10-30 新增：没有这道浅色，110cm 栏杆在白天读成实墙）
C_ROOF   = ( 74,  76,  78)   # 屋顶面（防水卷材/铁皮）—— ⭐ 与楼板分开，否则整栋楼读成一块水泥板
C_STEP  = (146, 141, 132)
C_CEIL  = (132, 127, 119)
C_UNIT  = (150, 144, 134)   # 户内隔断示意


def build_scene():
    B = []
    # 户数（规格书 §9-1 待拍：8 户/16 户）
    # --- 二层楼板（按开间分段，避免长条大面排序失准） ---
    for i in range(N_UNIT):
        B.append(box(i * UNIT_X, 0, F2_Z - SLAB_T, (i + 1) * UNIT_X, COR_Y1, F2_Z, C_FLOOR))
    # --- 各户：外墙（朝走廊那一侧，留门洞）+ 两侧隔墙 ---
    for no in range(201, 209):
        x0, x1 = unit_x_range(no)
        # 走廊侧外墙：y = COR_Y0-12 .. COR_Y0，墙上开门洞
        wy0, wy1 = ROOM_Y - 12.0, ROOM_Y
        d0 = unit_center(no) - DOOR_W / 2
        d1 = unit_center(no) + DOOR_W / 2
        if d0 > x0:
            B.append(box(x0, wy0, F2_Z, d0, wy1, F2_Z + 240, C_WALL))
        if d1 < x1:
            B.append(box(d1, wy0, F2_Z, x1, wy1, F2_Z + 240, C_WALL))
        # 门楣（洞上方到天花板）
        B.append(box(d0, wy0, F2_Z + DOOR_H, d1, wy1, F2_Z + 240, C_WALL))
        # 户与户之间隔墙
        if no > 201:
            B.append(box(x0 - 6, wy0, F2_Z, x0 + 6, wy1, F2_Z + 240, C_PARTY))
    # --- 外廊栏杆（分段） ---
    for i in range(N_UNIT):
        x0, x1 = i * UNIT_X, (i + 1) * UNIT_X
        B.append(box(x0, COR_Y1 - 8, F2_Z, x1, COR_Y1, F2_Z + 12, C_RAIL))
        B.append(box(x0, COR_Y1 - 8, F2_Z + 12, x1, COR_Y1, F2_Z + 62, C_RAIL))
        B.append(box(x0, COR_Y1 - 8, F2_Z + 62, x1, COR_Y1, F2_Z + RAIL_H, C_RAIL))
    for i in range(N_UNIT + 1):
        px = i * UNIT_X
        B.append(box(px - 4, COR_Y1 - 8, F2_Z, px + 4, COR_Y1, F2_Z + RAIL_H, C_RAIL))
    # 2026-10-30：压顶 —— 没有这道浅色，110cm 的栏杆在白天会读成一堵实墙
    for i in range(N_UNIT):
        x0, x1 = i * UNIT_X, (i + 1) * UNIT_X
        B.append(box(x0, COR_Y1 - 11, F2_Z + RAIL_H, x1, COR_Y1 + 1, F2_Z + RAIL_H + 5, C_COPING))
    # --- 走廊顶（天花板）：隧道感的关键 ---
    for i in range(N_UNIT):
        x0, x1 = i * UNIT_X, (i + 1) * UNIT_X
        B.append(box(x0, COR_Y0 - 12, F2_Z + 240, x1, COR_Y1, F2_Z + 252, C_CEIL))
        B.append(box(x0, COR_Y1, F2_Z + 240, x1, COR_Y1 + 26, F2_Z + 252, C_CEIL))
    # --- 背面外墙：由 build_back() 按「每户两扇窗」开洞生成 ---
    # ⚠️ 这里不放整块实心墙！原来写的是 box(0,0,0,FULL_X,12,ROOF_Z) 一整块，
    #    窗玻璃写在 y=2.4 就被埋进墙体 2.4cm，立面渲染实测整面墙一扇窗都没有。
    #    走廊侧那面墙至今还是这个毛病（见 2026-10-30 报给 Ronny 的 A/B）。
    # --- 屋顶（示意，给天台用） ---
    B.append(box(0, 0, ROOF_Z - SLAB_T, FULL_X + 360, 540, ROOF_Z, C_ROOF))
    B.append(box(0, 540 - 10, ROOF_Z, FULL_X + 360, 540, ROOF_Z + RAIL_H, C_RAIL))  # 女儿墙
    B.append(box(0, 0, ROOF_Z, 10, 540, ROOF_Z + RAIL_H, C_RAIL))
    B.append(box(0, 0, ROOF_Z, FULL_X + 360, 10, ROOF_Z + RAIL_H, C_RAIL))  # 背面女儿墙（原来也缺）
    # --- 东端楼梯（露天铁梯，14 级） ---
    N_STEP, RISE, RUN = 14, 17.14, 25.0
    sx0 = FULL_X + 40
    for i in range(N_STEP):
        s0 = sx0 + i * RUN
        top = F2_Z + (i + 1) * RISE
        B.append(box(s0, COR_Y0, F2_Z, s0 + RUN, COR_Y0 + 90, top, C_STEP))
    # 侧板 + 顶部落脚平台（连到屋顶层）
    B.append(box(sx0, COR_Y0 - 6, F2_Z, sx0 + N_STEP * RUN, COR_Y0, ROOF_Z, C_PARTY))
    B.append(box(sx0 + N_STEP * RUN, COR_Y0, ROOF_Z - 12, sx0 + N_STEP * RUN + 160, COR_Y0 + 200, ROOF_Z, C_FLOOR))
    return B


# ============================================================
# ③ 相机
# ============================================================
class Cam:
    def __init__(self, pos, look, f_mm, fov_hint=None):
        self.pos = np.array(pos, float)
        self.look = np.array(look, float)
        self.f_mm = f_mm
        self.fpx, self.fvd = fpx_of(f_mm)
        fwd = self.look - self.pos
        fwd = fwd / np.linalg.norm(fwd)
        up_w = np.array([0.0, 0.0, 1.0])
        right = np.cross(fwd, up_w)
        if np.linalg.norm(right) < 1e-6:
            right = np.array([1.0, 0.0, 0.0])
        right = right / np.linalg.norm(right)
        up = np.cross(right, fwd)
        self.fwd, self.right, self.up = fwd, right, up

    def project(self, pts):
        """pts (N,3) → (屏幕xy (N,2), 相机深度 (N,))。z<=0 为相机后方"""
        d = pts - self.pos
        x = d @ self.right
        y = d @ self.up
        z = d @ self.fwd
        ok = z > 1e-3
        zz = np.where(ok, z, 1.0)
        sx = W / 2.0 + self.fpx * x / zz
        sy = H / 2.0 - self.fpx * y / zz
        return np.stack([sx, sy], 1), z, ok


FACES = [((0, 1, 3, 2), 0), ((4, 6, 7, 5), 1),
         ((0, 2, 6, 4), 2), ((1, 5, 7, 3), 3),
         ((0, 4, 5, 1), 4), ((2, 3, 7, 6), 5)]

# 黄昏末天光：上方来光 ⇒ 朝上面亮、朝下面暗、侧面中
SHADE = {0: 0.70, 1: 1.16, 2: 0.94, 3: 0.94, 4: 0.86, 5: 1.02}
FOG_CM = 2200.0          # 超过这个距离基本融进天空
FOG_MAX = 0.55           # 最多淡化比例


def cube_corners(b):
    p0, p1, c = b
    xs = [p0[0], p1[0]]; ys = [p0[1], p1[1]]; zs = [p0[2], p1[2]]
    v = []
    for x in xs:
        for y in ys:
            for z in zs:
                v.append([x, y, z])
    return np.array(v, float), c


def render(name, cam, boxes, wire=True):
    img = np.zeros((H, W, 3), np.uint8)
    ramp = np.linspace(58, 214, H).astype(np.uint8)
    img[:] = ramp[:, None, None]
    img[:, :, 0] = np.clip(img[:, :, 0].astype(int) + 10, 0, 255)
    img[:, :, 2] = np.clip(img[:, :, 2].astype(int) - 8, 0, 255)
    items = []
    for b in boxes:
        v, c = cube_corners(b)
        S, z, ok = cam.project(v)
        if not ok.all():
            continue
        for idx, fid in FACES:
            poly = S[list(idx)]
            if np.any(z[list(idx)] <= 1e-3):
                continue
            # 背面剔除：屏幕空间有向面积
            area = 0.0
            for i in range(4):
                x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % 4]
                area += x0 * y1 - x1 * y0
            if area >= 0:
                continue
            depth = float(z[list(idx)].mean())
            cc = tuple(int(round(v * SHADE[fid])) for v in c)
            items.append((depth, poly, cc, min(1.0, depth / FOG_CM) * FOG_MAX))
    items.sort(key=lambda t: -t[0])          # 远的先画
    bg = img.copy()
    for depth, poly, c, fog in items:
        col = tuple(int(round(cv * (1 - fog) + bgv * fog)) for cv, bgv in zip(c, (200, 200, 200)))
        cv2.fillPoly(img, [poly.astype(np.int32)], col, cv2.LINE_AA)
        if wire:
            wc = int(round(70 * (1 - fog) + 150 * fog))
            cv2.polylines(img, [poly.astype(np.int32)], True, (wc, wc - 4, wc - 8), 1, cv2.LINE_AA)
    p = os.path.join(OUT, name + ".png")
    cv2.imencode(".png", img)[1].tofile(p)
    return p


# ============================================================
# ④ 生活痕迹层（2026-10-30 新增，grp=3）
#    来源：6 张白天实拍（台湾 7 层老公寓 / 澳洲红砖 walk-up /
#    台中转角楼 / 香港唐楼 / 楼间缝空调群 / 阿德莱德 2 层排屋）
#    ⛔ 全部按"白天肉眼可见"来建 —— 夜晚这些细节全部消失
# ============================================================
C_BAND   = (156, 150, 140)   # 墙裙（走廊墙下段，与上段不同漆）
C_LAMP   = (250, 246, 234)   # 壁灯罩（最亮，白天也是一块白）
C_PLATE  = (178, 182, 186)   # 不锈钢表札 / 信箱面板
C_METER  = (120, 122, 124)   # 电表 / 燃气表箱
C_AC     = (216, 214, 206)   # 空调外机（浅色塑料壳）
C_GRID   = ( 78,  76,  72)   # 防盗网 / 铁件
C_GLASS  = ( 58,  66,  72)   # 窗玻璃：白天读作暗洞
C_REVEAL = (112, 108, 100)   # 窗洞内壁（形成阴影线）
C_CLOTH  = (198, 190, 178)   # 晾晒衣物 A（白衬衫）
C_CLOTH2 = (176, 186, 196)   # 衣物 B（牛仔蓝）
C_CLOTH3 = (204, 174, 176)   # 衣物 C（浅粉）
C_CLOTH4 = (196, 178, 142)   # 衣物 D（米黄）
C_PIPE   = (162, 164, 168)   # 排水立管 / 燃气管
C_AWNING = (122, 134, 128)   # 雨棚 / 遮阳
C_MAT    = (104,  98,  90)   # 门口地垫
C_POT    = (146, 128, 112)   # 花盆
# ⭐ 2026-10-30 Ronny 选 B（实心扶手墙 + 推拉铝窗）+ 要底层铺子
C_ALU    = (200, 202, 198)   # 铝窗框（浅色，B 方案的标志）
C_GBOX   = (152, 166, 174)   # 封闭玻璃阳台盒的玻璃（比窗玻璃亮，白天会反光）
C_SHOP_G = ( 44,  52,  58)   # 店面玻璃（暗，白天也暗）
C_SIGNAGE= ( 84,  82,  86)   # 招牌板
C_SHUTTER= (152, 148, 142)   # 卷帘门盒
C_PIER   = (176, 170, 158)   # 铺面柱 / 腰墙

def _h(i, k=0):
    """确定性伪随机 0..1（⛔ 不用 random，保证每次重跑几何完全一致）"""
    return ((i * 7919 + k * 104729) % 997) / 997.0


def build_details():
    """走廊侧的"有人住"证据。每户 20+ 个盒，全部贴墙 y=420 面向走廊。"""
    Y = 420.0                    # 走廊侧墙面
    D = []
    for i in range(N_UNIT):
        no = 208 - i             # 208 最西
        x0, x1 = i * UNIT_X, (i + 1) * UNIT_X
        cx = 0.5 * (x0 + x1)
        dc = cx                  # 门中心
        # --- 墙裙：下段 90cm 换漆（参考图里所有楼都有这条分界） ---
        D.append(box(x0 + 4, Y, F2_Z, x1 - 4, Y + 1.6, F2_Z + 90, C_BAND))
        # --- 壁灯：门右上方，方乳白罩。（⚠️ 决定了走廊明暗节奏） ---
        D.append(box(dc + 46, Y, F2_Z + 206, dc + 66, Y + 13, F2_Z + 228, C_LAMP))
        # --- 表札 + 郵便受け面板：门左，不锈钢 ---
        D.append(box(dc - 80, Y, F2_Z + 96, dc - 46, Y + 12, F2_Z + 152, C_PLATE))
        # --- 电表/燃气表箱：靠户界，明装 ---
        D.append(box(x0 + 12, Y, F2_Z + 58, x0 + 46, Y + 16, F2_Z + 102, C_METER))
        # --- 两扇窗：玻璃 + 防盗网 ---
        for wx0, wx1 in ((dc - 162, dc - 96), (dc + 62, dc + 128)):
            # 玻璃面退到 Y-2.4（制造真正的凹进阴影），四周用内壁收边
            D.append(box(wx0, Y - 2.4, F2_Z + 96, wx1, Y - 1.6, F2_Z + 178, C_GLASS))
            D.append(box(wx0 - 1.6, Y - 2.4, F2_Z + 94.4, wx1 + 1.6, Y - 0.4, F2_Z + 96, C_REVEAL))
            D.append(box(wx0 - 1.6, Y - 2.4, F2_Z + 178, wx1 + 1.6, Y - 0.4, F2_Z + 179.6, C_REVEAL))
            D.append(box(wx0 - 1.6, Y - 2.4, F2_Z + 96, wx0, Y - 0.4, F2_Z + 178, C_REVEAL))
            D.append(box(wx1, Y - 2.4, F2_Z + 96, wx1 + 1.6, Y - 0.4, F2_Z + 178, C_REVEAL))
            # ⭐ B 方案：推拉铝窗（浅色细框）。⛔ 无防盗网 —— 防盗网是南方符号，B 不用
            D.append(box(wx0 - 2, Y - 3.0, F2_Z + 93, wx1 + 2, Y - 1.0, F2_Z + 96, C_ALU))   # 下框
            D.append(box(wx0 - 2, Y - 3.0, F2_Z + 176, wx1 + 2, Y - 1.0, F2_Z + 179, C_ALU)) # 上框
            D.append(box(wx0 - 2, Y - 3.0, F2_Z + 96, wx0, Y - 1.0, F2_Z + 176, C_ALU))     # 左框
            D.append(box(wx1, Y - 3.0, F2_Z + 96, wx1 + 2, Y - 1.0, F2_Z + 176, C_ALU))     # 右框
            D.append(box(x0 if False else 0.5 * (wx0 + wx1) - 1.2, Y - 3.0, F2_Z + 96,
                         0.5 * (wx0 + wx1) + 1.2, Y - 0.6, F2_Z + 176, C_ALU))               # 中挺（两扇推拉）
            D.append(box(wx0, Y - 2.9, F2_Z + 150, wx1, Y - 2.5, F2_Z + 152, C_ALU))          # 上亮子横档
        # --- 空调外机：1~2 台，位置错落（密度比位置更说明"住满人"） ---
        n_ac = 1 if _h(i, 1) < 0.55 else 2
        for a in range(n_ac):
            ax = x0 + 70 + _h(i, 2 + a) * (UNIT_X - 200)
            az = F2_Z + 142 + _h(i, 5 + a) * 46
            D.append(box(ax, Y, az, ax + 78, Y + 30, az + 34, C_AC))
            D.append(box(ax + 6, Y, az - 12, ax + 72, Y + 4, az, C_GRID))   # 支架
            D.append(box(ax + 4, Y, az + 2, ax + 12, Y + 34, az + 6, C_PIPE))  # 冷媒管
        # --- 排水立管：户界，竖直一根（参考图里每户界都有一根） ---
        D.append(box(x0 + 1, Y, F2_Z, x0 + 9, Y + 8, F2_Z + 240, C_PIPE))
        # --- 晾衣杆 + 衣物：跨走廊，白天是最强的"有人住"信号 ---
        rz = F2_Z + 206
        D.append(box(x0 + 34, 516, rz, x1 - 34, 520, rz + 3, C_PIPE))
        for k in range(3):
            hx = x0 + 60 + (_h(i, 11 + k) * (UNIT_X - 140))
            hw = 30 + _h(i, 21 + k) * 16
            _cc = (C_CLOTH, C_CLOTH2, C_CLOTH3, C_CLOTH4)[(i * 3 + k) % 4]
            D.append(box(hx, 512, rz - 40 - _h(i, 31 + k) * 9, hx + hw, 518, rz, _cc))
        # --- 花盆 / 塑料桶：栏杆边 ---
        for k in range(1 if _h(i, 41) < 0.6 else 2):
            px = x0 + 40 + _h(i, 51 + k) * (UNIT_X - 90)
            D.append(box(px, 508, F2_Z, px + 22, 530, F2_Z + 24, C_POT))
        # --- 门口地垫 ---
        D.append(box(dc - 38, Y, F2_Z, dc + 38, Y + 42, F2_Z + 1.6, C_MAT))
        # --- 雨棚：隔一户做一个，别让轮廓太齐 ---
        if i % 2 == 0:
            D.append(box(x0 + 20, COR_Y1, F2_Z + 238, x1 - 20, COR_Y1 + 62, F2_Z + 243, C_AWNING))
    D.extend(build_enclosure())
    D.extend(build_shops())
    return D


# ============================================================
# ④b 背面（y=0 侧）—— 2026-10-30 新增
#    外廊式アパート 的背面本来就没有入口：住户全部从走廊侧入户，
#    背面只有浴室/厨房换气小窗 + 排水立管 + 墙裙。
#    ⛔ 不做勝手口（后门）—— 那会引入"住户从哪进出"的空间设定，等 Ronny 拍。
#    ⚠️ 外墙面在 y=0、墙体 0..12 ⇒ 所有构件一律往 +y 内缩，
#       与走廊侧（墙 408..420、构件往 -y 内缩）完全镜像。写反了构件就埋进体里看不见。
# ============================================================
def _wall_back(x0, x1, holes):
    """带洞的后墙板（y 0..12，z 0..ROOF_Z）。
    holes = [(hx0,hx1,hz0,hz1), ...]
    ⭐ 做法：用所有洞的 x 边界把这段墙切成竖条，每条要么整条落在某个洞里、
      要么完全在洞外；落在洞里的再按 z 补上下两块墙。
      ⛔ 不切就是「整块实心墙 + 洞写在墙里面」= 窗永远看不见，
         走廊侧那面墙现在就是这个毛病。
    """
    cuts = sorted({x0, x1} | {v for h in holes for v in h[:2] if x0 < v < x1})
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        # ⚠️ 一条竖条可能同时落在两个洞里（二层窗和一层窗的 x 范围是重叠的），
        #    ⛔ 不能 next() 取第一个 —— 那样另一个洞就补不上，墙会把窗封死。必须合并所有洞的 z 区间。
        iv = sorted((h[2], h[3]) for h in holes if h[0] <= a and b <= h[1])
        merged = []
        for z0, z1 in iv:
            if merged and z0 <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], z1)
            else:
                merged.append([z0, z1])
        z = 0.0
        for z0, z1 in merged:
            if z0 > z:
                out.append(box(a, 0, z, b, 12, z0, C_WALL))
            z = max(z, z1)
        if z < ROOF_Z:
            out.append(box(a, 0, z, b, 12, ROOF_Z, C_WALL))
    return out


def _hole_win(hx0, hx1, hz0, hz1, m, glass_y, fr_y):
    """在一个已开的洞里装窗：内壁环 + 铝框环 + 玻璃 + 中挺。
    hx*/hz* 是「玻璃尺寸」，洞要往外放 m；金件全部落在洞内才看得见。"""
    a0, a1, b0, b1 = hx0 - m, hx1 + m, hz0 - m, hz1 + m
    g0, g1 = glass_y
    f0, f1 = fr_y
    W = []
    # 内壁环：从墙面 y=0.2 进到玻璃前 y=g0
    W.append(box(a0, 0.2, b0, a1, g0, hz0, C_REVEAL))          # 下
    W.append(box(a0, 0.2, hz1, a1, g0, b1, C_REVEAL))          # 上
    W.append(box(a0, 0.2, hz0, hx0, g0, hz1, C_REVEAL))        # 左
    W.append(box(hx1, 0.2, hz0, a1, g0, hz1, C_REVEAL))        # 右
    # 玻璃
    W.append(box(hx0, g0, hz0, hx1, g1, hz1, C_GLASS))
    # 铝框：贴着内壁前缘的环，比玻璃口外放 2cm
    W.append(box(a0, f0, b0, a1, f1, hz0 + 2, C_ALU))
    W.append(box(a0, f0, hz1 - 2, a1, f1, b1, C_ALU))
    W.append(box(a0, f0, hz0 + 2, hx0 + 1, f1, hz1 - 2, C_ALU))
    W.append(box(hx1 - 1, f0, hz0 + 2, a1, f1, hz1 - 2, C_ALU))
    # 中挺（两扇推拉）
    cm = 0.5 * (hx0 + hx1)
    W.append(box(cm - 1.2, f0, hz0 + 2, cm + 1.2, f1, hz1 - 2, C_ALU))
    return W, (a0, a1, b0, b1)


def build_back():
    B = []
    M = 2.0                      # 洞口比玻璃每边大 2cm
    GY = (3.0, 3.8)              # 玻璃在墙体里的进深
    FY = (-0.6, 1.4)             # 铝框：硬比墙面探出 0.6cm（否则与内壁环前面共面 → z-fighting）
    for i in range(N_UNIT):
        x0, x1 = i * UNIT_X, (i + 1) * UNIT_X
        cx = 0.5 * (x0 + x1)
        # --- 二层换气小窗 96×64：逐户横向错开 ±22，免得读成印刷品 ---
        wx0 = cx - 48 + (_h(i, 61) - 0.5) * 44
        wx1 = wx0 + 96
        wz0, wz1 = F2_Z + 98, F2_Z + 162
        # --- 一层（铺子/后厨背面）：高窗 110×70 ---
        gx0 = cx - 55 + (_h(i, 71) - 0.5) * 30
        gx1 = gx0 + 110
        gz0, gz1 = 130, 200
        # --- 墙：按两个洞切块 ---
        B.extend(_wall_back(x0, x1,
                            [(wx0 - M, wx1 + M, wz0 - M, wz1 + M),
                             (gx0 - M, gx1 + M, gz0 - M, gz1 + M)]))
        # --- 二层窗 ---
        w, (a0, a1, b0, b1) = _hole_win(wx0, wx1, wz0, wz1, M, GY, FY)
        B.extend(w)
        B.append(box(a0 - 3, -4.0, b0 - 3, a1 + 3, 0.4, b0, C_COPING))     # 窗台外挑
        # --- 一层窗 ---
        w, (a0, a1, b0, b1) = _hole_win(gx0, gx1, gz0, gz1, M, GY, FY)
        B.extend(w)
        B.append(box(a0 - 3, -4.0, b0 - 3, a1 + 3, 0.4, b0, C_COPING))
        # --- 墙裙：压住 0~90 的深色裙（墙脚没这条，整面砖会从头亮到尾） ---
        B.append(box(x0 + 4, -1.6, 0, x1 - 4, 0, 90.0, C_BAND))
        # --- 排水立管：户界，从地面一通到屋顶（外挑 8cm，与走廊侧同做法） ---
        B.append(box(x0 + 1, -8, 0, x0 + 9, 0, ROOF_Z, C_PIPE))
        for k in range(4):                                   # 管卡：每 120 一道
            B.append(box(x0, -10, 40 + k * 120, x0 + 10, 0, 48 + k * 120, C_PIPE))
    return B


# ============================================================
# ⑤ 封闭玻璃阳台盒（B 方案标志物 · 2026-10-30）
#    日本外廊改造的典型做法：腰壁（110 实心）以上整段封玻璃到顶。
#    ⭐ 只封 2 户 —— 全封就没有外廊了；不封就没有"有人改造过"的痕迹。
# ============================================================
ENCLOSED_UNITS = (2, 6)      # 索引：第 3 户、第 7 户（从西数）

def build_enclosure():
    E = []
    for i in ENCLOSED_UNITS:
        x0, x1 = i * UNIT_X, (i + 1) * UNIT_X
        a0, a1 = x0 + 18, x1 - 18
        yg0, yg1 = COR_Y1, COR_Y1 + 7          # 玻璃面在栏杆外侧
        z0, z1 = F2_Z + RAIL_H, F2_Z + 236     # 从栏杆顶到天花
        E.append(box(a0, yg0, z0, a1, yg1, z1, C_GBOX))
        E.append(box(a0 - 2, yg0 - 2, z0 - 3, a1 + 2, yg1 + 2, z0 + 2, C_ALU))    # 下横档
        E.append(box(a0 - 2, yg0 - 2, z1 - 2, a1 + 2, yg1 + 2, z1 + 3, C_ALU))    # 上横档
        for t in (0.0, 1.0 / 3, 2.0 / 3, 1.0):
            bx = a0 + (a1 - a0) * t
            E.append(box(bx - 2, yg0 - 2, z0, bx + 2, yg1 + 2, z1, C_ALU))        # 竖挺
        # 玻璃盒顶盖（外挑一点，出阴影）
        E.append(box(a0 - 4, yg0 - 4, z1 + 3, a1 + 4, yg1 + 10, z1 + 7, C_PIER))
    return E


# ============================================================
# ⑥ 一层沿街铺面（Ronny："搞点铺子啥的" · 2026-10-30）
#    建筑类型因此从「纯住宅」变成「下町式商住混合」：
#    一层 5 间铺子临街，二层外廊住戸在其上方。
# ============================================================
N_SHOP   = 5
SHOP_Z   = 228.0            # 铺面净高 = 层高240 − 楼板12（⚠️ 原来写 300，招牌顶进了二层走廊）
SHOP_YF  = 540.0            # 店面平面 = 与栏杆齐（二层楼板挑到 540）

def build_shops():
    S = []
    bay = FULL_X / N_SHOP
    for k in range(N_SHOP):
        x0 = k * bay
        x1 = x0 + bay
        # --- 铺面柱（每间两侧各 18 宽） ---
        S.append(box(x0, SHOP_YF - 24, 0, x0 + 18, SHOP_YF, SHOP_Z + 20, C_PIER))
        if k == N_SHOP - 1:
            S.append(box(x1 - 18, SHOP_YF - 24, 0, x1, SHOP_YF, SHOP_Z + 20, C_PIER))
        # --- 店面玻璃（退进 4cm） ---
        gx0, gx1 = x0 + 18, x1 - 18
        S.append(box(gx0, SHOP_YF - 6, 6, gx1, SHOP_YF - 2, 192, C_SHOP_G))
        # --- 铝框：下槛 / 上槛 / 中挺 ---
        S.append(box(gx0, SHOP_YF - 8, 0, gx1, SHOP_YF - 1, 8, C_ALU))
        S.append(box(gx0, SHOP_YF - 8, 192, gx1, SHOP_YF - 1, 200, C_ALU))
        for t in (0.25, 0.5, 0.75):
            bx = gx0 + (gx1 - gx0) * t
            S.append(box(bx - 2.5, SHOP_YF - 9, 6, bx + 2.5, SHOP_YF - 1, 194, C_ALU))
        # --- 卷帘门盒（z 200..228），两间拉下来到 96 表示打烊 ---
        S.append(box(gx0, SHOP_YF - 6, 200, gx1, SHOP_YF - 1, SHOP_Z, C_SHUTTER))
        if k in (1, 3):
            S.append(box(gx0, SHOP_YF - 4, 96, gx1, SHOP_YF - 1, 200, C_SHUTTER))
        # --- 招牌横板：吊在二层楼板下并外挑 62cm（192..266）---
        #     顶边 266 高过栏杆底 240 ⇒ 从走廊看出去会遮住下沿 26cm，这是真的
        s0, s1 = x0 + 10, x1 - 10
        S.append(box(s0, SHOP_YF, 192, s1, SHOP_YF + 62, 266, C_SIGNAGE))
        # ⚠️ 板边只能做上下两条唇，整面贴会被它把招牌板全盖住（2026-10-30 踩过）
        S.append(box(s0, SHOP_YF + 62, 260, s1, SHOP_YF + 67, 266, C_PIER))   # 上唇
        S.append(box(s0, SHOP_YF + 62, 192, s1, SHOP_YF + 67, 197, C_PIER))   # 下唇
        # --- 遮阳篷（单号铺面有，制造参差） ---
        if k % 2 == 0:
            S.append(box(s0 + 12, SHOP_YF + 6, 176, s1 - 12, SHOP_YF + 92, 181, C_AWNING))
    return S


# ============================================================
# ⑦ 环境层 L2（2026-10-30）—— 对面楼体块 / 人行道 / 路缘石 / 电线杆 / 行道树
#    ⭐ 只有一条判据：栏杆外必须"有东西挡住天空"。
#    存在感来自遮挡，不来自细节 ⇒ 体块优先于铺装，铺装优先于装饰。
# ============================================================
C_WALK   = (176, 172, 164)   # 人行道铺装
C_CURB   = (196, 192, 184)   # 路缘石
C_ROAD   = ( 92,  92,  94)   # 车行道沥青
C_FAR    = (168, 162, 154)   # 对面楼体
C_FAR2   = (146, 140, 132)   # 对面楼体（第二栋，色差避免雷同）
C_PLINTH = (108, 104, 100)   # 对面楼一层基座（比楼体暗，别用浅灰，否则像贴了一条白胶带）
C_FARWIN = ( 62,  70,  78)   # 对面楼窗（暗）
C_POLE   = (132, 126, 118)   # 电线杆
C_TREE   = ( 96, 110,  86)   # 树冠
C_TRUNK  = (104,  92,  80)   # 树干
C_WIRE   = ( 58,  56,  54)   # 架空电线（细盒，白天是一根暗线）
C_LINE   = (188, 184, 176)   # 路面标线
C_CAR    = ( 88,  96, 104)   # 路边停车车身
C_CARG   = ( 46,  54,  62)   # 车窗
C_VERGE  = (116, 134,  94)   # 临街草坪（地块 verge）
C_LOT    = (166, 164, 158)   # 停车场/场地铺装（地块 lot）
C_YARD   = (104, 118,  92)   # 后院草/泥地（2026-10-30：原来楼后只有一块兜底平面，过曝成白纸）

WALK_Y0, WALK_Y1 = 540.0, 790.0
CURB_Y1          = 806.0
ROAD_Y1          = 1900.0
FAR_Y0, FAR_Y1   = 1900.0, 2700.0
YARD_Y0          = -4200.0   # 后院进深（楼后 y<0）。⚠️ 要盖到背面机位脚下（S7 站 y=-26m）
ENV_X0, ENV_X1   = -2000.0, FULL_X + 2400.0   # 地面铺装跟着车行道同宽，⛔ 别只铺到走廊尽头（会露断面）

# ============================================================
# ⑧ 布局文件（由 layout_editor.html 生成，Ronny 自己拖杆/灯/树/草/车）
#    ⭐ 读不到就回退到本文件里的内置默认值 —— 保证没有 _layout.json 时老渲染一模一样
# ============================================================
LAYOUT_PATH = os.path.join(ROOT, "_layout.json")
_LAYOUT_KEYS = ("poles", "lamps", "trees", "grass", "cars")

# 地块默认值（kind, x0, y0, x1, y1）。⭐ 2026-10-30：原来这四个是写死的常量，
#   编辑器里只有得看没得改。现在由 _layout.json 的 bands 驱动，而且可以有多块
#   （街角地块要两条车行道拼成 L 形，固定 4 条表达不了）。
_BAND_DEF = [
    ("walk", ENV_X0,   WALK_Y0, ENV_X1, WALK_Y1),   # 人行道
    ("curb", ENV_X0,   WALK_Y1, ENV_X1, CURB_Y1),   # 路缘石
    ("road", ENV_X0,   CURB_Y1, ENV_X1, ROAD_Y1),   # 车行道
    ("far",  -300.0,   FAR_Y0,  4200.0, FAR_Y1),    # 对面楼
]

_BAND_KINDS = ("walk", "curb", "road", "verge", "lot", "far")


def load_layout():
    try:
        with open(LAYOUT_PATH, encoding="utf-8") as f:
            d = json.load(f)
        for k in _LAYOUT_KEYS:
            if not isinstance(d.get(k), list):
                raise ValueError("缺字段或类型不对: " + k)
        return d
    except Exception as e:
        print("[LAYOUT] 没用布局文件（%s）⇒ 回退内置默认" % e)
        return None


def band_list(LAY):
    """把布局里的 bands 摊成 [(kind, x0,y0,x1,y1)]。
    ⚠️ 不信任文件内容：x/y 反了就换回来，非数字/尺寸过小就丢掉，绝不让坏数据把场景铺坏。
    没有 bands 字段（老布局）时退回 _BAND_DEF，保证老渲染一模一样。"""
    raw = (LAY or {}).get("bands")
    if not raw:
        return list(_BAND_DEF)
    out = []
    for b in raw:
        kind = b.get("kind") or b.get("id")
        if kind not in _BAND_KINDS:
            print("[BAND] 未知类型 %r ⇒ 跳过" % kind)
            continue
        try:
            x0, y0, x1, y1 = (float(b[k]) for k in ("x0", "y0", "x1", "y1"))
        except Exception:
            print("[BAND] %s 坐标不是数字 ⇒ 跳过" % kind)
            continue
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        # ⚠️ 只挡「退化成一个面」的矩形。原来卡 20cm，结果竖向的路缘石（16cm 宽）被当成坏数据丢掉了。
        if x1 - x0 < 1.0 or y1 - y0 < 1.0:
            print("[BAND] %s 尺寸退化(%.1f×%.1f) ⇒ 跳过" % (kind, x1 - x0, y1 - y0))
            continue
        out.append((kind, x0, y0, x1, y1))
    # 兜底：至少要有人行道和车行道，否则整个场景没有地面
    for k in ("walk", "road"):
        if not any(t[0] == k for t in out):
            out.extend(t for t in _BAND_DEF if t[0] == k)
            print("[BAND] 缺 %s ⇒ 补默认" % k)
    return out


def lot_pitches(LAY):
    """停车场划线：所有 lot 地块里带 pitch 的，返回 [(x0,y0,x1,y1,pitch)]。
    ⭐ 没有这排线，11 台车只是一排灰盒子，看不出是垂直车位（02.jpg 里最显眼的就是这排线）。"""
    out = []
    for b in ((LAY or {}).get("bands") or []):
        if (b.get("kind") or b.get("id")) != "lot":
            continue
        try:
            p = float(b.get("pitch") or 0)
            x0, y0, x1, y1 = (float(b[k]) for k in ("x0", "y0", "x1", "y1"))
        except Exception:
            continue
        if p <= 0:
            continue
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        out.append((x0, y0, x1, y1, p))
    return out


def build_env():
    E = []
    LAY = load_layout()
    BANDS = band_list(LAY)
    WALKS = [b for b in BANDS if b[0] == "walk"]
    FARS  = [b for b in BANDS if b[0] == "far"]
    PITCHES = lot_pitches(LAY)
    # --- 后院地坪（楼后 y<0）---
    # ⚠️ 原来这块只有 _bmod_day.py 里那个 60m 兜底平面，曝光一开就是一整片白纸。
    #    补真地坪：3cm 厚、贴图染色成低饱和草绿，让 Pine 有立地。
    if LAY and LAY["grass"]:
        for g in LAY["grass"]:
            E.append(box(g["x0"], g["y0"], 0, g["x1"], g["y1"], 3, C_YARD))
    else:
        E.append(box(ENV_X0, YARD_Y0, 0, ENV_X1, 0, 3, C_YARD))
    # --- 地块（人行道 / 路缘石 / 车行道 / 草地 / 铺装）：一块一个盒子，顺序即叠放顺序 ---
    #     ⚠️ 同一高度上两块重叠会 z-fighting。现在各类型高度不同（14/18/2/6/8），
    #        所以「草地压在车行道上」这种叠法不会闪，但也意味着高度不是真实构造，只是防闪。
    BAND_MAT = {
        "walk":  (C_WALK,  14.0),
        "curb":  (C_CURB,  18.0),
        "road":  (C_ROAD,   2.0),
        "verge": (C_VERGE,  6.0),
        "lot":   (C_LOT,    8.0),
    }
    for kind, x0, y0, x1, y1 in BANDS:
        if kind in BAND_MAT:
            col, hh = BAND_MAT[kind]
            E.append(box(x0, y0, 0, x1, y1, hh, col))
    # --- 停车场车位划线（lot 的 pitch）。画在铺装面上方 1cm，宽 6cm，不会 z-fighting ---
    for px0, py0, px1, py1, pp in PITCHES:
        _ph = BAND_MAT["lot"][1] + 1.0
        if (px1 - px0) >= (py1 - py0):
            _x = px0 + pp
            while _x < px1 - 1.0:
                E.append(box(_x - 5.0, py0, _ph, _x + 5.0, py1, _ph + 2.0, C_LINE))
                _x += pp
        else:
            _y = py0 + pp
            while _y < py1 - 1.0:
                E.append(box(px0, _y - 5.0, _ph, px1, _y + 5.0, _ph + 2.0, C_LINE))
                _y += pp
    # --- 车行道中心虚线（每条 road 各画一条，横竖自动判断）---
    for kind, x0, y0, x1, y1 in BANDS:
        if kind != "road":
            continue
        if (x1 - x0) >= (y1 - y0):
            _my = (y0 + y1) / 2.0
            _x = x0
            while _x < x1:
                E.append(box(_x, _my - 4.0, 2, min(_x + 240.0, x1), _my + 4.0, 4, C_LINE))
                _x += 620.0
        else:
            _mx = (x0 + x1) / 2.0
            _y = y0
            while _y < y1:
                E.append(box(_mx - 4.0, _y, 2, _mx + 4.0, min(_y + 240.0, y1), 4, C_LINE))
                _y += 620.0
    # --- 对面楼（每块 far 拆成三栋，高矮错开，避免像一堵墙）---
    for _kind, fx0_all, fy0, fx1_all, fy1 in FARS:
        _n = 3
        _gap = (fx1_all - fx0_all) * 0.049
        _seg = ((fx1_all - fx0_all) - _gap * (_n - 1)) / _n
        for _i, _fh in enumerate((980.0, 620.0, 1180.0)):
            fx0 = fx0_all + _i * (_seg + _gap)
            fx1 = fx0 + _seg
            col = C_FAR if _i != 1 else C_FAR2
            E.append(box(fx0, fy0, 0, fx1, fy1, _fh, col))
            # 一层基座压暗一点：让远处楼读成"有店面/车库的楼"而不是一块板
            E.append(box(fx0, fy0 - 3, 0, fx1, fy0, 150, C_PLINTH))
            # 屋顶压顶（浅色，把轮廓从天空里拉出来）
            E.append(box(fx0 - 6, fy0 - 6, _fh, fx1 + 6, fy1 + 6, _fh + 10, C_CURB))
            # 窗阵：朝街那一面（y = fy0）
            ncol = max(3, int((fx1 - fx0) / 230))
            nrow = max(2, int(_fh / 300))
            for c in range(ncol):
                for r in range(nrow):
                    wx = fx0 + (fx1 - fx0) * (c + 0.5) / ncol - 62
                    wz = 200 + r * 300
                    if wz + 150 > _fh: continue
                    E.append(box(wx, fy0 - 2, wz, wx + 124, fy0 + 1, wz + 150, C_FARWIN))
    # 电线杆/路灯/车默认落位用「主街人行道」——取面积最大的那块 walk
    WK = max(WALKS, key=lambda b: (b[3] - b[1]) * (b[4] - b[2])) if WALKS else _BAND_DEF[0]
    CB = next((b for b in BANDS if b[0] == "curb"), (None, ENV_X0, WALK_Y1, ENV_X1, CURB_Y1))
    # --- 电线杆 ---
    # ⚠️ 布局里存的是「杆心 (x,y)」；杆身盒 26×26。
    # ⭐ 2026-10-30 修 bug：原来所有杆的 y 都被强行写成 `WK[4]-34`（主街人行道外缘），
    #    布局里 `p["y"]` 存了却在渲染时完全没被读 —— 编辑器里把杆拖到草坪上，
    #    渲出来它还立在人行道边缘。结果就是「杆子永远在人行道上、拖不动」。
    #    现在杆心 = (p.x, p.y)，只有缺 y 才回退到人行道外缘（老布局仍一模一样）。
    PINFO = ([(float(p["x"]), float(p.get("y", WK[4] - 21.0))) for p in LAY["poles"]]
             if LAY else [(353.0, WK[4] - 21.0), (993.0, WK[4] - 21.0), (1653.0, WK[4] - 21.0)])
    for px, py in PINFO:
        E.append(box(px - 13, py - 13, 0, px + 13, py + 13, 920, C_POLE))
        E.append(box(px - 83, py - 10, 860, px + 83, py + 10, 876, C_POLE))   # 横担
    # --- 架空电线（相邻杆之间拉两道，白天就是两条暗线，澳洲街上抬眼全是）---
    #     ⭐ 杆可以沿任意方向排，所以按「跨度大的那个轴」决定线是横拉还是竖拉。
    for (ax, ay), (bx_, by) in zip(PINFO[:-1], PINFO[1:]):
        for wz in (872.0, 856.0):
            if abs(bx_ - ax) >= abs(by - ay):
                E.append(box(min(ax, bx_), min(ay, by) - 1.0, wz,
                             max(ax, bx_), min(ay, by) + 1.0, wz + 2.2, C_WIRE))
            else:
                E.append(box(min(ax, bx_) - 1.0, min(ay, by), wz,
                             min(ax, bx_) + 1.0, max(ay, by), wz + 2.2, C_WIRE))
    # --- 路灯（2026-10-30 新增，位置由布局文件控制）---
    #     人行道上 4.5m 灯柱 + 朝街心探出的灯臂 + 灯具。⛔ 不做光晕，那是后期的事。
    for lp in (LAY["lamps"] if LAY else []):
        lx = float(lp["x"])
        lh = float(lp.get("h", 450.0))
        # ⭐ y 由布局给（编辑器里的灯可以贴人行道里侧任意位置）；缺省 = 人行道外缘往内 30cm
        sy = float(lp.get("y", WK[4] - 30.0))
        E.append(box(lx - 5, sy - 5, 0, lx + 5, sy + 5, lh, C_POLE))                  # 柱
        d = 1.0 if lp.get("side", "right") != "left" else -1.0
        E.append(box(min(lx, lx + d * 90), sy - 4, lh - 14, max(lx, lx + d * 90), sy + 4, lh - 6, C_POLE))  # 臂
        E.append(box(lx + d * 90 - 16, sy - 11, lh - 20, lx + d * 90 + 16, sy + 11, lh - 14, C_ALU))       # 灯具
    # --- 行道树：暂不建。⚠️ 盒体做不出树冠，一渲就是"一堵绿墙"，
    #     站在二层外廊往外看会被它整个吃掉。等有低模树或剪影贴图再加回来。---
    # --- 路边停车（车身 + 车顶，最强的尺度参照物）---
    #     车深固定 160cm（cy 是临路那一侧的内缘），车长与落位由布局文件给
    #     ⭐ rot:90 = 垂直车位（车头朝楼，车长沿 y 轴）。照片 02.jpg 楼前就是这种排法。
    CARS = ([(c["x"], c["y"], c["len"], float(c.get("rot", 0) or 0)) for c in LAY["cars"]] if LAY
            else [(1500.0, CB[4] + 40, 430.0, 0.0), (2500.0, CB[4] + 40, 460.0, 0.0)])
    for cx, cy, cl, crot in CARS:
        cx = float(cx); cy = float(cy); cl = float(cl)
        if int(crot) % 180 == 90:
            # 车头朝上（y 小的一侧）：车身 x 是 160 宽
            E.append(box(cx,           cy,        26, cx + 160,      cy + cl,      96,  C_CAR))
            E.append(box(cx + 15,      cy + 70,   96, cx + 145,      cy + cl - 80, 146, C_CAR))
            E.append(box(cx + 12,      cy + 80,  100, cx + 18,       cy + cl - 90, 142, C_CARG))
            E.append(box(cx + 142,     cy + 80,  100, cx + 148,      cy + cl - 90, 142, C_CARG))
        else:
            E.append(box(cx,           cy,        26, cx + cl,       cy + 160,     96,  C_CAR))
            E.append(box(cx + 70,      cy + 15,   96, cx + cl - 80,  cy + 145,     146, C_CAR))
            E.append(box(cx + 80,      cy + 12,  100, cx + cl - 90,  cy + 18,      142, C_CARG))
            E.append(box(cx + 80,      cy + 142, 100, cx + cl - 90,  cy + 148,     142, C_CARG))
    return E

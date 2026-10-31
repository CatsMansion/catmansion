# -*- coding: utf-8 -*-
"""生成方案 B：车位退到人行道后面（住宅规范版）。

⭐ 与上一版（A）的关键差别：90° 垂直车位**必须配一条车道**，否则 11 台车
   根本没路径开进车位。上一版承诺的「+450cm」装不下车道，所以 B 的真实
   下限是 +950cm。这里按成立的那一版生成，并把代价写进 _note。

y 轴（cm）：
    540        建筑外廊外沿（_gmod.py: ROOM_Y 420 + COR 120）
    540- 690   建筑前步道     150  walk
    690-1215   车位           525  lot    11 个 90°，车头朝楼
    1215-1765  内部车道       550  road   ⭐ 新增，车从这里倒进车位
    1765-1915  绿化带/设施带  150  verge  杆、灯、行道树
    1915-2165  临街人行道     250  walk
    2165-2181  路缘            16  curb
    2181-3275  主街 车行道 1094 road
    3275-3525  对侧人行道     250  walk
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- 尺寸 ----------
PATH_W   = 150.0
BAY_D    = 525.0
LANE_W   = 580.0
VERGE_W  = 150.0
SIDEWALK = 250.0
CURB     = 16.0
ROAD_W   = 1094.0
FAR_WALK = 250.0
B_FRONT  = 540.0

y0_path = B_FRONT
y1_path = y0_path + PATH_W          # 690
y0_lot  = y1_path
y1_lot  = y0_lot + BAY_D            # 1215
y0_lane = y1_lot
y1_lane = y0_lane + LANE_W          # 1765
y0_vrg  = y1_lane
y1_vrg  = y0_vrg + VERGE_W          # 1915
y0_sw   = y1_vrg
y1_sw   = y0_sw + SIDEWALK          # 2165
y0_curb = y1_sw
y1_curb = y0_curb + CURB            # 2181
y0_road = y1_curb
y1_road = y0_road + ROAD_W          # 3275
y0_fw   = y1_road
y1_fw   = y0_fw + FAR_WALK          # 3525

# ---------- x ----------
LOT_X0, LOT_X1 = -50.0, 2912.0
LAWN_X0, LAWN_X1 = 2912.0, 3900.0
PATH_N_X0, PATH_N_X1 = 3400.0, 3600.0    # 南北向步道（绕开车道的人行动线）
XW_X0 = 550.0                             # crossover 西端开口止于此
DW0, DW1, DC1, DR1 = 3900.0, 4160.0, 4176.0, 5270.0

bands = []


def add(kind, name, x0, y0, x1, y1, **kw):
    b = dict(kind=kind, name=name, x0=float(x0), y0=float(y0),
             x1=float(x1), y1=float(y1))
    b.update(kw)
    bands.append(b)
    return b


# ① 建筑前步道：从西端一路铺到 侧街 人行道
add("walk", "建筑前步道", LOT_X0, y0_path, LAWN_X1, y1_path, locked=True)

# ② 车位
add("lot", "楼前停车位", LOT_X0, y0_lot, LOT_X1, y1_lot, pitch=250.0, locked=True)

# ③ 内部车道（贯到西端 crossover）
add("lot", "内部车道", LOT_X0, y0_lane, LOT_X1, y1_lane, locked=True)

# ④ 绿化带 / 设施带：被南北步道切成两段，西端给 crossover 让口
add("verge", "临街绿化带-西", XW_X0, y0_vrg, PATH_N_X0, y1_vrg)
add("verge", "临街绿化带-东", PATH_N_X1, y0_vrg, LAWN_X1, y1_vrg)

# ⑤ 临街人行道：同样被南北步道切
add("walk", "临街人行道-西", XW_X0, y0_sw, PATH_N_X0, y1_sw, locked=True)
add("walk", "临街人行道-东", PATH_N_X1, y0_sw, LAWN_X1, y1_sw, locked=True)

# ⑥ crossover（车行道口）：把绿化带 + 人行道 + 路缘在西端挖开
add("lot", "车道出入口", LOT_X0, y0_vrg, XW_X0, y1_curb, locked=True)

# ⑦ 主街 街
add("curb", "主街 路缘", XW_X0, y0_curb, DC1, y1_curb, locked=True)
add("road", "主街 车行道", -2600.0, y0_road, DC1, y1_road, locked=True)
add("walk", "主街 对侧人行道", -2600.0, y0_fw, DC1, y1_fw, locked=True)

# ⑧ 侧街 街
add("walk", "侧街 人行道", DW0, -2600.0, DW1, y0_curb, locked=True)
add("curb", "侧街 路缘", DW1, -2600.0, DC1, y0_curb, locked=True)
add("road", "侧街 车行道", DC1, -2600.0, DR1, y1_road, locked=True)
add("far", "对面楼", DR1, -2600.0, 7600.0, y1_road, locked=True)

# ⑨ 侧院草坪：北块 + 中块（中块被南北步道切两半）
add("verge", "侧院草坪-北", LAWN_X0, -4200.0, LAWN_X1, y0_path)
add("verge", "侧院草坪-中-西", LAWN_X0, y1_path, PATH_N_X0, y1_lane)
add("verge", "侧院草坪-中-东", PATH_N_X1, y1_path, LAWN_X1, y1_lane)

# ⑩ 南北步道：楼前步道 → 临街人行道，全程不压车道
add("walk", "入户步道（南北）", PATH_N_X0, y1_path, PATH_N_X1, y0_sw, locked=True)

# ---------- 车：11 台，车头朝楼 ----------
cars = []
bx = LOT_X0
for _ in range(11):
    cars.append(dict(x=bx + (250.0 - 160.0) / 2.0, y=y0_lot + 55.0, len=430.0, rot=90))
    bx += 250.0

# ---------- 杆 / 灯：落在临街绿化带里 ----------
poles = [dict(x=780.0, y=y0_vrg + 75.0),
         dict(x=2260.0, y=y0_vrg + 75.0),
         dict(x=3720.0, y=y0_vrg + 75.0)]
lamps = [dict(x=1520.0, y=y0_vrg + 75.0, h=450.0, side="right"),
         dict(x=3000.0, y=y0_vrg + 75.0, h=450.0, side="right")]

# ---------- 组装 ----------
base = json.load(open(os.path.join(HERE, "_layout_oconnor_A.json.bak"), encoding="utf-8"))
out = dict(base)
out["bands"] = bands
out["cars"] = cars
out["poles"] = poles
out["lamps"] = lamps
out["building"] = {
    "box": {"x0": 0.0, "y0": 0.0, "x1": 2912.0, "y1": 540.0},
    "corr": {"y0": 420.0, "y1": 540.0},
    "units": 8, "noStart": 201, "label": "CatMansion 公寓",
}
out["_note"] = ("方案B 2026-10-31：车位退到人行道后，增设 580 内部车道；"
                "绿化带150 + 人行道250 + 路缘16 全在车位外侧；"
                "crossover 在西端 x -50..550")
out["_plan"] = "B"

s = json.dumps(out, ensure_ascii=False, indent=1)
for fn in ("_layout_oconnor.json", "_layout.json", "_layout_oconnor_B.json"):
    open(os.path.join(HERE, fn), "w", encoding="utf-8").write(s)

print("B 版已写入：11→%d 地块 / %d 车 / %d 杆 / %d 灯" % (len(bands), len(cars), len(poles), len(lamps)))
print("y: 步道 %.0f-%.0f | 车位 %.0f-%.0f | 车道 %.0f-%.0f | 绿化 %.0f-%.0f | 人行道 %.0f-%.0f | 路缘 %.0f-%.0f | 车行道 %.0f-%.0f"
      % (y0_path, y1_path, y0_lot, y1_lot, y0_lane, y1_lane,
         y0_vrg, y1_vrg, y0_sw, y1_sw, y0_curb, y1_curb, y0_road, y1_road))
print("前场深度（外廊→路缘）= %.0f cm（A 版 691，+%.0f）" % (y1_curb - B_FRONT, (y1_curb - B_FRONT) - 691))

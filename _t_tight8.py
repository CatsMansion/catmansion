# -*- coding: utf-8 -*-
"""紧密版（A）+ 车位收到 8 格（8 户一户一位），东端 962cm 改绿化。

为什么这么改：
  11 格铺满到 x=2912 时，从街上看到的是一条 27.5m 长的车墙，车直接撞到草坪边。
  收到 8 格（x -50..1950）+ 东端 962 绿化之后，画面读成「楼 / 车 / 草」三层，
  而不是「楼 / 一堵车」。
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(HERE, "_layout_oconnor_A.json.bak"), encoding="utf-8"))

LOT_X0, LOT_Y0, LOT_Y1 = -50.0, 690.0, 1215.0
PITCH, CAR_W, CAR_L, N = 250.0, 160.0, 430.0, 8
LOT_X1 = LOT_X0 + N * PITCH          # 1950
LAWN_X1 = 2912.0

bands = []
for b in A["bands"]:
    if b["name"] == "楼前停车前场":
        b = dict(b)
        b["x1"] = LOT_X1
        b["pitch"] = PITCH
        b["name"] = "楼前停车位"
    bands.append(b)

# 东端绿化（补在车位带原来的尾巴上）
bands.append(dict(kind="verge", name="车位东端绿化",
                  x0=LOT_X1, y0=LOT_Y0, x1=LAWN_X1, y1=LOT_Y1))

cars = [dict(x=LOT_X0 + i * PITCH + (PITCH - CAR_W) / 2.0,
             y=LOT_Y0 + 55.0, len=CAR_L, rot=90) for i in range(N)]

out = dict(A)
out["bands"] = bands
out["cars"] = cars
out["_note"] = ("方案A-紧凑 2026-10-31：8 户 8 位（车位收到 x=-50..1950），"
                "东端 962cm 改绿化；楼前步道 150 + 车位 525 + 路缘 16")
out["_plan"] = "A"

s = json.dumps(out, ensure_ascii=False, indent=1)
for fn in ("_layout_oconnor.json", "_layout.json"):
    open(os.path.join(HERE, fn), "w", encoding="utf-8").write(s)

print("地块 %d | 车 %d | 杆 %d | 灯 %d" % (len(bands), len(cars), len(out["poles"]), len(out["lamps"])))
print("车位 x %.0f..%.0f（%d 格）｜东端绿化 %.0f..%.0f" % (LOT_X0, LOT_X1, N, LOT_X1, LAWN_X1))

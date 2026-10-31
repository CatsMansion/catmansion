# -*- coding: utf-8 -*-
"""把楼前停车位里的车从 8 台减到 2 台。

为什么不减车位：Ronny 之前定过「起码每户一个车位」= 8 个车位（lot 的 pitch 8 格不动），
这次只减「停着的车」。正午的住宅前场本来就大半是空的。

为什么选第 3 格和第 7 格（x=495 / x=1495）：
  两车隔 4 格（1000cm）⇒ 中间留出能看穿到铺面的空隙，两端也各留空，
  读成「有空位的停车场」，而不是「两辆车孤零零杵在中间」。
"""
import json, shutil, os

CARS = [
    {"x": 495.0,  "y": 745.0, "len": 430.0, "rot": 90},
    {"x": 1495.0, "y": 745.0, "len": 430.0, "rot": 90},
]

for f in ("_layout.json", "_layout_oconnor.json"):
    shutil.copy(f, f + ".bak8cars") if not os.path.exists(f + ".bak8cars") else None
    d = json.load(open(f, encoding="utf-8"))
    d["cars"] = [dict(c) for c in CARS]
    d["_note"] = ("方案A-紧凑 2026-10-31 修订：8 台车 → 2 台（停第 3/第 7 格），"
                  "8 个车位不动；楼前步道 150 + 车位 525 + 路缘 16")
    json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("写入", f, "cars =", len(d["cars"]))

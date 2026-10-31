# -*- coding: utf-8 -*-
"""白天日光渲染（EEVEE）—— 灰模也能看出材质层次与硬阴影。
⭐ 为什么单独一支：原 _bmod.py 用 Workbench FLAT + 无阴影，是为了读"几何对位"；
   但要判断"白天看着像不像有人住的楼"，必须给真光。两支并存，互不覆盖输出目录。
用法：blender -b -P _bmod_day.py -- E3_d208_34 [分辨率百分比]
"""
import bpy, sys, os, json, math
from mathutils import Vector

ROOT = r"D:\mv\pierce_wide"
OUT  = os.path.join(ROOT, "_bmod_day")
os.makedirs(OUT, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TAGS = [a for a in argv if not a.isdigit()] or ["E3_d208_34", "E1_corr_east"]
PCT  = int([a for a in argv if a.isdigit()][0]) if any(a.isdigit() for a in argv) else 100

# ---------------------------------------------------------------
# 变体开关（只影响渲染，不改几何；默认全关 = 旧行为）
#   BMOD_TINT=1   贴图染色归一化（见 TEXMEAN）
#   BMOD_SPEC=_x  输出文件名后缀，避免覆盖旧图
# ---------------------------------------------------------------
TINT_ON = os.environ.get("BMOD_TINT") == "1"
LIGHT_ON = os.environ.get("BMOD_LIGHT") == "1"
SPEC    = os.environ.get("BMOD_SPEC", "")
EXPO_ADD = float(os.environ.get("BMOD_EXPO", "0") or 0)

SCENE = json.load(open(os.path.join(ROOT, "_bmod", "scene.json"), encoding="utf-8"))
CAMS  = json.load(open(os.path.join(ROOT, "_bmod", "cameras_export.json"), encoding="utf-8"))
CM = 0.01
FACES = [(0,1,3,2),(4,6,7,5),(0,2,6,4),(1,5,7,3),(0,4,5,1),(2,3,7,6)]

scene = bpy.context.scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)


# ---------- 灰阶 → 真实色（只影响渲染，不动几何） ----------
# 依据 6 张白天实拍取色：南方/东南亚老公寓的脏米白墙 + 深色墙裙 +
# 锈铁防盗网 + 暗青玻璃 + 奶白空调壳 + 彩色晾晒衣物
PALETTE = {
 (190, 184, 173): (206, 198, 183),   # 走廊侧外墙：脏米白
 (150, 145, 136): (186, 178, 164),   # 户界墙
 (168, 162, 150): (172, 166, 156),   # 楼板 / 地面
 (132, 127, 119): (178, 172, 162),   # 天花
 (146, 141, 132): (158, 152, 142),   # 台阶
 ( 96,  92,  86): ( 68,  72,  70),   # 栏杆：深铁灰
 (156, 150, 140): ( 74,  80,  74),   # 墙裙：深灰绿（压暗，不然阳光下与墙分不开）
 (250, 246, 234): (255, 249, 232),   # 壁灯罩：暖白
 (178, 182, 186): (198, 202, 206),   # 表札/信箱：不锈钢
 (120, 122, 124): (102, 104, 106),   # 电表箱
 (216, 214, 206): (230, 228, 218),   # 空调外机
 ( 78,  76,  72): ( 92,  68,  54),   # 防盗网：锈铁
 ( 96, 102, 106): ( 52,  62,  70),   # 窗玻璃：暗青
 (198, 190, 178): (238, 236, 230),   # 衣物 A 白
 (176, 186, 196): ( 92, 124, 158),   # 衣物 B 牛仔蓝
 (204, 174, 176): (214, 152, 158),   # 衣物 C 浅粉
 (196, 178, 142): (204, 178, 118),   # 衣物 D 米黄
 (162, 164, 168): (176, 176, 170),   # 管道
 (122, 134, 128): ( 84, 100,  90),   # 雨棚
 (104,  98,  90): (112,  74,  66),   # 地垫
 (146, 128, 112): (170, 106,  78),   # 花盆
 (200, 202, 198): (208, 210, 206),   # 铝窗框
 (152, 166, 174): (138, 162, 176),   # 封闭玻璃盒
 ( 44,  52,  58): ( 34,  40,  46),   # 店面玻璃
 ( 84,  82,  86): ( 54,  52,  56),   # 招牌板
 (152, 148, 142): (166, 162, 154),   # 卷帘门
 (176, 170, 158): (194, 188, 176),   # 铺面柱
 ( 74,  76,  78): ( 56,  58,  60),   # 屋顶面
 # ---- 环境层 L2（grp=4）----
 (176, 172, 164): (186, 182, 172),   # 人行道铺装
 (196, 192, 184): (210, 206, 198),   # 路缘石（石头比铺装亮一档）
 ( 92,  92,  94): ( 96,  96,  98),   # 车行道沥青（不压暗白天会发白；但也别压成黑带）
 (168, 162, 154): (150, 130, 116),   # 对面楼 A（贴图覆盖，此项只兜底）
 (146, 140, 132): (128, 120, 108),   # 对面楼 B（压暗，Plaster 太白发灰）
 (108, 104, 100): ( 88,  84,  80),   # 对面楼一层基座
 ( 62,  70,  78): ( 34,  40,  46),   # 对面楼窗：比本楼玻璃更暗（远景读作洞）
 (132, 126, 118): (170, 164, 155),   # 电线杆：比楼体亮一档，否则糊进背景
 ( 96, 110,  86): ( 72,  96,  60),   # 树冠
 (104,  92,  80): ( 84,  70,  56),   # 树干
 ( 58,  56,  54): ( 40,  38,  36),   # 架空电线
 (188, 184, 176): (206, 202, 194),   # 路面标线
 (88,  96, 104): ( 96, 104, 112),   # 路边车身
 (46,  54,  62): ( 34,  42,  50),   # 车窗
 (116, 134,  94): ( 96, 126,  64),   # 临街草坪（地块 verge）：比后院草绿一档，它是修过的草坪
 (166, 164, 158): (152, 150, 144),   # 停车场/场地铺装（地块 lot）：浅暖灰混凝土
 (104, 118,  92): (101, 122,  71),   # 后院草/泥地。⭐ 2026-10-30 按实拍校准：
                                     #   原 (106,122,94) 的 s=0.23 读起来是一块灰绿的纸；
                                     #   实拍草坪中位 (79,96,44) s=0.54、h=80°（偏黄）。
                                     #   折中取 h=85° s=0.42 v=0.48 —— 比实拍亮一档（二次元要亮），但不再是灰的。
}

def realcol(rgb):
    return PALETTE.get(tuple(int(v) for v in rgb), tuple(int(v) for v in rgb))

if TINT_ON:
    PALETTE.update({
      (190, 184, 173): (133, 106,  84),   # 走廊侧外墙：Bricks097 本色（这本来就是砖）
      (150, 145, 136): (120,  96,  78),   # 户界墙：同砖，压深一档
      (168, 162, 150): (176, 170, 158),   # 楼板 / 楼板端面：浅暖灰混凝土
      (132, 126, 118): ( 92,  82,  70),   # 电线杆：木杆（原来是白水泥柱，很假）
      (216, 214, 206): (206, 204, 196),   # 空调外机：压一档，别抢
      (152, 166, 174): (118, 142, 158),   # 封闭玻璃盒：偏冷蓝，别读成白板
    })

# ============================================================
# ⭐ BMOD_DARK=1 —— 深色金属构件（2026-10-30 按 Ronny 家附近实拍）
# 依据：参考图里那几栋楼最抓眼的不是砖、不是墙色，而是「近黑的金属线性构件」——
#   外挂铁梯 / 穿孔铝板栏板 / 雨棚边 / 深色铝合金窗框。它们把明度对比拉开，
#   是「像实景」和「像灰白纸板模型」之间最大的那一个差别。
# ⛔ 只改材质色，不动几何、不动灯光。⇒ 可以单独开关，能和 BMOD_WARM 叠加。
# ============================================================
DARK_ON = os.environ.get("BMOD_DARK", "") in ("1", "2")
DARK2   = os.environ.get("BMOD_DARK", "") == "2"
WARM_ON = os.environ.get("BMOD_WARM") == "1"

if DARK_ON:
    PALETTE.update({
      ( 96,  92,  86): ( 38,  40,  42),   # 栏杆 / 扶手墙：近黑铁灰（原 68,72,70）
      (200, 202, 198): ( 58,  60,  62),   # 铝窗框 → 深灰铝合金（原 208,210,206）
      (122, 134, 128): ( 42,  50,  48),   # 雨棚 / 遮阳（原 84,100,90）
      (178, 182, 186): ( 96, 100, 104),   # 表札 / 信箱：暗拉丝不锈钢
      (152, 148, 142): ( 78,  76,  74),   # 卷帘门盒
      ( 84,  82,  86): ( 28,  28,  30),   # 招牌板
      (132, 126, 118): ( 88,  82,  76),   # 电线杆：深木杆
      ( 88,  96, 104): ( 44,  48,  54),   # 路边车身（原来反照率 96 在强光下白成一块泡沫）
      ( 46,  54,  62): ( 20,  24,  28),   # 车窗
      ( 78,  76,  72): ( 74,  54,  42),   # 防盗网：锈铁（略压深，别跳成橘色）
      ( 44,  52,  58): ( 22,  26,  30),   # 店面玻璃：压到近黑（这张铺面玻璃是下半幅最大的面）
      (176, 170, 158): (150, 144, 134),   # 铺面柱：陪衬压一档，别比墙亮
    })

if DARK2:
    # ⭐ 第二档：把「二层那整片栏板」改成炭灰金属板。
    #    参考图 03/04/06/07 里，阳台栏板 / 外挂铁梯全是这种近黑的板 + 细金属框。
    #    我们这块目前是一整片 110cm 高的实心抹灰墙 —— 颜色再灰也还是一大片灰。
    #    ⛔ 只改材质色，不改几何：它仍然是实心墙，只是看起来像金属板。
    PALETTE.update({
      ( 96,  92,  86): ( 26,  28,  30),   # 栏板墙 → 炭灰金属板
      (206, 200, 188): ( 96, 100, 104),   # 扶手压顶 → 暗铝（原奶白，让它收边）
      (146, 141, 132): ( 96,  96,  96),   # 台阶 / 栏板底脚
    })

# ============================================================
# ⭐ BMOD_KEYMAP=1 —— 诊断用「材质分区图」
# 把每个候选色号涂成唯一的高饱和色，渲一张就知道「画面里那一大块到底是谁」。
# ⛔ 只用于定位，绝不出片。（当初就是因为不知道横向大带子是楼板还是栏杆，
#    改了半天「栏杆」结果画面上根本没那根东西。）
# ============================================================
KEYMAP_MARK = {
 (190, 184, 173): (255,   0,   0),   # 走廊侧外墙      → 红
 (168, 162, 150): (  0, 200,   0),   # 楼板/地面       → 绿
 (132, 127, 119): (  0,  80, 255),   # 天花            → 蓝
 ( 96,  92,  86): (255, 230,   0),   # 栏杆            → 黄
 (206, 200, 188): (255,   0, 255),   # 栏杆压顶        → 洋红
 ( 74,  76,  78): (  0, 230, 230),   # 屋顶面          → 青
 (156, 150, 140): (255, 130,   0),   # 墙裙            → 橙
 (146, 141, 132): (140,   0, 220),   # 台阶            → 紫
 (200, 202, 198): (255, 150, 150),   # 铝窗框          → 粉
 (122, 134, 128): (140, 255, 140),   # 雨棚            → 浅绿
 (216, 214, 206): (150, 150, 255),   # 空调外机        → 浅蓝
 (176, 170, 158): (255, 255, 130),   # 铺面柱/腰墙     → 奶黄
 (150, 145, 136): (120,  80,  20),   # 户界墙          → 褐
 (152, 166, 174): (  0, 160, 255),   # 封闭玻璃盒      → 天蓝
}
if os.environ.get("BMOD_KEYMAP") == "1":
    # ⛔ 染色（TINT）会盖掉外墙，所以分区图必须在 TINT 之后、DARK 之前生效
    PALETTE.update(KEYMAP_MARK)
elif os.environ.get("BMOD_KEYMAP") == "2":
    # 第二轮：标记剩下那些「第一轮没认出来」的色号
    PALETTE.update({
      (176, 172, 164): (255,   0,   0),   # 人行道铺装      → 红
      (196, 192, 184): (255, 140,   0),   # 路缘石          → 橙
      ( 92,  92,  94): (255,   0, 255),   # 车行道沥青      → 洋红
      (152, 148, 142): (0,   200,   0),   # 卷帘门盒        → 绿
      ( 44,  52,  58): (  0,   0, 255),   # 店面玻璃        → 蓝
      ( 84,  82,  86): (255, 255,   0),   # 招牌板          → 黄
      (178, 182, 186): (150,   0, 220),   # 表札/信箱       → 紫
      (162, 164, 168): (255, 150, 200),   # 排水立管        → 粉
      (104,  98,  90): (130,  70,   0),   # 地垫            → 褐
      (150, 144, 134): (  0, 230, 230),   # 户内隔断        → 青
      (250, 246, 234): (255, 255, 255),   # 壁灯罩          → 白
      (120, 122, 124): (  0,   0,   0),   # 电表箱          → 黑
    })

# ---------- 材质 ----------
_mats = {}
def _principled(m):
    """⭐ 按 bl_idname 找，不按名字 —— 本机 Blender 是中文界面，
       节点叫「原理化 BSDF」，写死 "Principled BSDF" 会 KeyError。"""
    for n in m.node_tree.nodes:
        if n.bl_idname == 'ShaderNodeBsdfPrincipled':
            return n
    raise RuntimeError("no Principled BSDF in " + m.name)

def mat(rgb, rough=0.82, metal=0.0):
    key = (tuple(rgb), rough, metal)
    if key in _mats: return _mats[key]
    m = bpy.data.materials.new("M_%02x%02x%02x" % tuple(rgb))
    m.use_nodes = True
    b = _principled(m)
    b.inputs["Base Color"].default_value = (rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    _mats[key] = m
    return m


# ============================================================
# 贴图（ambientCG · 全部 CC0 · 可商用）
# ⭐ 用「世界坐标盒式 UV」：同一材质在任何大小的盒子上砖缝尺度一致，
#    ⛔ 不用 Generated/Smart UV —— 那会让小盒子的砖变成大砖。
# ============================================================
TEXROOT = os.path.join(ROOT, "_tex")
TEX = {                      # 颜色键 -> (贴图文件, tile 边长 cm)
 (190, 184, 173): ("Bricks097_1K-JPG_Color.jpg",  106.0),  # 外墙：红砖（14 皮/tile × 7.6cm）
 (156, 150, 140): ("Plaster001_1K-JPG_Color.jpg", 130.0),   # 墙裙：抹灰
 (150, 145, 136): ("Concrete034_1K-JPG_Color.jpg",200.0),   # 户界墙
 (168, 162, 150): ("Concrete034_1K-JPG_Color.jpg",220.0),   # 楼板
 (132, 127, 119): ("Plaster001_1K-JPG_Color.jpg",200.0),    # 天花
 (146, 141, 132): ("Concrete034_1K-JPG_Color.jpg",150.0),   # 台阶
 ( 96,  92,  86): ("Concrete034_1K-JPG_Color.jpg",140.0),   # 栏杆
 (206, 200, 188): ("Plaster001_1K-JPG_Color.jpg",110.0),    # 栏杆压顶
 (176, 170, 158): ("Plaster001_1K-JPG_Color.jpg",150.0),    # 铺面柱/腰墙
 ( 74,  76,  78): ("Asphalt033_1K-JPG_Color.jpg", 320.0),   # 屋顶面
 # ---- 环境层 L2 ----
 (176, 172, 164): ("Concrete034_1K-JPG_Color.jpg", 240.0),      # 人行道：灰水泥板（PavingStones 偏棕，白天读成泥地）
 (196, 192, 184): ("Concrete034_1K-JPG_Color.jpg", 140.0),      # 路缘石
 ( 92,  92,  94): ("Asphalt033_1K-JPG_Color.jpg", 520.0),       # 车行道（tile 放很大，避免纹路重复太密）
 (168, 162, 154): ("Bricks097_1K-JPG_Color.jpg", 106.0),        # 对面楼 A：红砖，与本楼同一套尺度
 (146, 140, 132): ("Concrete048_1K-JPG_Color.jpg", 260.0),    # 对面楼 B：暖灰水泥
 (108, 104, 100): ("Concrete048_1K-JPG_Color.jpg", 200.0),    # 对面楼基座
 (132, 126, 118): ("Concrete034_1K-JPG_Color.jpg", 220.0),      # 电线杆
 (116, 134,  94): ("Asphalt033_1K-JPG_Color.jpg", 360.0),       # 临街草坪：同后院，用沥青细骨料当草皮噪声
 (166, 164, 158): ("Concrete034_1K-JPG_Color.jpg", 260.0),       # 场地铺装：混凝土
 (104, 118,  92): ("Asphalt033_1K-JPG_Color.jpg", 420.0),       # 后院：拿沥青细骨料当草/泥地噪声（纯色块会读成绿纸）
}
_texcache = {}
# ⭐ 贴图均值（PIL 实测，见 _tex 统计）。用途：染色归一化后「平均色 = PALETTE 目标色」，
#    贴图细节保留、明度/色相可控。⛔ 不给 tint 的话 texmat 会把 PALETTE 整个丢掉
#    （Concrete034 均值 184 的中性灰会把栏杆/楼板/台阶/电线杆全同化成一块水泥）。
TEXMEAN = {
 "Concrete034_1K-JPG_Color.jpg": (184, 184, 184),
 "Concrete048_1K-JPG_Color.jpg": (162, 152, 135),
 "Plaster001_1K-JPG_Color.jpg":  (215, 211, 208),
 "Bricks097_1K-JPG_Color.jpg":   (133, 106,  84),
 "Asphalt033_1K-JPG_Color.jpg":  ( 86,  82,  72),
}
def texmat(rgb, rough=0.85):
    key = (rgb, rough)
    if key in _texcache: return _texcache[key]
    fn, tile = TEX[rgb]
    m = bpy.data.materials.new("T_%s_%02x%02x%02x" % (fn[:9], rgb[0], rgb[1], rgb[2]))
    m.use_nodes = True
    nt = m.node_tree
    bsdf = _principled(m)
    bsdf.inputs["Roughness"].default_value = rough
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEXROOT, fn), check_existing=True)
    tex.interpolation = 'Cubic'
    if TINT_ON:
        tgt = realcol(rgb)
        mn  = TEXMEAN.get(fn, (184, 184, 184))
        tint = tuple(min(2.2, max(0.12, tgt[i] / max(1.0, mn[i]))) for i in range(3))
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = tint
        mul.location = (-260, 0)
        nt.links.new(tex.outputs["Color"], mul.inputs[0])
        nt.links.new(mul.outputs["Vector"], bsdf.inputs["Base Color"])
        print("[TINT] %-30s x(%.2f,%.2f,%.2f)" % (fn[:28], *tint))
    else:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    _texcache[key] = m
    return m

def build_tex(name, boxes):
    """带盒式 UV 的构建器"""
    verts, faces, fm, mats, keys = [], [], [], [], []
    slot = {}
    for b in boxes:
        x0,y0,z0,x1,y1,z1 = [float(v) for v in b[:6]]
        rgb = realcol(b[6]); rgb = tuple(int(v) for v in rgb)
        if x0>x1: x0,x1 = x1,x0
        if y0>y1: y0,y1 = y1,y0
        if z0>z1: z0,z1 = z1,z0
        base = len(verts)
        for x in (x0,x1):
            for y in (y0,y1):
                for z in (z0,z1):
                    verts.append((x*CM, y*CM, z*CM))
        # 贴图查找键用「映射前的灰阶色」——realcol 之后查不到
        raw = tuple(int(v) for v in b[6])
        if raw not in slot:
            slot[raw] = len(mats)
            mats.append(texmat(raw) if raw in TEX else mat(rgb))
            keys.append(raw)
        for f in FACES:
            faces.append(tuple(base+i for i in f)); fm.append(slot[raw])
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.validate(verbose=False)
    for m in mats: me.materials.append(m)
    for i,p in enumerate(me.polygons): p.material_index = fm[i]
    me.update()
    # ---- 世界坐标盒式 UV ----
    uvl = me.uv_layers.new(name="UVMap")
    N = me.polygons
    for poly in N:
        key = keys[poly.material_index]
        tile = TEX[key][1] * CM if key in TEX else 2.0
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:   u, v = co.y, co.z
            elif ax == 1: u, v = co.x, co.z
            else:         u, v = co.x, co.y
            uvl.data[li].uv = (u/tile, v/tile)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    print("[OK] %-16s %5d faces  (%d mat)" % (name, len(faces), len(mats)))
    return ob

def build(name, boxes):
    verts, faces, fm, mats = [], [], [], []
    slot = {}
    for b in boxes:
        x0,y0,z0,x1,y1,z1 = [float(v) for v in b[:6]]
        rgb = realcol(b[6])
        if x0>x1: x0,x1 = x1,x0
        if y0>y1: y0,y1 = y1,y0
        if z0>z1: z0,z1 = z1,z0
        base = len(verts)
        for x in (x0,x1):
            for y in (y0,y1):
                for z in (z0,z1):
                    verts.append((x*CM, y*CM, z*CM))
        if rgb not in slot:
            slot[rgb] = len(mats); mats.append(mat(rgb))
        for f in FACES:
            faces.append(tuple(base+i for i in f)); fm.append(slot[rgb])
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.validate(verbose=False)
    for m in mats: me.materials.append(m)
    for i,p in enumerate(me.polygons): p.material_index = fm[i]
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    print("[OK] %-16s %5d faces" % (name, len(faces)))
    return ob

byg = {0:[],1:[],2:[],3:[],4:[]}
for b in SCENE["boxes"]:
    g = int(b[7]) if len(b) >= 8 else 0
    byg.setdefault(g, []).append(b)
build_tex("Structure", byg[0])
if byg[1]: build_tex("RoofLayer", byg[1])
if byg[2] and "nofig" not in argv: build("Figures", byg[2])
if byg[3]: build_tex("LifeLayer", byg[3])
if byg[4]: build_tex("EnvLayer", byg[4])

# ============================================================
# 树（Quaternius Stylized Nature MegaKit · CC0 · 二次元/吉卜力风格）
# ⛔ 换掉 Poly Haven 写实树的原因：蓝花楹精简后仍有 661,770 面/棵，
#    而这里这些是 3,182~10,089 面/棵（1/70~1/200），且风格是平涂卡通，跟二次元 MV 对味。
# ⚠️ 正面位置必须避开电线杆 POLES=(340, 980, 1640) —— 上一版树摆在 300/1050/1800，
#    正好每棵贴着杆子，被 Ronny 抓到。
# ============================================================
TREE_DIR = os.path.join(ROOT, "_assets", "qn", "glTF")


def load_tree(name, tx, ty, sc, rot, sat, val):
    """导入一棵树并摆位；返回 mesh 个数。
    ⚠️ glTF 有层级：必须改 parent is None 的 root，改子物体是白改（位置一点不动）。"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(TREE_DIR, name + ".gltf"))
    fresh = [o for o in bpy.data.objects if o not in before]
    for r in [o for o in fresh if o.parent is None]:
        r.location = (tx / 100.0, ty / 100.0, 0.0)
        r.rotation_euler = (0.0, 0.0, math.radians(rot))
        r.scale = (sc, sc, sc)
    n = 0
    for o in fresh:
        if o.type != 'MESH':
            continue
        n += 1
        for m in o.data.materials:
            if not m or m.name.startswith("T_") or "HSL" in m.name:
                continue
            m.use_nodes = True
            nt = m.node_tree
            bsdf = next((x for x in nt.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled"), None)
            if not bsdf:
                continue
            src = bsdf.inputs["Base Color"]
            if not src.is_linked:
                continue
            up = src.links[0].from_socket
            hs = nt.nodes.new("ShaderNodeHueSaturation")
            hs.inputs["Saturation"].default_value = sat    # 降饱和 = 浅绿（二次元背景叶色本就比真树浅）
            hs.inputs["Value"].default_value = val
            hs.location = (bsdf.location.x - 260, bsdf.location.y)
            nt.links.new(up, hs.inputs["Color"])
            nt.links.new(hs.outputs["Color"], src)
    return n


# ============================================================
# 树 —— 全部来自 _layout.json（layout_editor.html 里 Ronny 自己拖）
# 没有布局文件时回退到下面这份内置默认，保证老渲染一模一样。
# ⚠️ 单位 cm。字段：model / x / y / scale / rot / sat / val
# ============================================================
DEFAULT_TREES = [
    ("CommonTree_1",  660,   775, 0.54,  12, 0.72, 1.18),
    ("CommonTree_5", 1310,   775, 0.58, 143, 0.72, 1.18),
    ("CommonTree_2", 1980,   775, 0.53, 258, 0.72, 1.18),
    ("CommonTree_5", 2650,   775, 0.56,  77, 0.72, 1.18),
    # 楼后（y<0）。⛔ 整包只有 Pine_5 树干干净，Pine_1/2/3/4 中下部都挂着一撮褐色裸枝。
    # 高度按「墙+女儿墙 590」的 1.0~1.3 倍取（7~8m）—— 做 11~12m 会把后墙整个吃掉（v1 实测）。
    ("Pine_5",        320,  -780, 0.90,  15, 0.78, 1.04),
    ("Pine_5",       1050, -1000, 1.05, 100, 0.78, 1.04),
    ("Pine_5",       1780,  -720, 0.84, 235, 0.78, 1.04),
    ("Pine_5",       2380, -1020, 0.98, 310, 0.78, 1.04),
    ("Pine_5",       2760,  -760, 0.80,  60, 0.78, 1.04),
    ("TwistedTree_1", -1100, -1700, 0.52,  40, 0.70, 1.02),
    ("TwistedTree_3", -1750,  -900, 0.46, 215, 0.70, 1.02),
    ("TwistedTree_2",  4380, -1600, 0.50, 140, 0.70, 1.02),
    ("TwistedTree_1",  3700,  -800, 0.44, 300, 0.70, 1.02),
    ("TwistedTree_3",  2300, -1900, 0.44,  95, 0.70, 1.02),
]

TREES_ON = os.environ.get("BMOD_TREES") == "1"
BACKTREE_ON = os.environ.get("BMOD_BACKTREE") == "1"
if TREES_ON or BACKTREE_ON:
    # ⛔ 变量名别叫 SPEC —— 那是输出文件名后缀（第 25 行），曾经被这里覆盖成树列表，
    #    结果「开树渲染」必然抛 TypeError: can only concatenate str (not "list") to str
    TREE_SPEC = DEFAULT_TREES
    try:
        with open(os.path.join(ROOT, "_layout.json"), encoding="utf-8") as f:
            _lay = json.load(f)
        _t = _lay.get("trees") or []
        if _t:
            TREE_SPEC = [(t["model"], t["x"], t["y"], t["scale"], t["rot"],
                          t.get("sat", 0.72), t.get("val", 1.14)) for t in _t]
            print("[LAYOUT] 用 _layout.json 的 %d 棵树" % len(TREE_SPEC))
    except Exception as _e:
        print("[LAYOUT] 树没读到 _layout.json（%s）⇒ 用内置默认" % _e)
    n_tree = sum(load_tree(*s) for s in TREE_SPEC)
    print("[OK] 树 %d 个 mesh / %d 处" % (n_tree, len(TREE_SPEC)))

# ---------- 地面 ----------
# ⛔ 2026-10-30 回退：为了背面机位把它从 60m 放大到 140m，结果正面 S0/S1 整帧亮度变了
#    （逐像素比对 92% 的像素差 >8）—— 一块大平面会改 EEVEE 的间接光。
#    ⇒ 兜底平面一律不动，背面靠 env 层那块后院地坪自己延长（见 _gmod.YARD_Y0）。
bpy.ops.mesh.primitive_plane_add(size=60.0, location=(FULL:= (SCENE["units"]=="cm" and 14.56) or 14.56, 8.0, 0.0))
gp = bpy.context.object; gp.name = "Ground"
gp.data.materials.append(mat((150,148,142), rough=0.95))

# ---------- 日光 ----------
sun_d = bpy.data.lights.new("Sun", type='SUN')
sun_d.energy = 3.4
sun_d.angle = math.radians(1.2)
sun = bpy.data.objects.new("Sun", sun_d)
scene.collection.objects.link(sun)
LIGHT_DIR = Vector((0.42, -0.80, -0.43)).normalized()   # 从走廊外侧斜射进来
if LIGHT_ON:
    # ⭐ 立面死平的根因：光几乎正对墙面 ⇒ 没有自阴影，所有水平面/竖直面同一亮度。
    #    改成侧上方斜射（太阳在画面左前高处），让开间隔墙在墙面上投出竖向阴影。
    LIGHT_DIR = Vector((0.54, -0.58, -0.61)).normalized()
    sun_d.energy = 4.4
sun.rotation_euler = LIGHT_DIR.to_track_quat('-Z', 'Y').to_euler()
print("[OK] sun elev=%.1f deg" % math.degrees(math.asin(-LIGHT_DIR.z)))

# ⭐ 补光（假的天空反弹）：没有它，对面楼投下的街面阴影在 EEVEE 里会读成一条纯黑带。
#    方向取"太阳的反向偏上"，能量小、角度大 ⇒ 只抬暗部，不产生第二组硬阴影。
fill_d = bpy.data.lights.new("Fill", type='SUN')
fill_d.energy = 1.6 if LIGHT_ON else 0.9
fill_d.angle = math.radians(60.0)
fill = bpy.data.objects.new("Fill", fill_d)
scene.collection.objects.link(fill)
fill.rotation_euler = Vector((-0.30, 0.85, -0.44)).normalized().to_track_quat('-Z', 'Y').to_euler()

# 天空补光
world = bpy.data.worlds.new("W") if not scene.world else scene.world
scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.bl_idname == "ShaderNodeBackground")
# ⭐ BMOD_WARM=1：把「冷蓝的阴天感」往「下午的暖灰」挪。
#    现状 B/R = 0.86/0.62 = 1.39 是相当蓝的天空；实拍傍晚的楼是被暖光照着的，
#    天空可以偏蓝，但**打到墙上的光不该是蓝的**。
#    ⇒ 天空降饱和 + 太阳加暖，两头一起收，而不是只把天空调白（那样会灰得发闷）。
if WARM_ON:
    bg.inputs[0].default_value = (0.66, 0.73, 0.82, 1.0)   # 原 (0.62,0.72,0.86)
    bg.inputs[1].default_value = (1.00 if LIGHT_ON else 0.55)
    sun_d.color = (1.00, 0.945, 0.875)                     # 暖白日光（≈5200K）
    fill_d.color = (0.92, 0.95, 1.00)                      # 补光留一点冷，暗部才不发黄
else:
    bg.inputs[0].default_value = (0.62, 0.72, 0.86, 1.0)
    bg.inputs[1].default_value = 1.05 if LIGHT_ON else 0.55

# ---------- 渲染设置 ----------
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        scene.render.engine = eng; break
    except Exception: pass
print("[OK] engine:", scene.render.engine)
if scene.render.engine == "CYCLES":
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
else:
    try: scene.eevee.taa_render_samples = 64
    except Exception: pass
    for a, v in (("use_shadows", True), ("use_raytracing", True)):
        try: setattr(scene.eevee, a, v)
        except Exception: pass
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.resolution_percentage = PCT
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.view_settings.exposure = -1.10
scene.view_settings.view_transform = 'AgX'
try: scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    try: scene.view_settings.look = 'AgX - Base Contrast'
    except Exception: pass

# ---------- 相机 ----------
def add_cam(c):
    cd = bpy.data.cameras.new(c["tag"])
    cd.sensor_fit = 'VERTICAL'
    cd.sensor_height = c["sensor_h_mm"]
    cd.lens = c["lens_mm"]
    ob = bpy.data.objects.new(c["tag"], cd)
    scene.collection.objects.link(ob)
    ob.location = Vector([v*CM for v in c["pos_cm"]])
    d = Vector([v*CM for v in c["look_cm"]]) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


# 专为"看白天细节"新设的机位（不在 8 机位规格里，只做目检用）
CUSTOM = {
  "D1_outside": dict(tag="D1_outside", pos_cm=[700, 820, 470], look_cm=[2000, 432, 336],
                     lens_mm=40.0, sensor_h_mm=20.25),
  "D2_door34": dict(tag="D2_door34", pos_cm=[1462, 472, 392], look_cm=[1252, 420, 322],
                    lens_mm=24.0, sensor_h_mm=20.25),
  "D3_wall": dict(tag="D3_wall", pos_cm=[1520, 478, 372], look_cm=[1300, 420, 352],
                  lens_mm=50.0, sensor_h_mm=20.25),
  # 街对面 3/4 看全楼：一层铺子 + 二层外廊 + 屋顶，一次看全
  # ⚠️ 机位必须落在 y<1900（车行道上）—— 1900 之后是对面楼的体块，进去就等于钻进砖里
  "S1_street": dict(tag="S1_street", pos_cm=[3450, 1420, 200], look_cm=[1200, 470, 330],
                    lens_mm=40.0, sensor_h_mm=20.25),
  # 近看铺面：卷帘门 / 招牌板 / 铝框玻璃
  "S2_shopfront": dict(tag="S2_shopfront", pos_cm=[1500, 1150, 160], look_cm=[1180, 500, 212],
                       lens_mm=40.0, sensor_h_mm=20.25),
  # ⭐ 验证「栏杆外有没有东西挡住天空」——站在二层外廊，隔着扶手墙往外看
  #    ⚠️ x 必须同时避开三样：封闭玻璃盒(2/6 户 = x 728..1092 / 2184..2548)、
  #       行道树(620/1260)、电线杆(340/980/1640)。踩中任何一个，镜头前就是一堵板。
  # ⚠️ y 要退到 432（离扶手墙 108cm）。站在 470 时墙顶在眼下方 45cm/70cm 处 = 32.7°，
  #    已经掉出 26mm 画面的下边缘 ⇒ 片子会像"悬浮在空中"，看不到扶手墙。
  "S3_out_rail": dict(tag="S3_out_rail", pos_cm=[1520, 432, 400], look_cm=[900, 2200, 250],
                      lens_mm=26.0, sensor_h_mm=20.25),
  # ⭐ 沿街：站在人行道上顺着铺面往左看（挤迫感 / 进深 / 遮挡）
  "S4_along": dict(tag="S4_along", pos_cm=[1700, 690, 155], look_cm=[60, 640, 185],
                   lens_mm=34.0, sensor_h_mm=20.25),
  # ⭐ 正立面（elevation）：判断「比例 / 开间 / 栏杆与楼板端头是否分得开」只能用这张。
  #    3/4 街景透视压缩太狠，立面关系读不出来。
  #    26mm @ 11.6m ⇒ 横向覆盖 ≈ 1600cm（楼宽 1440），纵向 934cm（楼高 480）。
  "S0_elev": dict(tag="S0_elev", pos_cm=[720, 1660, 250], look_cm=[720, 500, 250],
                  lens_mm=26.0, sensor_h_mm=20.25),
  # ⭐ 栏杆近景仰视：110cm 栏板 + 12cm 楼板端头 + 15cm 天花，一次看全
  "S6_rail": dict(tag="S6_rail", pos_cm=[720, 920, 170], look_cm=[720, 540, 300],
                  lens_mm=35.0, sensor_h_mm=20.25),
  # ============ 背面三机位（2026-10-30 新增，为「背面加 pine / twisted tree」立） ====
  # 楼后 = y<0；后墙在 y=0、高 480cm。所有背面树物理上都在墙外、镜头里在墙前，
  # 但因为都比 480cm 高 ⇒ 必然从墙头探出来（真实住宅区就是这样）。
  # ① 东后角 3/4：顺着后墙往西看，Pine 一列往纵深退
  "S7_back": dict(tag="S7_back", pos_cm=[3900, -2600, 320], look_cm=[1500, -200, 300],
                  lens_mm=45.0, sensor_h_mm=20.25),
  # ② 正后方全景：后墙全长 + 两端 TwistedTree 夹画面（楼宽 2912 ⇒ 34m 物距 40mm 才装得下）
  "S7b_back": dict(tag="S7b_back", pos_cm=[1456, -3400, 280], look_cm=[1456, 0, 320],
                   lens_mm=40.0, sensor_h_mm=20.25),
  # ③ 后墙近景：站到后院中段，后墙细节 + 松树探出墙头的比例（判断"树在楼后"只能靠这张）
  "S7c_back_tight": dict(tag="S7c_back_tight", pos_cm=[1300, -2600, 300], look_cm=[1500, 0, 380],
                         lens_mm=55.0, sensor_h_mm=20.25),
  # ⭐ 街角俯视（2026-10-30 新增）：看 侧街 St × 主街 St 的路口关系。
  #    ⚠️ 第一版放在东南角（6600,3400,2200）拍出来整幅被对面那三栋的屋顶填满 ——
  #       它们最高 1180cm，而那台相机只抬到 2200cm，几乎是贴着屋顶看。
  #       现在改成从 主街 St 正上方向北俯视，路口和两条路都在画面里。
  # ⚠️ 2026-10-31：布局改成 02.jpg 那种街角版以后，楼前多了 525cm 停车前场 +
  #    右侧整条 侧街 St，原来的机位会把楼东头切掉 ⇒ 拉远、瞄点移到楼中心偏西。
  "S8_corner": dict(tag="S8_corner", pos_cm=[2600, 5300, 6300], look_cm=[1200, 300, 0],
                    lens_mm=28.0, sensor_h_mm=20.25),
  # ===== 2026-10-31 新增：前场两台（为 A-紧凑版「8 户 8 位 + 楼前步道」立）=====
  # ⚠️ 老 S0_elev 的 26mm 是按老楼宽 1440cm 算的（注释里写着 1440），装不下现在的楼。
  # ⭐ 实测（不是猜）：_bmod/scene.json 里 grp=0 的建筑盒 x −6..3462 ⇒ 楼实宽 3468cm，
  #    不是 FULL_X=2912 —— 东端铁梯/铺面外挂一直伸到 3462。
  #    相机 sensor_fit='VERTICAL' + sensor_h=20.25 ⇒ 横向半视角 tan = 18/f。
  #    取 y=2650（到楼面前沿 540 的距离 2110cm）、f=19 ⇒ 半宽 1998cm / 全宽 3996cm，
  #    楼 3468 居中（look x = (−6+3462)/2 = 1728）⇒ 左右各留 264cm 余量，不再切头。
  "X1_front_wide": dict(tag="X1_front_wide", pos_cm=[1728, 2650, 205], look_cm=[1728, 480, 215],
                        lens_mm=19.0, sensor_h_mm=20.25),
  # 前场半鸟瞰：从东南方压低高度俯视，专门读「楼 / 步道 150 / 车位 525 / 路缘 16 / 车行道」
  # 五层。正面平视（上一版 X1）在 150cm 步道上只剩一条线，什么也证明不了。
  # 视高 1600cm、俯角 ≈25°，斜距 3525cm，f=37 ⇒ 横向盖 ≈ 3400cm。
  "X3_yard_air": dict(tag="X3_yard_air", pos_cm=[3200, 3000, 1600], look_cm=[1100, 600, 100],
                      lens_mm=37.0, sensor_h_mm=20.25),
  # 前场 3/4：从街对面东南角顺着车位往西看。
  # 比 S1_street 退后 930cm、广 14mm —— S1 贴楼太近，一排车读成一堵墙。
  "X2_lot_34": dict(tag="X2_lot_34", pos_cm=[3350, 2350, 230], look_cm=[900, 780, 140],
                    lens_mm=26.0, sensor_h_mm=20.25),
}

# 外景与内景的曝光不是一回事：
# 内景（走廊/户内）靠 -1.10 才不把墙面打死；外景在 -1.10 下会暗到像傍晚。
EXPO = {"S1_street": -0.10, "S2_shopfront": -0.20,
        "S3_out_rail": -0.35, "S4_along": -0.10,
        # ⚠️ 新机位必须登记，否则回退到内景的 -1.10（外景直接暗成傍晚）
        "S0_elev": -0.10, "S6_rail": -0.10,
        # 背面三机位（全部外景日光；S7b 照到最多地面 ⇒ 收一档，别让草地发白）
        "S7_back": -0.15, "S7b_back": -0.25, "S7c_back_tight": -0.20,
        # 街角鸟瞰：高空看下来地面占满，收一档
        "S8_corner": -0.35,
        # 前场三台（外景正午日光，同 S0_elev 档位）
        "X1_front_wide": -0.10, "X2_lot_34": -0.15, "X3_yard_air": -0.25}

cmap = {c["tag"]: c for c in CAMS["cameras"]}
cmap.update(CUSTOM)
for tag in TAGS:
    if tag not in cmap: print("[WARN] no cam", tag); continue
    scene.view_settings.exposure = EXPO.get(tag, -1.10) + EXPO_ADD
    print("[OK] exposure %.2f" % scene.view_settings.exposure)
    cam = add_cam(cmap[tag]); scene.camera = cam
    scene.render.filepath = os.path.join(OUT, tag + "_day" + SPEC + ".png")
    bpy.ops.render.render(write_still=True)
    print("[OK] ->", scene.render.filepath, "%.0f KB" % (os.path.getsize(scene.render.filepath)/1024))
print("[DONE]")

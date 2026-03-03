import math
import random

# ==============================================================================
# 1. 加载环 (Part-2) 数据 (保持不变)
# ==============================================================================
PART2_NODES_STR = """
1, 6., 0.; 2, 4.7, 0.; 3, 5.9, -1.07; 4, 4.62, -0.84; 5, 5.62, -2.11;
6, 4.4, -1.65; 7, 5.15, -3.08; 8, 4.03, -2.41; 9, 4.52, -3.95; 10, 3.54, -3.09;
11, 3.74, -4.69; 12, 2.93, -3.67; 13, 2.84, -5.28; 14, 2.23, -4.14; 15, 1.85, -5.71;
16, 1.45, -4.47; 17, 0.81, -5.95; 18, 0.63, -4.66; 19, -0.27, -5.99; 20, -0.21, -4.7;
21, -1.34, -5.85; 22, -1.05, -4.58; 23, -2.36, -5.52; 24, -1.85, -4.32; 25, -3.31, -5.01;
26, -2.59, -3.92; 27, -4.15, -4.34; 28, -3.25, -3.4; 29, -4.85, -3.53; 30, -3.8, -2.76;
31, -5.41, -2.6; 32, -4.23, -2.04; 33, -5.78, -1.6; 34, -4.53, -1.25; 35, -5.98, -0.54;
36, -4.68, -0.42; 37, -5.98, 0.54; 38, -4.68, 0.42; 39, -5.78, 1.6; 40, -4.53, 1.25;
41, -5.41, 2.6; 42, -4.23, 2.04; 43, -4.85, 3.53; 44, -3.8, 2.76; 45, -4.15, 4.34;
46, -3.25, 3.4; 47, -3.31, 5.01; 48, -2.59, 3.92; 49, -2.36, 5.52; 50, -1.85, 4.32;
51, -1.34, 5.85; 52, -1.05, 4.58; 53, -0.27, 5.99; 54, -0.21, 4.7; 55, 0.81, 5.95;
56, 0.63, 4.66; 57, 1.85, 5.71; 58, 1.45, 4.47; 59, 2.84, 5.28; 60, 2.23, 4.14;
61, 3.74, 4.69; 62, 2.93, 3.67; 63, 4.52, 3.95; 64, 3.54, 3.09; 65, 5.15, 3.08;
66, 4.03, 2.41; 67, 5.62, 2.11; 68, 4.4, 1.65; 69, 5.9, 1.07; 70, 4.62, 0.84
"""
PART2_ELEMS_STR = """
1,1,2,4,3; 2,3,4,6,5; 3,5,6,8,7; 4,7,8,10,9; 5,9,10,12,11;
6,11,12,14,13; 7,13,14,16,15; 8,15,16,18,17; 9,17,18,20,19; 10,19,20,22,21;
11,21,22,24,23; 12,23,24,26,25; 13,25,26,28,27; 14,27,28,30,29; 15,29,30,32,31;
16,31,32,34,33; 17,33,34,36,35; 18,35,36,38,37; 19,37,38,40,39; 20,39,40,42,41;
21,41,42,44,43; 22,43,44,46,45; 23,45,46,48,47; 24,47,48,50,49; 25,49,50,52,51;
26,51,52,54,53; 27,53,54,56,55; 28,55,56,58,57; 29,57,58,60,59; 30,59,60,62,61;
31,61,62,64,63; 32,63,64,66,65; 33,65,66,68,67; 34,67,68,70,69; 35,69,70,2,1
"""


# ==============================================================================
# 2. 几何核心算法
# ==============================================================================

class Node:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y


class Element:
    def __init__(self, id, n1, n2):
        self.id = id
        self.n1 = n1
        self.n2 = n2
        self.radius = 0.0

    def center(self, nodes):
        n1 = nodes[self.n1]
        n2 = nodes[self.n2]
        return ((n1.x + n2.x) / 2.0, (n1.y + n2.y) / 2.0)

    def angle(self, nodes):
        n1 = nodes[self.n1]
        n2 = nodes[self.n2]
        deg = abs(math.degrees(math.atan2(n2.y - n1.y, n2.x - n1.x)))
        if deg > 180: deg -= 180
        return deg


# --- 1. 圆孔切割算法 ---
def get_circle_intersection(p1, p2, center, r):
    x1, y1 = p1.x - center[0], p1.y - center[1]
    x2, y2 = p2.x - center[0], p2.y - center[1]
    dx, dy = x2 - x1, y2 - y1
    dr = math.sqrt(dx ** 2 + dy ** 2)
    D = x1 * y2 - x2 * y1
    delta = r ** 2 * dr ** 2 - D ** 2
    if delta < 0: return None
    sqrt_delta = math.sqrt(delta)
    sign_dy = 1 if dy >= 0 else -1
    ix1 = (D * dy + sign_dy * dx * sqrt_delta) / dr ** 2
    iy1 = (-D * dx + abs(dy) * sqrt_delta) / dr ** 2
    ix2 = (D * dy - sign_dy * dx * sqrt_delta) / dr ** 2
    iy2 = (-D * dx - abs(dy) * sqrt_delta) / dr ** 2
    sol1 = (ix1 + center[0], iy1 + center[1])
    sol2 = (ix2 + center[0], iy2 + center[1])

    def on_segment(pt, a, b):
        minx, maxx = min(a.x, b.x) - 1e-4, max(a.x, b.x) + 1e-4
        miny, maxy = min(a.y, b.y) - 1e-4, max(a.y, b.y) + 1e-4
        return minx <= pt[0] <= maxx and miny <= pt[1] <= maxy

    if on_segment(sol1, p1, p2): return sol1
    if on_segment(sol2, p1, p2): return sol2
    return None


# --- 2. 矩形边界切割算法 ---
def get_box_intersection(p1, p2, width, height):
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    t_list = []
    # Left
    if dx != 0:
        t = (0 - p1.x) / dx
        if 0 <= t <= 1:
            y = p1.y + t * dy
            if 0 <= y <= height: t_list.append((t, 0, y))
    # Right
    if dx != 0:
        t = (width - p1.x) / dx
        if 0 <= t <= 1:
            y = p1.y + t * dy
            if 0 <= y <= height: t_list.append((t, width, y))
    # Bottom
    if dy != 0:
        t = (0 - p1.y) / dy
        if 0 <= t <= 1:
            x = p1.x + t * dx
            if 0 <= x <= width: t_list.append((t, x, 0))
    # Top
    if dy != 0:
        t = (height - p1.y) / dy
        if 0 <= t <= 1:
            x = p1.x + t * dx
            if 0 <= x <= width: t_list.append((t, x, height))
    if not t_list: return None
    t_list.sort(key=lambda x: x[0])
    return (t_list[0][1], t_list[0][2])


def generate_trimmed_lattice(width, height, strut_len, pins, pin_radius, crack_tip_x):
    dx = strut_len
    dy = strut_len * math.sin(math.radians(60))

    # 为了保证对称性，我们先生成一个足够大的网格，然后移动它使其中心与试件中心对齐
    cols = int(width / dx) + 6
    rows = int(height / dy) + 6

    raw_nodes = {}
    temp_map = {}
    nid_counter = 1

    # 1. 生成初始全量网格 (Raw Generation)
    # 先不考虑具体坐标范围，先生成一整块矩阵
    nodes_list_for_centering = []

    for r in range(rows):
        off_x = 0 if r % 2 == 0 else dx * 0.5
        for c in range(cols):
            x = c * dx + off_x
            y = r * dy

            n = Node(nid_counter, x, y)
            raw_nodes[nid_counter] = n
            temp_map[(r, c)] = nid_counter
            nodes_list_for_centering.append(n)
            nid_counter += 1

    # 2. 自动对齐 (Auto-Centering)
    # 计算当前生成网格的几何中心
    min_x = min(n.x for n in nodes_list_for_centering)
    max_x = max(n.x for n in nodes_list_for_centering)
    min_y = min(n.y for n in nodes_list_for_centering)
    max_y = max(n.y for n in nodes_list_for_centering)

    current_center_x = (min_x + max_x) / 2.0
    current_center_y = (min_y + max_y) / 2.0

    target_center_x = width / 2.0
    target_center_y = height / 2.0

    shift_x = target_center_x - current_center_x
    shift_y = target_center_y - current_center_y

    # 应用平移：这步操作保证了网格相对于试件中心是对称的！
    for n in raw_nodes.values():
        n.x += shift_x
        n.y += shift_y

    # 3. 生成边连接 (Raw Edges)
    raw_edges = []
    for r in range(rows):
        for c in range(cols):
            u = temp_map.get((r, c))
            if not u: continue
            nbs = [(r, c + 1)]
            if r % 2 == 0:
                nbs.extend([(r + 1, c), (r + 1, c - 1)])
            else:
                nbs.extend([(r + 1, c), (r + 1, c + 1)])

            for nr, nc in nbs:
                v = temp_map.get((nr, nc))
                if v:
                    dist = math.sqrt((raw_nodes[u].x - raw_nodes[v].x) ** 2 + (raw_nodes[u].y - raw_nodes[v].y) ** 2)
                    if dist < strut_len * 1.1:
                        raw_edges.append((u, v))

    # 4. 执行切割 (Trim Logic)
    final_nodes_map = {}
    final_elems = []
    tie_nodes_top = []
    tie_nodes_bot = []

    def is_inside_circle(n, centers, r):
        for i, c in enumerate(centers):
            if math.sqrt((n.x - c[0]) ** 2 + (n.y - c[1]) ** 2) < r - 1e-4:
                return True, i
        return False, -1

    def is_inside_box(n, w, h):
        # 稍微放宽一点点容差，避免浮点数误差导致刚好在边界上的点被误判
        tol = 1e-5
        return -tol <= n.x <= w + tol and -tol <= n.y <= h + tol

    next_id = max(raw_nodes.keys()) + 1

    for u_id, v_id in raw_edges:
        u, v = raw_nodes[u_id], raw_nodes[v_id]

        # --- 裂纹检查 ---
        cx, cy = (u.x + v.x) / 2, (u.y + v.y) / 2
        mid_y = height / 2.0
        if (u.y - mid_y) * (v.y - mid_y) <= 0 and cx > crack_tip_x:
            continue

            # --- 状态判断 ---
        in_circle_u, idx_u = is_inside_circle(u, pins, pin_radius)
        in_circle_v, idx_v = is_inside_circle(v, pins, pin_radius)
        in_box_u = is_inside_box(u, width, height)
        in_box_v = is_inside_box(v, width, height)

        # Case 1: 保留 (在圆外 & 在箱内)
        if (not in_circle_u and not in_circle_v) and (in_box_u and in_box_v):
            final_nodes_map[u.id] = u
            final_nodes_map[v.id] = v
            final_elems.append([u.id, v.id])
            continue

        # Case 2: 圆孔切割
        if in_circle_u != in_circle_v:
            inner = u if in_circle_u else v
            outer = v if in_circle_u else u
            pin_idx = idx_u if in_circle_u else idx_v

            if is_inside_box(outer, width, height):
                pt = get_circle_intersection(inner, outer, pins[pin_idx], pin_radius)
                if pt:
                    new_node = Node(next_id, pt[0], pt[1])
                    final_nodes_map[outer.id] = outer
                    final_nodes_map[new_node.id] = new_node
                    if pin_idx == 0:
                        tie_nodes_top.append(new_node.id)
                    else:
                        tie_nodes_bot.append(new_node.id)
                    final_elems.append([outer.id, new_node.id])
                    next_id += 1
            continue

        # Case 3: 边界切割
        if not in_circle_u and not in_circle_v:
            if in_box_u != in_box_v:
                box_in = u if in_box_u else v
                box_out = v if in_box_u else u

                pt = get_box_intersection(box_in, box_out, width, height)
                if pt:
                    new_node = Node(next_id, pt[0], pt[1])
                    final_nodes_map[box_in.id] = box_in
                    final_nodes_map[new_node.id] = new_node
                    final_elems.append([box_in.id, new_node.id])
                    next_id += 1

    # 5. ID 整理
    sorted_ids = sorted(final_nodes_map.keys())
    old_to_new = {oid: i + 1 for i, oid in enumerate(sorted_ids)}

    clean_nodes = [final_nodes_map[oid] for oid in sorted_ids]
    clean_elems = []
    for eid, (n1, n2) in enumerate(final_elems):
        el = Element(eid + 1, old_to_new[n1], old_to_new[n2])
        clean_elems.append(el)

    clean_tie_top = [old_to_new[nid] for nid in tie_nodes_top]
    clean_tie_bot = [old_to_new[nid] for nid in tie_nodes_bot]

    return clean_nodes, clean_elems, clean_tie_top, clean_tie_bot


def parse_part2_data():
    p2_nodes = []
    for line in PART2_NODES_STR.replace('\n', '').split(';'):
        if line.strip(): p2_nodes.append([float(x) for x in line.split(',')])
    p2_elems = []
    for line in PART2_ELEMS_STR.replace('\n', '').split(';'):
        if line.strip(): p2_elems.append([int(x) for x in line.split(',')])
    return p2_nodes, p2_elems


# ==============================================================================
# 3. INP 生成
# ==============================================================================
def write_inp(filename, nodes, elements, tie_top, tie_bot, strategy, base_r, crack_tip_x, width, height, pins):
    p2_nodes, p2_elems = parse_part2_data()

    with open(filename, 'w') as f:
        f.write("*Heading\n")
        f.write(f"** CT Specimen (Auto-Centered, Trimmed, Tie Fixed) - {strategy}\n")
        f.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")

        # --- Part-1 (Lattice) ---
        f.write("*Part, name=Part-1\n*Node\n")
        node_dict = {}
        for i, n in enumerate(nodes):
            f.write(f"{i + 1}, {n.x:.6f}, {n.y:.6f}, 0.0\n")
            node_dict[i + 1] = n

        radius_sets = {}
        f.write("*Element, type=B21\n")
        for el in elements:
            f.write(f"{el.id}, {el.n1}, {el.n2}\n")
            r = base_r
            if strategy == 'aniso':
                if el.angle(node_dict) < 15 or el.angle(node_dict) > 165:
                    r *= 0.6
                else:
                    r *= 1.2
            elif strategy == 'gradient':
                cx, cy = el.center(node_dict)
                dist = math.sqrt((cx - crack_tip_x) ** 2 + (cy - height / 2.0) ** 2)
                r = base_r * (1.0 + 1.5 * math.exp(-0.1 * dist))
            elif strategy == 'random':
                r *= random.uniform(0.8, 1.2)

            r_key = f"{r:.3f}"
            if r_key not in radius_sets: radius_sets[r_key] = []
            radius_sets[r_key].append(el.id)

        f.write("*Nset, nset=Set-Hole-Top\n")
        for i in range(0, len(tie_top), 16): f.write(", ".join(map(str, tie_top[i:i + 16])) + "\n")
        f.write("*Nset, nset=Set-Hole-Bot\n")
        for i in range(0, len(tie_bot), 16): f.write(", ".join(map(str, tie_bot[i:i + 16])) + "\n")

        f.write("*Surface, type=NODE, name=Surf-Hole-Top\nSet-Hole-Top, 1.0\n")
        f.write("*Surface, type=NODE, name=Surf-Hole-Bot\nSet-Hole-Bot, 1.0\n")

        for r_key, eids in radius_sets.items():
            sname = f"Set_R_{r_key.replace('.', 'p')}"
            f.write(f"*Elset, elset={sname}\n")
            for i in range(0, len(eids), 16): f.write(", ".join(map(str, eids[i:i + 16])) + "\n")
            f.write(f"*Beam Section, elset={sname}, material=Ti-6Al-4V, section=CIRC\n{r_key}\n0.,0.,-1.\n")
        f.write("*End Part\n")

        # --- Part-2 (Pin) ---
        f.write("*Part, name=Part-2\n*Node\n")
        for row in p2_nodes: f.write(f"{int(row[0])}, {row[1]}, {row[2]}\n")
        f.write("*Element, type=CPS4R\n")
        for row in p2_elems: f.write(f"{row[0]}, {row[1]}, {row[2]}, {row[3]}, {row[4]}\n")
        f.write(
            "*Elset, elset=All_Elems, generate\n1, 35, 1\n*Solid Section, elset=All_Elems, material=Ti-6Al-4V\n1.,\n")

        # Surface Definitions
        f.write("*Surface, type=ELEMENT, name=Surf-Pin-Outer\nAll_Elems, S4\n")
        f.write("*Surface, type=ELEMENT, name=Surf-Pin-Inner\nAll_Elems, S2\n")
        f.write("*End Part\n")

        # --- Assembly ---
        f.write("**\n*Assembly, name=Assembly\n")
        f.write("*Instance, name=Lattice, part=Part-1\n*End Instance\n")
        f.write(f"*Instance, name=Pin-Top, part=Part-2\n{pins[0][0]}, {pins[0][1]}, 0.0\n*End Instance\n")
        f.write(f"*Instance, name=Pin-Bot, part=Part-2\n{pins[1][0]}, {pins[1][1]}, 0.0\n*End Instance\n")

        f.write(f"*Node\n10001, {pins[0][0]}, {pins[0][1]}, 0.0\n10002, {pins[1][0]}, {pins[1][1]}, 0.0\n")
        f.write("*Nset, nset=RP-Top\n10001,\n*Nset, nset=RP-Bot\n10002,\n")

        f.write("*Coupling, constraint name=Coup-Top, ref node=RP-Top, surface=Pin-Top.Surf-Pin-Inner\n*Kinematic\n")
        f.write("*Coupling, constraint name=Coup-Bot, ref node=RP-Bot, surface=Pin-Bot.Surf-Pin-Inner\n*Kinematic\n")

        f.write("*Tie, name=Tie-Top, adjust=yes, position tolerance=0.1\n")
        f.write("Lattice.Surf-Hole-Top, Pin-Top.Surf-Pin-Outer\n")
        f.write("*Tie, name=Tie-Bot, adjust=yes, position tolerance=0.1\n")
        f.write("Lattice.Surf-Hole-Bot, Pin-Bot.Surf-Pin-Outer\n")
        f.write("*End Assembly\n")

        # --- Step ---
        f.write("**\n*Material, name=Ti-6Al-4V\n*Density\n4.43e-09,\n*Elastic\n110000., 0.31\n")
        f.write("*Plastic, hardening=JOHNSON COOK\n1098.,1092., 0.33, 1.1,1605., 25.\n")
        f.write("*Damage Initiation, criterion=JOHNSON COOK\n-0.09, 0.27, 0.48, 0.014, 3.87, 1605., 25., 1.\n")
        f.write("*Damage Evolution, type=ENERGY\n86.,\n")
        f.write("**\n*Step, name=Load, nlgeom=YES\n*Dynamic, Explicit\n, 0.05\n")
        f.write("*Boundary\nRP-Bot, 1, 2, 0.0\nRP-Top, 1, 1, 0.0\n")
        f.write("*Boundary, type=VELOCITY\nRP-Top, 2, 2, 100.0\n")
        f.write("*Output, field, variable=PRESELECT, number interval=50\n*End Step\n")


# ==============================================================================
# 执行
# ==============================================================================
W_SPEC = 62.5
H_SPEC = 60.0
L_STRUT = 3.0
R_BASE = 0.3
PINS_POS = [(50.0, 48.75), (50.0, 11.25)]
R_PIN = 6.0
CRACK_TIP_X = 41.0

print("Generating CT_Right2Left_Aniso.inp...")
nodes, elems, t_top, t_bot = generate_trimmed_lattice(W_SPEC, H_SPEC, L_STRUT, PINS_POS, R_PIN, CRACK_TIP_X)
write_inp("CT_Right2Left_Aniso.inp", nodes, elems, t_top, t_bot, 'aniso', R_BASE, CRACK_TIP_X, W_SPEC, H_SPEC, PINS_POS)

print("Generating CT_Right2Left_Gradient.inp...")
nodes, elems, t_top, t_bot = generate_trimmed_lattice(W_SPEC, H_SPEC, L_STRUT, PINS_POS, R_PIN, CRACK_TIP_X)
write_inp("CT_Right2Left_Gradient.inp", nodes, elems, t_top, t_bot, 'gradient', R_BASE, CRACK_TIP_X, W_SPEC, H_SPEC,
          PINS_POS)

print("Done.")
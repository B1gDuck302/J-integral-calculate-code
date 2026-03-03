import math


# ==============================================================================
# 1. 基础类
# ==============================================================================
class Node:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y


class Element:
    def __init__(self, id, n1, n2, group):
        self.id = id
        self.n1 = n1
        self.n2 = n2
        self.group = group  # 'core' or 'filler'


# ==============================================================================
# 2. 几何算法：矩形切割
# ==============================================================================
def get_box_intersection(p1, p2, width, height):
    """ 计算线段 P1-P2 与矩形框 (0,0)-(width,height) 的交点 """
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    t_list = []

    # 1. Left (x=0)
    if dx != 0:
        t = (0 - p1.x) / dx
        if 0 <= t <= 1:
            y = p1.y + t * dy
            if 0 <= y <= height: t_list.append((t, 0, y))
    # 2. Right (x=width)
    if dx != 0:
        t = (width - p1.x) / dx
        if 0 <= t <= 1:
            y = p1.y + t * dy
            if 0 <= y <= height: t_list.append((t, width, y))
    # 3. Bottom (y=0)
    if dy != 0:
        t = (0 - p1.y) / dy
        if 0 <= t <= 1:
            x = p1.x + t * dx
            if 0 <= x <= width: t_list.append((t, x, 0))
    # 4. Top (y=height)
    if dy != 0:
        t = (height - p1.y) / dy
        if 0 <= t <= 1:
            x = p1.x + t * dx
            if 0 <= x <= width: t_list.append((t, x, height))

    if not t_list: return None
    # 排序，取离 P1 最近的交点（假设 P1 在内，P2 在外）
    t_list.sort(key=lambda x: x[0])
    return (t_list[0][1], t_list[0][2])


# ==============================================================================
# 3. 核心生成逻辑：严格拓扑 + 裁剪
# ==============================================================================
def generate_strict_sent_lattice(width, height, strut_len, crack_len):
    # 3.1 定义网格参数
    L = strut_len
    dx = L
    dy = L * math.sin(math.radians(60))

    # 3.2 生成足够大的“虚拟画布”
    # 我们生成一个比实际尺寸大一圈的网格，确保边缘被填满
    cols = int(width / dx) + 6
    rows = int(height / dy) + 6

    # 起始偏移量 (让网格覆盖左下角负区域，方便切割)
    start_x = -3.0 * L
    start_y = -3.0 * L

    # 3.3 生成节点 (按行列索引)
    raw_nodes = {}
    node_map = {}  # (row, col) -> node_id
    nid = 1

    for r in range(rows):
        # 偶数行不偏移，奇数行偏移 0.5*L
        off_x = 0.0 if r % 2 == 0 else 0.5 * L

        for c in range(cols):
            x = start_x + c * dx + off_x
            y = start_y + r * dy

            # 只要在“大框”范围内都生成
            if -50 <= x <= width + 50 and -50 <= y <= height + 50:
                n = Node(nid, x, y)
                raw_nodes[nid] = n
                node_map[(r, c)] = nid
                nid += 1

    # 3.4 建立拓扑连接 (严格索引规则)
    raw_edges = []  # (u_id, v_id, tag)

    for r in range(rows):
        for c in range(cols):
            u_id = node_map.get((r, c))
            if u_id is None: continue

            # --- Rule A: 水平连接 (r, c) -> (r, c+1) ---
            v_id = node_map.get((r, c + 1))
            if v_id:
                # 偶数行水平杆 -> Core (内凹骨架的一部分)
                # 奇数行水平杆 -> Filler (填充物)
                tag = 'core' if r % 2 == 0 else 'filler'
                raw_edges.append((u_id, v_id, tag))

            # --- Rule B: 斜向连接 (向上找 r+1) ---
            # 只有当 r 不是最后一行时才连
            if r < rows - 1:
                # 寻找下一行的邻居列索引
                if r % 2 == 0:
                    # 偶数行 (0偏移) -> 找下一行(有偏移)的 c-1 和 c
                    # 几何上：   U
                    #          /   \
                    #       V1       V2
                    neighbor_cols = [c - 1, c]
                else:
                    # 奇数行 (有偏移) -> 找下一行(无偏移)的 c 和 c+1
                    # 几何上：     U
                    #            /   \
                    #         V1       V2
                    neighbor_cols = [c, c + 1]

                for nc in neighbor_cols:
                    v_id = node_map.get((r + 1, nc))
                    if v_id:
                        # 所有斜杆都是骨架
                        raw_edges.append((u_id, v_id, 'core'))

    # 3.5 几何裁剪 (Box Trim & Crack)
    final_nodes_map = {}  # old_id -> node_obj
    final_elements = []  # Element obj
    new_nid = max(raw_nodes.keys()) + 1
    elem_id = 1

    def is_inside(n):
        tol = 1e-5
        return -tol <= n.x <= width + tol and -tol <= n.y <= height + tol

    for u_id, v_id, tag in raw_edges:
        u = raw_nodes[u_id]
        v = raw_nodes[v_id]

        # 1. 裂纹检查 (SENT: 左侧水平裂纹)
        mid_y = height / 2.0
        cx = (u.x + v.x) / 2.0
        # 跨越中线 且 在裂纹长度内 -> 剔除
        if (u.y - mid_y) * (v.y - mid_y) <= 0 and cx < crack_len:
            continue

        # 2. 矩形边界裁剪
        in_u = is_inside(u)
        in_v = is_inside(v)

        # A. 都在界内 -> 完美保留
        if in_u and in_v:
            final_nodes_map[u.id] = u
            final_nodes_map[v.id] = v
            final_elements.append(Element(elem_id, u.id, v.id, tag))
            elem_id += 1

        # B. 一内一外 -> 裁剪
        elif in_u != in_v:
            inner = u if in_u else v
            outer = v if in_u else u

            pt = get_box_intersection(inner, outer, width, height)
            if pt:
                # 创建边界新节点
                new_node = Node(new_nid, pt[0], pt[1])
                # 记录
                final_nodes_map[inner.id] = inner
                final_nodes_map[new_nid] = new_node

                # 连线：内点 -> 新边界点
                final_elements.append(Element(elem_id, inner.id, new_nid, tag))
                new_nid += 1
                elem_id += 1

    # 3.6 ID 重整 (从1开始连续编号)
    sorted_old_ids = sorted(final_nodes_map.keys())
    id_remap = {old: i + 1 for i, old in enumerate(sorted_old_ids)}

    clean_nodes = [final_nodes_map[old] for old in sorted_old_ids]
    # 更新单元的节点ID
    for el in final_elements:
        el.n1 = id_remap[el.n1]
        el.n2 = id_remap[el.n2]

    return clean_nodes, final_elements


# ==============================================================================
# 4. INP 写入函数
# ==============================================================================
def write_inp(filename, nodes, elements, width, height, r_core, r_filler):
    with open(filename, 'w') as f:
        f.write("*Heading\n")
        f.write(f"** SENT Composite Specimen (Strict Topology)\n")
        f.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")

        # --- Part ---
        f.write("*Part, name=Part-1\n")
        f.write("*Node\n")
        for n in nodes:
            f.write(f"{n.id}, {n.x:.6f}, {n.y:.6f}, 0.0\n")

        # 按组写入单元
        core_ids = []
        filler_ids = []
        radius_sets = {}  # radius_str -> list of element ids

        f.write("*Element, type=B21\n")
        for el in elements:
            f.write(f"{el.id}, {el.n1}, {el.n2}\n")

            # 分配半径
            r = r_core if el.group == 'core' else r_filler

            if el.group == 'core':
                core_ids.append(el.id)
            else:
                filler_ids.append(el.id)

            r_str = f"{r:.3f}"
            if r_str not in radius_sets: radius_sets[r_str] = []
            radius_sets[r_str].append(el.id)

        # 集合定义
        if core_ids:
            f.write("*Elset, elset=Set-Core\n")
            for i in range(0, len(core_ids), 16): f.write(", ".join(map(str, core_ids[i:i + 16])) + "\n")
        if filler_ids:
            f.write("*Elset, elset=Set-Filler\n")
            for i in range(0, len(filler_ids), 16): f.write(", ".join(map(str, filler_ids[i:i + 16])) + "\n")

        # 截面定义
        for r_str, eids in radius_sets.items():
            sname = f"Set_R_{r_str.replace('.', 'p')}"
            f.write(f"*Elset, elset={sname}\n")
            for i in range(0, len(eids), 16): f.write(", ".join(map(str, eids[i:i + 16])) + "\n")
            f.write(f"*Beam Section, elset={sname}, material=Ti-6Al-4V, section=CIRC\n{r_str}\n0.,0.,-1.\n")

        # 边界节点集
        f.write("*Nset, nset=Set-Top\n")
        top_ids = [n.id for n in nodes if abs(n.y - height) < 1e-4]
        for i in range(0, len(top_ids), 16): f.write(", ".join(map(str, top_ids[i:i + 16])) + "\n")

        f.write("*Nset, nset=Set-Bottom\n")
        bot_ids = [n.id for n in nodes if abs(n.y - 0.0) < 1e-4]
        for i in range(0, len(bot_ids), 16): f.write(", ".join(map(str, bot_ids[i:i + 16])) + "\n")

        f.write("*End Part\n")

        # --- Assembly ---
        f.write("**\n*Assembly, name=Assembly\n")
        f.write("*Instance, name=Lattice, part=Part-1\n*End Instance\n")
        f.write("*End Assembly\n")

        # --- Material ---
        f.write("**\n*Material, name=Ti-6Al-4V\n*Density\n4.43e-09,\n*Elastic\n110000., 0.31\n")
        f.write("*Plastic, hardening=JOHNSON COOK\n1098., 1092., 0.33, 0.014, 1.1, 1605., 25.\n")
        f.write("*Damage Initiation, criterion=JOHNSON COOK\n-0.09, 0.27, 0.48, 0.014, 3.87, 1605., 25., 1.\n")
        f.write("*Damage Evolution, type=ENERGY\n86.,\n")

        # --- Step ---
        f.write("**\n*Step, name=Load, nlgeom=YES\n*Dynamic, Explicit\n, 0.05\n")
        f.write("*Boundary\nLattice.Set-Bottom, 1, 6, 0.0\n")
        f.write("Lattice.Set-Top, 1, 1, 0.0\nLattice.Set-Top, 3, 6, 0.0\n")
        f.write("*Boundary, type=VELOCITY\nLattice.Set-Top, 2, 2, 100.0\n")
        f.write("*Output, field, variable=PRESELECT, number interval=50\n*End Step\n")


# ==============================================================================
# 执行
# ==============================================================================
W_SENT = 60.0
H_SENT = 120.0
L_CELL = 3.0
CRACK = 20.0

print("Generating SENT_Composite_Strict.inp...")
# 1. 骨架粗 (0.4)，填充细 (0.15)
nodes, elems = generate_strict_sent_lattice(W_SENT, H_SENT, L_CELL, CRACK)
write_inp("SENT_Composite_Strict.inp", nodes, elems, W_SENT, H_SENT, r_core=0.4, r_filler=0.15)

print("Done. Check the INP file.")
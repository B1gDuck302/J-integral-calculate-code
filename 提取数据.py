# -*- coding: utf-8 -*-
# SCRIPT: 提取数据.py (v10.3 - Full Version with FD & Rod CL)
#
# 功能包含:
# 1. FD: 提取力-位移曲线 (Force-Displacement)
# 2. CL: 提取裂纹长度 (Rod Clustering + Max Delta_a + Future Min Filter)
# 3. HO: 提取历史输出 (History Outputs)

import sys
import os
import csv
import project_config as cfg
from odbAccess import openOdb
from collections import defaultdict

# ==================================================
#    配置区域
# ==================================================
if len(sys.argv) > 1:
    EXPERIMENT_ID = sys.argv[-1]
else:
    EXPERIMENT_ID = 'B05Solid'

DATA_DIR = os.path.join(cfg.ROOT_DIR, cfg.DATA_DIR_NAME, EXPERIMENT_ID)
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

MASTER_CONFIG = {
    'ODB_FILE_PATH': os.path.join(cfg.ODB_DIR_PATH, EXPERIMENT_ID + '.odb'),
    'STEP_NAME': cfg.STEP_NAME,
    # FD
    'INSTANCE_NAME_FD': cfg.FD_INSTANCE,
    'NODE_SET_NAME_FD': cfg.FD_NODE_SET,
    'U_COMPONENT': cfg.FD_U_COMP,
    # 修正错误：使用 cfg.FD_RF_COMP
    'RF_COMPONENT': cfg.FD_RF_COMP,

    'CSV_OUTPUT_FD': os.path.join(DATA_DIR, EXPERIMENT_ID + '_force_displacement_from_FIELD.csv'),

    # CL (适配 J积分脚本的文件名)
    'INSTANCE_NAME_CL': cfg.CL_INSTANCE,
    'ELEMENT_SET_NAME_CL': cfg.CL_ELEMENT_SET,
    'STATUS_VARIABLE': cfg.CL_VAR_NAME,
    'CSV_OUTPUT_CL': os.path.join(DATA_DIR, EXPERIMENT_ID + '_crack_length_UserTip_vs_time.csv'),

    # HO
    'HISTORY_VARIABLES': ['ALLPD', 'ALLVD', 'ALLSE', 'ALLKE', 'ALLIE', 'ALLWK', 'ALLDMD'],
    'HISTORY_REGION_NAME': 'Assembly ASSEMBLY',
}


# ==================================================
#    通用 CSV 保存
# ==================================================
def save_to_csv(fpath, headers, data_rows):
    is_py3 = sys.version_info[0] >= 3
    f = None
    try:
        if is_py3:
            f = open(fpath, 'w', newline='', encoding='utf-8')
        else:
            f = open(fpath, 'wb')
        writer = csv.writer(f)
        if headers: writer.writerow(headers)
        writer.writerows(data_rows)
        print("       -> CSV Saved: " + os.path.basename(fpath))
    except Exception as e:
        print("       !! CSV Save Error: " + str(e))
    finally:
        if f: f.close()


# ==================================================
#    FD 提取函数 (Force-Displacement)
# ==================================================
def extract_fd_data(step, assembly, instance_name, node_set_name, u_comp, rf_comp):
    print("  [FD] Extracting Force-Disp (Set: " + node_set_name + ")...")

    node_set = None
    if node_set_name in assembly.nodeSets:
        node_set = assembly.nodeSets[node_set_name]
    elif instance_name in assembly.instances:
        instance = assembly.instances[instance_name]
        if node_set_name in instance.nodeSets:
            node_set = instance.nodeSets[node_set_name]

    if node_set is None:
        print("       !! Error: Node Set '" + node_set_name + "' not found")
        return None

    try:
        # 解析分量索引 (e.g., 'U2' -> index 1)
        u_idx = int(u_comp[-1]) - 1
        rf_idx = int(rf_comp[-1]) - 1
        data = []

        for frame in step.frames:
            try:
                # 获取场输出
                u_field = frame.fieldOutputs['U'].getSubset(region=node_set)
                rf_field = frame.fieldOutputs['RF'].getSubset(region=node_set)

                if u_field.values and rf_field.values:
                    val_u_obj = u_field.values[0]
                    val_rf_obj = rf_field.values[0]

                    # 兼容不同数据类型
                    try:
                        u_vec = val_u_obj.data
                        rf_vec = val_rf_obj.data
                    except:
                        u_vec = val_u_obj.dataDouble
                        rf_vec = val_rf_obj.dataDouble

                    u_val = u_vec[u_idx]
                    rf_val = rf_vec[rf_idx]

                    # 记录: Time, Disp, Force
                    data.append((frame.frameValue, u_val, rf_val))
            except:
                continue

        print("       -> Extracted " + str(len(data)) + " FD frames")
        return data
    except Exception as e:
        print("       !! Global FD Error: " + str(e))
        return None


# ==================================================
#    辅助：杆件分组 (Clustering)
# ==================================================
def group_elements_into_rods(element_id_list, connectivity_map):
    if not element_id_list: return []

    node_to_eids = {}
    for eid in element_id_list:
        if eid in connectivity_map:
            for nid in connectivity_map[eid]:
                if nid not in node_to_eids: node_to_eids[nid] = []
                node_to_eids[nid].append(eid)

    visited = set()
    groups = []
    for start_eid in element_id_list:
        if start_eid in visited: continue
        current_group = []
        stack = [start_eid]
        visited.add(start_eid)
        while stack:
            curr_eid = stack.pop()
            current_group.append(curr_eid)
            if curr_eid in connectivity_map:
                for nid in connectivity_map[curr_eid]:
                    for neighbor in node_to_eids.get(nid, []):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            stack.append(neighbor)
        groups.append(current_group)
    return groups


# ==================================================
#    CL 提取: 杆件中心 (Rod Centers)
# ==================================================
def extract_failed_rods(step, assembly, instance_name, set_name, status_var):
    print("  [CL] Extracting Failed Rods (Connectivity Clustering)...")
    try:
        instance = assembly.instances[instance_name]
        el_set = instance.elementSets[set_name]
        node_map = {n.label: n.coordinates[0] for n in instance.nodes}
        connectivity = {el.label: el.connectivity for el in el_set.elements}
    except Exception as e:
        print("       !! Mesh Read Error: " + str(e))
        return []

    csv_rows = []
    recorded_element_ids = set()

    print("       [Processing] Scanning frames...")
    for frame in step.frames:
        time_val = frame.frameValue
        current_new_failures = []
        try:
            subset = frame.fieldOutputs[status_var].getSubset(region=el_set)
            for v in subset.values:
                stat = v.data if hasattr(v, 'data') else v.dataDouble
                if abs(stat) < 1e-6:  # STATUS == 0.0
                    eid = v.elementLabel
                    if eid not in recorded_element_ids:
                        current_new_failures.append(eid)
                        recorded_element_ids.add(eid)
        except:
            continue

        if current_new_failures:
            rod_groups = group_elements_into_rods(current_new_failures, connectivity)
            for group in rod_groups:
                nodes_in_rod = set()
                for eid in group:
                    if eid in connectivity:
                        for nid in connectivity[eid]: nodes_in_rod.add(nid)

                x_vals = [node_map[nid] for nid in nodes_in_rod if nid in node_map]

                center_x = None
                if x_vals:
                    # 恢复原始的平均值逻辑
                    center_x = sum(x_vals) / float(len(x_vals))

                    csv_rows.append([time_val, center_x])

    return csv_rows


# ==================================================
#    核心函数: 倒序滤波 (Future Min)
# ==================================================
def filter_data_by_future_min(data_rows):
    if not data_rows: return []
    print("       [Filter] Applying 'Future Min' logic...")

    filtered_reversed = []
    last_val = data_rows[-1][2]
    min_future_da = last_val
    filtered_reversed.append(data_rows[-1])

    for i in range(len(data_rows) - 2, -1, -1):
        current_row = data_rows[i]
        current_da = current_row[2]

        if current_da <= min_future_da:
            filtered_reversed.append(current_row)
            min_future_da = current_da

    return filtered_reversed[::-1]


# ==================================================
#    [新增] CT 试件裂纹处理算法 (原有一套)
# ==================================================
def process_crack_CT(raw_rod_data):
    """
    CT 算法: 假设裂纹从右向左扩展 (或者基于坐标系定义)。
    逻辑: Delta_a = a0 - x (选取每帧 delta_a 最大的点)
    """
    print("       [Algo] Using CT Specimen Algorithm (a0 - x)")

    # 1. 按时间分组
    data_by_time = defaultdict(list)
    for t, x in raw_rod_data:
        data_by_time[t].append(x)

    sorted_times = sorted(data_by_time.keys())
    if not sorted_times:
        return []

    # 2. 确定 a0 (取第一帧失效数据的最右端/最大值)
    first_time = sorted_times[0]
    a0 = max(data_by_time[first_time])
    print("       [Info] CT a0 (Initial Crack Tip X) = " + str(a0))

    # 3. 计算 Delta_a
    intermediate_data = []
    for t in sorted_times:
        x_list = data_by_time[t]
        # 核心逻辑: 计算 a0 - x，取这一帧里最大的 delta_a
        candidates = [(x, a0 - x) for x in x_list]
        best = max(candidates, key=lambda item: item[1])  # 找 delta_a 最大的
        intermediate_data.append([t, best[0], best[1]])

    # 4. 倒序滤波 (CT 专用滤波)
    return filter_data_by_future_min(intermediate_data)


# ==================================================
#    [新增] SENT 试件裂纹处理算法 (新的一套)
# ==================================================
def process_crack_SENT(raw_rod_data):
    """
    SENT 算法: 假设裂纹从左向右扩展 (根据通常 SENT 构型)。
    逻辑: Delta_a = x - a0 (通常逻辑)
    注意: 你需要根据实际坐标系修改这里的数学逻辑
    """
    print("       [Algo] Using SENT Specimen Algorithm (x - a0)")

    # 1. 按时间分组
    data_by_time = defaultdict(list)
    for t, x in raw_rod_data:
        data_by_time[t].append(x)

    sorted_times = sorted(data_by_time.keys())
    if not sorted_times:
        return []

    # 2. 确定 a0
    # SENT 通常是从左边开始裂，初始裂纹尖端可能是第一帧里 X 最小的值？
    # 或者你需要手动指定 a0？这里假设是第一帧的最右端作为切口尖端
    first_time = sorted_times[0]
    # 【注意】这里通常取最大值还是最小值，取决于你的坐标系原点和建模方式
    # 假设：SENT 切口在左侧，向右扩展 -> a0 是第一帧失效的最右侧点
    a0 = max(data_by_time[first_time])
    print("       [Info] SENT a0 (Initial Notch Tip X) = " + str(a0))

    # 3. 计算 Delta_a
    intermediate_data = []
    for t in sorted_times:
        x_list = data_by_time[t]

        # 【不同点】SENT 可能是 x - a0 (向右扩展)
        # 找出这一帧里最靠右的点 (x 最大)
        current_tip_x = max(x_list)

        delta_a = current_tip_x - a0

        # 如果计算出负值，说明这一帧的数据点还在初始裂纹左边（杂讯），归零
        if delta_a < 0: delta_a = 0.0

        intermediate_data.append([t, current_tip_x, delta_a])

    # 4. 滤波
    # SENT 也可以用倒序滤波，或者你可以写一个简单的 "max so far" 滤波
    return filter_data_by_future_min(intermediate_data)


# ==================================================
#    Main
# ==================================================
def main():
    print("--- Extract Data (v10.3 - Complete) ---")
    odb = None
    try:
        odb = openOdb(MASTER_CONFIG['ODB_FILE_PATH'], readOnly=True)
        step = odb.steps[MASTER_CONFIG['STEP_NAME']]
        assembly = odb.rootAssembly

        # -------------------------------------------------------
        # 1. FD (力-位移)
        # -------------------------------------------------------
        fd_data = extract_fd_data(step, assembly,
                                  MASTER_CONFIG['INSTANCE_NAME_FD'],
                                  MASTER_CONFIG['NODE_SET_NAME_FD'],
                                  MASTER_CONFIG['U_COMPONENT'],
                                  MASTER_CONFIG['RF_COMPONENT'])
        if fd_data:
            save_to_csv(MASTER_CONFIG['CSV_OUTPUT_FD'], ['Time', 'Displacement', 'Force'], fd_data)

        # -------------------------------------------------------
        # 2. CL (裂纹长度 - 杆件聚类)
        # -------------------------------------------------------
        specimen_type = getattr(cfg, 'SPECIMEN_TYPE', 'CT')

        raw_rod_data = extract_failed_rods(
            step, assembly,
            MASTER_CONFIG['INSTANCE_NAME_CL'],
            MASTER_CONFIG['ELEMENT_SET_NAME_CL'],
            MASTER_CONFIG['STATUS_VARIABLE']
        )

        if raw_rod_data:
            print("       [Post-Processing] Specimen Type: " + specimen_type)
            final_data = []

            # === 分支判断核心 ===
            if specimen_type == 'SENT':
                final_data = process_crack_SENT(raw_rod_data)
            else:
                # 默认为 CT
                final_data = process_crack_CT(raw_rod_data)
            # ==================

            save_to_csv(
                MASTER_CONFIG['CSV_OUTPUT_CL'],
                ['Time', 'Tip_X', 'Filtered_delta_a'],
                final_data
            )
        else:
            print("       [!] No rod failures detected.")

        # -------------------------------------------------------
        # 3. HO (历史输出)
        # -------------------------------------------------------
        print("  [HO] Extracting History Outputs...")
        for var in MASTER_CONFIG['HISTORY_VARIABLES']:
            try:
                r = step.historyRegions[MASTER_CONFIG['HISTORY_REGION_NAME']]
                ho = r.historyOutputs[var].data
                if ho:
                    csv_path = os.path.join(DATA_DIR, EXPERIMENT_ID + "_" + var + "_vs_time.csv")
                    save_to_csv(csv_path, ['Time', var], ho)
            except:
                continue

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("!! Global Error: " + str(e))
    finally:
        if odb: odb.close()
        print("--- Done ---")


if __name__ == "__main__":
    main()
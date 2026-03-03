# -*- coding: utf-8 -*-
# file: project_config.py
import os


def _split_model_name(exp_id):
    parts = str(exp_id).split('_')
    if len(parts) < 3:
        raise ValueError(
            "模型名格式错误: '{0}'。期望格式类似 CT_Kagome_050_90。".format(exp_id)
        )
    return parts


def infer_specimen_type(exp_id):
    """根据模型名第一段识别试样类型。"""
    if not exp_id:
        raise ValueError("exp_id 不能为空，无法识别试样类型。")

    prefix = _split_model_name(exp_id)[0].upper()
    mapping = {
        'CT': 'CT',
        'SENT': 'SENT',
        'ST': 'SENT',
    }
    if prefix not in mapping:
        raise ValueError(
            "无法从模型名识别试样类型: '{0}'。请使用 CT_* / ST_* / SENT_* 命名。".format(exp_id)
        )
    return mapping[prefix]


def infer_lattice_type(exp_id):
    """根据模型名第二段识别晶格类型。"""
    if not exp_id:
        raise ValueError("exp_id 不能为空，无法识别晶格类型。")

    lattice_raw = _split_model_name(exp_id)[1]
    mapping = {
        'HOMO': 'Homo',
        'HEX': 'Hex',
        'HONEY': 'Honey',
        'KAGOME': 'Kagome',
    }
    key = lattice_raw.upper()
    if key not in mapping:
        raise ValueError(
            "无法从模型名识别晶格类型: '{0}'。请使用 Homo/Hex/Honey/Kagome。".format(exp_id)
        )
    return mapping[key]


def infer_thin_rod_width(exp_id):
    """根据模型名第三段三位数识别细杆宽度(mm)。

    规则: 0** 表示 0.** mm，例如:
      060 -> 0.6, 020 -> 0.2, 010 -> 0.1, 055 -> 0.55
    """
    if not exp_id:
        raise ValueError("exp_id 不能为空，无法识别细杆宽度。")

    token = _split_model_name(exp_id)[2]
    if not (len(token) == 3 and token.isdigit()):
        raise ValueError(
            "细杆宽度编码格式错误: '{0}'。期望三位数字(如 060/020/010/055)，并按 0** -> 0.** mm 解析。".format(token)
        )

    width = int(token) / 100.0
    if width <= 0:
        raise ValueError("细杆宽度必须大于0，当前解析值: {0}".format(width))
    return width


def get_rod_widths(exp_id):
    """返回(细杆宽度, 粗杆宽度)。粗杆宽度固定为0.6mm。"""
    thin_width = infer_thin_rod_width(exp_id)
    thick_width = 0.6
    return thin_width, thick_width


# ==========================================
#      0. 核心控制 (修改这里切换 CT / SENT)
# ==========================================
# 选项: 'CT' 或 'SENT'
SPECIMEN_TYPE = 'CT'

JOB_LIST = [
    'CT_Tri_HD_Vertical_024',
    # 'B05Solid',
]
# ==========================================
#      1. 几何参数 (所有计算脚本共用)
# ==========================================
# 通用参数
W = 50.0       # 宽度 (mm)
t = 0.24 * 2
B = t        # 厚度 (mm)
B_N = B        # 净厚度 (mm) - 如果无侧槽，则 B_N = B
SIGMA_0S = 1098.0     # 屈服强度 (MPa)
L_CHAR = 3.0        # 特征长度 (mm) - 用于无量纲化
E_MAT = 110000     # 弹性模量 (MPa)
H = 45.0
# ==========================================
#      2. ABAQUS 提取配置 (提取脚本专用)
# ==========================================
# ODB 文件所在的文件夹
ODB_DIR_PATH = r"F:\ABAQUS2024\temp"

# Step 名称
STEP_NAME = 'Step-1'

# --- [FD] 力-位移 ---
FD_INSTANCE = 'PART-2-1'   # Instance 名称
FD_NODE_SET = 'M_SET-1'    # Node Set 名称 (施力点)
FD_U_COMP = 'U2'         # 位移分量
FD_RF_COMP = 'RF2'        # 反力分量

# --- [CL] 裂纹长度 ---
# 原理: 监控失效单元(STATUS=0)的位置来推断裂纹尖端
CL_INSTANCE = 'PART-1-1'
CL_ELEMENT_SET = 'SET-1'
CL_VAR_NAME = 'STATUS'

# ==========================================
#      3. 自动路径辅助 (无需修改)
# ==========================================
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR_NAME = 'data'
RESULTS_DIR_NAME = 'results'

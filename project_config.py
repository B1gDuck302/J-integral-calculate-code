# -*- coding: utf-8 -*-
# file: project_config.py
import os

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
W        = 50.0       # 宽度 (mm)
t        = 0.24*2
B        = t        # 厚度 (mm)
B_N      = B        # 净厚度 (mm) - 如果无侧槽，则 B_N = B
SIGMA_0S = 1098.0     # 屈服强度 (MPa)
L_CHAR   = 3.0        # 特征长度 (mm) - 用于无量纲化
E_MAT    = 110000     # 弹性模量 (MPa)
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
FD_U_COMP   = 'U2'         # 位移分量
FD_RF_COMP  = 'RF2'        # 反力分量

# --- [CL] 裂纹长度 ---
# 原理: 监控失效单元(STATUS=0)的位置来推断裂纹尖端
CL_INSTANCE    = 'PART-1-1'
CL_ELEMENT_SET = 'SET-1'
CL_VAR_NAME    = 'STATUS'

# ==========================================
#      3. 自动路径辅助 (无需修改)
# ==========================================
try:
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except:
    ROOT_DIR = os.path.abspath(os.path.join(os.getcwd(), '..'))

DATA_DIR_NAME = 'data'
RESULTS_DIR_NAME = 'results'
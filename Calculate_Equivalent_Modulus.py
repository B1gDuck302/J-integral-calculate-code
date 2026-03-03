# -*- coding: utf-8 -*-
# SCRIPT: Calculate_Equivalent_Modulus.py (Final Complete Version - FIXED OUTPUT)
# 专注于使用无量纲柔度因子 V' 进行纯模量 E 的计算。

import pandas as pd
import numpy as np
import os
import sys
from scipy.stats import linregress
# 移除 matplotlib
import project_config as cfg

# ====================================================
#    配置参数 (简化)
# ====================================================
LINEAR_START_RATIO = 1e-6
LINEAR_END_RATIO = 0.3
ELASTIC_RATIO_EPSILON = 0.01

# ====================================================
#    核心算法: 无量纲柔度因子 V'
# ====================================================
def calculate_compliance_coefficient(a, W, sp_type):
    """
    计算无量纲柔度 V' (Dimensionless Compliance)
    定义: E = (Slope * V') / B
    """
    u = a / W
    if u > 0.99: u = 0.99

    if sp_type == 'SENT':
        # SENT (CMOD) 公式 - 来源于用户提供的多项式
        term_base = u / ((1 - u) ** 2)
        term_poly = 1.197 - 1.933 * u + 5.398 * (u ** 2) - 2.176 * (u ** 3) + 2.072 * (u ** 4)
        v_prime = term_base * term_poly * 2.0
    elif sp_type == 'CT':
        # CT (LLD) 公式 - 来源于 ASTM E1820
        part1 = ((1 + u) / (1 - u)) ** 2
        part2 = 2.1630 + 12.219 * u - 20.065 * u ** 2 - 0.9925 * u ** 3 + 20.609 * u ** 4 - 9.9314 * u ** 5
        v_prime = part1 * part2

    return v_prime


def load_simulation_data(data_dir, exp_id, file_suffix, col_name):
    """通用数据加载函数：加载 P-V, ALLWK, ALLSE 等"""
    f_path = os.path.join(data_dir, f'{exp_id}_{file_suffix}.csv')
    if not os.path.exists(f_path):
        if col_name != 'P' and col_name != 'V':  # P-V 缺失是致命错误，其他警告
            print(f"Warning: File for {col_name} not found at {f_path}")
        return None
    try:
        df = pd.read_csv(f_path)

        if col_name in ['P', 'V']:
            # P-V 数据的特殊处理：归零和重命名
            df = df.rename(columns=lambda x: 'P' if 'Force' in x else ('V' if 'Displacement' in x else x))
            df['V'] = df['V'] - df['V'].iloc[0]
            df['P'] = df['P'] - df['P'].iloc[0]
            return df
        else:
            # ALLWK, ALLSE 数据的处理：归零和重命名
            df = df.rename(columns={'Time': 'Time', col_name: col_name})
            df[col_name] = df[col_name] - df[col_name].iloc[0]
            return df[['Time', col_name]]

    except Exception as e:
        print(f"Error loading {col_name} data: {e}")
        return None


def main():
    # 获取实验 ID
    exp_id = sys.argv[1] if len(sys.argv) > 1 else 'Unknown'

    # 路径设置
    res_dir = os.path.join(cfg.ROOT_DIR, 'results', exp_id)
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)

    # ==========================================
    #   1. 读取几何与材料参数 (来自 project_config)
    # ==========================================
    try:
        d_rod = cfg.t  # 杆径 (对应配置里的 t)
        L_rod = cfg.L_CHAR  # 杆长 (对应配置里的 L_CHAR)
        E_s = cfg.E_MAT  # 基体材料模量 (对应配置里的 E_MAT)
    except AttributeError as e:
        print(f"!! [错误] project_config.py 缺少必要变量: {e}")
        return

    # ==========================================
    #   2. 使用圆截面杆三角形网格公式计算
    # ==========================================
    # 公式: E* = (sqrt(3)*pi / 6) * (d/L) * E_s
    geometric_factor = (np.sqrt(3.0) * np.pi) / 6.0  # 约等于 0.9069
    E_exact = geometric_factor * (d_rod / L_rod) * E_s

    # ==========================================
    #   3. 保存结果 (关键：匹配下游脚本读取格式)
    # ==========================================
    # 下游脚本 J_Integral...py 和 KR_Fit.py 会查找带有 "Method B (Energy):" 标签的行
    out_file = os.path.join(res_dir, f'{exp_id}_Modulus_EnergyCriteria.txt')

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"Experiment ID: {exp_id}\n")
        f.write(f"Specimen Type: {cfg.SPECIMEN_TYPE}\n")
        f.write(f"Calculation Method: Circular Rod Analytical (Triangular Lattice)\n")
        f.write(f"Formula: E = (sqrt(3)*pi/6) * (d/L) * E_s\n")
        f.write(f"------------------------------------------------\n")
        f.write(f"Rod Diameter (d): {d_rod} mm\n")
        f.write(f"Rod Length (L):   {L_rod} mm\n")
        f.write(f"Base Modulus (Es): {E_s} MPa\n")
        f.write(f"Geometric Factor: {geometric_factor:.4f}\n")
        f.write(f"------------------------------------------------\n")
        # 下面这一行是整合的关键，严禁修改格式，否则后续脚本会报错
        f.write(f"Method B (Energy): {E_exact:.4f}\n")

    print(f"[*] {exp_id} 模量计算成功！")
    print(f"[*] 精确等效模量 E = {E_exact:.2f} MPa (已采用圆截面修正公式)")
    print(f"[*] 结果已存入后续脚本的指定接口文件: {out_file}")

if __name__ == "__main__":
    main()



# -*- coding: utf-8 -*-
# SCRIPT: J积分计算_StepHold_Final.py
#
# 功能:
# 1. 计算: 使用 ASTM E1820 增量法计算全过程 J 积分。
# 2. 逻辑: 裂纹长度采用 Step-Hold (阶梯保持) 模式，杜绝线性插值。
# 3. 输出 (用户指定):
#    - Excel: 保存 "全时间步" (Full History) 的所有计算数据。
#    - Plot: 只画 "裂纹扩展点" (Fracture Points) 的 J-R 关系。

import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
import sys
import matplotlib.pyplot as plt
import os
import math
from dataclasses import dataclass, field
import numba
import argparse
import project_config as cfg


# --- (配置区域) ---
@dataclass
class ScriptConfig:
    EXPERIMENT_ID: str = None
    FD_FILE_SUFFIX: str = '_force_displacement_from_FIELD.csv'
    CRACK_FILE_SUFFIX: str = '_crack_length_UserTip_vs_time.csv'
    ALLWK_FILE_SUFFIX: str = '_ALLWK_vs_time.csv'

    l: float = cfg.L_CHAR
    W: float = cfg.W
    B: float = cfg.B
    B_N: float = cfg.B_N

    FILTER_CUTOFF_HZ: float = 50.0

    PROJECT_ROOT: str = field(init=False)
    BASE_DATA_DIR: str = field(init=False)
    BASE_RESULTS_DIR: str = field(init=False)
    DATA_DIR: str = field(init=False)
    RESULTS_DIR: str = field(init=False)
    FD_FILE: str = field(init=False)
    CRACK_FILE: str = field(init=False)
    ALLWK_FILE: str = field(init=False)
    OUTPUT_EXCEL_FILE: str = field(init=False)
    OUTPUT_PLOT_FD: str = field(init=False)
    OUTPUT_PLOT_JR: str = field(init=False)

    def __post_init__(self):
        try:
            self.PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except NameError:
            self.PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), '..'))

        self.BASE_DATA_DIR = os.path.join(self.PROJECT_ROOT, 'data')
        self.BASE_RESULTS_DIR = os.path.join(self.PROJECT_ROOT, 'results')
        self.DATA_DIR = os.path.join(self.BASE_DATA_DIR, self.EXPERIMENT_ID)
        self.RESULTS_DIR = os.path.join(self.BASE_RESULTS_DIR, self.EXPERIMENT_ID)
        os.makedirs(self.RESULTS_DIR, exist_ok=True)

        self.FD_FILE = os.path.join(self.DATA_DIR, f'{self.EXPERIMENT_ID}{self.FD_FILE_SUFFIX}')
        self.CRACK_FILE = os.path.join(self.DATA_DIR, f'{self.EXPERIMENT_ID}{self.CRACK_FILE_SUFFIX}')
        self.ALLWK_FILE = os.path.join(self.DATA_DIR, f'{self.EXPERIMENT_ID}{self.ALLWK_FILE_SUFFIX}')

        # 输出文件名
        self.OUTPUT_EXCEL_FILE = os.path.join(self.RESULTS_DIR, f'{self.EXPERIMENT_ID}_J-R_Curve_Results.xlsx')
        self.OUTPUT_PLOT_FD = os.path.join(self.RESULTS_DIR, f'{self.EXPERIMENT_ID}_Force_Disp_Check.png')
        self.OUTPUT_PLOT_JR = os.path.join(self.RESULTS_DIR, f'{self.EXPERIMENT_ID}_J_R_Curve_PointsOnly.png')


plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


# --- (绘图函数) ---
def plot_jr_curve(df_points, output_filename):
    """
    只绘制提取出的点 (df_points)，不绘制全过程曲线。
    """
    try:
        if df_points.empty or 'delta_a (mm)' not in df_points.columns: return

        # 过滤掉 J 极小的数据 (比如弹性段刚开始) 以免干扰绘图
        plot_data = df_points[df_points['J_total (N/mm)'] > 1e-3].copy()

        plt.figure(figsize=(10, 7))

        # 绘制散点
        plt.plot(plot_data['delta_a (mm)'], plot_data['J_total (N/mm)'],
                 'ro', markersize=6, label='Extracted Fracture Points')

        # 也可以用虚线连起来，看趋势
        plt.plot(plot_data['delta_a (mm)'], plot_data['J_total (N/mm)'],
                 'k--', linewidth=0.5, alpha=0.5)

        plt.title('J-R Curve (Fracture Points Only)')
        plt.xlabel(r'Crack Extension $\Delta a$ (mm)')
        plt.ylabel(r'J-Integral $J$ (N/mm)')
        plt.legend()
        plt.grid(True, linestyle=':', alpha=0.7)

        plt.tight_layout()
        plt.savefig(output_filename, dpi=300)
        plt.close()
        print(f"-> 绘图已保存(只含散点): {output_filename}")

    except Exception as e:
        print(f"J-R 绘图失败: {e}")


# --- (计算核心函数) ---
def filter_data(df_fd, cutoff_hz):
    if len(df_fd) < 10: return df_fd['Force']
    time_diffs = df_fd['Time'].diff().dropna()
    if time_diffs.empty or time_diffs.mean() <= 0: return df_fd['Force']
    fs = 1.0 / time_diffs.mean()
    nyquist = 0.5 * fs
    normal_cutoff = cutoff_hz / nyquist
    if normal_cutoff >= 1.0 or normal_cutoff <= 0: return df_fd['Force']
    b, a = butter(4, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, df_fd['Force'])


def calculate_eta_pl_CT(a_W):
    b_W = 1.0 - a_W
    b_W[b_W < 1e-4] = 1e-4  # 避免除零
    return 2.0 + (0.522 * b_W)


def calculate_gamma_pl_CT(a_W):
    b_W = 1.0 - a_W
    b_W[b_W < 1e-4] = 1e-4
    return 1.0 + (0.76 * b_W)


@numba.jit(nopython=True)
def compute_j_total_incremental_numba(n_points, J_total_out, a_i_arr, b_i_arr, eta_pl_arr, gamma_pl_arr,
                                      A_total_inc_arr, B_N):
    for i in range(1, n_points):
        J_prev = J_total_out[i - 1]
        b_prev = b_i_arr[i - 1]
        eta_prev = eta_pl_arr[i - 1]
        gamma_prev = gamma_pl_arr[i - 1]

        a_i = a_i_arr[i]
        A_total_inc = A_total_inc_arr[i]
        delta_a_step = max(0.0, a_i - a_i_arr[i - 1])

        if b_prev <= 1e-6 or np.isnan(eta_prev):
            J_i = J_prev
        else:
            term1 = J_prev
            term2 = (eta_prev * A_total_inc) / (B_N * b_prev)
            term3 = max(0.0, 1.0 - (gamma_prev * delta_a_step / b_prev))
            J_i = max(0.0, (term1 + term2) * term3)
        J_total_out[i] = J_i
    return J_total_out


def calculate_j_integral_FullHistory(df_calc, config):
    """
    对传入的全量数据表进行 J 积分计算
    """
    n = len(df_calc)
    if n < 2: return df_calc

    W, B_N = config.W, config.B_N

    # 1. 几何参数 (每一行都算)
    df_calc['a_W'] = df_calc['a_i(mm)'] / W
    df_calc['b_i (mm)'] = (W - df_calc['a_i(mm)']).clip(lower=1e-6)

    a_W_vals = df_calc['a_W'].values
    df_calc['eta_pl_current'] = calculate_eta_pl_CT(a_W_vals)
    df_calc['gamma_pl_current'] = calculate_gamma_pl_CT(a_W_vals)

    # 2. 能量增量 (ALLWK)
    # ALLWK 是累计功，差分得到每一步的增量功
    ALLWK_prev = df_calc['ALLWK'].shift(1).fillna(0)
    df_calc['A_total_inc (mJ)'] = (df_calc['ALLWK'] - ALLWK_prev).clip(lower=0.0)

    # 3. 递推积分类
    J_out = np.zeros(n, dtype=np.float64)
    compute_j_total_incremental_numba(
        n, J_out,
        df_calc['a_i(mm)'].values, df_calc['b_i (mm)'].values,
        df_calc['eta_pl_current'].values, df_calc['gamma_pl_current'].values,
        df_calc['A_total_inc (mJ)'].values, B_N
    )
    df_calc['J_total (N/mm)'] = J_out
    return df_calc


# --- (数据加载与预处理) ---
def load_data(config):
    print(f"--- 加载数据: {config.EXPERIMENT_ID} ---")
    try:
        df_fd = pd.read_csv(config.FD_FILE)
        df_crack = pd.read_csv(config.CRACK_FILE)
        df_allwk = pd.read_csv(config.ALLWK_FILE)
    except Exception as e:
        sys.exit(f"文件加载失败: {e}")

    # 列名标准化处理
    if 'Filtered_delta_a' not in df_crack.columns:
        if 'Crack Extension delta_a (mm)' in df_crack.columns:
            df_crack['Filtered_delta_a'] = df_crack['Crack Extension delta_a (mm)']
        else:
            df_crack['Filtered_delta_a'] = 0.0

    return df_fd, df_crack, df_allwk


def preprocess_step_hold(df_fd_raw, df_crack_raw, df_allwk_raw, config):
    # 1. 准备主轴 (ALLWK) - 保持不变
    wk_time = next((c for c in df_allwk_raw.columns if 'Time' in c), 'Time')
    wk_val = next((c for c in df_allwk_raw.columns if 'ALLWK' in c), 'ALLWK')

    df_main = df_allwk_raw.rename(columns={wk_time: 'Time', wk_val: 'ALLWK'}).copy()
    df_main = df_main.sort_values('Time').reset_index(drop=True)

    # 强制 0 点
    if df_main['Time'].min() > 1e-9:
        df_main = pd.concat([pd.DataFrame({'Time': [0.0], 'ALLWK': [0.0]}), df_main], ignore_index=True)
        df_main = df_main.sort_values('Time').reset_index(drop=True)

    # 2. 准备裂纹数据 (Strict Mode)
    print("   -> [Strict] 正在读取裂纹数据 (基于 Tip_X)...")

    # 严谨检查: 必须包含 Tip_X
    if 'Tip_X' not in df_crack_raw.columns:
        sys.exit("!! [Fatal Error] 裂纹数据缺少 'Tip_X' 列。无法进行物理计算，程序终止。")

    cl_time = next((c for c in df_crack_raw.columns if 'Time' in c), 'Time')
    df_cl_clean = df_crack_raw.rename(columns={cl_time: 'Time'})[['Time', 'Tip_X']].copy()
    df_cl_clean = df_cl_clean.sort_values('Time').dropna()

    if df_cl_clean.empty:
        sys.exit("!! [Fatal Error] 裂纹数据为空 (0 rows)。")

    # 3. 合并 (Step-Hold Backward)
    # 逻辑: 如果当前时刻没有裂纹记录，沿用上一时刻的坐标
    df_merged = pd.merge_asof(
        df_main,
        df_cl_clean,
        on='Time',
        direction='forward'
    )
    # 4. 自动截止 (User Req: "最后一部分就先不算了")
    # 如果 forward 匹配返回 NaN (意味着没有未来的断裂事件了)，直接丢弃这些行
    # 这会自动把数据截断在最后一个断裂点时刻
    initial_len = len(df_merged)
    df_merged = df_merged.dropna(subset=['Tip_X'])
    final_len = len(df_merged)

    if final_len < initial_len:
        print(f"      [Info] 自动截断数据: 忽略了最后 {initial_len - final_len} 个无后续断裂的时间步。")

    if df_merged.empty:
        sys.exit("!! [Error] 匹配后数据为空。请检查裂纹事件时间范围。")
    # 4. 填充空值 (使用第一帧数据作为初始状态)
    # 注意: 这里不再使用 config.a0_initial，而是信任提取出的坐标
    start_tip_x = df_cl_clean['Tip_X'].iloc[0]
    df_merged['Tip_X'] = df_merged['Tip_X'].fillna(start_tip_x)

    # 5. 核心物理计算
    # 物理裂纹长度 a = 试样宽度 W - 裂尖坐标 X
    df_merged['a_i(mm)'] = config.W - df_merged['Tip_X']

    # 计算扩展量 delta_a (用于 J-R 曲线绘制)
    # 公式: 当前物理长度 - 初始物理长度
    initial_a_phys = config.W - start_tip_x
    df_merged['delta_a (mm)'] = df_merged['a_i(mm)'] - initial_a_phys

    # 几何边界限制 (防止数值噪音导致 a > W)
    df_merged['a_i(mm)'] = df_merged['a_i(mm)'].clip(upper=0.999 * config.W)

    print(f"      [Info] 初始物理裂纹长度 a0 = {initial_a_phys:.4f} mm (来源: W - Tip_X)")

    # 6. 映射力-位移 (辅助数据，用于Excel查看) - 保持不变
    fd_time = next((c for c in df_fd_raw.columns if 'Time' in c), 'Time')
    df_fd_clean = df_fd_raw.rename(columns={fd_time: 'Time'}).sort_values('Time')

    # 简单滤波
    df_fd_clean['Force_Filtered'] = filter_data(df_fd_clean.copy(), config.FILTER_CUTOFF_HZ)

    # 插值映射
    df_merged['Displacement'] = np.interp(df_merged['Time'], df_fd_clean['Time'], df_fd_clean['Displacement'], left=0.0)
    df_merged['Force_Filtered'] = np.interp(df_merged['Time'], df_fd_clean['Time'], df_fd_clean['Force_Filtered'],
                                            left=0.0)

    return df_merged


def extract_specific_points(df_full, df_crack_raw):
    """
    只提取裂纹扩展发生的那些时刻点 (用于绘图)
    """
    print("   -> 提取裂纹扩展关键点...")
    time_col = next((c for c in df_crack_raw.columns if 'Time' in c), 'Time')
    target_times = df_crack_raw[[time_col]].rename(columns={time_col: 'Time'}).sort_values('Time')

    # 反向查找最近的计算结果
    df_points = pd.merge_asof(
        target_times,
        df_full,
        on='Time',
        direction='forward'
    )
    return df_points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exp_id', nargs='?', default='B05Solid')
    args = parser.parse_args()

    config = ScriptConfig(EXPERIMENT_ID=args.exp_id)

    # 1. 加载
    df_fd, df_cl, df_wk = load_data(config)

    # 2. 预处理 (Step-Hold, 全量表)
    df_full_input = preprocess_step_hold(df_fd, df_cl, df_wk, config)

    # 3. 计算 (全量 J 积分)
    df_full_res = calculate_j_integral_FullHistory(df_full_input, config)

    # 4. 提取 (关键点)
    df_points = extract_specific_points(df_full_res, df_cl)

    # 5. 保存 Excel (满足需求: 全时间J都写进去)
    print(f"   -> 正在保存 Excel: {config.OUTPUT_EXCEL_FILE}")
    with pd.ExcelWriter(config.OUTPUT_EXCEL_FILE) as writer:
        # Sheet1: 全过程数据 (Full History) - 您要求的
        df_full_res.to_excel(writer, sheet_name='Full_History_All_Steps', index=False)

        # Sheet2: 提取出的关键点 (Extracted Points) - 方便查看
        df_points.to_excel(writer, sheet_name='Extracted_Fracture_Points', index=False)

    print(f"Done: Excel 已保存。")

    # 6. 绘图 (满足需求: 只画想要的裂纹扩展点)
    # 注意这里传入的是 df_points，不是 df_full_res
    plot_jr_curve(df_points, config.OUTPUT_PLOT_JR)


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
# SCRIPT: J_Integral_Hybrid_Incremental_ALLPD.py (v12.1 - Custom SENT)
# 功能: 兼容 CT (旧增量法) 和 SENT (新总功法) 的 J 积分计算
# 核心: J = Jel(K) + Jpl(总功法/增量法)

import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
import sys
import matplotlib.pyplot as plt
import os
import argparse
import project_config as cfg  # 关键依赖

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


# ==================================================
#    A. 几何因子库 (Geometry Library)
# ==================================================

# --- 1. CT 试样 (ASTM E1820) ---
def calc_K_CT(P, a, W, B):
    # 标准 CT K解
    if P <= 0 or a >= W: return 0.0
    x = a / W
    x = np.clip(x, 0.0, 0.99)
    term1 = (2 + x) / ((1 - x) ** 1.5)
    term2 = 0.886 + 4.64 * x - 13.32 * (x ** 2) + 14.72 * (x ** 3) - 5.6 * (x ** 4)
    return (P / (B * np.sqrt(W))) * term1 * term2


def calc_eta_CT(a, W):
    return 2.0 + 0.522 * (1.0 - a / W)


def calc_gamma_CT(a, W):
    return 1.0 + 0.76 * (1.0 - a / W)


# --- 2. SENT 试样 (用户提供的公式) ---
# 基于公式 (5) 和 (6)
def calc_K_SENT(P, a, W, B):
    if P <= 0 or a >= W: return 0.0
    val_aW = a / W
    val_aW = np.clip(val_aW, 0.0, 0.999)  # 确保不超过 1

    # 计算 π*a/(2W)
    aW_half_pi = np.pi * val_aW / 2.0

    # 几何因子 f(a/W) - 公式 6
    # 确保分母 cos(aW_half_pi) 不为零
    cos_val = np.cos(aW_half_pi)
    if cos_val == 0.0: return 0.0

    term_sqrt = np.sqrt((2 * np.tan(aW_half_pi)) / cos_val)

    term_poly = (0.752
                 + 2.02 * val_aW
                 + 0.37 * (1.0 - np.sin(aW_half_pi)) ** 3
                 )

    f_aW = term_sqrt * term_poly

    # K_I^R 公式 (公式 5)
    K_val = (P / (B * np.sqrt(W))) * f_aW
    return K_val


# ----------------------------------------------
# 针对 SENT (Total Work) Jpl 不再需要 eta 和 gamma
# ----------------------------------------------
def calc_eta_SENT(a, W):
    return 1.0  # 仅为兼容性保留，在新逻辑中未使用


def calc_gamma_SENT(a, W):
    return 1.0  # 仅为兼容性保留，在新逻辑中未使用


# ==================================================
#    B. 通用计算流程
# ==================================================
def filter_signal(data_series, dt, cutoff=50):
    if len(data_series) < 10: return data_series
    fs = 1.0 / dt
    if cutoff >= 0.5 * fs: return data_series
    b, a = butter(4, cutoff / (0.5 * fs), btype='low')
    return filtfilt(b, a, data_series)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exp_id', nargs='?', default='Unknown')
    args = parser.parse_args()
    exp_id = args.exp_id

    print(f"--- J-Integral Calc ({cfg.SPECIMEN_TYPE}) : {exp_id} ---")

    # 1. 路径准备
    root = cfg.ROOT_DIR
    data_dir = os.path.join(root, 'data', exp_id)
    res_dir = os.path.join(root, 'results', exp_id)
    if not os.path.exists(res_dir): os.makedirs(res_dir)

    # 2. 读取数据
    try:
        df_fd = pd.read_csv(os.path.join(data_dir, f'{exp_id}_force_displacement_from_FIELD.csv'))
        df_cl = pd.read_csv(os.path.join(data_dir, f'{exp_id}_crack_length_UserTip_vs_time.csv'))
        # 假设 ALLPD_vs_time.csv 中的 ALLPD 列现在代表累计的塑性功 U_p^i
        df_pd = pd.read_csv(os.path.join(data_dir, f'{exp_id}_ALLPD_vs_time.csv'))

        # 模量读取
        mod_file = os.path.join(res_dir, f'{exp_id}_Modulus_EnergyCriteria.txt')
        with open(mod_file, 'r') as f:
            c = f.read()
            import re
            # E_val 对应公式中的 E_bar (有效杨氏模量)
            E_bar = float(re.search(r"Method B \(Energy\):\s*([0-9\.]+)", c).group(1))
    except Exception as e:
        print(f"!! Error loading data: {e}")
        return

    # 3. 数据预处理
    # 3.1 Force 滤波
    time_fd = df_fd[df_fd.columns[0]].values
    force_raw = df_fd[df_fd.columns[2]].values
    dt = np.mean(np.diff(time_fd))
    force_filt = filter_signal(force_raw, dt, cutoff=50)  # 50Hz 滤波
    df_fd['Force_Filt'] = force_filt

    # 3.2 对齐 ALLPD (假设其为 U_p)
    t_pd = next(c for c in df_pd.columns if 'Time' in c)
    v_pd = next(c for c in df_pd.columns if 'ALLPD' in c)
    df_pd = df_pd.rename(columns={t_pd: 'Time', v_pd: 'ALLPD'})

    # 3.3 对齐 Crack Tip & 计算物理 a
    t_cl = next(c for c in df_cl.columns if 'Time' in c)
    df_cl = df_cl.rename(columns={t_cl: 'Time'})

    # 融合
    df_merge = pd.merge_asof(df_pd, df_cl, on='Time', direction='forward').dropna()
    # 再次融合 Force
    df_fd_temp = df_fd[['Time', 'Force_Filt']].rename(columns={df_fd.columns[0]: 'Time'})
    df_calc = pd.merge_asof(df_merge, df_fd_temp, on='Time', direction='nearest')

    # ----------------------------------------------------
    #  关键分支: 物理 a 计算
    # ----------------------------------------------------
    W = cfg.W
    B = cfg.B
    B_N = cfg.B_N

    if df_cl.empty: return

    # 获取初始 Tip 位置
    tip_0 = df_cl['Tip_X'].iloc[0]

    # 计算当前物理裂纹长度 a
    if cfg.SPECIMEN_TYPE == 'SENT':
        # SENT: 假设 a = Tip_X
        df_calc['a'] = df_calc['Tip_X']
    else:
        # CT: 旧脚本逻辑 -> a = W - Tip_X
        df_calc['a'] = W - df_calc['Tip_X']

    # ----------------------------------------------------
    #  J 积分循环 (根据 SPECIMEN_TYPE 选择方法)
    # ----------------------------------------------------
    J_tot = []

    if cfg.SPECIMEN_TYPE == 'SENT':
        print("   -> Using NEW Total Work Method (Formulas 4 & 7) for SENT.")
        # Total Work Method (公式 4 & 7)
        func_K = calc_K_SENT

        for i in range(len(df_calc)):
            row = df_calc.iloc[i]
            curr_a = row['a']
            curr_P = row['Force_Filt']
            curr_Up = row['ALLPD']  # U_p^i

            # 1. Elastic J (K-based) - 公式 4
            K_val = func_K(curr_P, curr_a, W, B)
            J_el = (K_val ** 2) / E_bar  # 使用 E_bar

            # 2. Plastic J (Total Work) - 公式 7
            b = max(0.001, W - curr_a)  # 韧带宽度 b = W - a_i
            J_pl = (2.0 * curr_Up) / (B * b)

            J_total = J_el + J_pl
            J_tot.append(J_total)

    else:
        print("   -> Using OLD Hybrid Incremental Method for CT.")
        # Hybrid Incremental Method (原脚本逻辑 for CT)
        J_pl_accum = 0.0
        a_prev = df_calc['a'].iloc[0]
        allpd_prev = df_calc['ALLPD'].iloc[0]

        func_K = calc_K_CT
        func_eta = calc_eta_CT
        func_gamma = calc_gamma_CT

        for i in range(len(df_calc)):
            row = df_calc.iloc[i]
            curr_a = row['a']
            curr_P = row['Force_Filt']
            curr_allpd = row['ALLPD']

            # 1. Elastic J (K-based)
            K_val = func_K(curr_P, curr_a, W, B)
            J_el = (K_val ** 2) / E_bar  # 使用 E_bar

            # 2. Plastic J (Incremental)
            if i == 0:
                J_pl = 0
            else:
                da = curr_a - a_prev
                d_allpd = max(0, curr_allpd - allpd_prev)
                b = max(0.1, W - a_prev)  # 韧带

                eta = func_eta(a_prev, W)
                gamma = func_gamma(a_prev, W)

                term1 = (J_pl_accum + (eta * d_allpd) / (B_N * b))
                term2 = (1.0 - (gamma * da) / b)

                J_pl = term1 * max(0, term2)
                J_pl_accum = J_pl

            J_tot.append(J_el + J_pl_accum)

            a_prev = curr_a
            allpd_prev = curr_allpd

    df_calc['J_Total'] = J_tot
    # K_R^2 = E_bar * J_R (公式 8)
    df_calc['K_eq'] = np.sqrt(np.array(J_tot) * E_bar)

    # 保存结果
    out_file = os.path.join(res_dir, f'{exp_id}_J_Hybrid_{cfg.SPECIMEN_TYPE}.xlsx')
    df_calc.to_excel(out_file, index=False)
    print(f"   -> Result Saved: {out_file}")


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
SCRIPT: 对比.py (v6.0 Final)
修正点:
  1. 读取: 显式读取 'Filtered_delta_a'，不依赖 Tip_X 重算。
  2. 截断: 既然是超材料(Forward)，当未来无数据时直接 dropna，实现"不知则不算"。
  3. 信号: 引入 50Hz 低通滤波 + 强制 Force >= 0。
"""
import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import re
from scipy.signal import butter, filtfilt  # <--- [新增] 滤波库

# --- 配置 ---
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

try:
    import project_config as cfg
except ImportError:
    sys.exit("!! [Fatal] 缺失 project_config.py")


# ==========================================
#      [新增] 滤波函数 (与 J积分脚本一致)
# ==========================================
def filter_force_signal(force_series, dt, cutoff_hz=50.0):
    if len(force_series) < 10: return force_series
    fs = 1.0 / dt
    if cutoff_hz >= 0.5 * fs: return force_series  # 奈奎斯特频率检查
    b, a = butter(4, cutoff_hz / (0.5 * fs), btype='low', analog=False)
    return filtfilt(b, a, force_series)


def get_paths(exp_id):
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except:
        root = os.path.abspath(os.path.join(os.getcwd(), '..'))

    data_dir = os.path.join(root, 'data', exp_id)
    res_dir = os.path.join(root, 'results', exp_id)
    os.makedirs(res_dir, exist_ok=True)

    return {
        'id': exp_id,
        'root': root,
        'files': {
            'fd': os.path.join(data_dir, f'{exp_id}_force_displacement_from_FIELD.csv'),
            'cl': os.path.join(data_dir, f'{exp_id}_crack_length_UserTip_vs_time.csv'),
            'pd': os.path.join(data_dir, f'{exp_id}_ALLPD_vs_time.csv'),
            'wk': os.path.join(data_dir, f'{exp_id}_ALLWK_vs_time.csv'),
            'se': os.path.join(data_dir, f'{exp_id}_ALLSE_vs_time.csv')
        },
        'modulus_txt': os.path.join(res_dir, f'{exp_id}_Modulus_EnergyCriteria.txt'),
        'out_plot': os.path.join(res_dir, f'{exp_id}_ASTM_CLL_StepHold.png'),
        'out_excel': os.path.join(res_dir, f'{exp_id}_ASTM_CLL_StepHold_Data.xlsx')
    }


def load_modulus(txt_path):
    if not os.path.exists(txt_path):
        sys.exit(f"!! [Fatal] 找不到模量计算结果: {txt_path}\n请先运行模量计算脚本。")
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 优先匹配 Method B，如果没找到尝试匹配 Method A
    match = re.search(r"Method B \(Energy\):\s*([0-9\.]+)", content)
    if match: return float(match.group(1))

    match_a = re.search(r"Method A \(Slope\):\s*([0-9\.]+)", content)
    if match_a: return float(match_a.group(1))

    sys.exit("!! [Fatal] 模量文件格式无法解析。")


def load_and_sync_step_hold(paths):
    print(f"--- 加载数据 (Filtered & Truncated) ---")

    # 1. 主表: Force-Displacement
    if not os.path.exists(paths['files']['fd']):
        sys.exit(f"!! [Fatal] 找不到 FD 文件: {paths['files']['fd']}")

    df_fd = pd.read_csv(paths['files']['fd'])
    t_col = next((c for c in df_fd.columns if 'Time' in c), 'Time')
    f_col = next((c for c in df_fd.columns if 'Force' in c), 'Force')
    d_col = next((c for c in df_fd.columns if 'Displacement' in c), 'Displacement')

    df_fd = df_fd.rename(columns={t_col: 'Time', f_col: 'Force', d_col: 'Displacement'})
    df_fd = df_fd[['Time', 'Force', 'Displacement']].sort_values('Time').dropna()

    # --- [修正点 A] 信号处理 ---
    time_diffs = df_fd['Time'].diff().dropna()
    avg_dt = time_diffs.mean() if not time_diffs.empty else 0.0
    if avg_dt > 0:
        print("   [Processing] Force 滤波 (50Hz Low-pass)...")
        df_fd['Force'] = filter_force_signal(df_fd['Force'], avg_dt)

    # 强制去除负值 (物理修正)
    df_fd['Force'] = df_fd['Force'].clip(lower=0.0)

    # 2. 从表: Crack Length
    if not os.path.exists(paths['files']['cl']):
        sys.exit(f"!! [Fatal] 找不到裂纹文件: {paths['files']['cl']}")

    df_cl = pd.read_csv(paths['files']['cl'])
    df_cl.columns = df_cl.columns.str.strip()  # 清洗列名

    # --- [修正点 B] 显式读取 Filtered_delta_a ---
    req_cols = ['Tip_X', 'Filtered_delta_a']
    for c in req_cols:
        if c not in df_cl.columns:
            sys.exit(f"!! [Fatal] CSV 缺失列 '{c}'，请检查提取脚本。")

    t_cl = next((c for c in df_cl.columns if 'Time' in c), 'Time')
    # 把需要的列都加进白名单
    df_cl = df_cl.rename(columns={t_cl: 'Time'})[['Time', 'Tip_X', 'Filtered_delta_a']].sort_values('Time').dropna()

    if df_cl.empty: sys.exit("!! [Fatal] 裂纹数据为空。")

    # 3. 合并
    # 超材料定义: 裂纹位置由"前方即将断裂的杆"决定 -> Forward
    df_merged = pd.merge_asof(df_fd, df_cl, on='Time', direction='forward')

    # --- [修正点 C] 截断逻辑 ---
    # 如果未来没有裂纹数据了 (NaN)，直接丢弃，不进行填充计算
    df_merged = df_merged.dropna(subset=['Filtered_delta_a'])

    # 4. 物理计算
    # 初始裂纹 a0 = W - X_start (你的定义)
    start_tip = df_cl['Tip_X'].iloc[0]
    initial_a = cfg.W - start_tip

    # 当前裂纹 a_curr = a0 + delta_a
    df_merged['a_curr'] = initial_a + df_merged['Filtered_delta_a']
    df_merged['delta_a'] = df_merged['Filtered_delta_a']

    # 5. 其他能量表
    for key in ['pd', 'wk', 'se']:
        fpath = paths['files'][key]
        if os.path.exists(fpath):
            df_aux = pd.read_csv(fpath)
            t_aux = next((c for c in df_aux.columns if 'Time' in c), 'Time')
            target_str = key.upper()
            val_col = next((c for c in df_aux.columns if ('ALL' in c and target_str in c) or target_str in c), None)
            if val_col:
                df_aux = df_aux.rename(columns={t_aux: 'Time', val_col: f'ALL{target_str.replace("ALL", "")}'})
                df_merged = pd.merge_asof(df_merged, df_aux[['Time', f'ALL{target_str.replace("ALL", "")}']], on='Time',
                                          direction='forward')

    # 6. 归零 (仅位移和能量，Tip_X 绝对不动)
    for col in ['Displacement', 'ALLPD', 'ALLWK', 'ALLSE']:
        if col in df_merged.columns:
            df_merged[col] = df_merged[col] - df_merged[col].iloc[0]

    print(f"-> 数据就绪: a0={initial_a:.3f}, Points={len(df_merged)}")
    return df_merged


def calculate_astm_apl(df, params, E_val):
    print(f"--- 计算 ASTM A_pl (E={E_val:.1f}) ---")
    W, B, B_N = params['W'], params['B'], params['B_N']

    # 1. 计算 C_LL (使用正确的 a_curr)
    x = (df['a_curr'] / W).clip(upper=0.995)
    B_e = B - (B - B_N) ** 2 / B
    term1 = 1.0 / (E_val * B_e)
    term2 = ((1 + x) / (1 - x)) ** 2
    term3 = (2.1630 + 12.219 * x - 20.065 * (x ** 2) - 0.9925 * (x ** 3) + 20.609 * (x ** 4) - 9.9314 * (x ** 5))
    df['C_LL'] = term1 * term2 * term3

    # 2. 计算 V_pl
    df['V_pl_Calc'] = df['Displacement'] - df['Force'] * df['C_LL']

    # 3. 积分 A_pl
    P_avg = 0.5 * (df['Force'].values[:-1] + df['Force'].values[1:])
    dV_pl = np.diff(df['V_pl_Calc'].values)
    dA = P_avg * dV_pl
    df['A_pl_ASTM'] = np.concatenate(([0], np.cumsum(dA)))

    if 'ALLWK' in df.columns and 'ALLSE' in df.columns:
        df['Energy_Balance'] = df['ALLWK'] - df['ALLSE']

    return df


def plot_final(df, paths):
    plt.figure(figsize=(10, 7))
    x = df['Displacement']
    plt.plot(x, df['A_pl_ASTM'], 'b--', linewidth=2.5, label='Theory $A_{pl}$ (ASTM)')
    if 'ALLPD' in df.columns:
        plt.plot(x, df['ALLPD'], 'k-', linewidth=1.5, alpha=0.7, label='Abaqus ALLPD')
    if 'Energy_Balance' in df.columns:
        plt.plot(x, df['Energy_Balance'], 'r:', linewidth=1.5, label='Energy Balance')

    plt.title(f'Plastic Energy Comparison: {paths["id"]}\n(Filtered Force & Correct Crack Length)')
    plt.xlabel('Displacement (mm)')
    plt.ylabel('Plastic Energy (mJ)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(paths['out_plot'], dpi=300)
    print(f"-> 绘图保存: {paths['out_plot']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exp_id', nargs='?', default='B05Solid')
    args = parser.parse_args()
    paths = get_paths(args.exp_id)

    # 1. 加载
    df = load_and_sync_step_hold(paths)
    if df is None: return

    # 2. 模量
    E_val = load_modulus(paths['modulus_txt'])

    # 3. 计算
    params = {'W': cfg.W, 'B': cfg.B, 'B_N': cfg.B_N}
    df = calculate_astm_apl(df, params, E_val)

    # 4. 保存
    cols = ['Time', 'Displacement', 'Force', 'Tip_X', 'a_curr', 'delta_a', 'C_LL', 'V_pl_Calc', 'A_pl_ASTM', 'ALLPD']
    out_cols = [c for c in cols if c in df.columns]
    df[out_cols].to_excel(paths['out_excel'], index=False)
    print(f"-> Excel: {paths['out_excel']}")

    # 5. 绘图
    plot_final(df, paths)


if __name__ == "__main__":
    main()
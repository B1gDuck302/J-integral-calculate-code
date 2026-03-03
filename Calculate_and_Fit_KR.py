# -*- coding: utf-8 -*-
"""
SCRIPT: Calculate_and_Fit_KR_Discrete.py (Final Version)
功能:
  1. 读取 J 积分 Excel (默认第一张工作表)。
  2. 筛选出 J > 0.1 的有效扩展点。
  3. 对这些离散点进行 K_R 转换和幂律拟合。
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import os
import sys
import warnings

# [严谨来源] 强制导入配置
try:
    import project_config as cfg
except ImportError:
    sys.exit("!! [Fatal] 缺失 project_config.py，无法获取材料参数。")

warnings.filterwarnings('ignore')
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def get_paths(exp_id):
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except:
        project_root = os.path.abspath(os.path.join(os.getcwd(), '..'))

    results_dir = os.path.join(project_root, 'results', exp_id)
    if not os.path.exists(results_dir):
        sys.exit(f"!! [Error] 结果目录不存在: {results_dir}")

    # 获取 Specimen Type
    sp_type = getattr(cfg, 'SPECIMEN_TYPE', 'CT')

    return {
        'results_dir': results_dir,
        # 读取 J 积分脚本的实际输出文件名
        'jr_excel': os.path.join(results_dir, f'{exp_id}_J_Hybrid_{sp_type}.xlsx'),
        'modulus_txt': os.path.join(results_dir, f'{exp_id}_Modulus_EnergyCriteria.txt'),
        # 输出文件命名区分一下，避免覆盖
        'output_excel': os.path.join(results_dir, f'{exp_id}_KR_Discrete_Data.xlsx'),
        'output_plot': os.path.join(results_dir, f'{exp_id}_KR_Curve_Discrete_Fit.png'),
        'output_params': os.path.join(results_dir, f'{exp_id}_KR_Discrete_Fit_Parameters.txt')
    }


def load_modulus(txt_path):
    if not os.path.exists(txt_path):
        sys.exit(f"!! [Error] 找不到模量文件: {txt_path}")
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        sys.exit(f"!! [Error] 读取模量文件失败")

    import re
    match = re.search(r"Method B \(Energy\):\s*([0-9\.]+)", content)
    if match:
        return float(match.group(1))
    else:
        sys.exit("!! [Error] 无法从文件中解析出 Method B 模量。")


def dimensionless_model_func(x_star, intercept_star, alpha1, alpha2):
    # 幂律模型: y = a + b * x^c
    return intercept_star + alpha1 * (np.maximum(x_star, 1e-9) ** alpha2)


def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py ModelID")
        sys.exit(1)

    exp_id = sys.argv[1]
    print(f"--- K_R 拟合 (基于离散断裂点): {exp_id} ---")

    paths = get_paths(exp_id)

    # 1. 参数加载
    sigma_0s = cfg.SIGMA_0S
    l_char = cfg.L_CHAR
    print(f"   [Params] SIGMA_0s={sigma_0s} MPa, L_CHAR={l_char} mm")

    # 2. 模量加载
    E_val = load_modulus(paths['modulus_txt'])
    print(f"   [Params] E_Method_B={E_val:.1f} MPa")

    # 3. 读取数据
    paths = get_paths(exp_id)

    # 3.1. 读取 J 积分数据 (包含 Time 和 J_Total)
    if not os.path.exists(paths['jr_excel']):
        sys.exit(f"!! [Error] 找不到 J 积分 Excel: {paths['jr_excel']}")

    try:
        # 读取 J 积分 Excel 的默认工作表
        df_j = pd.read_excel(paths['jr_excel'])
        df_j = df_j.rename(columns=lambda x: 'Time' if 'Time' in x else x)
        print("   [Data] 成功读取 J 积分 Excel (J_Total, Time)。")
    except Exception as e:
        sys.exit(f"!! [Error] 读取 J Excel 失败。\nDetail: {e}")

    # J 积分脚本中的列名
    col_j = 'J_Total'

    if col_j not in df_j.columns or 'Time' not in df_j.columns:
        sys.exit(f"!! [Error] J Excel 中缺少所需的列 ('{col_j}' 或 'Time')。")

    # 3.2. 读取裂纹长度数据 (包含 Time, Tip_X 和 Filtered_delta_a)
    project_root = os.path.dirname(paths['results_dir'])  # ROOT_DIR/results
    project_root = os.path.dirname(project_root)  # ROOT_DIR
    crack_csv_path = os.path.join(project_root, cfg.DATA_DIR_NAME, exp_id, f'{exp_id}_crack_length_UserTip_vs_time.csv')
    if not os.path.exists(crack_csv_path):
        sys.exit(f"!! [Fatal] 找不到裂纹 CSV: {crack_csv_path}")

    try:
        df_cl = pd.read_csv(crack_csv_path)
        # 提取经过滤波的 delta_a
        col_da = 'delta_a (mm)'
        df_cl = df_cl.rename(columns={'Filtered_delta_a': col_da})
        df_cl = df_cl[['Time', col_da]]  # 只保留 Time 和 delta_a
        print("   [Data] 成功读取过滤后的裂纹扩展数据 (delta_a)。")
    except Exception as e:
        sys.exit(f"!! [Error] 读取裂纹 CSV 失败。\nDetail: {e}")

    # 4. 数据融合与 K_R 计算

    # 将 J 积分和 delta_a 数据基于 Time 融合 (使用 inner join 确保只有两者都存在的时间点)
    df_merged = pd.merge(df_j, df_cl, on='Time', how='inner')

    # 过滤 J > 0.1 的有效点，这些点对应于离散断裂时刻
    df_valid = df_merged[df_merged[col_j] > 0.1].copy()

    if df_valid.empty:
        sys.exit("!! [Error] 有效数据点为空 (所有 J < 0.1 或 Time 对齐失败)。")

    # 计算 K_R (公式 8)
    J_vals = df_valid[col_j].values
    df_valid['K_R'] = np.sqrt(J_vals * E_val)

    # 按照 delta_a 排序，确保曲线走向正确
    df_valid = df_valid.sort_values(by=col_da).reset_index(drop=True)

    # 5. 无量纲化
    K_norm_factor = sigma_0s * np.sqrt(l_char)
    df_valid['da_star'] = df_valid[col_da] / l_char
    df_valid['K_star'] = df_valid['K_R'] / K_norm_factor

    # 保存这份干净的数据供检查 (即您所求的“只有断裂时刻的表”)
    df_valid.to_excel(paths['output_excel'], index=False)
    print(f"   -> 断裂时刻数据表保存: {paths['output_excel']}")

    # ========================================================
    # A. 起裂准则 (Initiation Criterion)
    # ========================================================
    # 取第一个有效点作为 K_IC (Physical)
    first_point = df_valid.iloc[0]
    K_IC_phys = first_point['K_R']

    # 单位换算 MPa*mm^0.5 -> MPa*m^0.5 (乘以 0.031622)
    K_IC_SI = K_IC_phys * 0.031622

    print(f"\n   [Result] 起裂准则 (Initiation):")
    print(f"       Delta_a = {first_point[col_da]:.4f} mm")
    print(f"       K_IC    = {K_IC_SI:.2f} MPa·m^0.5")

    # ========================================================
    # B. 曲线拟合 (对齐 Wang et al. 2025 Eq.9)
    # 模型: y = Intercept + alpha1 * x^alpha2
    # ========================================================
    fit_success = False
    popt = [0, 0, 0]
    r_squared = 0

    if len(df_valid) >= 3:
        x_fit = df_valid['da_star'].values  # Delta_a / l
        y_fit = df_valid['K_star'].values  # KR / (sigma * sqrt(l))

        # 初始猜测 [截距, alpha1, alpha2]
        p0 = [y_fit[0], 1.0, 0.5]

        # 约束: 截距>0, alpha1>0, alpha2 在 0~2 之间
        bounds = ([0.0, 0.0, 0.0], [np.inf, np.inf, 2.0])

        try:
            popt, pcov = curve_fit(dimensionless_model_func, x_fit, y_fit, p0=p0, bounds=bounds, maxfev=5000)
            fit_success = True

            # R2 计算
            y_calc = dimensionless_model_func(x_fit, *popt)
            ss_res = np.sum((y_fit - y_calc) ** 2)
            ss_tot = np.sum((y_fit - np.mean(y_fit)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 1e-9 else 0

            print(f"   [Fit] 拟合成功 (R2={r_squared:.4f})")
            print(f"         拟合公式: Y = {popt[0]:.3f} + {popt[1]:.3f} * X^{popt[2]:.3f}")
            print(f"         对应论文参数: K_IC_norm={popt[0]:.3f}, alpha1={popt[1]:.3f}, alpha2={popt[2]:.3f}")

        except Exception as e:
            print(f"   [Warning] 拟合失败: {e}")
    else:
        print("   [Warning] 数据点不足，跳过拟合。")

    # ========================================================
    # 绘图 (复刻论文风格)
    # ========================================================
    # 设置论文风格字体 (Times New Roman 看起来更像 SCI)
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']

    fig, ax = plt.subplots(figsize=(7, 5.5))

    # 1. 绘制实验散点 (实心圆点)
    ax.scatter(df_valid['da_star'], df_valid['K_star'],
               c='black', s=40, edgecolors='none', alpha=0.9, label='Simulation')

    # 2. 绘制拟合曲线 (黑色实线)
    if fit_success:
        x_smooth = np.linspace(0, df_valid['da_star'].max() * 1.05, 100)
        y_smooth = dimensionless_model_func(x_smooth, *popt)
        ax.plot(x_smooth, y_smooth, 'k-', linewidth=1.5, label='Fit (Eq. 9)')

    # 3. 坐标轴设置 (完全复刻论文标签)
    ax.set_xlabel(r'$\Delta a / l$', fontsize=14)
    ax.set_ylabel(r'$\frac{K_R}{\sigma_{0s} \sqrt{l}}$', fontsize=16, rotation=90, labelpad=10)

    # 设置刻度字体大小
    ax.tick_params(axis='both', which='major', labelsize=12)

    # 添加图例和文本
    fit_str = ""
    if fit_success:
        fit_str = (r"$Y = %.2f + %.2f X^{%.2f}$" % (popt[0], popt[1], popt[2])) + "\n" + r"$R^2 = %.3f$" % r_squared
        ax.text(0.05, 0.95, fit_str, transform=ax.transAxes,
                verticalalignment='top', fontsize=12,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    plt.savefig(paths['output_plot'], dpi=600)  # 高清输出
    print(f"-> 绘图保存: {paths['output_plot']}")

    # 保存参数到 TXT
    with open(paths['output_params'], 'w') as f:
        f.write(f"Normalization Params:\n")
        f.write(f"  Sigma_0s = {sigma_0s} MPa\n")
        f.write(f"  l_char = {l_char} mm\n")
        f.write(f"  Norm_Factor = {K_norm_factor:.4f} MPa*mm^0.5\n\n")

        f.write(f"Fit Results (Wang et al. Eq.9):\n")
        if fit_success:
            f.write(f"  K_IC_norm (Intercept) = {popt[0]:.4f}\n")
            f.write(f"  alpha1 = {popt[1]:.4f}\n")
            f.write(f"  alpha2 = {popt[2]:.4f}\n")
            f.write(f"  R2 = {r_squared:.4f}\n")
        else:
            f.write("Fit Failed.\n")


if __name__ == "__main__":
    main()
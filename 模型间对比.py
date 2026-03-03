# -*- coding: utf-8 -*-
"""
SCRIPT: 模型间对比.py
功能: 绘制多个模型的 P-V 和 J-R 曲线对比图。
特点: 独立运行，不依赖 run_batch，用户在下方手动指定要对比的模型 ID。
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import sys

# ====================================================
#               【用户配置区】 (在此处修改)
# ====================================================
# 请将您想要对比的模型 ID 填入此列表
# 格式: ['模型A', '模型B', '模型C']
MODELS_TO_COMPARE = [
    'B05Solid_PlaneStrain',
    'B05Solid',
    # 'Another_Model_ID',  # 您可以随时注释掉不想画的模型
]

# ====================================================
#               【绘图配置】
# ====================================================
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# 定义颜色和线型序列，确保模型多了也能分得清
STYLES = ['-', '--', '-.', ':']
MARKERS = ['o', 's', '^', 'D', 'v', '*', 'p', 'h']
# 常用科研配色 (Blue, Orange, Green, Red, Purple, Brown, Pink, Gray)
COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']


def get_paths(exp_id):
    """
    根据模型 ID 获取数据文件路径 (适配 Strict Mode 目录结构)
    """
    try:
        # 获取项目根目录 (假设脚本在 scripts/ 或 src/ 下)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except:
        root = os.path.abspath(os.path.join(os.getcwd(), '..'))

    data_dir = os.path.join(root, 'data', exp_id)
    res_dir = os.path.join(root, 'results', exp_id)

    # 结果输出到 results/Multi_Model_Comparison 文件夹
    out_dir = os.path.join(root, 'results', 'Multi_Model_Comparison')

    return {
        # 1. P-V 源数据: CSV (来自 提取数据.py)
        'pv': os.path.join(data_dir, f'{exp_id}_force_displacement_from_FIELD.csv'),

        # 2. J-R 结果: Excel (来自 J积分计算.py)
        'jr': os.path.join(res_dir, f'{exp_id}_J-R_Curve_Results.xlsx'),

        'out_dir': out_dir
    }


def plot_comparison():
    target_list = MODELS_TO_COMPARE

    if not target_list:
        print("!! [提示] 模型列表为空。请在脚本顶部的 MODELS_TO_COMPARE 中添加模型 ID。")
        return

    print(f"--- 模型间对比 (共 {len(target_list)} 个) ---")
    print(f"    列表: {target_list}")

    # 准备画布
    fig_pv, ax_pv = plt.subplots(figsize=(10, 7))
    fig_jr, ax_jr = plt.subplots(figsize=(10, 7))

    has_data_pv = False
    has_data_jr = False

    for i, job_id in enumerate(target_list):
        paths = get_paths(job_id)

        # 样式循环
        style = STYLES[i % len(STYLES)]
        marker = MARKERS[i % len(MARKERS)]
        color = COLORS[i % len(COLORS)]

        # -------------------------------------------------------
        # 1. 绘制 P-V 曲线 (读取 CSV)
        # -------------------------------------------------------
        if os.path.exists(paths['pv']):
            try:
                df_pv = pd.read_csv(paths['pv'])

                # 鲁棒性列名查找
                t_col = next((c for c in df_pv.columns if 'Time' in c), 'Time')
                d_col = next((c for c in df_pv.columns if 'Displacement' in c), 'Displacement')
                f_col = next((c for c in df_pv.columns if 'Force' in c), 'Force')

                # 归零处理
                disp = df_pv[d_col] - df_pv[d_col].iloc[0]
                force = df_pv[f_col] - df_pv[f_col].iloc[0]

                ax_pv.plot(disp, force, label=job_id,
                           color=color, linestyle=style, linewidth=2, alpha=0.8)
                has_data_pv = True
                print(f"    [√] P-V: {job_id}")
            except Exception as e:
                print(f"    [!] P-V Error ({job_id}): {e}")
        else:
            print(f"    [x] P-V Missing: {paths['pv']}")

        # -------------------------------------------------------
        # 2. 绘制 J-R 曲线 (读取 Excel 关键点)
        # -------------------------------------------------------
        if os.path.exists(paths['jr']):
            try:
                # 优先读取只含关键点的 Sheet
                try:
                    df_jr = pd.read_excel(paths['jr'], sheet_name='Extracted_Fracture_Points')
                except:
                    # 兼容旧版本
                    df_jr = pd.read_excel(paths['jr'], sheet_name=0)

                # 查找列名
                da_col = next((c for c in df_jr.columns if 'delta_a' in c), None)
                j_col = next((c for c in df_jr.columns if 'J_total' in c), None)

                if da_col and j_col:
                    # 过滤掉 J 极小的无效点 (如 < 0.1 N/mm)
                    plot_data = df_jr[df_jr[j_col] > 0.1].sort_values(da_col)

                    if not plot_data.empty:
                        ax_jr.plot(plot_data[da_col], plot_data[j_col], label=job_id,
                                   color=color, linestyle=style,
                                   marker=marker, markersize=6, alpha=0.8)
                        has_data_jr = True
                        print(f"    [√] J-R: {job_id}")
                else:
                    print(f"    [!] J-R Columns missing in {job_id}")

            except Exception as e:
                print(f"    [!] J-R Error ({job_id}): {e}")
        else:
            print(f"    [x] J-R Missing: {paths['jr']}")

    # -------------------------------------------------------
    # 保存与输出
    # -------------------------------------------------------
    out_dir = get_paths('dummy')['out_dir']
    os.makedirs(out_dir, exist_ok=True)

    # 保存 P-V
    if has_data_pv:
        ax_pv.set_title("Force-Displacement Comparison", fontsize=14)
        ax_pv.set_xlabel("Displacement (mm)", fontsize=12)
        ax_pv.set_ylabel("Force (N)", fontsize=12)
        ax_pv.legend(fontsize=10, loc='best')
        ax_pv.grid(True, linestyle=':', alpha=0.7)

        pv_path = os.path.join(out_dir, 'Compare_PV.png')
        fig_pv.savefig(pv_path, dpi=300)
        print(f"    -> Saved: {pv_path}")
    else:
        print("    [Warn] 没有有效的 P-V 数据可绘图。")

    # 保存 J-R
    if has_data_jr:
        ax_jr.set_title("J-R Curve Comparison", fontsize=14)
        ax_jr.set_xlabel(r"Crack Extension $\Delta a$ (mm)", fontsize=12)
        ax_jr.set_ylabel(r"J-Integral $J$ (N/mm)", fontsize=12)
        ax_jr.legend(fontsize=10, loc='best')
        ax_jr.grid(True, linestyle=':', alpha=0.7)
        ax_jr.set_xlim(left=0)
        ax_jr.set_ylim(bottom=0)

        jr_path = os.path.join(out_dir, 'Compare_JR.png')
        fig_jr.savefig(jr_path, dpi=300)
        print(f"    -> Saved: {jr_path}")
    else:
        print("    [Warn] 没有有效的 J-R 数据可绘图。")

    plt.close('all')


if __name__ == "__main__":
    plot_comparison()
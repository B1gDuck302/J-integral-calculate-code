# -*- coding: utf-8 -*-
"""
SCRIPT: run_batch.py (终极全自动版)
功能: 一键完成 Abaqus 提取 + Python 全流程计算
"""

import subprocess
import os
import sys
import time
import project_config as cfg
# ====================================================
#               【用户必须修改的配置】
# ====================================================

# 1. 待处理的模型 ID 列表 (必须与 .odb 文件名一致)
JOB_LIST = getattr(cfg, 'JOB_LIST', [])

# 2. Abaqus 启动命令的【绝对路径】
#    (去 CMD 输入 'where abaqus' 可以查看，通常是下面这个)
ABAQUS_BAT_PATH = r"F:\ABAQUS2024\commands\abaqus.bat"

# 3. Abaqus 的工作目录 (你的 .odb 文件在哪里？)
#    脚本会“假装”自己在那个目录下运行 Abaqus
ABAQUS_WORK_DIR = r"F:\ABAQUS2024\temp"

# ====================================================
#               【脚本清单 (无需修改)】
# ====================================================
# 获取当前脚本所在的文件夹 (假设所有脚本都在一起)
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = {
    'Extract': os.path.join(CURRENT_SCRIPT_DIR, '提取数据.py'),
    'Modulus': os.path.join(CURRENT_SCRIPT_DIR, 'Calculate_Equivalent_Modulus.py'),
    'Verify': os.path.join(CURRENT_SCRIPT_DIR, '对比.py'),
    'J_Calc': os.path.join(CURRENT_SCRIPT_DIR, 'J_Integral_Hybrid_Incremental_ALLPD.py'),
    'KR_Fit': os.path.join(CURRENT_SCRIPT_DIR, 'Calculate_and_Fit_KR.py')
}


def run_abaqus_extract(script_path, job_id):
    """专门用于调用 Abaqus 的函数"""
    print(f"   >> [1.提取数据] 正在呼叫 Abaqus (工作目录: temp)...", end="", flush=True)
    start_time = time.time()

    # 组合命令: abaqus python "D:\...\提取数据.py" -- JobID
    cmd = [ABAQUS_BAT_PATH, 'python', script_path, '--', job_id]

    try:
        # 【关键技术点】: cwd参数指定了 Abaqus 在哪里运行
        subprocess.run(cmd, cwd=ABAQUS_WORK_DIR, shell=True, check=True)

        print(f" [√] 耗时 {time.time() - start_time:.1f}s")
        return True
    except subprocess.CalledProcessError:
        print(f" [X] Abaqus 提取失败!")
        print(f"      请检查 ODB 文件是否存在于: {os.path.join(ABAQUS_WORK_DIR, job_id + '.odb')}")
        return False


def run_python_calc(script_path, step_name, job_id):
    """用于调用本地 Python 3 计算的函数"""
    print(f"   >> [{step_name}] ...", end="", flush=True)
    start_time = time.time()

    # 使用当前 PyCharm 的 Python 解释器
    cmd = [sys.executable, script_path, job_id]

    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f" [√] {time.time() - start_time:.1f}s")
        return True
    except subprocess.CalledProcessError:
        print(f" [X] 失败!")
        return False


def main():
    print("=" * 70)
    print(f"   🚀 一键全自动批处理 (共 {len(JOB_LIST)} 个任务)")
    print(f"   📂 ODB 源目录: {ABAQUS_WORK_DIR}")
    print("=" * 70)

    for i, job_id in enumerate(JOB_LIST):
        print(f"\n>>> 进度 [{i + 1}/{len(JOB_LIST)}]: 处理模型 '{job_id}'")
        print("-" * 50)

        # --- 步骤 1: ABAQUS 数据提取 (跨环境调用) ---
        if not run_abaqus_extract(SCRIPTS['Extract'], job_id):
            print("!! 提取失败，跳过此模型后续步骤。")
            continue

        # --- 步骤 2-5: Python 本地计算 ---
        # 算模量
        if not run_python_calc(SCRIPTS['Modulus'], "2.计算模量", job_id): continue

        # 对比验证 (需模量)
        # if not run_python_calc(SCRIPTS['Verify'], "3.对比验证", job_id): continue

        #算 J 积分
        if not run_python_calc(SCRIPTS['J_Calc'], "4.J积分计算", job_id): continue
        #
        #算 K 并拟合
        if not run_python_calc(SCRIPTS['KR_Fit'], "5.阻力曲线", job_id): continue

    print("\n" + "=" * 70)
    print("✅ 所有流程执行完毕！")
    print("=" * 70)


if __name__ == "__main__":
    main()
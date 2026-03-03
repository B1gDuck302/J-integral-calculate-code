# -*- coding: utf-8 -*-
# SCRIPT: Calculate_Equivalent_Modulus.py
# 功能: 按模型名识别晶格类型/杆宽，并使用对应公式计算等效模量。

import math
import os
import sys
import project_config as cfg


def calculate_lattice_properties(lattice_type, t1, t2, L_rod, E_s):
    """根据晶格类型计算相对密度与等效模量。t1=细杆, t2=粗杆。"""
    sqrt3 = math.sqrt(3.0)

    if lattice_type == 'Honey':
        # ρ*/ρs = 2(t1+2t2)/(√3 L)
        rho_rel = 2.0 * (t1 + 2.0 * t2) / (sqrt3 * L_rod)
        # Ex = Ey = 2(t1+2t2)/(3√3 L) E
        E_x = E_y = 2.0 * (t1 + 2.0 * t2) * E_s / (3.0 * sqrt3 * L_rod)
        nu_xy = nu_yx = 1.0 / 3.0
        E_method = E_x
        formula = "Honey: Eeff = 2(t1+2t2)/(3sqrt(3)L) * Es"

    elif lattice_type == 'Kagome':
        # ρ*/ρs = √3(t1+t2)/L
        rho_rel = sqrt3 * (t1 + t2) / L_rod
        # Ex = Ey = (t1+t2)/(√3 L) E
        E_x = E_y = (t1 + t2) * E_s / (sqrt3 * L_rod)
        nu_xy = nu_yx = 1.0 / 3.0
        E_method = E_x
        formula = "Kagome: Eeff = (t1+t2)/(sqrt(3)L) * Es"

    elif lattice_type == 'Hex':
        # ρ*/ρs = (8t1+10t2)/(3√3L)
        rho_rel = (8.0 * t1 + 10.0 * t2) / (3.0 * sqrt3 * L_rod)
        # Ex, Ey from provided formulas
        E_x = (2.0 * sqrt3 / 9.0) * ((2.0 * t1 + t2) / L_rod) * E_s
        E_y = 2.0 * sqrt3 * ((t1 + 2.0 * t2) * (2.0 * t1 + t2)) * E_s / (L_rod * (17.0 * t1 + 10.0 * t2))
        nu_xy = (3.0 * t1 + 6.0 * t2) / (17.0 * t1 + 10.0 * t2)
        nu_yx = 1.0 / 3.0
        # 下游流程需要单一E，Hex为各向异性，这里采用 Ex/Ey 平均值作为接口值
        E_method = 0.5 * (E_x + E_y)
        formula = "Hex: E_method = (Ex+Ey)/2, Ex/Ey from provided closed-form expressions"

    elif lattice_type == 'Homo':
        # 用户要求: Homo 取 t1=t2=t，并使用任一已有公式。
        t = t1
        # 这里选用 Kagome 形式作为 Homo 的临时统一表达。
        rho_rel = sqrt3 * (t + t) / L_rod
        E_x = E_y = ((t + t) / (sqrt3 * L_rod)) * E_s
        nu_xy = nu_yx = 1.0 / 3.0
        E_method = E_x
        formula = "Homo(t1=t2=t): use Kagome-form Eeff = (2t)/(sqrt(3)L) * Es"

    else:
        raise ValueError("不支持的晶格类型: {0}".format(lattice_type))

    return {
        'rho_rel': rho_rel,
        'E_x': E_x,
        'E_y': E_y,
        'nu_xy': nu_xy,
        'nu_yx': nu_yx,
        'E_method': E_method,
        'formula': formula,
    }


def main():
    if len(sys.argv) < 2:
        raise ValueError('缺少模型ID参数。用法: python Calculate_Equivalent_Modulus.py <ModelID>')
    exp_id = sys.argv[1]

    specimen_type = cfg.infer_specimen_type(exp_id)
    lattice_type = cfg.infer_lattice_type(exp_id)
    t1, t2 = cfg.get_rod_widths(exp_id)

    res_dir = os.path.join(cfg.ROOT_DIR, 'results', exp_id)
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)

    L_rod = cfg.L_CHAR
    E_s = cfg.E_MAT

    props = calculate_lattice_properties(lattice_type, t1, t2, L_rod, E_s)

    out_file = os.path.join(res_dir, f'{exp_id}_Modulus_EnergyCriteria.txt')

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"Experiment ID: {exp_id}\n")
        f.write(f"Specimen Type: {specimen_type}\n")
        f.write(f"Lattice Type: {lattice_type}\n")
        f.write("Calculation Method: Lattice-Specific Analytical Model\n")
        f.write(f"Formula: {props['formula']}\n")
        f.write("------------------------------------------------\n")
        f.write(f"Thin Rod Width t1:  {t1:.3f} mm\n")
        f.write(f"Thick Rod Width t2: {t2:.3f} mm\n")
        f.write(f"Rod Length (L):     {L_rod} mm\n")
        f.write(f"Base Modulus (Es):  {E_s} MPa\n")
        f.write("------------------------------------------------\n")
        f.write(f"Relative Density (rho*/rho_s): {props['rho_rel']:.6f}\n")
        f.write(f"E_x: {props['E_x']:.4f} MPa\n")
        f.write(f"E_y: {props['E_y']:.4f} MPa\n")
        f.write(f"nu_xy: {props['nu_xy']:.6f}\n")
        f.write(f"nu_yx: {props['nu_yx']:.6f}\n")
        f.write("------------------------------------------------\n")
        # 下游脚本依赖该关键行
        f.write(f"Method B (Energy): {props['E_method']:.4f}\n")

    print(f"[*] {exp_id} 模量计算成功！")
    print(f"[*] 晶格类型: {lattice_type}")
    print(f"[*] 细杆宽度: {t1:.3f} mm, 粗杆宽度: {t2:.3f} mm")
    print(f"[*] 相对密度 rho*/rho_s = {props['rho_rel']:.6f}")
    print(f"[*] E_x={props['E_x']:.2f} MPa, E_y={props['E_y']:.2f} MPa")
    print(f"[*] Method B (Energy) 接口值 = {props['E_method']:.2f} MPa")
    print(f"[*] 结果已存入: {out_file}")


if __name__ == "__main__":
    main()

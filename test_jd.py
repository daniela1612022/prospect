# -*- coding: utf-8 -*-
"""
test_jd.py — Variante experimental del estres prospectivo con Jump-Diffusion.

Diferencia vs test.py:
  - Los factores GBM (FX + RV) se simulan con Jump-Diffusion de Merton.
  - LMM, HJM y CIR no cambian.

Uso:
    cd src
    python rfk_prospectivo/test_jd.py

Comparar resultados con los de test.py (GBM puro) para validar el impacto.
"""

import os
import sys
import logging

absolute_path = os.path.dirname(__file__)
relative_path = "rfk_prospectivo"
full_path = absolute_path.replace(relative_path, "")
sys.path.append(full_path)

import SimulationProspectivo_JD as rfk_sim_jd
import utils.Read as rd
import utils.CalibracionDinamica as cd

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

fecha = "20260430"
tesoreria = "Posicion Propia\\"
path_save = "C:\\Users\\dapinzo\\OneDrive - Grupo Bancolombia\\ReporteCorporativo\\05 Resultados\\08 Stress\\"
path_parquet = "C:\\Users\\dapinzo\\OneDrive - Grupo Bancolombia\\ReporteCorporativo\\04 Insumos\\02 Mercado\\Procesados\\Parquet\\"
path_files_parameters = "C:\\Users\\dapinzo\\OneDrive - Grupo Bancolombia\\ReporteCorporativo\\04 Insumos\\04 Parametros\\"
path_repo = r"C:\Users\dapinzo\Downloads\Azure\vrgo-migracion-derivados"

# ─── Calibracion dinamica de pesos (igual que test.py) ───────────────────────
path_var_excel = r"C:\Users\dapinzo\Downloads\Resultados 30_Apr_Zeros (10 dias) generado el 2026-05-04-16-21-43.xlsx"
config_path = os.path.join(path_repo, 'src', 'statics', 'config', 'pesos_factores_stress.json')

# Floor VaR: referencia para escalar simulaciones factor a factor.
# Debe apuntar al archivo Factores_Zeros MAS RECIENTE disponible (salida de MATLAB),
# que contiene filas Analisis='VaR' con los choques historicos correctos para TODAS
# las curvas del portfolio (DEEUR, IBR, SOFR, BRUSD, etc.).
# Si no existe, el floor usara path_var_excel como fallback.
path_floor_excel = (
    r"C:\Users\dapinzo\OneDrive - Grupo Bancolombia\ReporteCorporativo"
    r"\05 Resultados\07 Reportes\Reporte PP\30042026\prospecdef"
    r"\Resultados 30_Apr_Zeros (10 dias) generado el 2026-05-13-12-10-31.xlsx"
)

if path_var_excel and os.path.exists(path_var_excel):
    print("\n" + "=" * 80)
    print("  CALIBRACION DINAMICA DE PESOS")
    print("=" * 80)
    # NOTA: calibracion DESHABILITADA (guardar=False) para preservar pesos manuales
    # en pesos_factores_stress.json (v2.7 - curvas Colombia corregidas para PP).
    # Los pesos de BAAA2/BAAA3/COUSD/CECUVR fueron aumentados manualmente para
    # corregir el gap: Bancolombia PP stress(-88.5B) < VaR(-113.4B).
    try:
        pesos_calibrados, df_diagnostico = cd.calibrar_pesos_desde_var(
            path_var_excel=path_var_excel,
            config_path=config_path,
            nivel='Grupo Bancolombia',
            metodo='min_max',
            guardar=False  # No sobrescribir JSON — preservar ajuste manual v2.7
        )
        cd.imprimir_diagnostico(df_diagnostico)
        print(f"Pesos calibrados (no guardados): {len(pesos_calibrados)} factores | se usan pesos del JSON v2.7\n")
    except Exception as e:
        print(f"Error en calibracion dinamica: {str(e)}")
        print("Se usaran los pesos existentes en la configuracion\n")

# ─── Simulacion con JD ────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("  SIMULACION ESTRES PROSPECTIVO — MODELO JD (Merton Jump-Diffusion)")
print("  Factores GBM -> JD  |  LMM / HJM / CIR sin cambios")
print("=" * 80 + "\n")

names_rfk_stress = rd.Read.readParquet(path_parquet, nameFile='names_rfk_stress.parquet')
wfactors = list(names_rfk_stress.values[0])
wfactors = [f for f in wfactors if f != 'COCOP']

py_excel = rfk_sim_jd.simulationRfkProspectivo_JD(
    fecha, tesoreria, wfactors,
    path_files_parameters,
    path_parquet, path_save,
    path_repo,
    nSim=1500,
    seed=84759,
    path_var_excel=path_var_excel,    # calibracion de pesos (mayo 4)
    path_floor_excel=path_floor_excel, # floor VaR: usa Factores_Zeros mas reciente
)

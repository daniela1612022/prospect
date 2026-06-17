# -*- coding: utf-8 -*-
"""
Created on Thu Aug 11 21:27:15 2022

@author: victgonz

ACTUALIZACIÓN: Ahora integra calibración dinámica de pesos desde archivo VaR.
Si se proporciona path_var_excel, calibra automáticamente los pesos antes de la simulación.
"""

import os
import sys
import logging

absolute_path = os.path.dirname(__file__)
relative_path = "rfk_prospectivo"
full_path = absolute_path.replace(relative_path, "")
sys.path.append(full_path)

import SimulationProspectivo as rfk_sim
import utils.Read as rd
import utils.CalibracionDinamica as cd
# Para el torneo de modelos ver: test_torneo.py

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# import SimulationProspectivo as rfk_sim
# import Read as rd

fecha = "20260430"
tesoreria = "Posicion Propia\\"
#tesoreria = "Asset Management\\"
path_save = "C:\\Users\\dapinzo\\OneDrive - Grupo Bancolombia\\ReporteCorporativo\\05 Resultados\\08 Stress\\"
path_parquet = "C:\\Users\\dapinzo\\OneDrive - Grupo Bancolombia\\ReporteCorporativo\\04 Insumos\\02 Mercado\\Procesados\\Parquet\\"
path_files_parameters = "C:\\Users\\dapinzo\\OneDrive - Grupo Bancolombia\\ReporteCorporativo\\04 Insumos\\04 Parametros\\"
path_repo = r"C:\Users\dapinzo\Downloads\Azure\vrgo-migracion-derivados"

# ═══════════════════════════════════════════════════════════════════════════════
# CALIBRACIÓN DINÁMICA DE PESOS (NUEVO)
# ═══════════════════════════════════════════════════════════════════════════════
# Si tienes el archivo VaR Zeros actualizado, proporciona la ruta aquí para que
# los pesos se calibren automáticamente antes de la simulación.

path_var_excel = None  # CAMBIAR A: r"C:\Users\dapinzo\Downloads\Resultados_30_Apr_Zeros.xlsx"
config_path = os.path.join(path_repo, 'src', 'statics', 'config', 'pesos_factores_stress.json')

if path_var_excel and os.path.exists(path_var_excel):
    print("\n" + "="*80)
    print("  CALIBRACIÓN DINÁMICA DE PESOS — INICIANDO")
    print("="*80)
    try:
        pesos_calibrados, df_diagnostico = cd.calibrar_pesos_desde_var(
            path_var_excel=path_var_excel,
            config_path=config_path,
            nivel='Grupo Bancolombia',
            metodo='min_max',
            guardar=True
        )
        cd.imprimir_diagnostico(df_diagnostico)
        print(f"✓ Pesos calibrados: {len(pesos_calibrados)} factores JSON actualizados\n")
    except Exception as e:
        print(f"\n✗ Error en calibración dinámica: {str(e)}")
        print("  → Se usarán los pesos existentes en la configuración\n")
else:
    if path_var_excel:
        print(f"\n⚠ Archivo VaR no encontrado: {path_var_excel}")
        print("  → Se usarán los pesos existentes en la configuración\n")

# ═══════════════════════════════════════════════════════════════════════════════
# SIMULACIÓN DE RIESGO PROSPECTIVO
# ═══════════════════════════════════════════════════════════════════════════════

names_rfk_stress = rd.Read.readParquet(path_parquet, nameFile = 'names_rfk_stress.parquet')
wfactors = list(names_rfk_stress.values[0])
# Omitir factor de riesgo COCOP
wfactors = [f for f in wfactors if f != 'COCOP']

py_excel = rfk_sim.simulationRfkProspectivo(fecha,tesoreria,wfactors,
                                            path_files_parameters,
                                            path_parquet,path_save,
                                            path_repo,
                                            nSim = 1500)






# -*- coding: utf-8 -*-
"""
Torneo de modelos con datos reales del proyecto.

Evalua 4 modelos (GBM, Jump-Diffusion, ARMA, ARMA-GARCH) sobre factores
representativos de cada categoria:
    - Tasa de cambio  : USDCOP, USDCLP
    - Curva credito   : CEC (nodo 1d), BAAA2 (nodo 1d)
    - Indicador       : IBRn, DTFea
    - Renta variable  : ECOPETROL, ICOLCAP

Cada factor se toma de sus archivos .parquet reales y se usa el historico
completo disponible para evaluar cual modelo reproduce mejor la distribucion
de retornos acumulados a 20 dias (horizonte de estres).

Uso:
    cd src
    python rfk_prospectivo/test_torneo.py
"""

import os
import sys
import warnings
import logging
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

absolute_path = os.path.dirname(__file__)
relative_path = "rfk_prospectivo"
full_path = absolute_path.replace(relative_path, "")
sys.path.append(full_path)

import pandas as pd
import numpy as np
import utils.Read as rd
import torneo_modelos as tm

# =============================================================================
# CONFIGURACION
# =============================================================================

path_parquet = (
    "C:\\Users\\dapinzo\\OneDrive - Grupo Bancolombia\\"
    "ReporteCorporativo\\04 Insumos\\02 Mercado\\Procesados\\Parquet\\"
)

# Parametros del torneo
N_SIM = 1000    # simulaciones por modelo
H     = 20      # horizonte en dias (estres prospectivo)
SEED  = 42      # semilla para reproducibilidad

# =============================================================================
# DEFINICION DE FACTORES A EVALUAR
# (archivo_parquet, columna, nombre_display)
# =============================================================================

# Solo factores con ModeloSimulacion == 'GBM' en Parametros_Reporte.xlsx.
# Las curvas (LMM/HJM) y los indicadores de tasa (CIR) no se evaluan aqui
# porque tienen su propio modelo estructural y no es candidato el GBM vs JD.
FACTORES = {
    # ── Tasas de cambio (GBM en Excel) ────────────────────────────────────
    "USDCOP":    ("CurrenciesH.parquet",  "USDCOP",    "FX"),
    "USDCLP":    ("CurrenciesH.parquet",  "USDCLP",    "FX"),
    "EURUSD":    ("CurrenciesH.parquet",  "EURUSD",    "FX"),
    "GBPUSD":    ("CurrenciesH.parquet",  "GBPUSD",    "FX"),
    "USDBRL":    ("CurrenciesH.parquet",  "USDBRL",    "FX"),

    # ── Renta variable local (GBM en Excel) ───────────────────────────────
    "ECOPETROL": ("PreciosRVH.parquet",   "ECOPETROL", "RV Local"),
    "ICOLCAP":   ("PreciosRVH.parquet",   "ICOLCAP",   "RV Local"),
    "PFAVAL":    ("PreciosRVH.parquet",   "PFAVAL",    "RV Local"),

    # ── Renta variable internacional (GBM en Excel) ───────────────────────
    "SPY":       ("PreciosRVH.parquet",   "SPY",       "RV Internacional"),
    "XLF":       ("PreciosRVH.parquet",   "XLF",       "RV Internacional"),
}


# =============================================================================
# CARGA DE DATOS REALES
# =============================================================================

def cargar_serie(archivo: str, columna: str) -> pd.Series:
    """
    Carga una columna de un archivo parquet como Serie con indice datetime.
    """
    df = rd.Read.readParquet(path_parquet, archivo, DateROW=True)

    if columna not in df.columns:
        raise KeyError(
            f"Columna '{columna}' no encontrada en '{archivo}'.\n"
            f"Columnas disponibles: {df.columns[:10].tolist()}"
        )

    serie = df[columna].dropna().copy()

    # Convertir indice a datetime
    try:
        serie.index = pd.to_datetime(serie.index)
    except Exception:
        pass

    serie = serie.sort_index()

    # Filtrar valores no positivos (precios/tasas deben ser > 0 para log-retornos)
    serie = serie[serie > 0]

    n_obs = len(serie)
    if n_obs < 60:
        raise ValueError(f"Solo {n_obs} observaciones validas en {archivo}/{columna}. Minimo: 60.")

    return serie


# =============================================================================
# EJECUCION DEL TORNEO
# =============================================================================

def main():
    ancho = 92
    print("\n" + "=" * ancho)
    print("  TORNEO DE MODELOS — DATOS REALES")
    print(f"  nSim={N_SIM} | Horizonte={H} dias | Seed={SEED}")
    print("=" * ancho)

    resumen = []   # (categoria, factor, ganador, rank_ganador, n_obs)

    for factor_name, (archivo, columna, categoria) in FACTORES.items():

        print(f"\n  Cargando [{categoria}] {factor_name}  <--  {archivo} / {columna}")

        try:
            serie = cargar_serie(archivo, columna)
            n_obs = len(serie)
            fecha_ini = str(serie.index[0].date()) if hasattr(serie.index[0], 'date') else str(serie.index[0])
            fecha_fin = str(serie.index[-1].date()) if hasattr(serie.index[-1], 'date') else str(serie.index[-1])
            print(f"  {n_obs} observaciones  |  {fecha_ini} al {fecha_fin}")

        except Exception as e:
            print(f"  [!] No se pudo cargar {factor_name}: {e}")
            resumen.append((categoria, factor_name, "ERROR", None, 0))
            continue

        try:
            df_res = tm.torneo(
                serie,
                nSim=N_SIM,
                H=H,
                seed=SEED,
                factor_name=f"{factor_name}  [{categoria}]",
                verbose=True,
            )
            ganador     = df_res.index[0]
            rank_winner = df_res["Composite rank"].iloc[0]
            resumen.append((categoria, factor_name, ganador, rank_winner, n_obs))

        except Exception as e:
            print(f"  [!] Error en torneo de {factor_name}: {e}")
            resumen.append((categoria, factor_name, "ERROR", None, n_obs))

    # ── Tabla resumen final ───────────────────────────────────────────────────
    print("\n" + "=" * ancho)
    print("  RESUMEN FINAL — GANADOR POR FACTOR")
    print("=" * ancho)
    print(f"  {'Categoria':<18} {'Factor':<14} {'Ganador':<18} {'Comp.Rank':>10}  {'N obs':>7}")
    print("  " + "-" * (ancho - 2))

    scores = {}   # contador de victorias por modelo
    for cat, fac, winner, rank, n in resumen:
        rank_str = f"{rank:.2f}" if rank is not None else "  n/a"
        print(f"  {cat:<18} {fac:<14} {winner:<18} {rank_str:>10}  {n:>7,}")
        if winner != "ERROR":
            scores[winner] = scores.get(winner, 0) + 1

    print("\n  VICTORIAS POR MODELO:")
    for modelo, wins in sorted(scores.items(), key=lambda x: -x[1]):
        barra = "█" * wins
        print(f"    {modelo:<20} {barra}  ({wins})")

    print("=" * ancho + "\n")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Torneo de modelos de simulacion de factores de riesgo.

Compara cuatro modelos en su capacidad de reproducir la distribucion empirica
de retornos al horizonte de estres (por defecto 20 dias habiles):

  1. GBM         - Geometric Brownian Motion (baseline actual)
  2. JD          - Jump-Diffusion de Merton  (GBM + saltos Poisson)
  3. ARMA(1,1)   - AutoRegressive Moving Average sobre retornos log
  4. ARMA-GARCH  - ARMA(1,1) con varianza condicional GARCH(1,1)

Metodologia de evaluacion
--------------------------
  * Distribucion empirica de referencia: retornos log acumulados a H dias,
    calculados con ventanas solapadas (stride=5) sobre el historico.
  * Cada modelo genera nSim trayectorias de H dias desde el valor actual.
  * Se comparan las distribuciones simuladas vs empirica en 5 metricas:
      1. KS distance        - distancia KS             (menor es mejor)
      2. Error P05          - error cola izquierda      (menor es mejor)
      3. Error P95          - error cola derecha        (menor es mejor)
      4. Error volatilidad  - ratio sigma sim/emp       (menor es mejor)
      5. Error curtosis     - diferencia de fat-tails   (menor es mejor)
  * Composite rank: rango promedio de cada modelo sobre las 5 metricas.
  * Ganador: menor composite rank.

Uso desde consola
-----------------
    cd src
    python rfk_prospectivo/torneo_modelos.py <parquet_path> <archivo.parquet>
    python rfk_prospectivo/torneo_modelos.py <parquet_path> <archivo.parquet> --factor USDCOP --nSim 800

Uso desde Python
----------------
    from rfk_prospectivo.torneo_modelos import torneo
    import pandas as pd

    serie = pd.read_parquet("...")["precio_col"].dropna()
    df_resultados = torneo(serie, factor_name="USDCOP", nSim=1000)
"""

import os
import sys
import logging
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats

# ── path setup ────────────────────────────────────────────────────────────────
_dir = os.path.dirname(__file__)
_root = _dir.replace("rfk_prospectivo", "")
sys.path.append(_root)

import utils.Read as rd


# =============================================================================
# UTILERIAS
# =============================================================================

def _log_returns(prices: pd.Series) -> np.ndarray:
    """Retornos logaritmicos diarios."""
    p = prices.dropna().values
    return np.diff(np.log(np.abs(p) + 1e-12))


def _empirical_H_returns(prices: pd.Series, H: int = 20, stride: int = 5) -> np.ndarray:
    """
    Retornos acumulados a H dias usando ventanas solapadas.
    stride controla el desplazamiento entre ventanas consecutivas.
    """
    lp = np.log(np.abs(prices.dropna().values) + 1e-12)
    starts = range(0, len(lp) - H, stride)
    emp = np.array([lp[i + H] - lp[i] for i in starts])
    return emp[np.isfinite(emp)]


def _metrics(sim_20d: np.ndarray, emp_20d: np.ndarray) -> dict:
    """Calcula las 5 metricas de comparacion entre distribucion simulada y empirica."""
    sim_20d = sim_20d[np.isfinite(sim_20d)]
    emp_20d = emp_20d[np.isfinite(emp_20d)]

    ks_stat, _ = stats.ks_2samp(sim_20d, emp_20d)

    def pct_err(p):
        sp = np.percentile(sim_20d, p)
        ep = np.percentile(emp_20d, p)
        return abs(sp - ep) / (abs(ep) + 1e-12)

    vol_err  = abs(sim_20d.std() - emp_20d.std()) / (emp_20d.std() + 1e-12)
    kurt_err = abs(stats.kurtosis(sim_20d) - stats.kurtosis(emp_20d)) / (
        1.0 + abs(stats.kurtosis(emp_20d))
    )

    return {
        "KS distance":       round(float(ks_stat),  4),
        "Error P05":         round(float(pct_err(5)), 4),
        "Error P95":         round(float(pct_err(95)), 4),
        "Error volatilidad": round(float(vol_err),   4),
        "Error curtosis":    round(float(kurt_err),  4),
    }


# =============================================================================
# MODELOS (cada uno devuelve un ndarray de nSim retornos acumulados a H dias)
# =============================================================================

def _sim_gbm(returns: np.ndarray, nSim: int, H: int, rng: np.random.Generator) -> np.ndarray:
    """
    Geometric Brownian Motion (baseline actual, sin reduccion ad-hoc de sigma).

    Ecuacion:
        S_t = S_0 * exp((mu - sigma^2/2)*t + sigma*W_t)
    """
    mu    = returns.mean()
    sigma = returns.std()

    Z = rng.standard_normal((H, nSim))
    W = np.cumsum(Z, axis=0)
    t = np.arange(1, H + 1)[:, None]

    drift     = (mu - 0.5 * sigma**2) * t
    diffusion = sigma * W
    return (drift + diffusion)[-1, :]          # retorno acumulado en el dia H


def _sim_jd(returns: np.ndarray, nSim: int, H: int, rng: np.random.Generator,
            jump_threshold_sigma: float = 2.5) -> np.ndarray:
    """
    Jump-Diffusion de Merton.

    Ecuacion:
        ln(S_t/S_0) = (mu_d - sigma_d^2/2 - lambda*k_bar)*t
                     + sigma_d*W_t
                     + sum_{i=1}^{N(t)} J_i

    Donde:
        N(t)  ~ Poisson(lambda * dt)
        J_i   ~ Normal(mu_j, sigma_j^2)
        k_bar = exp(mu_j + sigma_j^2/2) - 1     # correccion de drift

    Calibracion:
        Retornos con |r| > threshold_sigma*sigma → clasificados como saltos.
        El resto → componente de difusion.
    """
    sigma_total = returns.std()
    threshold   = jump_threshold_sigma * sigma_total
    is_jump     = np.abs(returns) > threshold

    n_jumps = is_jump.sum()
    if n_jumps < 3:
        logging.warning("JD: solo %d saltos detectados (umbral %.2f*sigma). "
                        "Usando GBM como fallback.", n_jumps, jump_threshold_sigma)
        return _sim_gbm(returns, nSim, H, rng)

    ret_d = returns[~is_jump]
    ret_j = returns[is_jump]

    mu_d    = ret_d.mean()
    sigma_d = ret_d.std() if ret_d.std() > 0 else 1e-6
    lam     = n_jumps / len(returns)       # intensidad diaria (saltos/dia)
    mu_j    = ret_j.mean()
    sigma_j = ret_j.std() if len(ret_j) > 1 else sigma_total

    # correccion del drift (Merton 1976)
    k_bar  = np.exp(mu_j + 0.5 * sigma_j**2) - 1.0
    mu_adj = mu_d - lam * k_bar

    # Simulacion paso a paso
    cum = np.zeros(nSim)
    for _ in range(H):
        # componente difusion
        Z    = rng.standard_normal(nSim)
        diff = (mu_adj - 0.5 * sigma_d**2) + sigma_d * Z

        # componente saltos
        N_t = rng.poisson(lam, nSim)
        J_t = np.where(
            N_t > 0,
            np.array([rng.normal(mu_j, sigma_j, max(n, 1)).sum() if n > 0 else 0.0
                      for n in N_t]),
            0.0
        )
        cum += diff + J_t

    return cum


def _sim_arma(returns: np.ndarray, nSim: int, H: int, rng: np.random.Generator) -> np.ndarray:
    """
    ARMA(1,1) sobre retornos log.

    Ecuacion:
        r_t = c + phi*r_{t-1} + theta*e_{t-1} + e_t
        e_t ~ N(0, sigma_e^2)

    Calibracion: maxima verosimilitud (statsmodels ARIMA).
    """
    try:
        from statsmodels.tsa.arima.model import ARIMA

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = ARIMA(pd.Series(returns), order=(1, 0, 1)).fit()

        ar1     = float(res.arparams[0]) if len(res.arparams) > 0 else 0.0
        ma1     = float(res.maparams[0]) if len(res.maparams) > 0 else 0.0
        mu_c    = float(res.params.get("const", 0.0))
        sigma_e = float(res.resid.std())

        r_prev = np.full(nSim, returns[-1])
        e_prev = np.full(nSim, float(res.resid.iloc[-1]))
        cum    = np.zeros(nSim)

        for _ in range(H):
            e_new  = rng.normal(0.0, sigma_e, nSim)
            r_new  = mu_c + ar1 * r_prev + ma1 * e_prev + e_new
            cum   += r_new
            r_prev = r_new
            e_prev = e_new

        return cum

    except ImportError:
        logging.warning("statsmodels no disponible. ARMA usa GBM como fallback.")
        return _sim_gbm(returns, nSim, H, rng)
    except Exception as ex:
        logging.warning("ARMA fallo (%s). Usando GBM como fallback.", ex)
        return _sim_gbm(returns, nSim, H, rng)


def _sim_arma_garch(returns: np.ndarray, nSim: int, H: int, rng: np.random.Generator) -> np.ndarray:
    """
    ARMA(1,1) - GARCH(1,1) sobre retornos log.

    Ecuaciones:
        r_t   = c + phi*r_{t-1} + e_t          (media: AR(1))
        e_t   = sigma_t * z_t,  z_t ~ N(0,1)
        h_t   = omega + alpha*e_{t-1}^2 + beta*h_{t-1}   (varianza condicional)
        sigma_t = sqrt(h_t)

    Calibracion: maxima verosimilitud (arch package).
    """
    try:
        import arch as arch_pkg

        pct = pd.Series(returns * 100.0)   # arch requiere Serie o array; iloc[-1] funciona con Serie

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = arch_pkg.arch_model(
                pct, mean="AR", lags=1, vol="GARCH", p=1, q=1, dist="normal"
            )
            res = model.fit(disp="off", show_warning=False)

        p = res.params
        # nombres de parametros pueden variar segun version de arch
        ar1    = float(p.get("ar[1]",    p.get("ar.L1",    0.0)))
        mu_c   = float(p.get("Const",    p.get("mu",       0.0)))
        omega  = float(p["omega"])
        alpha1 = float(p.get("alpha[1]", 0.0))
        beta1  = float(p.get("beta[1]",  0.0))

        # condiciones iniciales (ultimo periodo observado)
        h_t = np.full(nSim, float(res.conditional_volatility.iloc[-1]) ** 2)
        r_t = np.full(nSim, float(pct.iloc[-1]))
        e_t = np.full(nSim, float(res.resid.iloc[-1]))

        cum = np.zeros(nSim)
        for _ in range(H):
            h_new = np.maximum(omega + alpha1 * e_t**2 + beta1 * h_t, 1e-8)
            z     = rng.standard_normal(nSim)
            e_new = np.sqrt(h_new) * z
            r_new = mu_c + ar1 * r_t + e_new
            cum  += r_new / 100.0    # de vuelta a decimal
            r_t   = r_new
            e_t   = e_new
            h_t   = h_new

        return cum

    except ImportError:
        logging.warning("arch no disponible. ARMA-GARCH usa ARMA como fallback.")
        return _sim_arma(returns, nSim, H, rng)
    except Exception as ex:
        logging.warning("ARMA-GARCH fallo (%s). Usando ARMA como fallback.", ex)
        return _sim_arma(returns, nSim, H, rng)


# =============================================================================
# TORNEO
# =============================================================================

MODELOS = {
    "GBM":         _sim_gbm,
    "JD (Merton)": _sim_jd,
    "ARMA(1,1)":   _sim_arma,
    "ARMA-GARCH":  _sim_arma_garch,
}

_MEDAL = {1: "[1]", 2: "[2]", 3: "[3]", 4: "[4]"}


def torneo(
    serie_precios: pd.Series,
    nSim: int          = 1000,
    H: int             = 20,
    seed: int          = 42,
    factor_name: str   = "Factor",
    verbose: bool      = True,
) -> pd.DataFrame:
    """
    Ejecuta el torneo de modelos.

    Parameters
    ----------
    serie_precios : pd.Series
        Precios historicos diarios ordenados cronologicamente.
    nSim : int
        Numero de trayectorias simuladas por modelo.
    H : int
        Horizonte de proyeccion en dias (default=20).
    seed : int
        Semilla aleatoria. La MISMA semilla se usa para todos los modelos
        para garantizar comparacion justa.
    factor_name : str
        Nombre del factor (aparece en el reporte).
    verbose : bool
        Imprime la tabla de resultados en consola.

    Returns
    -------
    pd.DataFrame
        Metricas y ranking de cada modelo, ordenados de mejor a peor.
    """
    serie = serie_precios.dropna().sort_index()
    n_obs = len(serie)

    if n_obs < H + 30:
        raise ValueError(
            f"Se necesitan al menos {H + 30} observaciones para el torneo "
            f"(hay {n_obs})."
        )

    returns  = _log_returns(serie)
    emp_20d  = _empirical_H_returns(serie, H=H, stride=5)

    if len(emp_20d) < 5:
        raise ValueError(
            f"Muy pocos retornos empiricos a {H} dias ({len(emp_20d)}). "
            "Proporcione mas historia."
        )

    # ── Ejecutar cada modelo ──────────────────────────────────────────────────
    resultados = {}
    for nombre, fn_sim in MODELOS.items():
        rng = np.random.default_rng(seed)      # misma semilla por modelo
        try:
            sim = fn_sim(returns, nSim, H, rng)
            resultados[nombre] = _metrics(sim, emp_20d)
        except Exception as ex:
            logging.error("Error en modelo %s: %s", nombre, ex)
            resultados[nombre] = {k: np.nan for k in
                                  ["KS distance", "Error P05", "Error P95",
                                   "Error volatilidad", "Error curtosis"]}

    # ── Calcular ranking compuesto ────────────────────────────────────────────
    metricas = ["KS distance", "Error P05", "Error P95",
                "Error volatilidad", "Error curtosis"]

    df = pd.DataFrame(resultados).T[metricas]
    df_rank = df.rank(axis=0, method="min", na_option="bottom")
    df["Composite rank"] = df_rank.mean(axis=1).round(2)
    df["Posicion"]       = df["Composite rank"].rank(method="min").astype(int)
    df = df.sort_values("Posicion")

    if verbose:
        _print_tabla(df, metricas, factor_name, H, nSim, len(emp_20d))

    return df


# =============================================================================
# REPORTE EN CONSOLA
# =============================================================================

def _print_tabla(df, metricas, factor_name, H, nSim, n_emp):
    ancho = 92
    sep   = "=" * ancho

    print(f"\n{sep}")
    print(f"  TORNEO DE MODELOS | Factor: {factor_name} | Horizonte: {H} dias | "
          f"nSim: {nSim} | Ref empirica: {n_emp} ventanas")
    print(sep)

    # Cabecera
    header = f"  {'Modelo':<20}"
    for m in metricas:
        header += f"  {m:>16}"
    header += f"  {'Comp.Rank':>10}  Pos"
    print(header)
    print("  " + "-" * (ancho - 2))

    for modelo, row in df.iterrows():
        pos    = int(row["Posicion"])
        medal  = _MEDAL.get(pos, "   ")
        linea  = f"  {medal} {modelo:<17}"
        for m in metricas:
            val = row[m]
            linea += f"  {val:>16.4f}" if pd.notna(val) else f"  {'n/a':>16}"
        linea += f"  {row['Composite rank']:>10.2f}  #{pos}"
        print(linea)

    ganador = df.index[0]
    segundo = df.index[1] if len(df) > 1 else ""

    print(f"\n  >> GANADOR: {ganador}  (Composite rank {df['Composite rank'].iloc[0]:.2f})")
    if segundo:
        diff = df['Composite rank'].iloc[1] - df['Composite rank'].iloc[0]
        print(f"  >> 2do:     {segundo}  (diferencia: {diff:.2f} puntos de rango)")

    # Guia de metricas
    print(f"\n  Metricas (todas: menor es mejor)")
    print(f"    KS distance       - distancia Kolmogorov-Smirnov entre distribuciones")
    print(f"    Error P05/P95     - error relativo en percentil 5/95 (colas)")
    print(f"    Error volatilidad - error relativo en sigma de 20d")
    print(f"    Error curtosis    - diferencia normalizada en fat-tails")
    print(f"  Composite rank: promedio de rangos 1-4 en las 5 metricas\n")
    print(sep + "\n")


# =============================================================================
# INTEGRACION CON EL PROYECTO: cargar un factor del parquet
# =============================================================================

def cargar_factor_y_correr(
    path_parquet: str,
    nombre_archivo: str,
    columna: str      = None,
    factor_name: str  = None,
    **kwargs_torneo,
) -> pd.DataFrame:
    """
    Carga un archivo parquet del proyecto y ejecuta el torneo.

    Parameters
    ----------
    path_parquet : str
        Carpeta donde estan los archivos .parquet.
    nombre_archivo : str
        Nombre del archivo (ej: 'USDCOP.parquet').
    columna : str, optional
        Columna a usar como precio. Si es None usa la primera numerica.
    factor_name : str, optional
        Nombre a mostrar en el reporte. Por defecto usa el nombre del archivo.
    **kwargs_torneo :
        Argumentos adicionales para :func:`torneo` (nSim, H, seed, etc.).

    Returns
    -------
    pd.DataFrame
        Resultado del torneo.
    """
    df_hist = rd.Read.readParquet(path_parquet, nameFile=nombre_archivo, DateROW=True)

    if columna:
        serie = df_hist[columna].dropna()
    else:
        num_cols = df_hist.select_dtypes(include=np.number).columns
        if len(num_cols) == 0:
            raise ValueError(f"El parquet '{nombre_archivo}' no tiene columnas numericas.")
        serie = df_hist[num_cols[0]].dropna()

    try:
        serie.index = pd.to_datetime(serie.index)
    except Exception:
        pass

    serie = serie.sort_index()

    fname = factor_name or nombre_archivo.replace(".parquet", "")
    return torneo(serie, factor_name=fname, **kwargs_torneo)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Torneo de modelos de simulacion de factores de riesgo"
    )
    parser.add_argument("parquet_path",  help="Ruta a la carpeta de parquets")
    parser.add_argument("parquet_file",  help="Nombre del archivo .parquet")
    parser.add_argument("--columna",     default=None, help="Columna de precios")
    parser.add_argument("--factor",      default=None, help="Nombre del factor")
    parser.add_argument("--nSim",  type=int, default=1000)
    parser.add_argument("--H",     type=int, default=20,
                        help="Horizonte de proyeccion en dias (default: 20)")
    parser.add_argument("--seed",  type=int, default=42)

    args = parser.parse_args()

    cargar_factor_y_correr(
        path_parquet=args.parquet_path,
        nombre_archivo=args.parquet_file,
        columna=args.columna,
        factor_name=args.factor,
        nSim=args.nSim,
        H=args.H,
        seed=args.seed,
    )

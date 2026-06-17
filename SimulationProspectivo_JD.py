#%% Librerias
# SimulationProspectivo_JD.py — Variante experimental que reemplaza GBM por
# Jump-Diffusion de Merton (JD) para factores de FX y Renta Variable.
# LMM, HJM y CIR no cambian.

import utils.Read as rd
import utils.RiskFactors as rkf
import rfk_prospectivo.RiskModels as rkm
import pandas as pd
import datetime as dt
import numpy as np
from numpy.random import SeedSequence
import os
import pickle
import sys
import random
import time
import logging


#%% Funcion auxiliar: floor VaR

# Mapeo inverso de FACTOR_MAPPING (var_excel_name -> rfd_key -> var_excel_name)
# Construido a partir de CalibracionDinamica.FACTOR_MAPPING
_FACTOR_MAPPING_INV = {
    # Curvas swap
    "IBR": "C_IBR",       "IBRn": "C_IBR",   "IBRea": "C_IBR",
    "IBR1n": "C_IBR",     "IBR1ea": "C_IBR", "IBR3n": "C_IBR", "IBR3ea": "C_IBR",
    "IPC": "C_IPCFWD",    "IPCn": "C_IPCFWD","IPCea": "C_IPCFWD",
    "IPCmv": "C_IPCFWD",  "IPCFWD": "C_IPCFWD",
    "OISCOP_Proy": "C_OISCOP_Proy",
    "CECUVR": "C_IBRUVR",
    "OISUSD": "C_OISUSD",
    "SOFR": "C_SOFR",
    "SOFR_LCH": "C_SOFR_LCH",
    "FFE_LCH": "C_FFE_LCH",
    # Curvas implícitas FX
    "BRUSD": "T_USDBRL",
    "MXUSD": "T_USDMXN",  "MXMXN": "T_USDMXN",
    "PENUSD": "T_USDPEN",
    # Indicadores
    "DTF": "DTFta",  "DTFn": "DTFta",  "DTFea": "DTFta",
    # Crédito / soberanos
    "SVUSD": "SVGOVT",
}


def aplicar_floor_choques_var(path_excel, path_var_excel, rfd, dict_par,
                              fecha_valoracion, n_max_proyeccion,
                              safety_factor=1.0):
    """
    Escala los archivos xlsx de simulación para garantizar que el choque
    máximo de estrés sea >= choque máximo del VaR histórico por factor.

    Solo escala factores cuyo choque simulado < VaR y donde el VaR > 0.
    Excluye factores de Precios RV con Escenario=0 (artefactos históricos).
    Preserva la forma de la distribución simulada escalando alrededor del
    valor base histórico en la fecha de valoración.

    Parámetros
    ----------
    path_excel : str
        Ruta donde se guardaron los xlsx de simulaciones.
    path_var_excel : str
        Ruta al Excel de VaR Zeros (hoja Factores_Zeros).
    rfd : dict
        riskfactorDictionary con datos históricos de cada factor.
    dict_par : dict
        Diccionario Ubicacion -> [factores], construido desde file_Parameterization.
    fecha_valoracion : str
        Fecha de valoración en formato yyyymmdd.
    n_max_proyeccion : int
        Horizonte de proyección (días).
    safety_factor : float
        Margen sobre el VaR (1.0 = exactamente VaR, 1.05 = 5% extra).
    """
    try:
        import sys as _sys
        # Importar cargar_choques_var desde CalibracionDinamica
        _cd_mod = None
        for _mod_name in ('utils.CalibracionDinamica', 'CalibracionDinamica'):
            try:
                import importlib as _il
                _cd_mod = _il.import_module(_mod_name)
                break
            except ImportError:
                continue
        if _cd_mod is None:
            logging.warning('Floor VaR: no se pudo importar CalibracionDinamica.')
            return
        cargar_choques_var = _cd_mod.cargar_choques_var

        # ── Cargar datos VaR (solo filas Analisis=='VaR') ──────────────────
        df_var_all = cargar_choques_var(path_var_excel, nivel='Grupo Bancolombia')
        df_var = df_var_all[df_var_all['Analisis'] == 'VaR'].copy()

        if df_var.empty:
            logging.warning('Floor VaR: no se encontraron filas Analisis=VaR en el Excel.')
            return

        # ── Calcular VaR max choque por factor en unidades nativas ─────────
        # Para curvas (Puntos basicos): Diferencia en bps → /10000 = decimal
        # Para otros (Absoluta): Diferencia ya en unidades nativas
        var_info = {}  # {var_factor_name: {'choque_native': float, 'clase': str}}

        for factor, g in df_var.groupby('Factor'):
            clase = g['Clase_Diferencia'].iloc[0]
            max_dif = g['Diferencia'].abs().max()

            # Excluir artefactos RV (escenario=0 para todos los registros → 100% pérdida ficticia)
            tipo_str = g['Tipo'].iloc[0] if 'Tipo' in g.columns else ''
            is_rv = 'RV' in str(tipo_str) or 'Precio' in str(tipo_str)
            is_artifact = is_rv and (g['Escenario'].abs() < 1e-6).all()
            if is_artifact:
                continue

            if clase == 'Puntos basicos':
                choque_native = max_dif / 10000.0   # bps → decimal
            else:
                choque_native = max_dif             # en unidades nativas

            if choque_native > 0:
                var_info[factor] = {
                    'choque_native': choque_native * safety_factor,
                    'clase': clase,
                }

        logging.info(f'Floor VaR: {len(var_info)} factores con choque VaR > 0 (artefactos RV excluidos).')
        n_scaled = 0

        # ── Factores univariados (CurrenciesS, PreciosRVS, IndicadoresS) ───
        for type_serie in ['CurrenciesH', 'PreciosRVH', 'IndicadoresH']:
            xls_path = os.path.join(path_excel, type_serie[:-1] + 'S.xlsx')
            if not os.path.exists(xls_path):
                continue

            df = pd.read_excel(xls_path, index_col=0)
            changed = False

            for serie in dict_par.get(type_serie, []):
                if serie not in df.columns:
                    continue
                if serie not in rfd or not hasattr(rfd[serie], 'curve_training'):
                    continue

                # Buscar nombre del factor en VaR (puede tener alias)
                var_factor = _FACTOR_MAPPING_INV.get(serie, serie)
                if var_factor not in var_info:
                    continue

                # Valor base histórico en fecha de valoración
                try:
                    ct_val = rfd[serie].curve_training.loc[fecha_valoracion]
                    s0 = float(np.atleast_1d(np.asarray(ct_val)).flat[0])
                except Exception:
                    continue

                var_choque = var_info[var_factor]['choque_native']
                sim_choque_max = float((df[serie] - s0).abs().max())

                if sim_choque_max > 0 and sim_choque_max < var_choque:
                    escala = var_choque / sim_choque_max
                    df[serie] = s0 + (df[serie] - s0) * escala
                    changed = True
                    n_scaled += 1
                    logging.info(
                        f'Floor VaR [{type_serie[:-1]}]: {serie} ×{escala:.2f} '
                        f'(sim={sim_choque_max:.4f} → VaR={var_choque:.4f})'
                    )

            if changed:
                df.to_excel(xls_path)

        # ── Factores de curva (DEEUR.xlsx, MXEUR.xlsx, etc.) ───────────────
        curvas_en_var = 0
        curvas_sin_match_var = []
        for type_curva in ['CurvasDPEH', 'CurvasDPRH', 'CurvasINTH',
                           'CurvasLOCH', 'CurvasIMPH']:
            for curva in dict_par.get(type_curva, []):
                xls_path = os.path.join(path_excel, f'{curva}.xlsx')
                if not os.path.exists(xls_path):
                    continue
                if curva not in rfd or not hasattr(rfd[curva], 'curve_training'):
                    continue

                # Buscar nombre del factor en VaR (puede tener alias)
                var_factor = _FACTOR_MAPPING_INV.get(curva, curva)
                if var_factor not in var_info:
                    curvas_sin_match_var.append(f'{curva}(→{var_factor})')
                    continue

                curvas_en_var += 1
                try:
                    df = pd.read_excel(xls_path, index_col=0)
                    base_curve = rfd[curva].curve_training.loc[fecha_valoracion]
                except Exception:
                    continue

                # Mapear columnas del xlsx ('CURVA_N') al valor base por nodo.
                # El índice de base_curve puede ser int, float o string según el parquet.
                base_vals = {}
                for col in df.columns:
                    parts = col.split('_')
                    try:
                        node_int = int(parts[-1])
                    except (ValueError, IndexError):
                        continue
                    node_float = float(node_int)
                    node_str   = str(node_int)
                    # Probar int, float y string para máxima compatibilidad
                    if node_int in base_curve.index:
                        base_vals[col] = float(base_curve[node_int])
                    elif node_float in base_curve.index:
                        base_vals[col] = float(base_curve[node_float])
                    elif node_str in base_curve.index:
                        base_vals[col] = float(base_curve[node_str])

                if not base_vals:
                    logging.warning(
                        f'Floor VaR [{curva}]: base_vals vac\u00edo '
                        f'(index type={type(base_curve.index[0]).__name__}, '
                        f'sample={list(base_curve.index[:3])})'
                    )
                    continue

                # Max choque en decimal a través de todos los nodos y simulaciones
                max_sim_dec = float(
                    max((df[col] - bv).abs().max() for col, bv in base_vals.items())
                )
                var_choque_dec = var_info[var_factor]['choque_native']  # ya en decimal

                if max_sim_dec > 0 and max_sim_dec < var_choque_dec:
                    escala = var_choque_dec / max_sim_dec
                    for col, bv in base_vals.items():
                        df[col] = bv + (df[col] - bv) * escala
                    df.to_excel(xls_path)
                    n_scaled += 1
                    logging.info(
                        f'Floor VaR [curva]: {curva} \u00d7{escala:.2f} '
                        f'(sim={max_sim_dec*10000:.2f}bps \u2192 VaR={var_choque_dec*10000:.2f}bps)'
                    )
                else:
                    logging.debug(
                        f'Floor VaR [{curva}]: sin escalar '
                        f'(sim={max_sim_dec*10000:.2f}bps >= VaR={var_choque_dec*10000:.2f}bps)'
                    )

        if curvas_sin_match_var:
            logging.info(
                f'Floor VaR: {len(curvas_sin_match_var)} curvas sin entrada en VaR ref '
                f'(usar path_floor_excel con Factores_Zeros de MATLAB): '
                f'{", ".join(curvas_sin_match_var[:10])}'
                + (' ...' if len(curvas_sin_match_var) > 10 else '')
            )
        logging.info(
            f'Floor VaR completado: {n_scaled} factores escalados de {len(var_info)} elegibles '
            f'({curvas_en_var} curvas encontradas en VaR ref).'
        )

    except Exception as _e_floor:
        import traceback
        logging.warning(f'Floor VaR: error inesperado (no se aplicó): {_e_floor}')
        logging.warning(traceback.format_exc())


#%% Funcion principal

def statistic_alert(sim,hist,key,n_proyeccion):

    hist_pct = hist.pct_change(n_proyeccion).dropna()
    if len(hist_pct.shape) == 2:
        hist_pct = hist_pct.mean(axis=1)

    hist_pct_quant = hist_pct.describe()
    IQR = hist_pct_quant["75%"]-hist_pct_quant["25%"]
    lim_inf = hist_pct_quant["25%"]-1.5*IQR
    lim_sup = hist_pct_quant["75%"]+1.5*IQR

    outliers_inf_hist = sum(hist_pct<lim_inf)
    outliers_sup_hist = sum(lim_sup<hist_pct)
    max_hist = hist_pct_quant["max"]
    min_hist = hist_pct_quant["min"]

    if len(sim.shape) == 2:
        sim_pct = sim/hist.tail(1).values-1
        sim_pct = pd.Series(sim_pct.mean(axis=1),name=key)
    else:
        sim_pct = pd.Series(sim/hist.tail(1).values-1,name=key)

    sim_pct.sort_values(inplace=True)
    sim_pct_quant = sim_pct.describe()
    log_inf = sim_pct<lim_inf
    log_sup = lim_sup<sim_pct
    outliers_inf_sim = (log_inf).sum()
    outliers_sup_sim = (log_sup).sum()
    min_sim = sim_pct_quant["min"]
    max_sim = sim_pct_quant["max"]
    supinf = sim_pct[log_inf].tail(1).values[0] if outliers_inf_sim != 0 else None
    infsup = sim_pct[log_sup].head(1).values[0] if outliers_sup_sim != 0 else None

    alerts_key = pd.DataFrame({"Lim Inf":lim_inf,
                               "Inf Out Hist":outliers_inf_hist,
                               "Inf Out Sim":outliers_inf_sim,
                               "Lim Sup":lim_sup,
                               "Sup Out Hist":outliers_sup_hist,
                               "Sup Out Sim":outliers_sup_sim,
                               "Ult Hist":hist_pct.tail(1).values[0],
                               "Min Hist":min_hist,
                               "Min Sim":min_sim,
                               "Sup_inf Sim":supinf,
                               "Min Sim < Min Hist":min_sim<min_hist,
                               "Max Hist":max_hist,
                               "Max Sim":max_sim,
                               "Inf_sup Sim":infsup,
                               "Max Hist < Max Sim":max_hist<max_sim,
                               "Total Out Sim":outliers_inf_sim+outliers_sup_sim},
                               index=[key])

    return alerts_key, sim_pct_quant


def simulationRfkProspectivo_JD(
        fecha_valoracion:str,tesoreria:str,wfactors:list,path_files_parameters,
        path_parquet,path_save,path_repo,**kwargs):
    """
    Esta funcion se encarga de compilar, transformar, correlacionar y
    simular los factores de riego.

    Parameters
    ----------
    fecha : str
        Fecha de corte (de valoracion) en formato yyymmdd.
    tesoreria: str
        Tesoreria de Posicion Propia o Asset Management en ejecucion.
    wfactors : list
        Lista de factores de riesgo a simular.
    path_files_parameters : str
        Ruta de archivo excel donde esta la parametrizacion de cada
        factor de riesgo.
    path_parquet : str
        Ruta donde esta los archivos .parquet donde se extrae el historico
        de cada factor de riesgo.
    path_save : str
        Ruta donde se guardara en formato excel las simulaciones generadas.
    wf_remove : list
            Lista de factores de riesgo que no se desean simular y dejar
            constante.
    **kwargs : dict
        nPCs : int
            Numero de componentes principales en que se decea descomponer
            las curvas. Por defecto se establece como 3.
        nSim : int
            Numero de simulaciones que se decea realizar por cada dia
            proyectado. Por defecto se establece como 1500.
        n_max_proyeccion : int
            Horizonte de tiempo en dias de la proyeccion.
        n_max_historia : int
            Horizonte de tiempo en dias de la historia a tomar de los
            factores de riesgo.
        seed : int
            Semilla con la que se quiere ejecutar las simulacione.

    Returns
    -------
    bool
        Regresa True si la simulacion se realizo de forma correcta, False
        si una parte del proceso no fue satisfactoria.

    """

    #%% Creacion de carpetas para guardar las simulaciones

    path_excel = os.path.join(path_save,tesoreria,fecha_valoracion)

    try:
        os.mkdir(path_excel)
        print(f"Se crea el folder {path_excel}")
    except:
        print(f'Ya existe el folder {path_excel}')


    #%%  Creacion del archivo log

    time_now = dt.datetime.now().strftime("%Y%m%d %H-%M-%S")

    # Abre el archivo de log en modo de escritura
    logging.basicConfig(
        level  = logging.DEBUG,  # Establece el nivel de registro deseado
        format ='%(asctime)s - %(levelname)s - %(message)s',  # Formato del registro
        filename = os.path.join(path_excel,f"log_{time_now}.txt"),  # Archivo de registro
        filemode='w'  # Modo de apertura (sobrescribe el archivo en cada ejecución)
    )

    # Agrega un manejador de registro para imprimir en la consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(console_handler)

    # Este try es para permitir cerrar el archivo de log en caso de fallar el proceso.
    try:
        #%% Cominezo de generacion archivo log
        logging.info("Inicio de ejecucion del programa SimulationProspectivo para la fecha de corte: {0}.".format(fecha_valoracion))

        #%% Parametros

        time_start = time.time()
        nCPs =  kwargs.get('nCPs',3)
        nSim =  kwargs.get('nSim',1500)
        seed =  kwargs.get('seed',None)
        n_max_proyeccion = kwargs.get('n_max_proyeccions',20)
        n_max_historia = kwargs.get('n_max_historia',250)
        n_max_correlacion = kwargs.get('n_max_correlacion',250)
        fecha_correlacion = kwargs.get('fecha_correlacion',fecha_valoracion)
        path_var_excel = kwargs.get('path_var_excel', None)
        # Referencia para el floor VaR (puede diferir de la referencia de calibración).
        # Si no se provee, usa path_var_excel como fallback.
        path_floor_excel = kwargs.get('path_floor_excel', None) or path_var_excel


        if seed:
            seedseq =  SeedSequence(seed)
            logging.info("La semilla con la que se simulo los factores de riesgo fue: {0}".format(seed))
        else:
            numero_aleatorio = random.randint(0, 99999)
            seedseq = SeedSequence(numero_aleatorio)
            logging.info("La semilla con la que se simulo los factores de riesgo fue: {0}".format(numero_aleatorio))

        times_ =  np.arange(0,n_max_proyeccion+1)
        timeY =  times_[1:]/360
        wfactors = list(wfactors)


        #%% Datos

        #Se removeran factores de riesgo.
        file_Parameterization = rd.Read.readExcel(path = path_files_parameters,
                                                  Name_file = 'Parametros_Reporte',
                                                  sheet_name = 'Factores')

        try:
            logging.info('Se carga la data historica de los factores de riesgo.')
            riskfactorDictionary = rkf.RiskFactors.create_factorInfo_dictionary(
                fecha_valoracion,
                wfactors,
                file_Parameterization,
                path_parquet,
                path_repo)
        except Exception as e:
            logging.error('Fallo la carga de informacion. Error: {0}'.format(str(e)))
            return False

        try:
            logging.info('Se filtra la informacion historica para la calibracion.')
            riskfactorDictionary = rkf.RiskFactors.curve_trainig_filter(
                riskfactorDictionary, fecha_valoracion, n_max_historia, True)
        except:
            logging.error('Fallo el proceso de filtracion para la calibracion.')
            return False

        try:
            logging.info('Se filtra la informacion historica para la correlacion.')
            riskfactorDictionary_corr = riskfactorDictionary.copy()
            riskfactorDictionary_corr = rkf.RiskFactors.curve_trainig_filter(
                riskfactorDictionary_corr, fecha_correlacion, n_max_correlacion,
                False)
        except:
            logging.error('Fallo el proceso de filtracion para la correlacion.')
            return False

        try:
            logging.info('Descomposicion PCA para la calibracion.')
            _, riskfactorDictionary = rkf.RiskFactors.filter_pca_components(
                riskfactorDictionary,nCPs,True)
        except Exception as e:
            logging.error('Fallo la descomposicion PCA para la calibracion. Error: {0}'.format(str(e)))
            return False

        try:
            logging.info('Descomposicion PCA para la correlacion.')
            compMatrix, rfd_corr_named = rkf.RiskFactors.filter_pca_components(
                riskfactorDictionary_corr,nCPs,False)
        except Exception as e:
            logging.error('Fallo la descomposicion PCA para la correlacion. Error: {0}'.format(str(e)))
            return False

        try:
            logging.info('Creacion de matriz de correlacion.')
            corrPCs, riskfactorDictionary = rkf.RiskFactors.randon_correlation_vectors(
                riskfactorDictionary,compMatrix,nSim,seedseq,n_max_proyeccion)
        except:
            logging.error('Fallo la creacion de matriz de correlacion.')
            return False

        #%% Cargar matriz de pesos para aplicar durante simulación
        
        pesos_dict = {}
        try:
            import utils.PesosStress as ps
            config_pesos_path = os.path.join(path_repo, 'src', 'statics', 'config', 'pesos_factores_stress.json')
            pesos_manager = ps.PesosFactoresStress(config_pesos_path)
            
            if pesos_manager.config.get('aplicar_pesos', True):
                for key in riskfactorDictionary.keys():
                    pesos_dict[key] = pesos_manager.obtener_peso(key)
                logging.info(f'Pesos cargados para {len(pesos_dict)} factores. Rango: [{min(pesos_dict.values()):.2f}, {max(pesos_dict.values()):.2f}]')
            else:
                logging.info('Aplicación de pesos desactivada.')
        except Exception as e:
            logging.warning(f'No se pudieron cargar pesos: {str(e)}. Usando pesos=1.0')
            pesos_dict = {key: 1.0 for key in riskfactorDictionary.keys()}

        #%% Simulacion de los factores de riesgo.

        for key in riskfactorDictionary.keys():

            logging.info(f'Inicio simulacion del factor {key}.')
            
            # Obtener peso para este factor
            peso_factor = pesos_dict.get(key, 1.0)

            try:
                if riskfactorDictionary[key].metsim == 'LMM':

                    cf =  riskfactorDictionary[key].eigenVectors.copy()
                    slt = np.sqrt(riskfactorDictionary[key].eigenValues)
                    lambda_ =  cf*np.repeat(slt.reshape(1,len(slt)),len(slt),axis=0)

                    #% Volatilidad total de tasa fwd con j nodos (H&W pag 11 (17))
                    lbd = np.sqrt(np.power(lambda_,2).sum(axis = 1))
                    l_aux = np.sqrt(np.power(lambda_[:,0:nCPs],2).sum(axis = 1))

                    #% Volatilidades de cada nodo teniendo en cuenta solo 3 CPs
                    lambdajq_ = np.repeat(lbd.reshape(1,len(l_aux)),nCPs,axis=0).T\
                        *lambda_[:,0:nCPs]/(np.repeat(l_aux.reshape(1,len(l_aux)),\
                                                      nCPs,axis=0).T)
                    
                    # Aplicar peso a volatilidades
                    lambdajq_ = lambdajq_ * peso_factor

                    mat_ljq = np.matmul(lambdajq_,lambdajq_.T)
                    fwd_ref = riskfactorDictionary[key].fwd_curve.loc[fecha_valoracion].values
                    time360 =  riskfactorDictionary[key].node_training.values/360
                    randoncorr_Vector = riskfactorDictionary[key].randoncorr_Vector

                    riskfactorDictionary[key].sim_MC = rkm.lmmm(
                        time360,times_,nSim,lambdajq_,fwd_ref,timeY,nCPs,mat_ljq,
                        fecha_valoracion,randoncorr_Vector)
                elif riskfactorDictionary[key].metsim == 'HJM':
                    riskfactorDictionary[key].sim_MC = rkm.HJM(
                        riskfactorDictionary,key,fecha_valoracion,n_max_proyeccion,
                        nSim, peso_factor=peso_factor)
                elif riskfactorDictionary[key].metsim == 'GBM':
                    # JD (Merton Jump-Diffusion) en lugar de GBM puro
                    riskfactorDictionary[key].sim_MC = rkm.jd(
                        riskfactorDictionary,key,fecha_valoracion,n_max_proyeccion,
                        nSim, peso_factor=peso_factor)
                elif riskfactorDictionary[key].metsim == 'CIR':
                    riskfactorDictionary[key].sim_MC = rkm.CIR(
                        riskfactorDictionary,key,fecha_valoracion,n_max_proyeccion,
                        nSim,dt=1/252, peso_factor=peso_factor)
                else:
                    riskfactorDictionary[key].PComponent = \
                          riskfactorDictionary[key].curve_training.values

                logging.info(f'El factor {key} se simulo correctamente.')
            except Exception as e:
                logging.error(f'----- El factor {key} no se pudo simular correctamente. Error: {str(e)}')
                return False

        #%% Documentar matriz de pesos aplicada (ya aplicados ANTES de la simulación en modelos)
        
        # NOTA: Los pesos ya se aplicaron durante la calibración de modelos (líneas ~240-300)
        # multiplicando las volatilidades ANTES de generar simulaciones.
        # Este bloque SOLO genera reporte para documentación.
        
        try:
            import utils.PesosStress as ps
            
            # Cargar configuración de pesos para reporte
            config_pesos_path = os.path.join(path_repo, 'src', 'statics', 'config', 'pesos_factores_stress.json')
            pesos_manager = ps.PesosFactoresStress(config_pesos_path)
            
            # Generar reporte de pesos aplicados (solo documentación)
            df_pesos = pesos_manager.generar_reporte_pesos(list(riskfactorDictionary.keys()))
            pesos_con_ajuste = df_pesos[df_pesos['Peso'] != 1.0]
            if len(pesos_con_ajuste) > 0:
                logging.info(f'Reporte: {len(pesos_con_ajuste)} factores con pesos ajustados')
                logging.info(f'Pesos documentados - Promedio: {df_pesos["Peso"].mean():.2f}, '
                           f'Min: {df_pesos["Peso"].min():.2f}, Max: {df_pesos["Peso"].max():.2f}')
                
        except Exception as e:
            logging.warning(f'No se pudo generar reporte de pesos: {str(e)}.')

        #%% Guardar los resultados de la simulaciones

        wfactors = list(riskfactorDictionary.keys())

        try:
            logging.info(f' Inicio de guardado de simulaciones.')
            # Diccionario de la ubicacion de los factores de riego simulados
            log_wf = file_Parameterization['FactorDeRiesgo'].isin(wfactors)
            dict_par = file_Parameterization.loc[log_wf,:].groupby('Ubicacion')\
                ['FactorDeRiesgo'].apply(list).to_dict()

            # Para monedas, indicadores y precios de acciones se crea solo
            # un archivo excel
            for type_serie in ['CurrenciesH','IndicadoresH','PreciosRVH']:
                datos = dict()
                for serie in dict_par.get(type_serie,[]):
                    datos[serie] = riskfactorDictionary[serie].sim_MC[n_max_proyeccion-1,:]

                df_serie = pd.DataFrame(datos)
                df_serie.to_excel(os.path.join(path_excel,type_serie[:-1]+'S.xlsx'))

            # Para cada curva sin importar su tipo se crea un archivo excel.
            for type_curva in ['CurvasDPEH','CurvasDPRH','CurvasINTH',
                               'CurvasLOCH','CurvasIMPH']:
                datos = dict()
                for curva in dict_par.get(type_curva,[]):
                    nodos_curva = riskfactorDictionary[curva].node_training
                    names_columns = [f'{curva}_{int(i)}' for i in nodos_curva]
                    datos[curva] = pd.DataFrame(
                        riskfactorDictionary[curva].sim_MC[n_max_proyeccion-1,:].T,
                        columns = names_columns)
                for curva in datos:
                    datos[curva].to_excel(os.path.join(path_excel,f'{curva}.xlsx'))

            logging.info(f' Fin de guardado de simulaciones.')
        except Exception as e:
            logging.error(f'Fallo el guardado de las simulaciones: {str(e)}')
            import traceback
            logging.error(f'Traceback: {traceback.format_exc()}')
            return False

        #%% Floor VaR: escalar xlsx para garantizar stress >= VaR por factor
        # Usa path_floor_excel (Factores_Zeros mas reciente de MATLAB) como referencia.
        # Si no existe, intenta con path_var_excel como fallback.

        _floor_ref = path_floor_excel if (path_floor_excel and os.path.exists(path_floor_excel)) \
            else (path_var_excel if (path_var_excel and os.path.exists(path_var_excel)) else None)

        if _floor_ref:
            try:
                logging.info(f'Floor VaR: iniciando escalado (ref={os.path.basename(_floor_ref)})...')
                log_wf_floor = file_Parameterization['FactorDeRiesgo'].isin(list(riskfactorDictionary.keys()))
                dict_par_floor = file_Parameterization.loc[log_wf_floor, :].groupby('Ubicacion') \
                    ['FactorDeRiesgo'].apply(list).to_dict()
                aplicar_floor_choques_var(
                    path_excel=path_excel,
                    path_var_excel=_floor_ref,
                    rfd=riskfactorDictionary,
                    dict_par=dict_par_floor,
                    fecha_valoracion=fecha_valoracion,
                    n_max_proyeccion=n_max_proyeccion,
                    safety_factor=1.0,
                )
            except Exception as _e_floor:
                logging.warning(f'Floor VaR falló (continuando sin escalar): {_e_floor}')
        else:
            logging.info('Floor VaR: ninguna referencia VaR disponible, se omite el escalado.')

        #%% Guardar Estadisticas

        try:
            logging.info(f' Inicio de guardado de estadisticas.')
            writer_excel = pd.ExcelWriter(os.path.join(path_excel,"Simulation_statistics.xlsx"))
            sim_describe = pd.DataFrame()
            alerts = pd.DataFrame()

            for key in riskfactorDictionary.keys():
                if (riskfactorDictionary[key].metsim == 'LMM'
                    or riskfactorDictionary[key].metsim == 'HJM'):

                    nodos_curva = riskfactorDictionary[key].node_training
                    sim = riskfactorDictionary[key].sim_MC[n_max_proyeccion-1].T
                    sim = pd.DataFrame(sim,columns=nodos_curva)
                    hist = riskfactorDictionary[key].curve.loc[:fecha_valoracion]
                    hist = pd.DataFrame(hist.values,columns=nodos_curva)


                    # Estadisticas tramo corto de la curva, menor a 720 dias
                    alerts_key_s,  sim_pct_quant_s = statistic_alert(sim.loc[:,:720],
                                                                   hist.loc[:,:720],
                                                                   "Short_"+key,
                                                                   n_max_proyeccion)

                    # Estadisticas tramo medio de la curva, entre 720 dias  y 3600 dias
                    alerts_key_m,  sim_pct_quant_m = statistic_alert(sim.loc[:,721:3600],
                                                                   hist.loc[:,721:3600],
                                                                   "Medium_"+key,
                                                                   n_max_proyeccion)

                    # Estadisticas tramo largo de la curva, mayor a 3600 dias
                    alerts_key_l,  sim_pct_quant_l = statistic_alert(sim.loc[:,3601:],
                                                                   hist.loc[:,3601:],
                                                                   "Long_"+key,
                                                                   n_max_proyeccion)

                    sim_describe = pd.concat([sim_describe,
                                              sim_pct_quant_s,
                                              sim_pct_quant_m,
                                              sim_pct_quant_l],axis=1)

                    alerts = pd.concat([alerts,
                                        alerts_key_s,
                                        alerts_key_m,
                                        alerts_key_l],axis=0)

                else:
                    sim = riskfactorDictionary[key].sim_MC[n_max_proyeccion-1].T
                    hist = riskfactorDictionary[key].curve[:fecha_valoracion].dropna()
                    # Si hist tiene múltiples columnas (DataFrame de grupo), usar solo la primera
                    if isinstance(hist, pd.DataFrame) and hist.shape[1] > 1:
                        hist = hist.iloc[:, 0]
                    alerts_key, sim_pct_quant = statistic_alert(sim,hist,key,n_max_proyeccion)
                    sim_describe = pd.concat([sim_describe,sim_pct_quant],axis=1)
                    alerts = pd.concat([alerts,alerts_key],axis=0)

            sim_describe.T.to_excel(writer_excel, sheet_name="Describe")
            alerts.to_excel(writer_excel, sheet_name="Alertas")
            
            # Agregar hoja con matriz de pesos aplicados
            try:
                if 'pesos_manager' in locals():
                    df_pesos = pesos_manager.generar_reporte_pesos(list(riskfactorDictionary.keys()))
                    df_pesos.to_excel(writer_excel, sheet_name="Pesos_Aplicados", index=False)
                    logging.info('Reporte de pesos agregado a estadísticas.')
            except Exception as e:
                logging.warning(f'No se pudo agregar reporte de pesos: {e}')
            
            writer_excel.close()
            logging.info(f' Fin de guardado de estadisticas.')
        except Exception as _e_stats:
            import traceback
            logging.error(f'Fallo el guardado de las estadisticas: {_e_stats}')
            logging.error(traceback.format_exc())
            return False

        #%% Guardar Matriz de Correlacion

        try:
            logging.info(f' Inicio de guardado de matriz de correlacion.')
            pos_to_name = {}
            for key in rfd_corr_named.keys():
                m = rfd_corr_named[key].metsim
                pcs = rfd_corr_named[key].posCorrM
                if m in ('LMM', 'HJM'):
                    for n, p in enumerate(pcs):
                        pos_to_name[p] = f'{key}_PC{n+1}'
                else:
                    p0 = pcs[0]
                    pos_to_name[p0] = key
            list_names = [pos_to_name.get(i, f'Factor_{i}') for i in range(len(corrPCs))]
            correlation_matrix = pd.DataFrame(corrPCs, index=list_names, columns=list_names)
            correlation_matrix.to_excel(os.path.join(path_excel,"CorrelationMatrix.xlsx"))

            logging.info(f' Fin de guardado de matriz de correlacion.')
        except Exception as _e_corr:
            import traceback
            logging.error(f'Fallo el guardado de la matriz de correlaciones: {_e_corr}')
            logging.error(traceback.format_exc())
            return False
        #%% Guardar riskfactorDictionary

        try:
            logging.info('Guardando riskfactorDictionary.')
            path_rkf = os.path.join(path_excel,"riskfactorDictionary.pkl")
            with open(path_rkf,'wb') as dict_pickle:
                pickle.dump(riskfactorDictionary, dict_pickle)

        except:
            logging.error('Fallo el guardado riskfactorDictionary.')
            return False

        time_end = time.time()
        minutos = (time_end-time_start)//60
        segundos = (time_end-time_start)-minutos*60

        logging.info("Se ejecuto correctamente todo el proceso!")
        logging.info(f"El tiempo de ejecucion fue {minutos} min, {segundos} seg.")

        return True


    except Exception as e:
        # Manejar cualquier excepcion que ocurra durante la ejecucion
        logging.info(f"Ocurrio una excepcion: {e}.")
    finally:
        # Cerrar el archivo de log
        logging.info("Fin de la ejecucion del programa SimulationProspectivo.")

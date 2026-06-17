#%% Librerias

import utils.Read as rd
import utils.RiskFactors as rkf
import rfk_prospectivo.RiskModels as rkm
import pandas as pd
import datetime as dt
import numpy as np
from numpy.random import SeedSequence, default_rng
import os
import pickle
import sys
import random
import time
import logging


#%% Funciones Auxiliares para Correlación Mejorada
def fix_correlation_matrix(rho, method='eigenvalue'):
    """
    Ajusta matriz de correlación para ser definida positiva.
    
    Parameters
    ----------
    rho : ndarray
        Matriz de correlación potencialmente mal condicionada
    method : str
        'eigenvalue': Ajusta valores propios negativos
        'shrinkage': Contrae hacia matriz identidad
    
    Returns
    -------
    rho_fixed : ndarray
        Matriz de correlación definida positiva
    """
    # Verificar y limpiar NaN/Inf
    rho = np.nan_to_num(rho, nan=0.0, posinf=1.0, neginf=-1.0)
    
    # Asegurar simetría
    rho = (rho + rho.T) / 2
    
    # Asegurar diagonal = 1
    np.fill_diagonal(rho, 1.0)
    
    if method == 'eigenvalue':
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(rho)
            # Reemplazar valores propios negativos con pequeño valor positivo
            eigenvalues[eigenvalues < 1e-10] = 1e-10
            rho_fixed = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
            # Hacer una copia para poder modificarla
            rho_fixed = rho_fixed.copy()
            # Normalizar diagonal a 1
            d_diag = np.diag(rho_fixed)
            # Evitar división por cero
            d_diag[d_diag < 1e-10] = 1.0
            d = np.sqrt(d_diag)
            d_inv = 1.0 / d
            rho_fixed = np.outer(d_inv, d_inv) * rho_fixed
            # Asegurar diagonal = 1
            np.fill_diagonal(rho_fixed, 1.0)
            return rho_fixed
        except Exception as e:
            logging.warning(f"Fallo ajuste eigenvalue: {str(e)[:50]}. Usando shrinkage.")
            return fix_correlation_matrix(rho, method='shrinkage')
    
    elif method == 'shrinkage':
        # Shrinkage hacia matriz identidad
        shrinkage_intensity = 0.1
        rho_fixed = (1 - shrinkage_intensity) * rho + shrinkage_intensity * np.eye(rho.shape[0])
        return rho_fixed


def correlation_with_decay(compMatrix, half_life=30):
    """
    Calcula matriz de correlación con ponderación exponencial decreciente.
    
    Observaciones más recientes tienen mayor peso, simulando que las 
    correlaciones recientes son más relevantes para proyecciones futuras.
    
    Parameters
    ----------
    compMatrix : ndarray
        Componentes históricos (T × N) donde T = tiempo, N = factores
    half_life : int
        Días para que el peso se reduzca a la mitad (default=30)
    
    Returns
    -------
    correlation : ndarray
        Matriz de correlación ponderada (N × N)
    
    Notes
    -----
    Fórmula: weight_t = exp(-lambda * (T-1-t))
    donde lambda = ln(2) / half_life
    
    Para AUMENTAR ESTRÉS:
    - Reducir half_life (ej: 15-20) da más peso a períodos recientes estresados
    - Usar n_max_correlacion más corto para capturar solo crisis recientes
    """
    T = compMatrix.shape[0]
    lambda_decay = np.log(2) / half_life
    
    # Cambios porcentuales normalizados (esto reduce dimensión a T-1)
    returns = np.diff(compMatrix, axis=0) / compMatrix[:-1]
    returns = np.nan_to_num(returns)  # Reemplazar NaN por 0
    
    # Pesos exponenciales decrecientes para T-1 observaciones
    # Se invierten índices para que los datos recientes tengan mayor peso
    T_returns = returns.shape[0]  # T-1
    weights = np.exp(-lambda_decay * np.arange(T_returns-1, -1, -1))
    weights = weights / weights.sum()
    
    logging.info(f"Ponderación exponencial: peso máximo={weights[0]:.4f}, "
                f"peso mínimo={weights[-1]:.4f}, half_life={half_life} días")
    
    # Covarianza ponderada
    weighted_cov = np.cov(returns.T, aweights=weights)
    
    # Convertir a matriz de correlación
    d = np.sqrt(np.diag(weighted_cov))
    
    # Manejar varianzas cero (factores constantes)
    # Reemplazar desviaciones estándar cero con un valor pequeño para evitar división por cero
    zero_variance = d < 1e-10
    if np.any(zero_variance):
        n_zero = np.sum(zero_variance)
        logging.warning(f"{n_zero} factores tienen varianza cero o muy baja, se ajustará la correlación.")
        d[zero_variance] = 1.0  # Establecer a 1 para evitar división por cero
    
    # Calcular matriz de correlación
    correlation = weighted_cov / np.outer(d, d)
    
    # Corregir correlaciones donde había varianza cero (establecer a 0 excepto diagonal)
    for i in range(len(zero_variance)):
        if zero_variance[i]:
            correlation[i, :] = 0.0
            correlation[:, i] = 0.0
            correlation[i, i] = 1.0
    
    # Reemplazar NaN/Inf por valores válidos
    correlation = np.nan_to_num(correlation, nan=0.0, posinf=1.0, neginf=-1.0)
    
    # Asegurar que la diagonal sea 1
    np.fill_diagonal(correlation, 1.0)
    
    # Redondear para evitar errores numéricos
    correlation = np.round(correlation, 8)
    
    return correlation


def generate_correlated_random_vectors(correlation_matrix, nSim, n_max_proyeccion,
                                       seedseq, n_assets):
    """
    Genera vectores aleatorios correlacionados usando descomposición de Cholesky.
    
    Parameters
    ----------
    correlation_matrix : ndarray
        Matriz de correlación (N × N)
    nSim : int
        Número de simulaciones
    n_max_proyeccion : int
        Horizonte de proyección en días
    seedseq : SeedSequence
        Semilla para reproducibilidad
    n_assets : int
        Número de activos/factores
    
    Returns
    -------
    corrZ : ndarray
        Vectores correlacionados (n_assets × n_max_proyeccion × nSim)
    correlation_matrix : ndarray
        Matriz de correlación utilizada (para registro)
    """
    # Validar que sea definida positiva
    eigenvalues = np.linalg.eigvals(correlation_matrix)
    if np.any(eigenvalues < -1e-10):
        logging.warning(f"Matriz no es definida positiva. Min eigenvalue: {eigenvalues.min():.2e}")
        correlation_matrix = fix_correlation_matrix(correlation_matrix)
        logging.info("Matriz de correlación ajustada")
    
    # Descomposición de Cholesky
    try:
        L = np.linalg.cholesky(correlation_matrix)
        logging.info("Descomposición Cholesky exitosa")
    except np.linalg.LinAlgError:
        logging.warning("Cholesky falló, usando SVD como alternativa")
        U, s, _ = np.linalg.svd(correlation_matrix)
        L = U @ np.diag(np.sqrt(s))
    
    # Generar números aleatorios independientes
    child_seeds = seedseq.spawn(n_assets)
    streams = [default_rng(s) for s in child_seeds]
    Z = np.array([s.normal(0, 1, (n_max_proyeccion, nSim)) for s in streams])
    
    # Aplicar transformación Cholesky para introducir correlación
    corrZ = np.empty(Z.shape)
    for i in range(nSim):
        corrZ[:, :, i] = L @ Z[:, :, i]
    
    return corrZ, correlation_matrix


def apply_stress_to_correlation(corr_matrix, stress_factor=0.0):
    """
    Aplica factor de estrés a matriz de correlación.
    
    Aumenta las correlaciones (en valor absoluto) hacia 1 o -1, 
    haciendo que los factores se muevan más juntos en escenarios extremos.
    
    Parameters
    ----------
    corr_matrix : ndarray
        Matriz de correlación base (N × N)
    stress_factor : float
        Factor de estrés entre 0 y 1:
        - 0.0 = sin estrés (correlación original)
        - 0.2 = estrés moderado (aumenta 20% hacia ±1)
        - 0.5 = estrés alto (aumenta 50% hacia ±1)
        - 1.0 = estrés extremo (todas correlaciones = ±1)
    
    Returns
    -------
    stressed_corr : ndarray
        Matriz de correlación estresada
    
    Examples
    --------
    >>> corr = np.array([[1.0, 0.5], [0.5, 1.0]])
    >>> apply_stress_to_correlation(corr, 0.2)
    array([[1.0, 0.6], [0.6, 1.0]])  # 0.5 + 0.2*(1-0.5) = 0.6
    
    Notes
    -----
    - Preserva el signo de las correlaciones
    - Mantiene diagonal = 1
    - Útil para escenarios de crisis donde las correlaciones aumentan
    """
    if stress_factor <= 0:
        return corr_matrix
    
    if stress_factor > 1:
        stress_factor = 1.0
        logging.warning("stress_factor > 1 ajustado a 1.0")
    
    stressed = corr_matrix.copy()
    n = stressed.shape[0]
    
    # Para cada elemento fuera de la diagonal
    for i in range(n):
        for j in range(i+1, n):
            # Mover hacia ±1 preservando signo
            sign = np.sign(stressed[i, j])
            abs_val = np.abs(stressed[i, j])
            
            # Nueva correlación: avanzar stress_factor del camino hacia 1
            new_abs_val = abs_val + stress_factor * (1.0 - abs_val)
            
            stressed[i, j] = sign * new_abs_val
            stressed[j, i] = sign * new_abs_val
    
    logging.info(f"Estrés aplicado: factor={stress_factor:.2f}, "
                f"corr_promedio_original={np.mean(np.abs(corr_matrix - np.eye(n))):.4f}, "
                f"corr_promedio_estresada={np.mean(np.abs(stressed - np.eye(n))):.4f}")
    
    return stressed


#%% Funcion Principal de Alerta Estadistica

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
        # sim es 1D
        hist_last_value = hist.tail(1).values if isinstance(hist.tail(1).values, (int, float, np.number)) else hist.tail(1).values[0]
        sim_pct = pd.Series(sim/hist_last_value-1, name=key)

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


#%% Función Principal de Simulación

def simulationRfkProspectivo(
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
        half_life_correlation : int
            Vida media (en días) para ponderación exponencial de correlaciones.
            Por defecto 30 días.
        stress_factor_correlation : float
            Factor de estrés para amplificar correlaciones (0.0 a 1.0).
            0.0 = sin estrés, 0.2 = estrés moderado, 0.3 = estrés moderado-alto (default), 0.5 = estrés alto.
            Mueve correlaciones hacia ±1.0 para escenarios más conservadores.

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
        logging.info("Inicio de ejecucion del programa SimulationProspectivo (v2 - Correlación Mejorada con Estrés 30%) para la fecha de corte: {0}.".format(fecha_valoracion))

        #%% Parametros

        time_start = time.time()
        nCPs =  kwargs.get('nCPs',3)
        nSim =  kwargs.get('nSim',1500)
        seed =  kwargs.get('seed',None)
        n_max_proyeccion = kwargs.get('n_max_proyeccion', kwargs.get('n_max_proyeccions',20))
        n_max_historia = kwargs.get('n_max_historia',250)
        n_max_correlacion = kwargs.get('n_max_correlacion',250)
        fecha_correlacion = kwargs.get('fecha_correlacion',fecha_valoracion)
        half_life_correlation = kwargs.get('half_life_correlation', 30)
        stress_factor_correlation = kwargs.get('stress_factor_correlation', 0.3)  # Default 0.3 = 30% estrés

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
            riskfactorDictionary, failed_factors = rkf.RiskFactors.create_factorInfo_dictionary(
                fecha_valoracion,
                wfactors,
                file_Parameterization,
                path_parquet,
                path_repo)
            
            if len(failed_factors) > 0:
                warning_msg = f'No se pudieron cargar los siguientes factores: {failed_factors}'
                logging.warning(warning_msg)
                print(f'[WARNING] {warning_msg}')
            
            if len(riskfactorDictionary) == 0:
                logging.error('No se cargaron factores de riesgo disponibles.')
                return False
        except Exception as e:
            logging.error(f'Fallo la carga de informacion. Error: {str(e)[:100]}')
            return False

        try:
            logging.info('Se filtra la informacion historica para la calibracion.')
            riskfactorDictionary = rkf.RiskFactors.curve_trainig_filter(
                riskfactorDictionary, fecha_valoracion, n_max_historia, True)
        except Exception as e:
            logging.error(f'Fallo el proceso de filtracion para la calibracion. Error: {str(e)}')
            import traceback
            logging.error(f'Traceback: {traceback.format_exc()}')
            return False

        try:
            logging.info('Se filtra la informacion historica para la correlacion.')
            riskfactorDictionary_corr = riskfactorDictionary.copy()
            riskfactorDictionary_corr = rkf.RiskFactors.curve_trainig_filter(
                riskfactorDictionary_corr, fecha_correlacion, n_max_correlacion,
                False)
        except Exception as e:
            logging.error(f'Fallo el proceso de filtracion para la correlacion. Error: {str(e)}')
            import traceback
            logging.error(f'Traceback: {traceback.format_exc()}')
            return False

        try:
            logging.info('Descomposicion PCA para la calibracion.')
            _, riskfactorDictionary = rkf.RiskFactors.filter_pca_components(
                riskfactorDictionary,nCPs,True)
        except Exception as e:
            logging.error(f'Fallo la descomposicion PCA para la calibracion. Error: {str(e)}')
            import traceback
            logging.error(f'Traceback: {traceback.format_exc()}')
            return False

        try:
            logging.info('Descomposicion PCA para la correlacion.')
            compMatrix, _ = rkf.RiskFactors.filter_pca_components(
                riskfactorDictionary_corr,nCPs,False)
        except Exception as e:
            logging.error(f'Fallo la descomposicion PCA para la correlacion. Error: {str(e)}')
            import traceback
            logging.error(f'Traceback: {traceback.format_exc()}')
            return False

        #%% Creacion de matriz de correlacion con ponderacion exponencial

        try:
            logging.info(f'Creacion de matriz de correlacion con ponderacion exponencial (half_life={half_life_correlation} dias).')
            
            # Calcular correlación con ponderación exponencial
            corrPCs = correlation_with_decay(compMatrix, half_life=half_life_correlation)
            
            # Aplicar factor de estrés si se especifica
            if stress_factor_correlation > 0:
                logging.info(f'Aplicando factor de estres a correlaciones: {stress_factor_correlation:.2f}')
                corrPCs = apply_stress_to_correlation(corrPCs, stress_factor=stress_factor_correlation)
            
            # Validar y ajustar si es necesario
            corrPCs = fix_correlation_matrix(corrPCs, method='eigenvalue')
            
            # Generar vectores aleatorios correlacionados
            corrZ, corrPCs = generate_correlated_random_vectors(
                corrPCs, nSim, n_max_proyeccion, seedseq, compMatrix.shape[1])
            
            # Asignar vectores correlacionados a cada factor
            for key in riskfactorDictionary.keys():
                pos = riskfactorDictionary[key].posCorrM
                riskfactorDictionary[key].randoncorr_Vector = corrZ[pos, :, :]
            
            logging.info('Matriz de correlacion generada exitosamente.')
            
        except Exception as e:
            logging.error(f'Fallo la creacion de matriz de correlacion: {str(e)[:100]}')
            return False

        #%% Simulacion de los factores de riesgo.

        for key in riskfactorDictionary.keys():

            logging.info(f'Inicio simulacion del factor {key}.')

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
                        nSim)
                elif riskfactorDictionary[key].metsim == 'GBM':
                    riskfactorDictionary[key].sim_MC = rkm.gbm(
                        riskfactorDictionary,key,fecha_valoracion,n_max_proyeccion,
                        nSim)
                elif riskfactorDictionary[key].metsim == 'CIR':
                    riskfactorDictionary[key].sim_MC = rkm.CIR(
                        riskfactorDictionary,key,fecha_valoracion,n_max_proyeccion,
                        nSim,dt=1/252)
                else:
                    riskfactorDictionary[key].PComponent = \
                          riskfactorDictionary[key].curve_training.values

                logging.info(f'El factor {key} se simulo correctamente.')
            except Exception as e:
                logging.error(f'----- El factor {key} no se pudo simular correctamente. Error: {str(e)[:100]}')
                return False

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
                    try:
                        sim_data = riskfactorDictionary[serie].sim_MC
                        
                        # Asegurarse de que sim_data es un numpy array
                        if not isinstance(sim_data, np.ndarray):
                            # Si no es array, convertirlo
                            sim_data = np.array(sim_data)
                        
                        # Verificar si es 3D (curva forward) o 2D (spot)
                        if len(sim_data.shape) == 3:
                            # Shape: (n_max_proyeccion, num_nodes, nSim)
                            # Guardar como múltiples columnas (una por nodo)
                            sim_at_horizon = sim_data[n_max_proyeccion-1, :, :]  # (num_nodes, nSim)
                            
                            # Obtener nombres de nodos si existen
                            if hasattr(riskfactorDictionary[serie], 'node_training') and riskfactorDictionary[serie].node_training is not None:
                                nodos = riskfactorDictionary[serie].node_training
                                # Convertir a array si es necesario
                                if isinstance(nodos, pd.Series):
                                    nodos = nodos.values
                                elif isinstance(nodos, pd.DataFrame):
                                    nodos = nodos.iloc[:, 0].values
                                elif isinstance(nodos, (list, tuple)):
                                    nodos = np.array(nodos)
                                elif isinstance(nodos, np.ndarray):
                                    pass  # Ya es array
                                else:
                                    # Escalar o tipo desconocido - usar índices
                                    logging.warning(f"node_training de {serie} es tipo {type(nodos)}, usando índices")
                                    nodos = np.arange(sim_at_horizon.shape[0])
                                names_columns = [f'{serie}_{int(i)}' for i in nodos]
                            else:
                                names_columns = [f'{serie}_N{i+1}' for i in range(sim_at_horizon.shape[0])]
                            
                            # Transponer para que cada fila sea una simulación y cada columna un nodo
                            df_sim = pd.DataFrame(sim_at_horizon.T, columns=names_columns)
                            for col in df_sim.columns:
                                datos[col] = df_sim[col].values
                        else:
                            # Shape: (n_max_proyeccion, nSim) - factor spot normal
                            datos[serie] = sim_data[n_max_proyeccion-1,:]
                    except Exception as e:
                        logging.error(f"Error guardando serie {serie}: {str(e)[:100]}")
                        raise

                if datos:
                    df_serie = pd.DataFrame(datos)
                    df_serie.to_excel(os.path.join(path_excel,type_serie[:-1]+'S.xlsx'))

            # Para cada curva sin importar su tipo se crea un archivo excel.
            for type_curva in ['CurvasDPEH','CurvasDPRH','CurvasINTH',
                               'CurvasLOCH','CurvasIMPH']:
                datos = dict()
                for curva in dict_par.get(type_curva,[]):
                    try:
                        nodos_curva = riskfactorDictionary[curva].node_training
                        # Asegurar que nodos_curva sea iterable
                        if isinstance(nodos_curva, pd.Series):
                            nodos_curva = nodos_curva.values
                        elif isinstance(nodos_curva, pd.DataFrame):
                            nodos_curva = nodos_curva.iloc[:, 0].values
                        elif isinstance(nodos_curva, (list, tuple)):
                            nodos_curva = np.array(nodos_curva)
                        elif isinstance(nodos_curva, np.ndarray):
                            pass  # Ya es array
                        else:
                            logging.warning(f"node_training de {curva} es tipo {type(nodos_curva)}, convirtiendo")
                            nodos_curva = np.array([nodos_curva]) if not hasattr(nodos_curva, '__iter__') else np.array(nodos_curva)
                        
                        names_columns = [f'{curva}_{int(i)}' for i in nodos_curva]
                        datos[curva] = pd.DataFrame(
                            riskfactorDictionary[curva].sim_MC[n_max_proyeccion-1,:].T,
                            columns = names_columns)
                    except Exception as e:
                        logging.error(f"Error guardando curva {curva}: {str(e)[:100]}")
                        raise
                for curva in datos:
                    datos[curva].to_excel(os.path.join(path_excel,f'{curva}.xlsx'))

            logging.info(f' Fin de guardado de simulaciones.')
        except Exception as e:
            logging.error(f'Fallo el guardado de las simulaciones: {str(e)[:100]}')
            return False

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
                    sim = riskfactorDictionary[key].sim_MC[n_max_proyeccion-1]
                    hist = riskfactorDictionary[key].curve[:fecha_valoracion].dropna()
                    
                    # Verificar si es una curva (múltiples columnas)
                    if len(sim.shape) == 3:
                        # sim tiene shape (1, num_nodes, nSim) para curvas GBM/CIR
                        # Tratar como curva similar a LMM/HJM
                        num_nodes = sim.shape[1]
                        
                        # Aplanar a (num_nodes, nSim) para el horizonte específico
                        sim = sim[0, :, :]  # o sim.squeeze(0) si es necesario
                        
                        # Estadísticas por tramos de curva
                        # Convertir sim a DataFrame con nodos como índice
                        if hasattr(riskfactorDictionary[key], 'node_training') and riskfactorDictionary[key].node_training is not None:
                            node_training = riskfactorDictionary[key].node_training
                            # Manejar diferentes tipos de manera segura
                            if isinstance(node_training, pd.Series):
                                nodos = node_training.values
                            elif isinstance(node_training, pd.DataFrame):
                                nodos = node_training.iloc[:, 0].values
                            elif isinstance(node_training, (list, tuple, np.ndarray)):
                                nodos = node_training
                            else:
                                # Tipo inesperado, usar índices
                                nodos = range(num_nodes)
                            sim_df = pd.DataFrame(sim.T, columns=nodos)
                        else:
                            sim_df = pd.DataFrame(sim.T, columns=range(num_nodes))
                        
                        # Obtener columnas de hist que coincidan
                        if isinstance(hist, pd.DataFrame):
                            hist_df = hist
                        else:
                            hist_df = pd.DataFrame(hist)
                        
                        # Estadísticas tramo corto de la curva, menor a 720 días
                        cols_short = [col for col in sim_df.columns if (isinstance(col, (int, float)) and col <= 720) or 
                                      (isinstance(col, str) and col.isdigit() and int(col) <= 720)]
                        if cols_short:
                            alerts_key_s, sim_pct_quant_s = statistic_alert(
                                sim_df[cols_short].T.values,
                                hist_df[cols_short] if cols_short else hist_df.iloc[:, :min(5, len(hist_df.columns))],
                                "Short_"+key,
                                n_max_proyeccion)
                            sim_describe = pd.concat([sim_describe, sim_pct_quant_s], axis=1)
                            alerts = pd.concat([alerts, alerts_key_s], axis=0)
                        
                        # Estadísticas tramo medio de la curva, entre 720 días y 3600 días
                        cols_medium = [col for col in sim_df.columns if (isinstance(col, (int, float)) and 720 < col <= 3600) or
                                       (isinstance(col, str) and col.isdigit() and 720 < int(col) <= 3600)]
                        if cols_medium:
                            alerts_key_m, sim_pct_quant_m = statistic_alert(
                                sim_df[cols_medium].T.values,
                                hist_df[cols_medium] if cols_medium else hist_df.iloc[:, min(5, len(hist_df.columns)):min(15, len(hist_df.columns))],
                                "Medium_"+key,
                                n_max_proyeccion)
                            sim_describe = pd.concat([sim_describe, sim_pct_quant_m], axis=1)
                            alerts = pd.concat([alerts, alerts_key_m], axis=0)
                        
                        # Estadísticas tramo largo de la curva, mayor a 3600 días
                        cols_long = [col for col in sim_df.columns if (isinstance(col, (int, float)) and col > 3600) or
                                     (isinstance(col, str) and col.isdigit() and int(col) > 3600)]
                        if cols_long:
                            alerts_key_l, sim_pct_quant_l = statistic_alert(
                                sim_df[cols_long].T.values,
                                hist_df[cols_long] if cols_long else hist_df.iloc[:, min(15, len(hist_df.columns)):],
                                "Long_"+key,
                                n_max_proyeccion)
                            sim_describe = pd.concat([sim_describe, sim_pct_quant_l], axis=1)
                            alerts = pd.concat([alerts, alerts_key_l], axis=0)
                    
                    elif len(sim.shape) == 2:
                        # sim tiene shape (num_nodes, nSim) o (nSim, algo_más)
                        # Verificar si realmente es una curva usando node_training (NO NaN, NO float escalar)
                        node_training = riskfactorDictionary[key].node_training
                        is_curve = isinstance(node_training, (pd.Series, pd.DataFrame, list, tuple, np.ndarray)) and \
                                   not (isinstance(node_training, float) and np.isnan(node_training))
                        
                        if is_curve and sim.shape[0] > 1 and sim.shape[0] < sim.shape[1]:
                            # Es una curva con (num_nodes, nSim)
                            logging.info(f"Factor {key} tiene sim 2D con shape {sim.shape}. Es curva con {sim.shape[0]} nodos.")
                            # Similar al caso 3D pero sin necesidad de indexar la primera dimensión
                            alerts_key, sim_pct_quant = statistic_alert(sim, hist, key, n_max_proyeccion)
                            sim_describe = pd.concat([sim_describe, sim_pct_quant], axis=1)
                            alerts = pd.concat([alerts, alerts_key], axis=0)
                        else:
                            # NO es curva - es factor spot con formato extraño o (nSim, 1)
                            # Aplanar y tratar como 1D
                            sim = sim.flatten()
                            if isinstance(hist, pd.DataFrame) and hist.shape[1] > 1:
                                logging.warning(f"Factor {key} tiene hist con múltiples columnas ({hist.shape[1]}). Usando la primera.")
                                hist = hist.iloc[:, 0]
                            
                            alerts_key, sim_pct_quant = statistic_alert(sim, hist, key, n_max_proyeccion)
                            sim_describe = pd.concat([sim_describe, sim_pct_quant], axis=1)
                            alerts = pd.concat([alerts, alerts_key], axis=0)
                    
                    else:
                        # sim es 1D - factor spot normal
                        if len(sim.shape) > 1:
                            if sim.shape[0] == 1:
                                sim = sim.flatten()
                            elif sim.shape[1] == 1:
                                sim = sim.flatten()
                        
                        if isinstance(hist, pd.DataFrame):
                            if hist.shape[1] == 1:
                                hist = hist.iloc[:, 0]
                            else:
                                logging.warning(f"Factor {key} tiene hist con múltiples columnas ({hist.shape[1]}). Usando la primera.")
                                hist = hist.iloc[:, 0]
                        
                        alerts_key, sim_pct_quant = statistic_alert(sim, hist, key, n_max_proyeccion)
                        sim_describe = pd.concat([sim_describe, sim_pct_quant], axis=1)
                        alerts = pd.concat([alerts, alerts_key], axis=0)

            sim_describe.T.to_excel(writer_excel, sheet_name="Describe")
            alerts.to_excel(writer_excel, sheet_name="Alertas")
            writer_excel.close()
            logging.info(f' Fin de guardado de estadisticas.')
        except Exception as e:
            logging.error(f'Fallo el guardado de las estadisticas: {str(e)[:100]}')
            return False

        #%% Guardar Matriz de Correlacion

        try:
            logging.info(f' Inicio de guardado de matriz de correlacion.')
            # Construir list_names como un diccionario primero para manejar posiciones correctamente
            list_names_dict = {}
            for key in riskfactorDictionary.keys():
                if (riskfactorDictionary[key].metsim == 'LMM' or
                    riskfactorDictionary[key].metsim == 'HJM'):

                    size = len(riskfactorDictionary[key].posCorrM)
                    for n in range(size):
                        pos_corrM = riskfactorDictionary[key].posCorrM[n]
                        list_names_dict[pos_corrM] = f'{key}_PC{n+1}'
                else:
                    # Para GBM/CIR con múltiples columnas (curvas forward)
                    posCorrM_list = riskfactorDictionary[key].posCorrM
                    if len(posCorrM_list) == 1:
                        # Factor de un solo valor (ej: spot equity)
                        list_names_dict[posCorrM_list[0]] = key
                    else:
                        # Factor con múltiples columnas (ej: curvas forward de monedas)
                        for n, pos_corrM in enumerate(posCorrM_list):
                            # Usar node_training si existe, sino índice
                            if hasattr(riskfactorDictionary[key], 'node_training') and riskfactorDictionary[key].node_training is not None:
                                node_training = riskfactorDictionary[key].node_training
                                # Manejar diferentes tipos de node_training de manera segura
                                if isinstance(node_training, pd.Series):
                                    node_name = node_training.iloc[n] if n < len(node_training) else n
                                elif isinstance(node_training, pd.DataFrame):
                                    node_name = node_training.iloc[n, 0] if n < len(node_training) else n
                                elif isinstance(node_training, (list, tuple, np.ndarray)):
                                    node_name = node_training[n] if n < len(node_training) else n
                                else:
                                    # Tipo inesperado (escalar, etc.)
                                    node_name = n
                                list_names_dict[pos_corrM] = f'{key}_{int(node_name) if isinstance(node_name, (int, float, np.number)) else node_name}'
                            else:
                                list_names_dict[pos_corrM] = f'{key}_N{n+1}'
            
            # Convertir diccionario a lista ordenada por posiciones
            max_pos = max(list_names_dict.keys())
            list_names = [list_names_dict.get(i, f'Unknown_{i}') for i in range(max_pos + 1)]
            
            correlation_matrix = pd.DataFrame(corrPCs,index = list_names,columns = list_names)
            correlation_matrix.to_excel(os.path.join(path_excel,"CorrelationMatrix.xlsx"))

            logging.info(f' Fin de guardado de matriz de correlacion.')
        except Exception as e:
            logging.error(f'Fallo el guardado de la matriz de correlaciones: {str(e)[:100]}')
            return False
            
        #%% Guardar riskfactorDictionary

        try:
            logging.info('Guardando riskfactorDictionary.')
            path_rkf = os.path.join(path_excel,"riskfactorDictionary.pkl")
            with open(path_rkf,'wb') as dict_pickle:
                pickle.dump(riskfactorDictionary, dict_pickle)

        except Exception as e:
            logging.error(f'Fallo el guardado riskfactorDictionary: {str(e)[:100]}')
            return False

        time_end = time.time()
        minutos = (time_end-time_start)//60
        segundos = (time_end-time_start)-minutos*60

        logging.info("Se ejecuto correctamente todo el proceso!")
        logging.info(f"El tiempo de ejecucion fue {minutos} min, {segundos} seg.")

        return True


    except Exception as e:
        # Manejar cualquier excepcion que ocurra durante la ejecucion
        logging.error(f"Ocurrio una excepcion: {e}.")
        return False
    finally:
        # Cerrar el archivo de log
        logging.info("Fin de la ejecucion del programa SimulationProspectivo.")

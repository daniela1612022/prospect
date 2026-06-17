# -*- coding: utf-8 -*-

#%% Librerias

import pandas as pd
import numpy as np
import datetime as dt
import logging
pd.options.mode.chained_assignment = None  # default='warn'
import sys
sys.path.append("E:\\Repositorio_Proyectos\\DyV\\Codigos")
import utils.Read as rd
from ismember import ismember
from utils.DayCount import daysdif,yearfrac
from numpy.random import SeedSequence, default_rng
import arch
import scipy.optimize
from scipy.optimize import fsolve
from datetime import timedelta, datetime
import utils.RiskFactors as rkf

import os
os.environ["KMP_DUPLICATE_LIB_OK"]="True"

#%% Clase RiskFactors


def lmmm(time360,times_,nSim,lambdajq_,Fwdref,timeY,nCPs,MatLjq,date_valuation,randoncorr_Vector):
    """
    Crea un modelo de Libor market model (LMM)-calibrado con volatidad historico
    Parameters
    ----------
    time360 : numpy.ndarray
        Vector con nodos de la curva que se va a modelar en anos.
    times_ : numpy.ndarray
        Vector con los horizontes (en dias) que se quieren proyectar.
    nSim : int
        Numero de simuaciones que se quieren realizar.
    lambdajq_ : numpy.ndarray
        Volatilidades de los nodos de la curva forward.
    Fwdref : numpy.ndarray
        Curva forward de referencia.
    timeY : TYPE
        DESCRIPTION.
    nCPs : int
        Numero de componentes principales con los cuales se calibrara el modelo.
    MatLjq : TYPE
        DESCRIPTION.
    date_valuation : datetime
        Fecha de corte para simular las curvas.
    randoncorr_Vector : np.ndarry
        Matriz de numeros aleatorios  que surge de la correlacion de los facotres de riesgo que se decea simular.

    Returns
    -------
    zero : np.ndarry
        Matriz de curvas ceros simuladas a los horizontes times_ con nsim simulaciones.

    """

    len_Fwdref = len(Fwdref)
    Fwdref = Fwdref.reshape(1,len(Fwdref))
    Fi = np.repeat(Fwdref,(len(timeY)+1)*nSim,axis =0)

    Fi  = Fi.reshape(len(timeY)+1,len_Fwdref,nSim)
    Fi  = (Fi-Fi).copy()
    IoIIi = (Fi-Fi).copy()          #I/II. Producto de Deltaj, Fj y volatilidades
    IIIi  = (Fi-Fi).copy()         # III. Varianza/2
    IVi   = (Fi-Fi).copy()         # IV. Producto de volatilidad y Browniano
    zero  = (Fi-Fi).copy()          # Curvas zero a partir de las curvas forward implicitas
    Fi    =  (Fi-Fi).copy()           # Factores de descuento con curvas zero
    Fi[0,:,:] = np.repeat(Fwdref.T,nSim,axis =1)
        #
        # Fi.shape
    #pd.DataFrame(np.repeat(Fwdref.T,nSim,axis =1))  s1[0:0+3,:] s1[tk*3:(tk+1)*3,:]
    ii =4
    for  tk  in range(len(timeY)):
        s = randoncorr_Vector[:,tk,:]  #s1[tk*3:(tk+1)*3,:]
        horizontek =  timeY[tk]
        for fi in range(len_Fwdref):

            nodoi = time360[fi]
            if  horizontek < nodoi:
                poskeni = np.unravel_index(np.argmin(abs(time360-horizontek), axis=None), abs(time360-horizontek).shape)[0]
                periodos = time360[poskeni:fi+1]                           # Nodos: desde el mas cercano a k hasta el nodo i en consideracion
                forwards = Fi[tk,poskeni:fi+1,0]                              # Tasas forward de periodos (simulación de referencia)
                fila = range(poskeni,fi+1)
                mt = poskeni                                             # m(t) es la posicion de k en los nodos de la curva i
                ii = len(fila)

            elif horizontek > nodoi:
                poskeni = np.unravel_index(np.argmin(abs(horizontek-time360), axis=None),
                                            abs(horizontek-time360).shape)[0]
                periodos = time360[fi:poskeni+1]                           # Nodos: desde el mas cercano a k hasta el nodo i en consideracion
                forwards = Fi[tk,fi:poskeni+1,0]                              # Tasas forward de periodos (simulación de referencia)
                fila = range(fi,poskeni+1)
                mt = fi -1                                            # m(t) es la posicion de k en los nodos de la curva i
                ii = len(fila)



            if  (horizontek != nodoi) & (ii != 1):
                #3.2 Posicion de lambda i-m(t). Volatilidad equivalente a la distancia entre mt e i.

                if ii -1 >= mt:
                    norm_imt = abs(periodos[mt] - periodos[ii-1])             # Distancia entre i y mt. |periodos(ii)-periodos(mt)|
                    jdist = abs(periodos - periodos[mt])             #jdist: periodos - mt
                else:#if ii < mt      :                                        # Este caso corrige la posicion de m(t) cuando mt > ii
                    pos = 0
                    norm_imt = abs(periodos[pos] - periodos[ii-1])
                    jdist = abs(periodos - periodos[pos])

                poslambdaim = np.unravel_index(np.argmin(abs(norm_imt - time360),
                                                            axis=None), abs(norm_imt - time360).shape)[0] #pos del nodo mas cercano a norm_imt (i.e., pos del nodo ii (pos de i))

                #Se trae volatilidad del nodo de la curva mas cercano a norm_imt (distancia entre periodo2 e ii) (i.e., pos del nodo ii (pos de i))
                lambdaim = lambdajq_[poslambdaim,:]

                # 3.3 Posicion de lambdas j-m(t). Volatilidades j-esimas entre mt e i.
                dist = (np.repeat(jdist.reshape(1,len(jdist)),len(time360),
                                axis =0) -np.repeat(time360.reshape(len(time360),1),len(jdist),axis =1)).T

                aa = [np.unravel_index(np.argmin(abs(dist[nin,:]),axis=None),dist[nin,:].shape)[0] for nin in range(0,len(dist))]
                lambdajm = lambdajq_[aa]
                deltaj = periodos[1:]- periodos[:-1]       # deltaj: delta entre nodo i y nodo i-1 de periodos
                sumprodLambdas = np.matmul(lambdajm, lambdaim.reshape(len(lambdaim),1))

                # Calculo de parte I/II
                #No se tiene en cuenta el primer elemento de sumprodLambdas ni de forwards (exp: sumatoria empieza en k+1)
                IoII_ = sum(sum(deltaj*forwards[1:]*sumprodLambdas[1:].T / (1 + deltaj*forwards[1:]) ))
                # 3.5 Calculo de parte III
                III_ = MatLjq[poslambdaim, poslambdaim]/2

            else :
                poslambdaim = 0
                ii = 1

            #Delta k
            deltak = times_[tk+1] - times_[tk]

            #3.7 Calculo de parte IV

            lambdaiq = lambdajq_[poslambdaim,:]  # Volatilidad del nodo j (tasa forward j) de la curva i
            IV_ = np.matmul(lambdaiq.reshape(1,nCPs),s*np.sqrt(deltak) )
                #
                #
                #
            if (horizontek < nodoi) & ( ii != 1  )  :

                Fi[tk+1,fi,:] = Fi[tk,fi,:] * np.exp((IoII_ - III_)*deltak+ IV_)
                IoIIi[tk+1,fi,:] = IoII_
                IIIi[tk+1,fi,:]  = III_
                IVi[tk+1,fi,:]   = IV_

            elif (horizontek > nodoi) & ( ii != 1  )  :

                Fi[tk+1,fi,:] = Fi[tk,fi,:] * np.exp(-(IoII_ - III_)*deltak+ IV_)
                IoIIi[tk+1,fi,:] = IoII_
                IIIi[tk+1,fi,:]  = III_
                IVi[tk+1,fi,:]   = IV_

            elif (horizontek == nodoi) | ( ii == 1  )  :
                Fi[tk+1,fi,:] = Fi[tk,fi,:]* np.exp(IV_)
                IVi[tk+1,fi,:] = IV_

    date_valuation_dt = dt.datetime.strptime(date_valuation, '%Y%m%d')
    curveDates = [date_valuation_dt+ dt.timedelta(days = int(day)) for day in time360*360]

    for n  in range(nSim):
        for tk  in range(len(timeY)):
            zero[tk,:,n] = rkf.RiskFactors.fwd2zero(Fi[tk,:,n],curveDates, date_valuation_dt, compounding = 1, basis =3)
    return  zero


def sigma_rs(returns):
    # Modelo para la varianza
    model  =  arch.arch_model(returns,vol = 'GARCH', p = 1, q = 1)
    res  = model.fit()
    yhat  =  res.forecast(horizon = 1)
    sigma = np.sqrt(yhat.variance.values[-1, 0])
    return sigma

def sigma_ewma(retornos, alpha):
    """
    Calcula la volatilidad EWMA y la proyecta a n días.

    Args:
    retornos (list o pandas.Series): Serie de retornos.
    ventana (int): Número de días para la ventana de cálculo de la EWMA.
    n (int): Número de días para la proyección.

    Returns:
    float: Volatilidad EWMA proyectada a n días.
    """

    # Convierte la lista de retornos en una Serie de pandas
    retornos = pd.Series(retornos)

    # Calcula la volatilidad EWMA con la ventana especificada
    volatilidad_ewma = retornos.ewm(alpha=alpha, adjust=False).std()

    # Proyecta la volatilidad a n días
    volatilidad_proyectada = volatilidad_ewma.iloc[-1]

    return volatilidad_proyectada


def sigma_std(returns):
    sigma = np.std(returns)
    return sigma


def gbm(riskfactorDictionary,key,date_valuation: str,n_max_proyeccion,nSim,**kwargs ) :
    """
    Crea y muestra modelos geometricos de movimiento browniano- Los modelos de movimiento browniano geometrico (GBM)  permiten simular caminos
    de muestra de variables de estado  impulsadas por fuentes de riesgo de movimiento browniano durante periodos de observacion consecutivos

    Parameters
    ----------
    riskfactorDictionary : dict
        Diccionario de factores de riesgo, donde cada elemento es un objeto de
        la clase RiskFactors.
    key : string
        Llave del diccionario riskfactorDictionary que indica la curva a simular.
    date_valuation : datetime.datetime
        Fecha de corte para considerar historico de factores de riesgo.
    n_max_proyeccion : int
        Horizonte (en dias) que se quieren proyectar.
    nSim : int
        Numero de simulaciones que sedeceans realizar por cada dia proyectado. Por defecto se establece como 1500.
    **kwargs :
        dt : int
            incrementos de tiempo positivos entre observaciones.
    Returns
    -------
    s_ : np.ndarry
          Matriz de los diferentes a los horizontes con nsim simulaciones.

    """
    sigma_method = kwargs.get("sigma_method","STD")
    dt   = kwargs.get('dt',1)
    peso_factor = kwargs.get('peso_factor', 1.0)  # Peso de la matriz de pesos

    # Historico del factor de riesgo
    data = riskfactorDictionary[key].curve_training
    
    # Si data es un DataFrame con múltiples columnas (curva completa), usar solo la primera columna
    # GBM está diseñado para factores univariados, no para curvas completas
    if isinstance(data, pd.DataFrame) and data.shape[1] > 1:
        # Usar la primera columna
        data = data.iloc[:, 0]
        logging.warning(f'Factor {key} con GBM tiene {riskfactorDictionary[key].curve_training.shape[1]} columnas. Usando solo la primera columna.')

    #Retornos de la data
    returns = np.log(data.iloc[1:].values)-np.log(data.iloc[:-1].values)

    # Hiperparametros media y sigma
    mu = np.mean(returns)

    if sigma_method == "STD":
        sigma = sigma_std(returns) * 0.90 * peso_factor  # Reducción 10% base + aplicar peso individual
    elif sigma_method == "GARCH":
        sigma = sigma_rs(returns)
    else:
        sigma = sigma_ewma(returns,0.94) # Opcion de escogencia de sigma: sigma_rs(returns)

    # Numero de steps y vector de steps
    N  =  n_max_proyeccion / dt
    t  =  np.arange(1, int(N) + 1)

    # Suma de #horizont distribuciones Normales
    random_vector = riskfactorDictionary[key].randoncorr_Vector[0,:,:]
    if not np.isfinite(random_vector).any():
        logging.warning(f'GBM [{key}]: randoncorr_Vector todo NaN. Usando normales independientes.')
        rng_fb = np.random.default_rng(seed=hash(key) % (2**31))
        random_vector = rng_fb.standard_normal((n_max_proyeccion, nSim))
    W = np.cumsum(random_vector,axis=0)

    drift =  (mu - 0.5 * sigma**2) * t
    #Drift and difussion
    drift = drift.reshape(1,n_max_proyeccion)
    drift = np.repeat(drift.T,nSim,axis =1)

    diffusion  = sigma*W

    #Estado inicial
    s_0  =  data.loc[date_valuation]

    # Simulacion
    s_ = s_0 * np.exp(drift + diffusion)

    return  s_


def single_iter(rt, a, b, delta, sigma, weiner_diff):
    return rt + a*(b-rt)*delta + sigma*np.sqrt(rt*delta)*weiner_diff


def run_sim(n, a, b, r0, sigma, delta, random_v):
    output = []
    for i in range(n):
        if i == 0:
            output.append(single_iter(r0, a, b, delta, sigma, random_v[i]))
        else:
            output.append(single_iter(output[i-1], a, b, delta, sigma, random_v[i]))
    return np.array(output)


def jd(riskfactorDictionary, key, date_valuation: str, n_max_proyeccion, nSim, **kwargs):
    """
    Jump-Diffusion de Merton para factores de riesgo univariados (FX, RV).

    Ecuacion:
        ln(S_t/S_0) = (mu_d - sigma_d^2/2 - lambda*k_bar)*t
                     + sigma_d*W_t
                     + sum_{i=1}^{N(t)} J_i

    N(t) ~ Poisson(lambda*dt), J_i ~ Normal(mu_j, sigma_j^2)
    k_bar = exp(mu_j + sigma_j^2/2) - 1  (correccion de drift de Merton 1976)

    Calibracion:
        Retornos con |r| > jump_threshold_sigma * sigma_total → saltos.
        El resto → componente de difusion gaussiana.

    Si hay 0 saltos detectados, la componente de saltos se desactiva (lambda=0)
    y JD degenera en difusion pura.

    Parameters
    ----------
    riskfactorDictionary : dict
    key : str
    date_valuation : str  (formato YYYYMMDD)
    n_max_proyeccion : int  horizonte en dias
    nSim : int
    **kwargs:
        jump_threshold_sigma : float  umbral para clasificar saltos (default 2.5)
        peso_factor : float  factor de escala de volatilidad (default 1.0)
        dt : int  (no usado, mantenido por compatibilidad)
    """
    jump_threshold_sigma = kwargs.get('jump_threshold_sigma', 2.5)
    peso_factor          = kwargs.get('peso_factor', 1.0)

    data = riskfactorDictionary[key].curve_training

    if isinstance(data, pd.DataFrame) and data.shape[1] > 1:
        data = data.iloc[:, 0]
        logging.warning(f'Factor {key} con JD tiene multiples columnas. Usando solo la primera.')

    returns = np.log(data.iloc[1:].values) - np.log(data.iloc[:-1].values)
    returns = returns[np.isfinite(returns)]

    sigma_total = returns.std()
    threshold   = jump_threshold_sigma * sigma_total
    is_jump     = np.abs(returns) > threshold
    n_jumps     = is_jump.sum()

    if n_jumps == 0:
        # Sin saltos detectados: JD degenera en difusion pura (lambda=0)
        logging.warning(f'JD [{key}]: 0 saltos detectados. Usando difusion pura (lambda=0).')
        is_jump = np.zeros(len(returns), dtype=bool)

    ret_d   = returns[~is_jump]
    ret_j   = returns[is_jump]
    mu_d    = ret_d.mean()
    sigma_d = max(ret_d.std(), 1e-8) * peso_factor
    lam     = n_jumps / len(returns)        # intensidad diaria (0 si no hay saltos)
    mu_j    = ret_j.mean() if n_jumps > 0 else 0.0
    sigma_j = ret_j.std() if len(ret_j) > 1 else (sigma_total if n_jumps > 0 else 0.0)

    # Correccion de drift Merton 1976
    k_bar  = np.exp(mu_j + 0.5 * sigma_j**2) - 1.0
    mu_adj = mu_d - lam * k_bar

    # Numeros aleatorios correlacionados
    random_vector = riskfactorDictionary[key].randoncorr_Vector[0, :, :]  # (n_max, nSim)
    if not np.isfinite(random_vector).any():
        logging.warning(f'JD [{key}]: randoncorr_Vector todo NaN. Usando normales independientes.')
        rng = np.random.default_rng(seed=hash(key) % (2**31))
        random_vector = rng.standard_normal((n_max_proyeccion, nSim))

    s_0 = data.loc[date_valuation]

    # Simulacion paso a paso usando random_vector para la difusion
    # y numpy.random.default_rng independiente para los saltos Poisson
    rng = np.random.default_rng(seed=hash(key) % (2**31))

    log_paths = np.zeros((n_max_proyeccion, nSim))
    cum_log   = np.zeros(nSim)

    for t in range(n_max_proyeccion):
        z    = random_vector[t, :]                          # ruido correlacionado
        diff = (mu_adj - 0.5 * sigma_d**2) + sigma_d * z   # componente difusion

        # Componente saltos
        N_t = rng.poisson(lam, nSim)
        J_t = np.where(
            N_t > 0,
            np.array([rng.normal(mu_j, sigma_j, max(n, 1)).sum() if n > 0 else 0.0
                      for n in N_t]),
            0.0
        )
        cum_log += diff + J_t
        log_paths[t, :] = cum_log

    # Convertir a niveles de precio
    s_ = s_0 * np.exp(log_paths)
    return s_


def CIR(riskfactorDictionary,key,date_valuation: str,n_max_proyeccion,nSim,**kwargs):
    """
    Crea el modelo de difusion de raiz cuadrada de inversion media de Cox-Ingersoll-Ross (CIR)

    Parameters
    ----------
    riskfactorDictionary : dict
        Diccionario de factores de riesgo, donde cada elemento es un objeto de
        la clase RiskFactors.
    key : string
        Llave del diccionario riskfactorDictionary que indica la curva a simular.
    date_valuation : datetime.datetime
        Fecha de corte para considerar historico de factores de riesgo.
    n_max_proyeccion : int
        Horizonte (en dias) que se quieren proyectar.
    nSim : int
        Numero de simulaciones que se decean realizar por cada dia proyectado. Por defecto se establece como 1500.
    **kwargs :
        dt : int
            incrementos de tiempo positivos entre observaciones.

    Returns
    -------
    path : np.ndarry
          Matriz de los diferentes a los horizontes times_ con nsim simulaciones.
    """
    dt   = kwargs['dt'] if 'dt' in kwargs else 1/252
    peso_factor = kwargs.get('peso_factor', 1.0)  # Peso de matriz de pesos

    data = riskfactorDictionary[key].curve_training
    
    # Si data es un DataFrame con múltiples columnas (curva completa), usar solo la primera columna
    # CIR está diseñado para factores univariados, no para curvas completas
    if isinstance(data, pd.DataFrame) and data.shape[1] > 1:
        # Usar la primera columna
        data = data.iloc[:, 0]
        logging.warning(f'Factor {key} con CIR tiene {riskfactorDictionary[key].curve_training.shape[1]} columnas. Usando solo la primera columna.')
    
    random_vector = riskfactorDictionary[key].randoncorr_Vector[0,:,:]
    if not np.isfinite(random_vector).any():
        logging.warning(f'CIR [{key}]: randoncorr_Vector todo NaN. Usando normales independientes.')
        rng_fb = np.random.default_rng(seed=hash(key) % (2**31))
        random_vector = rng_fb.standard_normal((n_max_proyeccion, nSim))
    r0  =  data.loc[date_valuation]

    # Funcion de optimizacion de los parametros del modelo CIR
    def CIRobjective(X):

        dataL=data.shift(1)
        nobs=len(data)
        timestep=dt

        alpha=X[0]
        mu=X[1]
        sigma=X[2]

        c = 2*alpha/((sigma**2)*(1-np.exp(-alpha*timestep)))
        q = 2*alpha*mu/sigma**2-1
        u = c*np.exp(-alpha*timestep)*dataL.dropna()
        v = c*data
        # Se utiliza la version exponencial de la funcion de Bessel modificada
        # debido a problemas en la optimizacion de la version original (cipy.special.iv)
        z = 2*np.sqrt(u*v)
        bfe = scipy.special.ive(q, z)
        lnL = -(nobs-1)*np.log(c) + (u + v - 0.5*q*np.log(v/u) - np.log(bfe) - z).sum()

        return lnL

    xopt = scipy.optimize.minimize(CIRobjective, x0=[0.5, 0.5, 0.5])
    
    # Aplicar reducción conservadora a parámetros CIR
    alpha_adj = xopt['x'][0]
    mu_adj = xopt['x'][1]
    sigma_adj = xopt['x'][2] * 0.90 * peso_factor  # Reducir 10% base + aplicar peso
    
    paths= run_sim(n_max_proyeccion, alpha_adj, mu_adj, r0, sigma_adj, dt, random_vector)

    return paths


def HJM(riskfactorDictionary,key,date_valuation: str,n_max_proyeccion,nSim,**kwargs):
    """
    Modelo HJM con límites de volatilidad para prevenir escenarios extremos
    Genera simulaciones de la curva de interes (key), usando como marco de
    referencia el modelo HJM.

    Parameters
    ----------
    riskfactorDictionary : dict
        Diccionario de factores de riesgo, donde cada elemento es un objeto de
        la clase RiskFactors.
    key : string
        Llave del diccionario riskfactorDictionary que indica la curva a simular.
    date_valuation : datetime.datetime
        Fecha de corte para considerar historico de factores de riesgo.
    n_max_proyeccion : int
        Horizonte (en dias) que se quieren proyectar.
    nSim : int
        Numero de simulaciones.

    Returns
    -------
    df_simulacion: np.ndarry
        Matriz de curvas ceros simuladas a los horizontes times_ con nsim simulaciones.

    """
    # Parámetro de cap de volatilidad para HJM  
    vol_cap_hjm = kwargs.get('vol_cap_hjm', 0.55)  # Cap conservador al 55%
    peso_factor = kwargs.get('peso_factor', 1.0)  # Peso de matriz de pesos

    def elementoSumaScore(s,x_ti,x_t0,ti,T):
        Multiplo1 = (x_ti-x_t0)*(s**-1)*(np.sqrt(ti)**-1)-0.5*s*np.sqrt(ti)*(2*T-ti)
        Multiplo2 = -(x_ti-x_t0)*(s**-2)*(np.sqrt(ti)**-1)-0.5*np.sqrt(ti)*(2*T-ti)
        return Multiplo1*Multiplo2

    def score(s,*args):
        """
        Derivada de la funcion logVerosimititud con respecto a sigma (volatilidad).
        """
        args = list(args)
        Datos = args[0]
        T = args[1]
        n = len(Datos)
        t = range(1,n+1)
        ElementosSuma = [elementoSumaScore(s,Datos[ti-1],Datos[0],ti,T) for ti in t]
        Suma = sum(ElementosSuma)
        return -n*(s**-1)-Suma


    def elementoSumaInformacion(s,x_ti,x_t0,ti,T):
        Multiplo1 = (x_ti-x_t0)*(s**-2)*(np.sqrt(ti)**-1)+0.5*np.sqrt(ti)*(2*T-ti)
        Multiplo2 = (x_ti-x_t0)*(s**-1)*(np.sqrt(ti)**-1)-0.5*s*np.sqrt(ti)*(2*T-ti)
        Multiplo3 = 2*(x_ti-x_t0)*(s**-3)*(np.sqrt(ti)**-1)
        return Multiplo1**2+Multiplo2*Multiplo3

    def informacion(s,*args):
        """
        Segunda derivada de la funcion logVerosimititud con respecto a sigma (volatilidad).
        """
        args = list(args)
        Datos = args[0]
        T = args[1]
        n = len(Datos)
        t = range(1,n+1)
        ElementosSuma = [elementoSumaInformacion(s,Datos[ti-1],Datos[0],ti,T) for ti in t]
        Suma = sum(ElementosSuma)
        return -n*(s**-2)+Suma

    def simulacionCurva(t,x_t0,T,s,random_vec):
        """
        Generacion de simulaciones usando el modelo HJM.

        Parameters
        ----------
        t : numpy.array
            Dias a proyectar.
        x_t0 : numpy.array
            Inicio de la serie de tiempo a simular.
        T : np.array
            Nodos de la curva a simular.
        s : numpy.array
            Volatilidad estimada por nodo a simular.
        random_vec : numpy.ndarray
            Matriz de simulaciones Normales.

        Returns
        -------
        sim : numpy.array
            Matriz de simulaciones de la curva nsim X Nodos.

        """

        n = len(t)
        n_T = len(T)
        t_matrix = np.repeat(t,n_T).reshape(n,n_T)
        media = x_t0+0.5*(s**2)*t_matrix*(2*T-t_matrix)
        sigma = s*np.sqrt(t_matrix)
        matrix_norm = np.repeat(random_vec,n_T).reshape(n,n_T)
        sim = media+sigma*matrix_norm

        return sim

    # Se extrae informacion del diccionario riskfactorDictionary
    tenors = riskfactorDictionary[key].node_training.values # Nodos
    hist_rates = riskfactorDictionary[key].fwd_curve.values # Curvas Forward
    random_mat = riskfactorDictionary[key].randoncorr_Vector[0,:,:] # Matriz de simulaciones Normales

    # Estimacion de Volatilidad
    sigma = []
    for n_T in range(len(tenors)):

        # Puntos iniciales para hacer la iteracion
        s_0 = [0.000001,0.00001,0.0001,0.001,0.01]
        i = 0
        # Estimacion de la volatilidad como solucion de la ecuacion score=0
        root = fsolve(score,s_0[i],args = (hist_rates[:,n_T],tenors[n_T]))

        # Se determina si se a encontrado un minimo utilizando la funcion de informacion.
        # En caso contrario se procede a una nueva iteracion para hacer la estimacion usando un punto inicial diferente.
        while i < len(s_0) and informacion(root[0],hist_rates[:,n_T],tenors[n_T]) < 0:
            i = i+1
            root = fsolve(score,s_0[i],args = (hist_rates[:,n_T],tenors[n_T]))
        if i == len(s_0):
            print(f'No se alcanzo la maxima verosimilitud para el tenor {int(tenors[n_T])}.')
            root = hist_rates[:,n_T]

        sigma.append(root[0])


    T = np.array(tenors) # Nodos
    sigma_all = np.array(sigma) * peso_factor # Volatilidad estimada ajustada por peso

    df_simulacion = []
    # Iteracion por cada dia en el vector de horizontes
    timefor = np.arange(1,n_max_proyeccion+1)
    for pos_test in timefor:

        t = np.array([1]*nSim) # Proyeccion a un dia por cada horizonte
        random_vec = random_mat[pos_test-1,:]

        if pos_test == 1:
            # Para el primer horizonte se toma como dato inicial la ultima curva historica.
            x_0 = np.tile(np.array(hist_rates[-1,:]),[nSim,1])
            simulacion_test = simulacionCurva(t,x_0,T,sigma_all,random_vec)
            x_0 = simulacion_test
        else:
            # Para el segundo horizonte y posteriores, se toma como dato inicial la simulaciones anteriores.
            simulacion_test = simulacionCurva(t,x_0,T,sigma_all,random_vec)
            x_0 = simulacion_test


        df = pd.DataFrame(simulacion_test,columns=tenors,dtype = float).T

        # Se procede a convertir la curva Instantaneous Forward Rate a Zero Coupon.
        df_simulacion_i = []

        date_valuation_dt = dt.datetime.strptime(date_valuation, '%Y%m%d')

        for col in df.columns:
            curveDates_test = [date_valuation_dt + timedelta(days = int(day)) for day in riskfactorDictionary[key].node_training.values]
            zero = rkf.RiskFactors.fwd2zero(df[col].values,curveDates_test,date_valuation_dt, basis = 3, compounding = 1,outputCompounding = 1)
            df_simulacion_i.append(zero)
        df_simulacion_i = pd.DataFrame(df_simulacion_i,dtype = float).T
        
        # Aplicar cap a volatilidad extrema en HJM
        # Si el CV es muy alto, escalar las simulaciones hacia la media
        for col_idx in range(df_simulacion_i.shape[1]):
            col_data = df_simulacion_i.iloc[:, col_idx]
            cv = col_data.std() / abs(col_data.mean()) if col_data.mean() != 0 else 0
            if cv > vol_cap_hjm:
                scaling_factor = vol_cap_hjm / cv
                mean_val = col_data.mean()
                df_simulacion_i.iloc[:, col_idx] = mean_val + (col_data - mean_val) * scaling_factor
        
        df_simulacion.append(df_simulacion_i)

    df_simulacion = np.array(df_simulacion)

    return df_simulacion














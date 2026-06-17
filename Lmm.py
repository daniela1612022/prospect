
from operator import matmul
from pickle import NONE
import sys
from tkinter import NS
#from Equity import Equity
sys.path.append("E:\\ReporteCorporativoPy\\Codigos")
import utils.Read as rd
import utils.RiskFactors as rkf
import pandas as pd
import datetime as dt
import numpy as np
from numpy.random import MT19937
from numpy.random import RandomState, SeedSequence


def lmmm(time360,nSim,lambdajq_,Fwdref,timeY,nCPs,MatLjq,s1,date_valuation):
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
        s = s1[tk*3:(tk+1)*3,:]
        horizontek =  timeY[tk]
        for fi in range(len_Fwdref):

            nodoi = time360[fi]
            if  horizontek < nodoi:
                poskeni = np.unravel_index(np.argmin(abs(time360-horizontek), axis=None), abs(time360-horizontek).shape)[0]
                periodos = time360[poskeni:fi+1]                           # Nodos: desde el mas cercano a k hasta el nodo i en consideracion
                forwards = Fi[tk,poskeni:fi+1,1]                              # Tasas forward de periodos
                fila = range(poskeni,fi+1)
                mt = poskeni                                             # m(t) es la posicion de k en los nodos de la curva i
                ii = len(fila)

            elif horizontek > nodoi:
                poskeni = np.unravel_index(np.argmin(abs(horizontek-time360), axis=None),
                                            abs(horizontek-time360).shape)[0]
                periodos = time360[fi:poskeni+1]                           # Nodos: desde el mas cercano a k hasta el nodo i en consideracion
                forwards = Fi[tk,fi:poskeni+1,1]                              # Tasas forward de periodos
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

    curveDates = [date_valuation+ dt.timedelta(days = day) for day in time360*360]

    for n  in range(nSim):
        for tk  in range(len(timeY)):
            zero[tk,:,n] = rkf.RiskFactors.fwd2zero(Fi[tk,:,n],curveDates, date_valuation, compounding = 1, basis =3)
    return  zero


#rs = RandomState(MT19937(SeedSequence(123456789)))
np.random.seed(0)
fechaValoracion = '01/06/2021'
date_valuation =  dt.datetime.strptime(fechaValoracion,'%d/%m/%Y')

#wfactors = ['USDCOP','C_IBR','C_SOFR','IBRea','T_USDMXN']
#wfactors = ['USDCOP','C_IBR','C_SOFR','IBRea','C_USDIBR','C_OISUSD','CEC','CECUVR']
wfactors = ['C_IBR','C_OISUSD','C_SOFR','C_USDIBR',	'CEC','CECUVR','IBRea','USDCOP']

path_files_parameters = 'E:\\ReporteCorporativoPy\\04 Insumos\\04 Parametros'
path_files_parquet = 'E:\\ReporteCorporativoPy\\04 Insumos\\02 Mercado\\Procesados\\Parquet'
file_Parameterization = rd.Read.readExcel(path = path_files_parameters, Name_file = 'Parametros_Reporte', sheet_name = 'Factores')
riskfactorDictionary = rkf.RiskFactors.create_factorInfo_dictionary(wfactors,file_Parameterization, path_files_parquet)
riskfactorDictionary =  rkf.RiskFactors.curve_trainig_filter(riskfactorDictionary,date_valuation,data_number =250)#,data_number =898
riskfactorDictionary.keys()

riskfactorDictionary['USDCOP'].curve_training
riskfactorDictionary['C_IBR'].node_training
type(riskfactorDictionary['CEC'].node_training[0])
nCPs = 3
nSim = 1000
timefor = np.array([1,2,9,10,29,30,59,60,89,90,179,180,359,360,719,
                    720,1079,1080,1439,1440,1799,1800,2519,2520,
                    3599,3600,4319,4320,5039,5040])
times_ =np.array([0, 1,2,9,10,29,30,59,60,89,90,179,180,359,360,719,
                    720,1079,1080,1439,1440,1799,1800,2519,2520,
                    3599,3600,4319,4320,5039,5040])
timefor = np.array( [1,2,19,20])
times_ = np.array( [0,1,2,19,20])
timeY = timefor/360
CompMatrix = np.array([])
ii = 4
key = 'C_SOFR'
for key in riskfactorDictionary.keys():
    s1 = np.random.normal(0, 1, size=(3*len(timefor), 1000))
    if riskfactorDictionary[key].metsim == 'LMM':
        discount_curve = []
        fwd_curve = []
        for index in   riskfactorDictionary[key].curve_training.index.to_pydatetime():
            curveDates = [index+ dt.timedelta(days = day) for day in riskfactorDictionary[key].node_training.values]
            zeroRates  = riskfactorDictionary[key].curve_training.loc[index].values
            #rkf.RiskFactors.zero2disc(zeroRates, curveDates, index,basis = 3, compounding = 1)
            discount = rkf.RiskFactors.zero2disc(zeroRates, curveDates, index, basis = 3, compounding = 1)
            fwd = rkf.RiskFactors.zero2fwdn(zeroRates, curveDates, index, basis = 3, compounding = 1)
            discount_curve.append(discount)
            fwd_curve.append(fwd)
        riskfactorDictionary[key].fwd_curve = pd.DataFrame(fwd_curve,columns= riskfactorDictionary[key].curve_training.columns,
                                index=riskfactorDictionary[key].curve_training.index)
        c = riskfactorDictionary[key].fwd_curve.cov() #   Niveles fwdrates(#fechas * # nodos) -> V(# nodos*# nodos) Matriz de varianzas y covarianzas
        evals, evecs = np.linalg.eigh(c) # % [volatilidad, Coeficientes] -> PCA sobre varcov
        # Orgnizar Vectores de mayor a menor
        idx = evals.argsort()[::-1]
        riskfactorDictionary[key].eigenValues = evals[idx]     #  % Varianzas de CPs (valores propios)
        riskfactorDictionary[key].eigenVectors = evecs[:,idx]   # % Coeficientes de CPs (loadings)
        #eigenVectors = pd.DataFrame(evecs[:,idx])   # % Coeficientes de CPs (loadings)
        riskfactorDictionary[key].PComponent = np.matmul(riskfactorDictionary[key].fwd_curve.values,
                                                         riskfactorDictionary[key].eigenVectors[:,0:nCPs])
        cf =  riskfactorDictionary[key].eigenVectors.copy()
        lt =  riskfactorDictionary[key].eigenValues.copy()
        slt = np.sqrt(riskfactorDictionary[key].eigenValues);
        lambda_ =  cf*np.repeat(slt.reshape(1,len(slt)),len(slt),axis=0)

        LBD = np.sqrt(np.power(lambda_,2).sum(axis = 1)) #% Volatilidad total de tasa fwd con j nodos (H&W pag 11 (17))
        L_aux = np.sqrt(np.power(lambda_[:,0:nCPs],2).sum(axis = 1))
        #% Volatilidades de cada nodo teniendo en cuenta solo 3 CPs
        lambdajq_ = np.repeat(LBD.reshape(1,len(L_aux)),nCPs,axis=0).T*lambda_[:,0:nCPs]/(np.repeat(L_aux.reshape(1,len(L_aux)),nCPs,axis=0).T)

        MatLjq = np.matmul(lambdajq_,lambdajq_.T)
        Fwdref = riskfactorDictionary[key].fwd_curve.loc[date_valuation].values
        time360 =  riskfactorDictionary[key].node_training.values/360
        riskfactorDictionary[key].zerosim = lmmm(time360,nSim,lambdajq_,Fwdref,timeY,nCPs,MatLjq,s1,date_valuation)

    elif riskfactorDictionary[key].metsim == 'GBM':
        riskfactorDictionary[key].PComponent =  riskfactorDictionary[key].curve_training.values
    elif riskfactorDictionary[key].metsim == 'CIR':
        riskfactorDictionary[key].PComponent =  riskfactorDictionary[key].curve_training.values
    else:
        riskfactorDictionary[key].PComponent =  riskfactorDictionary[key].curve_training.values
    if len(CompMatrix)==0:
        CompMatrix = riskfactorDictionary[key].PComponent.copy()
    else:
        CompMatrix = np.c_[CompMatrix,riskfactorDictionary[key].PComponent]
diffcompM =  np.diff(CompMatrix, n=1, axis=0)
#Matriz de correlaciones:
#Se calcula la correlacion entre las diferencias de los primeros tres componentes
#principales de las curvas (Componentes calculados sobre el nivel de las
#tasas forward), la IBR y las monedas

corrPCs  = np.corrcoef(diffcompM.T)
a,b = np.linalg.eig(corrPCs)
if all(a>0):
    R = np.linalg.cholesky(corrPCs)
else:
    R = np.linalg.cholesky(corrPCs) +np.identity(len(corrPCs))
pd.DataFrame(np.linalg.cholesky(corrPCs))
cmpa = pd.DataFrame(CompMatrix)
pd.DataFrame(corrPCs)
pd.DataFrame(diffcompM).corr()



key = 'C_IBR'
vets =   pd.DataFrame(riskfactorDictionary[key].PComponent )
vets.corr()
settle = index
zeroRates       = riskfactorDictionary['C_IBR'].curve_training.loc[index].values
curvadatesaa = riskfactorDictionary['C_IBR'].curve_training.values
riskfactorDictionary['C_IBR'].curve_training.iloc[0]
nodesaa  = riskfactorDictionary['C_IBR'].node_training.values
curvadatesaa+ dt.timedelta(days = nodesaa)
riskfactorDictionary['C_SOFR'].curve.isnull().values.any()

riskfactorDictionary['C_IBR'].metsim
date_ = date_valuation










for fi_ in range(len(Fwdref)):
    print(fi_)

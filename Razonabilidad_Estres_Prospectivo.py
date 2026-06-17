"""
-----------------------------------------------------------------------------
-----------------------------------------------------------------------------
-- Vicepresidencia de Riesgos                                              --
-- Gerencias de Posicion Propia - Evolucion Analitica - Metodologias       --
-----------------------------------------------------------------------------
-- Descripción: Script para realizar la razonabilidad de estres            --
--              prospectivo                                                --
-- Fecha Creación: 20240331                                                --
-- Autores: victgonz                                                       --
-- Última Fecha Modificación: 20240331                                     --
-- Últimos Contribuidores: victgonz                                        --
-----------------------------------------------------------------------------
-----------------------------------------------------------------------------
"""

#%% Librerias

import pandas as pd
import os
import logging
from datetime import datetime as dt


#%% Parametros

print("#"*42)
print("#    RAZONABILIDAD ESTRES PROSPECTIVO    #")
print("#       VICEPRECIDENCIA DE RIESGOS       #")
print("# GCIA METODOLOGIA RGO MKDO DE CAPITALES #")
print("#"*42)


date_valuation = str(input('Ingresar fecha de valoracion en formato yyyymmdd:'))
date_valuation_dt = dt.strptime(date_valuation, '%Y%m%d')
date_valuation_ddmmyyyy = date_valuation_dt.strftime("%d%m%Y")

tesoreria = 'Grupo PP'

dict_tes2num = {'Grupo PP': 1}

#%% Rutas

path_base = "\\\\10.8.45.116\\vp_riesgos\\DIR_RIES_MER_LIQ\\CORP_RIES_MER_LIQ\\02. GCIA_METODOLOGIA_RGO"

path_VaR = os.path.join(path_base, f"VaR\\VaR_tesoreria\\{date_valuation_ddmmyyyy}")
name_VaR = str(input("Ingresar nombre del archivo (.xlsx) de VaR:"))
path_file_VaR = os.path.join(path_VaR, name_VaR+'.xlsx')

path_Stress = os.path.join(path_base, f"Estres\\Prospectivo\\{date_valuation_ddmmyyyy}")
name_Stress = str(input("Ingresar nombre del archivo (.xlsx) de Stress:"))
path_file_Stress = os.path.join(path_Stress, name_Stress+'.xlsx')


#%% Creacion de carpetas y rutas de guardado

path_save = os.path.join(path_Stress, 'Razonabilidad')
try:
    os.mkdir(path_save)
except:
    print('Ya existe el directorio de razonabilidad')

path_file_log = os.path.join(path_save,"Log_Razonabilidad_Prospectivo_"+date_valuation+".txt")

path_file_excel = os.path.join(path_save,"Razonabilidad_Prospectivo_"+date_valuation+".xlsx")


#%% Inicio de logging

# Abre el archivo de registro en modo de escritura (w)
with open(path_file_log, 'w') as f:
    # Escribe un encabezado en el archivo de registro
    f.write("#"*42+"\n")
    f.write("#    RAZONABILIDAD ESTRES PROSPECTIVO    #"+"\n")
    f.write("#       VICEPRECIDENCIA DE RIESGOS       #"+"\n")
    f.write("# GCIA METODOLOGIA RGO MKDO DE CAPITALES #"+"\n")
    f.write("#"*42+"\n")
    f.write("\n")

# Obten el registrador raíz
logger = logging.getLogger('razonabilidad_stres_prospectivo')
logger.setLevel(logging.DEBUG)

# Desactiva la propagacion de mensajes de log
logger.propagate = False

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Crea un manejador de archivo para el log
file_handler = logging.FileHandler(filename = path_file_log, mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Agrega un manejador de registro para imprimir en la consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


#%% Datos iniciales

logger.info(f'Fecha de valoracion: {date_valuation}')
logger.info(f'Tesoreria: {tesoreria}')
logger.info(f'Ruta VaR: {path_file_VaR}')
logger.info(f'Ruta Stress: {path_file_Stress}')

#%% Lectura de los reportes

sheet_name = "Resultados_Zeros"
df_VaR = pd.read_excel(path_file_VaR, sheet_name = sheet_name)
df_VaR_Ori = df_VaR
df_Stress = pd.read_excel(path_file_Stress, sheet_name = sheet_name)
df_Stress_Ori = df_Stress

#%% Comparacion inicial

# Validacion de las fechas
date_VaR = list(df_VaR['Fecha'].unique())[-1]
date_Stress = list(df_Stress['Fecha'].unique())[-1]

if date_valuation_dt.strftime("%d/%m/%Y") in date_VaR:
    logger.info('Fecha del VaR coincide: SI')
else:
    logger.warning('Fecha del VaR coincide: NO')

if date_valuation_dt.strftime("%d/%m/%Y") in date_Stress:
    logger.info('Fecha del Stress coincide: SI')
else:
    logger.warning('Fecha del Stress coincide: NO')


# Validacion del numero de posiciones
n_VaR = df_VaR.shape[0]
n_Stress = df_Stress.shape[0]

if n_VaR == n_Stress:
    logger.info('Numero de posiciones coinciden: SI')
else:
    logger.warning('Numero de posiciones coinciden: NO')


# Validacion del nominal
sum_nominal_VaR = df_VaR["Nominal"].sum()
sum_nominal_Stress = df_Stress["Nominal"].sum()

if sum_nominal_VaR == sum_nominal_Stress:
    logger.info('El nominal total coincide: SI')
else:
    logger.warning('El nominal total coincide: NO')


# Validacion de valoracion
sum_valoracion_VaR = df_VaR["Valoracion"].sum()
sum_valoracion_Stress = df_Stress["Valoracion"].sum()

if sum_valoracion_VaR == sum_valoracion_Stress:
    logger.info('La valoracion total coincide: SI')
else:
    logger.warning('La valoracion total coincide: NO')

# Validacion de VaR
sum_VaR_VaR = df_VaR[f'ComponentVaR_RC{dict_tes2num[tesoreria]}'].sum()
sum_VaR_Stress = df_Stress[f'ComponentVaR_RC{dict_tes2num[tesoreria]}'].sum()

if sum_VaR_VaR == sum_VaR_Stress:
    logger.info('El VaR total coincide: SI')
else:
    logger.warning('El VaR total coincide: NO')


#%% Comparacion detallada

list_columns = ['Key', 'Nominal', 'Valoracion', f'ComponentVaR_RC{dict_tes2num[tesoreria]}']


df_VaR['Key'] = df_VaR['Pais']+'_'+df_VaR['Institucion']+'_'+df_VaR['Mesa']+'_'+\
    df_VaR['Portafolio']+'_'+df_VaR['Producto']+'_'+df_VaR['Id1']+'_'+df_VaR['Id2']


df_VaR = df_VaR[list_columns].groupby(by='Key').sum()

df_Stress['Key'] = df_Stress['Pais']+'_'+df_Stress['Institucion']+'_'+df_Stress['Mesa']+'_'+\
    df_Stress['Portafolio']+'_'+df_Stress['Producto']+'_'+df_Stress['Id1']+'_'+df_Stress['Id2']

df_Stress = df_Stress[list_columns].groupby(by='Key').sum()


df = df_VaR.merge(df_Stress, on='Key', how='outer', suffixes = ('_VaR','_Stress'))


# Validacion por operacion

for name_col in list_columns[1:]:
    df[name_col+'_Razonabilidad'] = df[name_col+'_VaR'] == df[name_col+'_Stress']


for name_col in list_columns[1:]:
    val = df[name_col+'_Razonabilidad']

    if val.all():
        logger.info(f'{name_col} coincide por operacion: SI')
    else:
        logger.warning(f'{name_col} coincide por operacion: NO')


#%% Guardado de resultados

df.to_excel(path_file_excel)

with pd.ExcelWriter(path_file_excel) as writer:
    df.to_excel(writer, sheet_name = "Razonabilidad")
    df_VaR_Ori.to_excel(writer, sheet_name = "Resultados_Zeros_VaR")
    df_Stress_Ori.to_excel(writer, sheet_name = "Resultados_Zeros_Stress")

logger.info(f'Se escribe el archivo detallado en la ruta: {path_file_excel}')


file_handler.close()



































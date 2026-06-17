# -*- coding: utf-8 -*-
"""
Script para ajustar pesos de factores de riesgo en stress testing
Permite modificar la concentración de riesgo de forma interactiva
o calibrarlos dinámicamente desde un archivo VaR Zeros.
"""

import os
import sys
import json

absolute_path = os.path.dirname(__file__)
relative_path = "rfk_prospectivo"
full_path = absolute_path.replace(relative_path, "")
sys.path.append(full_path)

import utils.PesosStress as ps
import utils.CalibracionDinamica as cd


def mostrar_pesos_actuales():
    """Muestra los pesos actuales configurados"""
    config_path = os.path.join(full_path, 'statics', 'config', 'pesos_factores_stress.json')
    pesos_manager = ps.PesosFactoresStress(config_path)
    
    print("="*80)
    print("PESOS ACTUALES POR CATEGORÍA")
    print("="*80)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\nCategorías configuradas:")
    for categoria, info in data['pesos_por_categoria'].items():
        peso = info['peso']
        desc = info['descripcion']
        n_factores = len(info['factores'])
        print(f"\n{categoria}:")
        print(f"  Peso: {peso:.2f} ({(peso-1)*100:+.0f}% volatilidad)")
        print(f"  Descripción: {desc}")
        print(f"  Factores: {n_factores}")
        
    print("\n" + "="*80)
    print("OVERRIDES INDIVIDUALES")
    print("="*80)
    overrides = data.get('pesos_individuales_override', {})
    if overrides:
        for factor, peso in overrides.items():
            if isinstance(peso, (int, float)):
                print(f"  {factor}: {peso:.2f} ({(peso-1)*100:+.0f}%)")
            else:
                print(f"  {factor}: {peso}")
    else:
        print("  (ninguno configurado)")


def ajustar_peso_individual(factor, nuevo_peso, config_path=None):
    """
    Ajusta el peso de un factor específico
    
    Parameters
    ----------
    factor : str
        Nombre del factor
    nuevo_peso : float
        Nuevo peso (1.0 = sin cambio, >1.0 = mayor impacto, <1.0 = menor impacto)
    config_path : str, optional
        Ruta al archivo de configuración
    """
    if config_path is None:
        config_path = os.path.join(full_path, 'statics', 'config', 'pesos_factores_stress.json')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['pesos_individuales_override'][factor] = nuevo_peso
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Peso de {factor} ajustado a {nuevo_peso:.2f}")


def ajustar_categoria(nombre_categoria, nuevo_peso, config_path=None):
    """
    Ajusta el peso de toda una categoría
    
    Parameters
    ----------
    nombre_categoria : str
        Nombre de la categoría
    nuevo_peso : float
        Nuevo peso
    config_path : str, optional
        Ruta al archivo de configuración
    """
    if config_path is None:
        config_path = os.path.join(full_path, 'statics', 'config', 'pesos_factores_stress.json')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if nombre_categoria in data['pesos_por_categoria']:
        data['pesos_por_categoria'][nombre_categoria]['peso'] = nuevo_peso
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        n_factores = len(data['pesos_por_categoria'][nombre_categoria]['factores'])
        print(f"✓ Peso de categoría {nombre_categoria} ajustado a {nuevo_peso:.2f}")
        print(f"  Afecta a {n_factores} factores")
    else:
        print(f"✗ Categoría {nombre_categoria} no encontrada")


def activar_desactivar_pesos(activar=True, config_path=None):
    """
    Activa o desactiva completamente el sistema de pesos
    
    Parameters
    ----------
    activar : bool
        True para activar, False para desactivar
    config_path : str, optional
        Ruta al archivo de configuración
    """
    if config_path is None:
        config_path = os.path.join(full_path, 'statics', 'config', 'pesos_factores_stress.json')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['configuracion']['aplicar_pesos'] = activar
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    estado = "ACTIVADO" if activar else "DESACTIVADO"
    print(f"✓ Sistema de pesos {estado}")


def calibrar_dinamicamente(path_var_excel, nivel='Grupo Bancolombia',
                            metodo='min_max', guardar=True, config_path=None):
    """
    Calibra los pesos dinámicamente a partir del archivo VaR Zeros.

    Extrae los choques históricos de la hoja ``Factores_Zeros``, los normaliza
    dentro de cada tipo de activo (Tasa Cambio, Curva, Acciones, etc.) y los
    mapea al rango ``[peso_minimo, peso_maximo]`` definido en la configuración.

    Parameters
    ----------
    path_var_excel : str
        Ruta completa al archivo Excel de resultados VaR Zeros.
        Ejemplo: ``"C:/Downloads/Resultados_30_Apr_Zeros.xlsx"``
    nivel : str
        Nivel de agregación del Excel.  Por defecto ``'Grupo Bancolombia'``.
    metodo : str
        ``'min_max'``: escala lineal entre choque mínimo y máximo por tipo.
        ``'percentil'``: rango percentil del factor dentro de su tipo.
    guardar : bool
        Si ``True`` (default), actualiza ``pesos_factores_stress.json``.
    config_path : str, optional
        Ruta al JSON de configuración.  Si es ``None`` usa la ruta estándar.

    Returns
    -------
    pesos_calibrados : dict
        ``{factor_json: peso_float}``
    df_diagnostico : pd.DataFrame
        Tabla con Factor_Excel, Tipo, Choque_Max, Factores_JSON, Peso_Dinamico.

    Examples
    --------
    >>> import ajustar_pesos_stress as aps
    >>> pesos, diag = aps.calibrar_dinamicamente(
    ...     r"C:/Downloads/Resultados_30_Apr_Zeros.xlsx"
    ... )
    """
    if config_path is None:
        config_path = os.path.join(
            full_path, 'statics', 'config', 'pesos_factores_stress.json'
        )

    pesos_calibrados, df_diagnostico = cd.calibrar_pesos_desde_var(
        path_var_excel=path_var_excel,
        config_path=config_path,
        nivel=nivel,
        metodo=metodo,
        guardar=guardar,
    )

    cd.imprimir_diagnostico(df_diagnostico)
    return pesos_calibrados, df_diagnostico


def ejemplo_ajustes_personalizados():
    """
    Ejemplos de cómo hacer ajustes personalizados
    """
    print("\n" + "="*80)
    print("EJEMPLOS DE AJUSTES")
    print("="*80)

    print("\n# Ejemplo 1: Calibración dinámica desde archivo VaR (recomendado)")
    print('calibrar_dinamicamente(r"C:/Downloads/Resultados_Zeros.xlsx")')

    print("\n# Ejemplo 2: Aumentar impacto de USDCOP a 1.8x")
    print("ajustar_peso_individual('USDCOP', 1.8)")

    print("\n# Ejemplo 3: Reducir impacto de acciones internacionales a 0.7x")
    print("ajustar_categoria('Acciones_Internacional_Media', 0.7)")

    print("\n# Ejemplo 4: Concentrar riesgo en divisas críticas")
    print("ajustar_categoria('Divisas_Mayor_Impacto', 1.6)")
    print("ajustar_categoria('Divisas_Impacto_Medio', 1.2)")
    print("ajustar_categoria('Divisas_Bajo_Impacto', 0.6)")

    print("\n# Ejemplo 5: Desactivar completamente los pesos")
    print("activar_desactivar_pesos(False)")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("GESTOR DE PESOS PARA STRESS TESTING")
    print("="*80)

    # Mostrar pesos actuales
    mostrar_pesos_actuales()

    # Mostrar ejemplos
    ejemplo_ajustes_personalizados()

    print("\n" + "="*80)
    print("USO:")
    print("="*80)
    print("1. Importar:  import ajustar_pesos_stress as aps")
    print("2. Dinámico:  aps.calibrar_dinamicamente(r'ruta/Resultados_Zeros.xlsx')")
    print("3. Manual:    aps.ajustar_peso_individual('USDCOP', 1.5)")
    print("4. Ejecutar:  python test.py")
    print("5. Revisar:   Simulation_statistics.xlsx > Pestaña 'Pesos_Aplicados'")
    print("="*80 + "\n")

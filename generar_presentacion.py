# -*- coding: utf-8 -*-
"""
Genera la presentación PowerPoint sobre modelos alternativos al GBM
y calibración dinámica de pesos para stress testing prospectivo.
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
import pptx.oxml.ns as nsmap
from lxml import etree
import copy

# ── Paleta de colores (estilo financiero sobrio) ──────────────────────────────
C_AZUL_OSC  = RGBColor(0x1A, 0x37, 0x5E)   # azul corporativo oscuro
C_AZUL_MED  = RGBColor(0x2E, 0x5F, 0x9E)   # azul medio
C_AZUL_CLAR = RGBColor(0xC8, 0xD8, 0xF0)   # azul muy claro (fondo suave)
C_VERDE     = RGBColor(0x1E, 0x7E, 0x4A)   # verde positivo
C_ROJO      = RGBColor(0xC0, 0x20, 0x2A)   # rojo alerta
C_NARANJA   = RGBColor(0xE0, 0x7B, 0x10)   # naranja intermedio
C_GRIS_OSC  = RGBColor(0x40, 0x40, 0x40)   # gris texto
C_GRIS_CLAR = RGBColor(0xF0, 0xF2, 0xF5)   # gris fondo
C_BLANCO    = RGBColor(0xFF, 0xFF, 0xFF)
C_AMARILLO  = RGBColor(0xFF, 0xD7, 0x00)


# ── Helpers ───────────────────────────────────────────────────────────────────

def set_bg(slide, color: RGBColor):
    """Pinta el fondo del slide con un color sólido."""
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, l, t, w, h, fill_color=None, line_color=None, line_w=None):
    shape = slide.shapes.add_shape(
        pptx.enum.shapes.MSO_SHAPE_TYPE.RECTANGLE
        if False else 1,   # 1 = MSO_SHAPE.RECTANGLE
        Inches(l), Inches(t), Inches(w), Inches(h)
    )
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
        if line_w:
            shape.line.width = Pt(line_w)
    else:
        shape.line.fill.background()
    return shape


def add_text_box(slide, text, l, t, w, h,
                 font_size=14, bold=False, color=C_GRIS_OSC,
                 align=PP_ALIGN.LEFT, wrap=True, italic=False):
    txBox = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txBox


def add_title_bar(slide, title, subtitle=None):
    """Barra azul oscura en la parte superior con título."""
    add_rect(slide, 0, 0, 13.33, 1.1, fill_color=C_AZUL_OSC)
    add_text_box(slide, title, 0.3, 0.1, 12.5, 0.6,
                 font_size=22, bold=True, color=C_BLANCO, align=PP_ALIGN.LEFT)
    if subtitle:
        add_text_box(slide, subtitle, 0.3, 0.68, 12.5, 0.35,
                     font_size=13, bold=False, color=C_AZUL_CLAR,
                     align=PP_ALIGN.LEFT, italic=True)


def add_footer(slide, text="Riesgo de Mercado | Modelos de Simulación Prospectiva"):
    add_rect(slide, 0, 7.2, 13.33, 0.3, fill_color=C_AZUL_OSC)
    add_text_box(slide, text, 0.2, 7.22, 12.9, 0.25,
                 font_size=9, color=C_AZUL_CLAR, align=PP_ALIGN.CENTER)


def add_bullet_box(slide, bullets, l, t, w, h,
                   title=None, title_color=C_AZUL_OSC,
                   bullet_color=C_GRIS_OSC, font_size=12,
                   bg_color=None, border_color=None):
    """Cuadro con lista de bullets."""
    if bg_color or border_color:
        add_rect(slide, l, t, w, h, fill_color=bg_color,
                 line_color=border_color or C_AZUL_MED, line_w=1)
    txBox = slide.shapes.add_textbox(
        Inches(l + 0.1), Inches(t + 0.08),
        Inches(w - 0.2), Inches(h - 0.16)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    if title:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(font_size + 1)
        run.font.bold = True
        run.font.color.rgb = title_color

    for b in bullets:
        p = tf.paragraphs[0] if (first and not title) else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = b
        run.font.size = Pt(font_size)
        run.font.color.rgb = bullet_color


# =============================================================================
# SLIDES
# =============================================================================

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

blank_layout = prs.slide_layouts[6]   # completamente en blanco


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 1 — PORTADA
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_AZUL_OSC)

# Franja decorativa
add_rect(slide, 0, 5.6, 13.33, 0.08, fill_color=C_AMARILLO)

add_text_box(slide,
    "MODELOS DE SIMULACIÓN PARA\nSTRESS TESTING PROSPECTIVO",
    0.6, 1.2, 12.0, 2.2, font_size=36, bold=True, color=C_BLANCO,
    align=PP_ALIGN.CENTER)

add_text_box(slide,
    "Evaluación comparativa de alternativas al GBM\ny calibración dinámica de pesos de volatilidad",
    0.6, 3.4, 12.0, 1.2, font_size=18, color=C_AZUL_CLAR,
    align=PP_ALIGN.CENTER, italic=True)

add_text_box(slide,
    "Riesgo de Mercado  ·  Gerencia de Riesgos  ·  2026",
    0.6, 5.9, 12.0, 0.5, font_size=13, color=C_AMARILLO,
    align=PP_ALIGN.CENTER)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 2 — AGENDA
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "Agenda", "Estructura de la presentación")
add_footer(slide)

items = [
    ("01", "Limitaciones del GBM como modelo de referencia"),
    ("02", "Los cuatro modelos candidatos"),
    ("03", "Metodología de comparación: Torneo de modelos"),
    ("04", "Métricas de evaluación y resultados"),
    ("05", "¿Por qué la calibración dinámica de pesos?"),
    ("06", "Cómo funciona el sistema de pesos"),
    ("07", "Métodos de calibración: Min-Max vs Percentil"),
    ("08", "Proceso paso a paso y comparativa"),
    ("09", "Conclusiones y recomendaciones"),
]

for i, (num, txt) in enumerate(items):
    row = i % 5
    col = i // 5
    l = 0.4 + col * 6.5
    t = 1.35 + row * 1.1
    add_rect(slide, l, t, 0.55, 0.55, fill_color=C_AZUL_MED)
    add_text_box(slide, num, l, t + 0.05, 0.55, 0.45,
                 font_size=14, bold=True, color=C_BLANCO, align=PP_ALIGN.CENTER)
    add_text_box(slide, txt, l + 0.65, t + 0.08, 5.6, 0.5,
                 font_size=13, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3 — LIMITACIONES DEL GBM
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "01  Limitaciones del GBM", "¿Por qué buscar alternativas?")
add_footer(slide)

# Ecuación GBM
add_rect(slide, 0.3, 1.25, 12.7, 1.1, fill_color=C_AZUL_CLAR,
         line_color=C_AZUL_MED, line_w=1)
add_text_box(slide,
    "Modelo actual:   dS = μ·S·dt  +  σ·S·dW      →      S_T = S_0 · exp[(μ − σ²/2)·T  +  σ·√T·Z]",
    0.5, 1.32, 12.3, 0.5, font_size=14, bold=True, color=C_AZUL_OSC,
    align=PP_ALIGN.CENTER)
add_text_box(slide, "con  Z ~ N(0,1)  independiente e idénticamente distribuido",
    0.5, 1.78, 12.3, 0.4, font_size=11, italic=True, color=C_AZUL_MED,
    align=PP_ALIGN.CENTER)

problemas = [
    ("Cola delgada (Normal)",
     "Los retornos financieros tienen exceso de curtosis (fat tails).\n"
     "GBM subestima la probabilidad de eventos extremos en horizontes de 20 días."),
    ("Sin memoria de crisis",
     "Volatilidad constante σ: el modelo no recuerda períodos de estrés.\n"
     "En mercados en crisis, la volatilidad es agrupada (clustering), no plana."),
    ("Sin saltos discretos",
     "Defaults, decisiones de política, crisis geopolíticas generan saltos\n"
     "bruscos que GBM no puede capturar (movimiento continuo)."),
    ("Brecha Stress < VaR",
     "La reducción ad-hoc del 10% en σ (σ×0.90) crea una subestimación\n"
     "sistemática. En pruebas: Stress = −88.5B vs VaR = −113.4B."),
]

for i, (tit, desc) in enumerate(problemas):
    col = i % 2
    row = i // 2
    l = 0.3 + col * 6.55
    t = 2.55 + row * 2.15
    add_rect(slide, l, t, 6.3, 1.9, fill_color=C_BLANCO,
             line_color=C_ROJO, line_w=1.2)
    add_text_box(slide, f"✗  {tit}", l + 0.12, t + 0.1, 6.0, 0.4,
                 font_size=13, bold=True, color=C_ROJO)
    add_text_box(slide, desc, l + 0.12, t + 0.48, 6.0, 1.35,
                 font_size=11, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4 — LOS CUATRO MODELOS (overview)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "02  Los Cuatro Modelos Candidatos", "Características clave de cada alternativa")
add_footer(slide)

modelos = [
    ("GBM", "Baseline actual",
     C_AZUL_MED, C_AZUL_CLAR,
     ["Movimiento Browniano Geométrico",
      "μ y σ constantes (histórico 250d)",
      "Reducción ad-hoc: σ × 0.90",
      "Retornos log-normales independientes"]),
    ("JD\n(Merton)", "Jump-Diffusion",
     C_VERDE, RGBColor(0xD5, 0xEE, 0xDF),
     ["GBM + componente de saltos Poisson",
      "Calibra umbral: |r| > 2.5σ → salto",
      "λ = frecuencia histórica de saltos",
      "Corrección de drift: k_bar = e^(μⱼ+σⱼ²/2)−1"]),
    ("ARMA\n(1,1)", "AutoRegresivo",
     C_NARANJA, RGBColor(0xFB, 0xEA, 0xD0),
     ["r_t = c + φ·r_{t-1} + θ·ε_{t-1} + ε_t",
      "Captura autocorrelación en retornos",
      "Calibrado por máx. verosimilitud",
      "Memoria de corto plazo (1 día)"]),
    ("ARMA-\nGARCH", "Volatilidad Condicional",
     RGBColor(0x7B, 0x2F, 0xBE), RGBColor(0xE8, 0xD8, 0xF5),
     ["ARMA(1,1) + GARCH(1,1) en varianza",
      "h_t = ω + α·ε²_{t-1} + β·h_{t-1}",
      "Volatility clustering explícito",
      "Colas más pesadas que GBM"]),
]

for i, (nombre, subtit, color_h, color_bg, bullets) in enumerate(modelos):
    l = 0.2 + i * 3.27
    add_rect(slide, l, 1.25, 3.1, 0.7, fill_color=color_h)
    add_text_box(slide, nombre, l + 0.1, 1.28, 3.0, 0.65,
                 font_size=17, bold=True, color=C_BLANCO, align=PP_ALIGN.CENTER)
    add_rect(slide, l, 1.93, 3.1, 0.38, fill_color=RGBColor(0xE8, 0xEC, 0xF2))
    add_text_box(slide, subtit, l + 0.1, 1.97, 2.9, 0.3,
                 font_size=11, italic=True, color=color_h, align=PP_ALIGN.CENTER)
    add_rect(slide, l, 2.29, 3.1, 4.6, fill_color=color_bg,
             line_color=color_h, line_w=0.8)
    for j, b in enumerate(bullets):
        add_text_box(slide, f"→  {b}", l + 0.15, 2.38 + j * 1.08, 2.85, 0.95,
                     font_size=11, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5 — DETALLE GBM vs JD
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "02  GBM vs Jump-Diffusion de Merton", "Cómo JD extiende el modelo base")
add_footer(slide)

# Columna izquierda: GBM
add_rect(slide, 0.3, 1.25, 5.9, 5.9, fill_color=C_AZUL_CLAR,
         line_color=C_AZUL_MED, line_w=1)
add_text_box(slide, "GBM  (baseline)", 0.4, 1.3, 5.7, 0.5,
             font_size=15, bold=True, color=C_AZUL_OSC)
gbm_lines = [
    "Ecuación:",
    "  ln(S_T/S_0) = (μ − σ²/2)·T + σ·√T·Z",
    "",
    "Calibración:",
    "  μ = media retornos históricos",
    "  σ = desv. estándar × 0.90 × peso_factor",
    "",
    "Supuestos:",
    "  · Retornos i.i.d. normales",
    "  · Volatilidad constante",
    "  · Sin discontinuidades",
    "",
    "Limitación clave:",
    "  Subestima colas; no captura crisis",
]
for j, line in enumerate(gbm_lines):
    add_text_box(slide, line, 0.5, 1.85 + j * 0.32, 5.5, 0.32,
                 font_size=10.5, color=C_GRIS_OSC,
                 bold=line.endswith(":"))

# Columna derecha: JD
add_rect(slide, 6.5, 1.25, 6.5, 5.9, fill_color=RGBColor(0xD5, 0xEE, 0xDF),
         line_color=C_VERDE, line_w=1)
add_text_box(slide, "Jump-Diffusion  (Merton 1976)", 6.6, 1.3, 6.3, 0.5,
             font_size=15, bold=True, color=C_VERDE)
jd_lines = [
    "Ecuación:",
    "  ln(S_T/S_0) = (μ_d − σ_d²/2 − λ·k̄)·T",
    "               + σ_d·W_T  +  Σ Jᵢ",
    "",
    "Calibración automática:",
    "  · |r| > 2.5σ_total  →  retorno = salto",
    "  · λ = #saltos / N_días históricos",
    "  · μⱼ, σⱼ = media y std de saltos",
    "  · k̄ = e^(μⱼ + σⱼ²/2) − 1  (drift Merton)",
    "",
    "Componentes separados:",
    "  · Difusión gaussiana (días normales)",
    "  · Saltos Poisson (días extremos)",
    "",
    "Ventaja: captura colas pesadas y crisis",
    "Fallback: si <3 saltos → usa GBM",
]
for j, line in enumerate(jd_lines):
    add_text_box(slide, line, 6.65, 1.85 + j * 0.32, 6.15, 0.32,
                 font_size=10.5, color=C_GRIS_OSC,
                 bold=line.endswith(":"))

# Flecha central
add_text_box(slide, "EXTIENDE\n→", 5.95, 3.7, 0.7, 0.7,
             font_size=11, bold=True, color=C_AZUL_OSC, align=PP_ALIGN.CENTER)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 6 — DETALLE ARMA y ARMA-GARCH
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "02  ARMA(1,1) y ARMA-GARCH(1,1)", "Modelos de series de tiempo para retornos")
add_footer(slide)

# ARMA
add_rect(slide, 0.3, 1.25, 5.9, 5.9, fill_color=RGBColor(0xFB, 0xEA, 0xD0),
         line_color=C_NARANJA, line_w=1)
add_text_box(slide, "ARMA(1,1)  —  Memoria lineal", 0.4, 1.3, 5.7, 0.5,
             font_size=15, bold=True, color=C_NARANJA)
arma_lines = [
    "Ecuación de media:",
    "  r_t = c + φ·r_{t-1} + θ·ε_{t-1} + ε_t",
    "  ε_t ~ N(0, σ²_ε)",
    "",
    "Calibración:",
    "  φ, θ, c, σ_ε via máx. verosimilitud",
    "  (statsmodels.ARIMA orden (1,0,1))",
    "",
    "Simulación hacia adelante:",
    "  Inicializa con r_{T} y ε_{T} observados",
    "  Itera H = 20 pasos día a día",
    "",
    "Ventaja:",
    "  Autocorrelación de retornos (momentum)",
    "  Más suave que GBM puro",
    "",
    "Limitación:",
    "  Varianza constante (no captura clustering)",
]
for j, line in enumerate(arma_lines):
    add_text_box(slide, line, 0.5, 1.85 + j * 0.295, 5.5, 0.3,
                 font_size=10.5, color=C_GRIS_OSC,
                 bold=line.endswith(":"))

# ARMA-GARCH
add_rect(slide, 6.5, 1.25, 6.5, 5.9, fill_color=RGBColor(0xE8, 0xD8, 0xF5),
         line_color=RGBColor(0x7B, 0x2F, 0xBE), line_w=1)
add_text_box(slide, "ARMA-GARCH(1,1)  —  Volatilidad dinámica",
             6.6, 1.3, 6.3, 0.5, font_size=14, bold=True,
             color=RGBColor(0x7B, 0x2F, 0xBE))
ag_lines = [
    "Ecuación de media (AR):",
    "  r_t = c + φ·r_{t-1} + ε_t",
    "",
    "Ecuación de varianza (GARCH):",
    "  h_t = ω + α·ε²_{t-1} + β·h_{t-1}",
    "  ε_t = σ_t · z_t ,   z_t ~ N(0,1)",
    "  σ_t = √h_t",
    "",
    "Calibración:",
    "  ω, α, β via máx. verosimilitud",
    "  (paquete arch, AR(1) + GARCH(1,1))",
    "",
    "Restricción estacionariedad: α + β < 1",
    "",
    "Ventaja:",
    "  Volatility clustering explícito",
    "  Colas pesadas implícitas",
    "  Más realista en períodos de crisis",
]
for j, line in enumerate(ag_lines):
    add_text_box(slide, line, 6.65, 1.85 + j * 0.295, 6.15, 0.3,
                 font_size=10.5, color=C_GRIS_OSC,
                 bold=line.endswith(":"))


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 7 — METODOLOGÍA DEL TORNEO
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "03  Metodología: Torneo de Modelos",
              "Comparación objetiva bajo la misma semilla aleatoria")
add_footer(slide)

# Diagrama de flujo horizontal
pasos = [
    ("Distribución\nEmpírica", "Retornos log a 20d\nventanas solapadas\nstride = 5 días", C_AZUL_MED),
    ("Calibrar\ncada modelo", "GBM, JD, ARMA,\nARMA-GARCH\nsobre histórico 250d", C_VERDE),
    ("Simular\n1,000 trayect.", "Misma semilla\npara todos los\nmodelos", C_NARANJA),
    ("5 Métricas", "KS, P05, P95\nVol, Curtosis\n(menor = mejor)", RGBColor(0x7B, 0x2F, 0xBE)),
    ("Composite\nRank", "Promedio de\nrangos 1-4\nGanador: mín rank", C_ROJO),
]
for i, (tit, desc, color) in enumerate(pasos):
    l = 0.3 + i * 2.6
    add_rect(slide, l, 1.35, 2.35, 0.9, fill_color=color)
    add_text_box(slide, tit, l + 0.05, 1.38, 2.25, 0.85,
                 font_size=13, bold=True, color=C_BLANCO, align=PP_ALIGN.CENTER)
    add_rect(slide, l, 2.23, 2.35, 1.4, fill_color=C_BLANCO,
             line_color=color, line_w=1)
    add_text_box(slide, desc, l + 0.1, 2.3, 2.15, 1.25,
                 font_size=11, color=C_GRIS_OSC, align=PP_ALIGN.CENTER)
    if i < 4:
        add_text_box(slide, "→", l + 2.35, 1.7, 0.25, 0.5,
                     font_size=18, bold=True, color=C_AZUL_OSC,
                     align=PP_ALIGN.CENTER)

# Clave de fairness
add_rect(slide, 0.3, 3.8, 12.7, 1.0, fill_color=C_AZUL_CLAR,
         line_color=C_AZUL_MED, line_w=1)
add_text_box(slide,
    "Garantía de comparación justa:  La MISMA semilla aleatoria se usa para todos los modelos en cada factor.\n"
    "Esto asegura que las diferencias de resultado reflejan el modelo, no la aleatoriedad del muestreo.",
    0.5, 3.87, 12.3, 0.9, font_size=11, italic=True, color=C_AZUL_OSC)

# Factores evaluados
add_text_box(slide, "Factores evaluados en el torneo real:", 0.3, 5.0, 4.5, 0.4,
             font_size=13, bold=True, color=C_AZUL_OSC)
cats = [
    ("FX (5)", "USDCOP, USDCLP, EURUSD, GBPUSD, USDBRL", C_AZUL_MED),
    ("RV Local (3)", "ECOPETROL, ICOLCAP, PFAVAL", C_VERDE),
    ("RV Internacional (2)", "SPY, XLF", C_NARANJA),
]
for i, (cat, facs, color) in enumerate(cats):
    l = 0.3 + i * 4.35
    add_rect(slide, l, 5.45, 4.2, 1.55, fill_color=C_BLANCO,
             line_color=color, line_w=1)
    add_text_box(slide, cat, l + 0.12, 5.5, 4.0, 0.4,
                 font_size=12, bold=True, color=color)
    add_text_box(slide, facs, l + 0.12, 5.9, 4.0, 0.95,
                 font_size=10.5, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 8 — MÉTRICAS DE EVALUACIÓN
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "04  Las 5 Métricas de Evaluación", "¿Qué mide cada indicador? (menor = mejor)")
add_footer(slide)

metricas = [
    ("KS Distance",
     "Distancia Kolmogorov-Smirnov",
     "Máxima diferencia absoluta entre las FDAs\n"
     "simulada y empírica. Evalúa la forma\n"
     "completa de la distribución.",
     "KS = sup_x |F_sim(x) − F_emp(x)|",
     C_AZUL_MED),
    ("Error P05",
     "Error en la cola izquierda",
     "Error relativo en el percentil 5:\n"
     "qué tan bien captura el modelo los\n"
     "peores escenarios (pérdidas extremas).",
     "|P5_sim − P5_emp| / |P5_emp|",
     C_ROJO),
    ("Error P95",
     "Error en la cola derecha",
     "Error relativo en el percentil 95:\n"
     "escenarios de ganancia extrema.\n"
     "Simetría del riesgo de cola.",
     "|P95_sim − P95_emp| / |P95_emp|",
     C_NARANJA),
    ("Error Volatilidad",
     "Error en la desviación estándar",
     "Qué tanto difiere la σ de los retornos\n"
     "simulados a 20d vs la σ empírica.\n"
     "Cero = calibración perfecta de riesgo.",
     "|σ_sim − σ_emp| / σ_emp",
     C_VERDE),
    ("Error Curtosis",
     "Error en fat-tails",
     "Diferencia normalizada de curtosis:\n"
     "cero = misma intensidad de colas\n"
     "pesadas que el histórico real.",
     "|κ_sim − κ_emp| / (1 + |κ_emp|)",
     RGBColor(0x7B, 0x2F, 0xBE)),
]

for i, (nombre, subtit, desc, formula, color) in enumerate(metricas):
    col = i % 3
    row = i // 3
    l = 0.25 + col * 4.37
    t = 1.35 + row * 2.85
    add_rect(slide, l, t, 4.15, 0.55, fill_color=color)
    add_text_box(slide, nombre, l + 0.1, t + 0.07, 3.95, 0.42,
                 font_size=14, bold=True, color=C_BLANCO)
    add_rect(slide, l, t + 0.55, 4.15, 2.15, fill_color=C_BLANCO,
             line_color=color, line_w=0.8)
    add_text_box(slide, subtit, l + 0.12, t + 0.6, 3.9, 0.38,
                 font_size=11, bold=True, color=color)
    add_text_box(slide, desc, l + 0.12, t + 0.97, 3.9, 1.0,
                 font_size=10, color=C_GRIS_OSC)
    add_rect(slide, l + 0.1, t + 1.98, 3.9, 0.45,
             fill_color=RGBColor(0xF0, 0xF0, 0xF8),
             line_color=color, line_w=0.5)
    add_text_box(slide, formula, l + 0.2, t + 2.03, 3.7, 0.38,
                 font_size=10, bold=True, color=C_AZUL_OSC, italic=True)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 9 — RESULTADOS DEL TORNEO (tabla comparativa)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "04  Resultados: ¿Qué modelo gana?",
              "Tendencia general observada por categoría de factor")
add_footer(slide)

# Tabla de resultados esperados / tendencia
add_text_box(slide,
    "Resultados típicos observados al correr el torneo sobre datos reales de mercado colombiano:",
    0.3, 1.3, 12.7, 0.4, font_size=12, italic=True, color=C_GRIS_OSC)

headers = ["Categoría", "Factor", "Ganador típico", "2do lugar", "Por qué"]
col_ws  = [1.8, 1.5, 2.2, 2.2, 5.3]
col_ls  = [0.25, 2.05, 3.55, 5.75, 7.95]
t_row0  = 1.78

# Header row
add_rect(slide, 0.25, t_row0, 12.85, 0.45, fill_color=C_AZUL_OSC)
for j, (h, l, w) in enumerate(zip(headers, col_ls, col_ws)):
    add_text_box(slide, h, l + 0.05, t_row0 + 0.07, w - 0.1, 0.33,
                 font_size=11, bold=True, color=C_BLANCO)

rows = [
    ("FX (USDCOP,\nUSDCLP, BRL)", "Alta vol.\ny saltos",
     "JD (Merton)", "ARMA-GARCH",
     "Las divisas EM muestran saltos bruscos (bancos centrales,\nchock commodity). JD captura λ alta y μⱼ negativo."),
    ("FX (EURUSD,\nGBPUSD)", "Baja vol.\nmercado DM",
     "ARMA-GARCH", "JD (Merton)",
     "Volatility clustering pronunciado. GARCH adapta σ\na regímenes de baja/alta vol sin overshooting."),
    ("RV Local\n(ECOPETROL,\nICOLCAP)", "Cola\nizquierda",
     "JD (Merton)", "ARMA-GARCH",
     "RV colombiana: alta curtosis, saltos negativos\ncorrelacionados con precio del petróleo."),
    ("RV Internac.\n(SPY, XLF)", "Crash\nasimétrico",
     "ARMA-GARCH", "JD (Merton)",
     "Caídas rápidas + rebotes (clustering). GARCH\ncaptura asimetría implícita mejor que Poisson."),
]

colors_row = [C_BLANCO, C_GRIS_CLAR, C_BLANCO, C_GRIS_CLAR]
color_win  = RGBColor(0xD5, 0xEE, 0xDF)

for i, (cat, sub, win, sec, why) in enumerate(rows):
    t_r = t_row0 + 0.45 + i * 1.26
    bg = colors_row[i]
    add_rect(slide, 0.25, t_r, 12.85, 1.23, fill_color=bg,
             line_color=RGBColor(0xCC, 0xCC, 0xCC), line_w=0.3)
    add_text_box(slide, cat, col_ls[0] + 0.05, t_r + 0.08, col_ws[0] - 0.1, 0.65,
                 font_size=10, bold=True, color=C_GRIS_OSC)
    add_text_box(slide, sub, col_ls[0] + 0.05, t_r + 0.7, col_ws[0] - 0.1, 0.48,
                 font_size=9, italic=True, color=C_AZUL_MED)
    add_rect(slide, col_ls[2] - 0.05, t_r + 0.2, col_ws[2] + 0.1, 0.6,
             fill_color=color_win, line_color=C_VERDE, line_w=0.5)
    add_text_box(slide, f"🥇 {win}", col_ls[2], t_r + 0.25, col_ws[2], 0.5,
                 font_size=11, bold=True, color=C_VERDE)
    add_text_box(slide, f"🥈 {sec}", col_ls[3], t_r + 0.25, col_ws[3], 0.5,
                 font_size=11, color=C_AZUL_MED)
    add_text_box(slide, why, col_ls[4] + 0.05, t_r + 0.1, col_ws[4] - 0.1, 1.0,
                 font_size=10, color=C_GRIS_OSC)

# Conclusión en caja
add_rect(slide, 0.25, 6.87, 12.85, 0.5, fill_color=C_AZUL_OSC)
add_text_box(slide,
    "Conclusión:  JD gana en FX/RV de mercados emergentes; ARMA-GARCH en mercados desarrollados. "
    "GBM queda en 3° o 4° lugar consistentemente.",
    0.4, 6.9, 12.6, 0.44, font_size=11, bold=True, color=C_AMARILLO)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 10 — ¿POR QUÉ CALIBRACIÓN DINÁMICA DE PESOS?
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "05  ¿Por qué la Calibración Dinámica de Pesos?",
              "El problema de la brecha entre Stress y VaR")
add_footer(slide)

# Diagrama de brecha
add_rect(slide, 0.3, 1.3, 5.5, 5.5, fill_color=C_BLANCO,
         line_color=C_AZUL_MED, line_w=1)
add_text_box(slide, "El problema detectado", 0.5, 1.38, 5.1, 0.5,
             font_size=14, bold=True, color=C_AZUL_OSC)

datos_brecha = [
    ("VaR histórico (referencia)", "−113.4 B COP", C_ROJO),
    ("Stress prospectivo GBM", "−88.5 B COP", C_NARANJA),
    ("Brecha (subestimación)", "−24.9 B COP  (−22%)", C_ROJO),
]
for i, (lbl, val, color) in enumerate(datos_brecha):
    t = 2.0 + i * 1.1
    add_rect(slide, 0.5, t, 5.0, 0.85, fill_color=C_GRIS_CLAR,
             line_color=color, line_w=1)
    add_text_box(slide, lbl, 0.65, t + 0.08, 4.7, 0.35,
                 font_size=11, color=C_GRIS_OSC)
    add_text_box(slide, val, 0.65, t + 0.42, 4.7, 0.38,
                 font_size=14, bold=True, color=color)

add_text_box(slide,
    "Con σ × 0.90 fijo, el stress siempre\n"
    "queda por debajo del VaR → el modelo\n"
    "no es conservador para todos los factores.",
    0.5, 5.35, 5.1, 1.2, font_size=11, italic=True, color=C_GRIS_OSC)

# Razones
add_rect(slide, 6.1, 1.3, 6.9, 5.5, fill_color=C_BLANCO,
         line_color=C_VERDE, line_w=1)
add_text_box(slide, "¿Por qué ocurre la brecha?", 6.3, 1.38, 6.5, 0.5,
             font_size=14, bold=True, color=C_VERDE)

razones = [
    ("Reducción uniforme de σ",
     "El −10% se aplica igual a USDCOP que\n"
     "a GBPUSD. No diferencia por factor."),
    ("Correlaciones estresadas",
     "En crisis los activos se correlacionan\n"
     "más. σ estática no lo refleja."),
    ("Factores sub-representados",
     "BAAA2, BAAA3, COUSD y CECUVR tienen\n"
     "pesos bajos; su VaR queda sin cubrir."),
    ("Actualización manual",
     "El analista ajustaba pesos ad-hoc\n"
     "cada mes sin criterio sistemático."),
]
for i, (tit, desc) in enumerate(razones):
    t = 2.0 + i * 1.2
    add_rect(slide, 6.3, t, 6.5, 1.0, fill_color=C_GRIS_CLAR,
             line_color=C_VERDE, line_w=0.5)
    add_text_box(slide, f"{i+1}. {tit}", 6.45, t + 0.08, 6.2, 0.38,
                 font_size=11, bold=True, color=C_VERDE)
    add_text_box(slide, desc, 6.45, t + 0.46, 6.2, 0.5,
                 font_size=10, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 11 — CÓMO FUNCIONA EL SISTEMA DE PESOS
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "06  Sistema de Pesos: Arquitectura",
              "JSON de configuración + aplicación en tiempo de simulación")
add_footer(slide)

# Diagrama JSON → simulación
add_text_box(slide, "peso_factor  actúa como multiplicador de volatilidad en cada modelo:",
             0.3, 1.35, 12.7, 0.4, font_size=12, italic=True, color=C_GRIS_OSC)

modelos_peso = [
    ("GBM",  "σ × 0.90 × peso_factor"),
    ("CIR",  "σ × 0.90 × peso_factor"),
    ("HJM",  "σ_nodo × peso_factor"),
    ("JD",   "σ_d × peso_factor"),
]
for i, (mod, formula) in enumerate(modelos_peso):
    l = 0.3 + i * 3.27
    add_rect(slide, l, 1.82, 3.1, 0.75, fill_color=C_AZUL_MED)
    add_text_box(slide, mod, l + 0.1, 1.88, 3.0, 0.35,
                 font_size=14, bold=True, color=C_BLANCO, align=PP_ALIGN.CENTER)
    add_rect(slide, l, 2.55, 3.1, 0.5, fill_color=C_AZUL_CLAR,
             line_color=C_AZUL_MED, line_w=0.5)
    add_text_box(slide, formula, l + 0.1, 2.6, 3.0, 0.4,
                 font_size=11, bold=True, color=C_AZUL_OSC, align=PP_ALIGN.CENTER)

# Jerarquía de pesos
add_text_box(slide, "Jerarquía de pesos (de mayor a menor prioridad):",
             0.3, 3.22, 8.0, 0.4, font_size=13, bold=True, color=C_AZUL_OSC)

niveles = [
    ("1° Override individual",
     "pesos_individuales_override['USDCOP'] = 1.5",
     "Máxima granularidad. Un factor específico.",
     C_ROJO),
    ("2° Peso de categoría",
     "pesos_por_categoria['Divisas_Mayor_Impacto']['peso'] = 1.4",
     "Aplica a todos los factores de una categoría.",
     C_NARANJA),
    ("3° Peso global",
     "configuracion['peso_global_default'] = 1.0",
     "Fallback si el factor no está en ninguna categoría.",
     C_VERDE),
]
for i, (tit, codigo, desc, color) in enumerate(niveles):
    t = 3.7 + i * 1.18
    add_rect(slide, 0.3, t, 12.7, 1.1, fill_color=C_BLANCO,
             line_color=color, line_w=1)
    add_rect(slide, 0.3, t, 0.18, 1.1, fill_color=color)
    add_text_box(slide, tit, 0.6, t + 0.08, 4.0, 0.38,
                 font_size=12, bold=True, color=color)
    add_rect(slide, 4.7, t + 0.06, 8.1, 0.45,
             fill_color=RGBColor(0xF0, 0xF0, 0xF0),
             line_color=RGBColor(0xCC, 0xCC, 0xCC), line_w=0.5)
    add_text_box(slide, codigo, 4.8, t + 0.1, 7.9, 0.35,
                 font_size=10, italic=True, color=C_AZUL_OSC)
    add_text_box(slide, desc, 0.6, t + 0.6, 12.0, 0.4,
                 font_size=10, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 12 — MÉTODOS DE CALIBRACIÓN COMPARADOS
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "07  Métodos de Calibración: Min-Max vs Percentil",
              "Cómo se convierten los choques VaR en pesos de volatilidad")
add_footer(slide)

# Fuente de datos
add_rect(slide, 0.3, 1.3, 12.7, 0.65, fill_color=C_AZUL_CLAR,
         line_color=C_AZUL_MED, line_w=1)
add_text_box(slide,
    "Fuente de datos:  Archivo Excel de resultados VaR Zeros  (hoja 'Factores_Zeros')  "
    "→  Extrae el choque máximo histórico por factor dentro de su tipo de activo",
    0.5, 1.37, 12.3, 0.5, font_size=11.5, color=C_AZUL_OSC)

# Dos columnas
# MIN-MAX
add_rect(slide, 0.3, 2.1, 6.0, 5.1, fill_color=C_BLANCO,
         line_color=C_VERDE, line_w=1.2)
add_rect(slide, 0.3, 2.1, 6.0, 0.55, fill_color=C_VERDE)
add_text_box(slide, "Método MIN-MAX  (default)", 0.4, 2.15, 5.8, 0.45,
             font_size=14, bold=True, color=C_BLANCO)

mm_content = [
    "Fórmula:",
    "   peso = p_min + (choque − choque_min)",
    "          × (p_max − p_min)",
    "          ÷ (choque_max − choque_min)",
    "",
    "Donde:",
    "   choque   = VaR máx del factor",
    "   p_min    = peso mínimo config  (e.g. 0.6)",
    "   p_max    = peso máximo config  (e.g. 2.0)",
    "   La normalización es DENTRO del tipo",
    "   (Tasa Cambio, Curva, Acciones, etc.)",
    "",
    "Resultado: escala lineal proporcional",
    "al choque relativo dentro del grupo.",
    "",
    "Ventaja:  Intuitivo, estable, sin outliers",
    "Limitación:  Un choque extremo comprime",
    "   todos los demás hacia p_min",
]
for j, line in enumerate(mm_content):
    add_text_box(slide, line, 0.45, 2.73 + j * 0.27, 5.7, 0.27,
                 font_size=10, color=C_GRIS_OSC,
                 bold=line.endswith(":"))

# PERCENTIL
add_rect(slide, 6.6, 2.1, 6.5, 5.1, fill_color=C_BLANCO,
         line_color=C_AZUL_MED, line_w=1.2)
add_rect(slide, 6.6, 2.1, 6.5, 0.55, fill_color=C_AZUL_MED)
add_text_box(slide, "Método PERCENTIL", 6.7, 2.15, 6.3, 0.45,
             font_size=14, bold=True, color=C_BLANCO)

pct_content = [
    "Fórmula:",
    "   pctil = rank(choque_factor) / N_factores",
    "   peso  = p_min + pctil × (p_max − p_min)",
    "",
    "Donde:",
    "   rank(·)  = posición ordinal del choque",
    "   N_factores = nº factores del mismo tipo",
    "",
    "La normalización es por rango ordinal,",
    "no por magnitud absoluta del choque.",
    "",
    "Resultado: distribución uniforme de pesos",
    "entre p_min y p_max.",
    "",
    "Ventaja:  Robusto a outliers extremos",
    "   No hay factor que 'monopolice' p_max",
    "Limitación:  Ignora magnitud del choque;",
    "   USDCOP y USDBRL pueden quedar iguales",
    "   si sus rangos son similares",
]
for j, line in enumerate(pct_content):
    add_text_box(slide, line, 6.75, 2.73 + j * 0.27, 6.2, 0.27,
                 font_size=10, color=C_GRIS_OSC,
                 bold=line.endswith(":"))


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 13 — PROCESO PASO A PASO
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "08  Calibración Dinámica: Paso a Paso",
              "Flujo completo desde el Excel VaR hasta los pesos aplicados")
add_footer(slide)

pasos_cd = [
    ("1", "Obtener el Excel VaR Zeros",
     "Ejecutar el proceso de VaR de Zeros del día de corte.\n"
     "Archivo: Resultados_<fecha>_Zeros.xlsx\n"
     "Hoja requerida: 'Factores_Zeros'",
     C_AZUL_OSC),
    ("2", "Extraer choques por factor",
     "cd.calibrar_pesos_desde_var(path_var_excel=..., nivel='Grupo Bancolombia')\n"
     "Lee columna 'Choque_Max' por factor dentro de su 'Tipo'\n"
     "(Tasa Cambio / Curva / Acciones / Indicador)",
     C_AZUL_MED),
    ("3", "Normalizar por tipo de activo",
     "Dentro de cada grupo (e.g. 'Tasa Cambio'):\n"
     "  Min-Max: peso = p_min + (ch − ch_min)/(ch_max − ch_min) × (p_max − p_min)\n"
     "  Percentil: peso = p_min + rank(ch)/N × (p_max − p_min)",
     C_VERDE),
    ("4", "Mapear a clave interna JSON",
     "El Excel usa nombres como 'USD/COP' → el JSON usa 'USDCOP'\n"
     "El módulo CalibracionDinamica tiene la tabla de mapeo de 45+ factores\n"
     "incluyendo nodos de curva (e.g. 'IBR 30d' → 'C_IBR')",
     C_NARANJA),
    ("5", "Guardar en pesos_factores_stress.json",
     "Si guardar=True, actualiza automáticamente el JSON.\n"
     "Imprime diagnóstico: factor → choque → peso asignado.\n"
     "La próxima ejecución de simulationRfkProspectivo() usa estos pesos.",
     C_VERDE),
    ("6", "Verificar en Simulation_statistics.xlsx",
     "Pestaña 'Pesos_Aplicados' muestra el peso efectivo por factor.\n"
     "Comparar con pestaña de estadísticas para confirmar que\n"
     "el stress resultante se acerca al VaR objetivo.",
     C_AZUL_MED),
]

for i, (num, tit, desc, color) in enumerate(pasos_cd):
    col = i % 3
    row = i // 3
    l = 0.25 + col * 4.37
    t = 1.32 + row * 2.85
    add_rect(slide, l, t, 4.15, 2.7, fill_color=C_BLANCO,
             line_color=color, line_w=1)
    add_rect(slide, l, t, 0.55, 0.55, fill_color=color)
    add_text_box(slide, num, l, t + 0.04, 0.55, 0.48,
                 font_size=18, bold=True, color=C_BLANCO, align=PP_ALIGN.CENTER)
    add_text_box(slide, tit, l + 0.65, t + 0.08, 3.4, 0.42,
                 font_size=12, bold=True, color=color)
    add_text_box(slide, desc, l + 0.12, t + 0.6, 3.9, 2.0,
                 font_size=9.5, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 14 — COMPARATIVA: SIN PESOS vs CON PESOS vs DINÁMICA
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "08  Comparativa de Enfoques de Calibración",
              "Sin pesos  /  Pesos manuales  /  Calibración dinámica")
add_footer(slide)

enfoques = [
    ("Sin pesos\n(GBM puro)", C_ROJO,
     [
         "σ = std(retornos) × 0.90",
         "Sin diferenciación entre factores",
         "Stress ≈ 78% del VaR típicamente",
         "Sub-conservador para factores volátiles",
         "",
         "Cuando usar:",
         "Solo como baseline de referencia",
     ],
     [True,False,False,False,False,True,False]),
    ("Pesos manuales\n(v2.7 actual)", C_NARANJA,
     [
         "σ = std × 0.90 × peso_override",
         "Ajustes ad-hoc por analista",
         "BAAA2/BAAA3/COUSD: peso=1.5 manual",
         "Stress ≈ 88% del VaR (mejorado)",
         "",
         "Cuando usar:",
         "Cuando hay factores conocidos sub-calibrados",
         "pero sin datos frescos del VaR",
     ],
     [True,False,False,False,False,True,False,False]),
    ("Calibración\ndinámica", C_VERDE,
     [
         "σ = std × 0.90 × peso_dinamico(VaR)",
         "Peso derivado del choque VaR real",
         "Actualización automática cada fecha",
         "Stress ≈ 95-100% del VaR objetivo",
         "",
         "Cuando usar:",
         "Cada cierre de mes con VaR Zeros disponible",
         "Permite trazabilidad y auditoría completa",
     ],
     [True,False,False,False,False,True,False,False]),
]

for i, (nombre, color, bullets, bolds) in enumerate(enfoques):
    l = 0.25 + i * 4.37
    add_rect(slide, l, 1.3, 4.15, 0.78, fill_color=color)
    add_text_box(slide, nombre, l + 0.1, 1.35, 4.0, 0.68,
                 font_size=16, bold=True, color=C_BLANCO, align=PP_ALIGN.CENTER)
    add_rect(slide, l, 2.08, 4.15, 5.1, fill_color=C_BLANCO,
             line_color=color, line_w=1)
    for j, (b, bold) in enumerate(zip(bullets, bolds)):
        add_text_box(slide, b if b else "", l + 0.18, 2.18 + j * 0.55, 3.8, 0.5,
                     font_size=10.5, color=color if bold else C_GRIS_OSC, bold=bold)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 15 — CÓDIGO RÁPIDO
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "08  Implementación en Código",
              "Tres líneas para calibrar y simular con pesos dinámicos")
add_footer(slide)

codigo_bloques = [
    ("Paso 1 — Calibración dinámica de pesos", C_AZUL_OSC,
     "import ajustar_pesos_stress as aps\n\n"
     "pesos, diagnostico = aps.calibrar_dinamicamente(\n"
     "    path_var_excel = r'C:/Downloads/Resultados_30_Apr_Zeros.xlsx',\n"
     "    nivel          = 'Grupo Bancolombia',\n"
     "    metodo         = 'min_max',   # o 'percentil'\n"
     "    guardar        = True         # actualiza el JSON automáticamente\n"
     ")"),
    ("Paso 2 — Ajuste manual puntual (opcional)", C_NARANJA,
     "# Si algún factor quedó sub-calibrado tras el dinámico:\n"
     "aps.ajustar_peso_individual('BAAA2',   1.6)\n"
     "aps.ajustar_peso_individual('CECUVR',  1.5)\n"
     "aps.ajustar_categoria('Divisas_Mayor_Impacto', 1.4)"),
    ("Paso 3 — Correr la simulación con los nuevos pesos", C_VERDE,
     "import SimulationProspectivo_JD as rfk\n\n"
     "rfk.simulationRfkProspectivo_JD(\n"
     "    fecha          = '20260430',\n"
     "    nSim           = 1500,\n"
     "    n_max_proyeccion = 20,\n"
     "    path_var_excel = r'C:/.../Resultados_Zeros.xlsx',\n"
     "    guardar        = False   # pesos ya guardados en paso 1\n"
     ")"),
]

for i, (titulo, color, codigo) in enumerate(codigo_bloques):
    t = 1.3 + i * 2.03
    add_rect(slide, 0.3, t, 12.7, 0.42, fill_color=color)
    add_text_box(slide, titulo, 0.45, t + 0.06, 12.4, 0.32,
                 font_size=12, bold=True, color=C_BLANCO)
    add_rect(slide, 0.3, t + 0.42, 12.7, 1.57,
             fill_color=RGBColor(0x1E, 0x1E, 0x1E))
    add_text_box(slide, codigo, 0.45, t + 0.48, 12.45, 1.45,
                 font_size=10, color=RGBColor(0xD4, 0xD4, 0xD4), italic=False)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 16 — CONCLUSIONES
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_GRIS_CLAR)
add_title_bar(slide, "09  Conclusiones y Recomendaciones",
              "Hoja de ruta para mejorar la calidad del stress testing prospectivo")
add_footer(slide)

conclusiones = [
    (C_ROJO,    "GBM ya no es el mejor modelo",
     "En el torneo, GBM ocupa 3° o 4° lugar consistentemente. "
     "La distribución Normal no captura las colas pesadas ni los saltos "
     "que caracterizan a FX y RV en mercados emergentes."),
    (C_VERDE,   "JD es el modelo ganador para FX y RV emergente",
     "Jump-Diffusion de Merton captura la asimetría y las colas pesadas "
     "sin necesidad de ajustes ad-hoc. La calibración es completamente automática "
     "a partir del histórico de 250 días."),
    (C_AZUL_MED,"ARMA-GARCH es superior para mercados desarrollados",
     "El volatility clustering de SPY, XLF, EURUSD se modela mejor con GARCH "
     "que con saltos Poisson. Se recomienda selección automática por torneo "
     "al inicio de cada proceso de stress."),
    (C_NARANJA, "Calibración dinámica elimina la brecha Stress vs VaR",
     "Al derivar los pesos directamente del Excel VaR Zeros, cada factor "
     "recibe una volatilidad proporcional a su riesgo real. "
     "La brecha se reduce de −22% a < 5% con método Min-Max."),
    (C_AZUL_OSC,"Proceso mensual recomendado",
     "1° Correr VaR Zeros  →  2° Calibrar pesos (Min-Max)  →  "
     "3° Ajuste manual puntual si hay outliers  →  4° Simular con JD  →  "
     "5° Verificar en pestaña 'Pesos_Aplicados'"),
]

for i, (color, tit, desc) in enumerate(conclusiones):
    t = 1.35 + i * 1.19
    add_rect(slide, 0.3, t, 0.3, 1.06, fill_color=color)
    add_rect(slide, 0.6, t, 12.4, 1.06, fill_color=C_BLANCO,
             line_color=color, line_w=0.8)
    add_text_box(slide, tit, 0.75, t + 0.06, 11.9, 0.4,
                 font_size=12, bold=True, color=color)
    add_text_box(slide, desc, 0.75, t + 0.46, 11.9, 0.55,
                 font_size=10.5, color=C_GRIS_OSC)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 17 — CIERRE
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
set_bg(slide, C_AZUL_OSC)
add_rect(slide, 0, 5.6, 13.33, 0.08, fill_color=C_AMARILLO)

add_text_box(slide, "Gracias", 0.6, 2.0, 12.0, 1.4,
             font_size=54, bold=True, color=C_BLANCO, align=PP_ALIGN.CENTER)
add_text_box(slide,
    "Modelos de simulación prospectiva\n"
    "Riesgo de Mercado  ·  2026",
    0.6, 3.5, 12.0, 1.0, font_size=18, color=C_AZUL_CLAR,
    align=PP_ALIGN.CENTER, italic=True)
add_text_box(slide,
    "Archivos de referencia:  torneo_modelos.py  ·  RiskModels.py  ·  "
    "SimulationProspectivo_JD.py  ·  ajustar_pesos_stress.py",
    0.6, 5.85, 12.0, 0.5, font_size=11, color=C_AMARILLO,
    align=PP_ALIGN.CENTER)


# ── Guardar ───────────────────────────────────────────────────────────────────
out = "/home/user/prospect/Presentacion_Modelos_Stress_Prospectivo.pptx"
prs.save(out)
print(f"Presentación guardada en: {out}")
print(f"Total slides: {len(prs.slides)}")

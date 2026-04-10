import json
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from flask import send_file
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.platypus import Image
from reportlab.platypus import PageTemplate, Frame
from reportlab.pdfgen import canvas
import os
from flask import current_app
import mercadopago

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
APP_URL = os.environ.get("APP_URL", "http://localhost:5000")

def add_page_number(canvas, doc):
    page_num = canvas.getPageNumber()
    text = f"Página {page_num}"
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0] - 2*cm, 1.5*cm, text)

DATA_PATH = Path("data/questions.json")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

ALAS = {
    1: (9, 2),
    2: (1, 3),
    3: (2, 4),
    4: (3, 5),
    5: (4, 6),
    6: (5, 7),
    7: (6, 8),
    8: (7, 9),
    9: (8, 1),
}

DESCRIPCION_ALAS = {
    "1w9": "Más tranquilo, idealista, moral, reservado.",
    "1w2": "Más servicial, orientado a ayudar, más expresivo.",
    "2w1": "Más responsable, ético, estructurado.",
    "2w3": "Más sociable, carismático, orientado al éxito.",
    "3w2": "Encantador, enfocado en la imagen y relaciones.",
    "3w4": "Más introspectivo, creativo, busca autenticidad.",
    "4w3": "Más expresivo, artístico, orientado a destacar.",
    "4w5": "Más introspectivo, profundo, reservado.",
    "5w4": "Creativo, sensible, más emocional.",
    "5w6": "Analítico, estratégico, más racional y cauteloso.",
    "6w5": "Más intelectual, prudente, observador.",
    "6w7": "Más sociable, inquieto, busca seguridad en grupos.",
    "7w6": "Más responsable y colaborador.",
    "7w8": "Más fuerte, independiente y dominante.",
    "8w7": "Más enérgico, impulsivo, expansivo.",
    "8w9": "Más calmado, protector, firme pero estable.",
    "9w8": "Más firme, protector, práctico.",
    "9w1": "Más idealista, organizado y correcto.",
}

VIRTUDES_POR_TIPO = {
    1: "Organizar",
    2: "Escuchar",
    3: "Arriesgar",
    4: "Emocionar",
    5: "Razonar",
    6: "Asegurar",
    7: "Hablar",
    8: "Ejecutar",
    9: "Presente en el aquí y ahora",
}

EJES_SIMETRIA = {
    "SER": {"tipos": [4, 5], "antidoto": "Participar"},
    "TENER": {"tipos": [3, 6], "antidoto": "Relajación"},
    "COMUNICAR": {"tipos": [2, 7], "antidoto": "Diálogo"},
    "HACER": {"tipos": [1, 8], "antidoto": "Consenso"},
    "ESTAR": {"tipos": [9], "antidoto": "Compromiso"},
}

ORDEN_EJES = ["HACER", "COMUNICAR", "TENER", "SER", "ESTAR"]
MEDIA_TEO = 11.1
TOL = 0.1  # permite 11.0–11.2 como “equilibrado/desarrollado”

def es_desarrollado(valor: float) -> bool:
    return valor >= (MEDIA_TEO - TOL)

def es_bajo(valor: float) -> bool:
    return valor < (MEDIA_TEO - TOL)

def load_questions():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    questions = data["questions"]
    # nos quedamos solo con las que tienen type 1..9
    questions = [q for q in questions if q.get("type") in range(1, 10)]
    return questions
    
EJES_AFINIDAD = {
    
    "RESPONSABILIDAD": {
        "tipos": [1, 6],
        "descripcion": "El eje de RESPONSABILIDAD describe el sentido del deber, compromiso, ética y lealtad. Se busca seguridad a través del cumplimiento y la coherencia.",
        "perfil_alto": "En lo personal, sueles sostenerte en la coherencia, el deber y la confiabilidad. Te cuesta relajarte o soltar el control. En lo profesional, destacas por responsabilidad, seguimiento, cumplimiento y mirada preventiva. Riesgo: rigidez o exceso de carga.",
        "perfil_bajo": "En lo personal, puede costarte sostener hábitos, disciplina o compromisos sin sentir presión o culpa. En lo profesional, el desafío es sostener consistencia, procesos y acuerdos, evitando postergar o improvisar.",
    },
    "DISTANCIA": {
        "tipos": [2, 5],
        "descripcion": "El eje de DISTANCIA describe el manejo del vínculo desde la regulación de la cercanía. Uno de los atributos se acerca cuidando y el otro se aleja para proteger su energía.",
        "perfil_alto": "En lo personal, regulas la intimidad con claridad: sabes cuándo acercarte y cuándo tomar distancia. Riesgo: irte a extremos. En lo profesional, puedes vincularte con empatía sin perder foco, o sostener límites sanos y autonomía intelectual.",
        "perfil_bajo": "En lo personal, puede haber confusión en límites: o te sobreinvolucras, o te aíslas sin darte cuenta. En lo profesional, el desafío es manejar cercanía con clientes/equipo sin agotarte ni desconectarte.",
    },
    "PODER": {
        "tipos": [3, 8],
        "descripcion": "El eje de PODER describe la fuerza, el impacto y la orientación a resultados. Uno expresa poder por logro e imagen; el otro por liderazgo directo y control.",
        "perfil_alto": "En lo personal, tiendes a tomar el mando, avanzar y proteger lo tuyo. Riesgo: dureza o exceso de control. En lo profesional, destacas en ejecución, liderazgo, negociación y logro de objetivos. Riesgo: intensidad o intolerancia al error.",
        "perfil_bajo": "En lo personal, puede costarte tomar tu lugar, poner límites o sostener decisiones con firmeza. En lo profesional, el desafío es liderazgo, asertividad y ejecución consistente.",
    },
    "LIBERTAD": {
        "tipos": [4, 7],
        "descripcion": "El eje de LIBERTAD describe la búsqueda de experiencia y autenticidad. Uno busca libertad emocional y expresión auténtica; el otro libertad de opciones y experiencias.",
        "perfil_alto": "En lo personal, necesitas espacio interno para sentir y elegir. Riesgo: dispersión o dramatización. En lo profesional, destacas en creatividad, ideas y expansión. Riesgo: falta de estructura o constancia.",
        "perfil_bajo": "En lo personal, puede costarte conectar con deseo propio, autenticidad o disfrute sin culpa. En lo profesional, el desafío es innovar, permitir creatividad y sostener motivación.",
    },
    "INTEGRADOR": {
        "tipos": [9],
        "descripcion": "El eje de INTEGRADOR funciona como punto de integración y armonización: mediación, síntesis y capacidad de unir extremos.",
        "perfil_alto": "En lo personal, tiendes a armonizar, bajar tensiones y sostener paz interna/externa. Riesgo: postergarte. En lo profesional, destacas como mediador, facilitador, integrador de equipos.",
        "perfil_bajo": "En lo personal, el desafío es presencia, decisión y sostener tu agenda sin diluirte. En lo profesional, el desafío es tomar postura, decidir y priorizar sin evitar el conflicto.",
    },
}


# ✅ palabras/virtudes para la síntesis (como pediste)
PALABRAS_AFINIDAD_POR_TIPO = {
    1: "responsabilidad moral (hacer lo correcto)",
    6: "responsabilidad hacia el grupo (seguridad y compromiso)",
    2: "acercamiento/cuidado (cercanía)",
    5: "distancia/autonomía (protección de energía)",
    3: "poder por logro/imagen",
    8: "poder directo (liderazgo/control)",
    4: "libertad emocional (expresión auténtica)",
    7: "libertad de opciones/experiencias",
    9: "integración/armonía (mediación natural)",
}

OPUESTOS_COMPLEMENTARIOS = {
    "ORDEN – AIRE": {
        "tipos": [1, 5],
        "descripcion": "El eje ORDEN – AIRE describe la organización de la realidad desde la estructura. Uno ordena lo externo; el otro estructura lo interno.",
        "virtudes": {1: "orden externo, controlar", 5: "orden interno, entender"},
        "msg_bajo": "Este eje aparece por debajo de la media, lo que indica dificultad para ordenar lo externo o estructurar lo interno de forma consistente. La persona debe establecer un nuevo orden en su vida. Revisar seriamente dónde pone su tiempo y energía.",
        "msg_equilibrado": "Este eje aparece equilibrado, lo que indica buena integración entre estructura externa y claridad interna.",
        "msg_alto": "Este eje aparece por encima de la media, lo que indica una fuerte capacidad de ordenar, planificar y estructurar; en exceso puede rigidizarse.",
        "luz": "En su luz: sensatez, coherencia, claridad, organización y profundidad.",
        "sombra": "En su sombra: juicio, rigidez, control mental o exceso de perfeccionismo/aislamiento, autocrítica.",
    },

    "RELACIÓN – AGUA": {
        "tipos": [2, 6],
        "descripcion": "El eje RELACIÓN – AGUA describe el intercambio vincular. Uno expresa el vínculo a través del dar; el otro desde la lealtad y el recibir.",
        "virtudes": {2: "dar, servir", 6: "recibir, sostener"},
        "msg_bajo": "Este eje aparece por debajo de la media, lo que indica dificultad para dar sin perderte o para recibir sin desconfianza.",
        "msg_equilibrado": "Este eje aparece equilibrado, lo que indica un intercambio vincular sano entre dar y recibir.",
        "msg_alto": "Este eje aparece por encima de la media, lo que indica fuerte orientación al vínculo; en exceso puede generar dependencia o hipervigilancia.",
        "luz": "En su luz: empatía, cooperación, sostén afectivo, compromiso y confianza.",
        "sombra": "En su sombra: dependencia, sobreentrega, miedo, control emocional o dependencia del vínculo.",
    },

    "IMAGEN – TIERRA": {
        "tipos": [3, 7],
        "descripcion": "El eje IMAGEN – TIERRA describe la proyección al mundo. Uno busca lograr; el otro expandirse y mostrarse.",
        "virtudes": {3: "lograr, emprender", 7: "relajar, disfrutar"},
        "msg_bajo": "Este eje aparece por debajo de la media, lo que indica dificultad para sostener motivación, proyección o visibilidad. La persona no está logrando concretar algo en su vida. Tiene que materializar.",
        "msg_equilibrado": "Este eje aparece equilibrado, lo que indica buena relación entre logro, presencia y expansión sin exceso de imagen.",
        "msg_alto": "Este eje aparece por encima de la media, lo que indica alta proyección externa; en exceso puede volverse superficial o compulsivo.",
        "luz": "En su luz: proactividad, ambición sana, entusiasmo, inspiración y concreción.",
        "sombra": "En su sombra: apariencia, adicción al éxito, dispersión, postureo o desconexión emocional.",
    },

    "FUERZA – FUEGO": {
        "tipos": [4, 8],
        "descripcion": "El eje FUERZA – FUEGO describe la intensidad vital. Uno canaliza fuerza interna; el otro expresa fuerza externa.",
        "virtudes": {4: "fuerza interna, crear, autoestima", 8: "fuerza externa, decidir"},
        "msg_bajo": "Este eje aparece por debajo de la media, lo que indica dificultad para sostener intensidad, límites o decisión. La persona está consumiendo su propia energía de reserva. Es propicio que se recargue conectando con la naturaleza y su lado espiritual.",
        "msg_equilibrado": "Este eje aparece equilibrado, lo que indica integración entre intensidad interna y acción externa.",
        "msg_alto": "Este eje aparece por encima de la media, lo que indica potencia y presencia; en exceso puede intensificarse como control o dramatismo.",
        "luz": "En su luz: firmeza, coraje, autenticidad, presencia y liderazgo con propósito.",
        "sombra": "En su sombra: egocentrismo, reactividad, dureza, victimismo o intensidad desbordada.",
    },

    "LUZ": {
        "tipos": [9],
        "descripcion": "El eje LUZ representa la integración y la plenitud como síntesis de los demás ejes.",
        "virtudes": {9: "plenitud"},
        "msg_bajo": "Este eje aparece por debajo de la media, lo que indica dificultad para sostener presencia, armonía y decisión.",
        "msg_equilibrado": "Este eje aparece equilibrado, lo que indica capacidad de integración, síntesis y serenidad activa.",
        "msg_alto": "Este eje aparece por encima de la media, lo que indica alta capacidad integradora; en exceso puede ser evitación del conflicto o postergación.",
        "luz": "En su luz: calma, integración, escucha, presencia y ecuanimidad.",
        "sombra": "En su sombra: anestesia, postergación, dilución personal o evitación.",
    },
}

def add_header_footer(canvas, doc):
    canvas.saveState()

    logo_path = os.path.join(current_app.root_path, "static", "img", "logo_az.png")

    canvas.drawImage(
        logo_path,
        2*cm,
        A4[1] - 2.2*cm,
        width=2*cm,
        height=2*cm,
        preserveAspectRatio=True,
        mask='auto'
    )

    canvas.setFont("Helvetica", 8)

    contacto = (
        "AZ Consultora\n"
        "@az_coaching.terapeutico\n"
        "+54 2975203761"
    )

    text_obj = canvas.beginText(A4[0] - 7*cm, A4[1] - 1.8*cm)
    for line in contacto.split("\n"):
        text_obj.textLine(line)
    canvas.drawText(text_obj)

    # Número de página
    page_num = canvas.getPageNumber()
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0] - 2*cm, 1.5*cm, f"Página {page_num}")

    canvas.restoreState()
    
# -----------------------------
# BONUS: Estructura del pensamiento
# -----------------------------

def _rank_3(values: dict) -> dict:
    """
    values: {"nombre": valor_float, ...} (3 items)
    retorna: dict con ranking MAYOR/MEDIO/MENOR, porcentaje y dominante
    """
    items = list(values.items())
    total = sum(v for _, v in items) or 1.0

    # orden por valor desc
    ordered = sorted(items, key=lambda x: x[1], reverse=True)

    ranking = {}
    for i, (k, v) in enumerate(ordered):
        pos = "MAYOR" if i == 0 else ("MENOR" if i == 2 else "MEDIO")
        ranking[k] = {
            "valor": round(v, 1),
            "porcentaje": round((v / total) * 100, 1),
            "posicion": pos,
        }

    dominante = ordered[0][0]
    return {"dominante": dominante, "detalle": ranking}


def bonus_pensamiento(porcentaje_scores: dict) -> dict:
    # Inductivo: 2-3-4 | Deductivo: 5-6-7 | Analógico: 8-9-1
    inductivo = sum(porcentaje_scores[t] for t in (2, 3, 4))
    deductivo = sum(porcentaje_scores[t] for t in (5, 6, 7))
    analogico = sum(porcentaje_scores[t] for t in (8, 9, 1))

    r = _rank_3({"Inductivo": inductivo, "Deductivo": deductivo, "Analógico": analogico})
    dom = r["dominante"]

    if dom == "Inductivo":
        parrafo = (
            "Tu pensamiento es predominantemente INDUCTIVO. Procesas la realidad desde la experiencia "
            "relacional y emocional. Captas matices humanos antes que estructuras lógicas."
        )
    elif dom == "Deductivo":
        parrafo = (
            "Tu pensamiento es predominantemente DEDUCTIVO. Analizas escenarios, evalúas riesgos y "
            "construyes decisiones desde la lógica y la previsión."
        )
    else:
        parrafo = (
            "Tu pensamiento es predominantemente ANALÓGICO. Integras información de manera global, "
            "estratégica e intuitiva, detectando patrones con rapidez."
        )

    return {"titulo": "Pensamiento", "dominante": dom, "parrafo": parrafo, **r}


def bonus_inteligencia(porcentaje_scores: dict) -> dict:
    # Práctica: 1-3-7 | Analítica: 2-5-9 | Emocional: 4-6-8
    practica = sum(porcentaje_scores[t] for t in (1, 3, 7))
    analitica = sum(porcentaje_scores[t] for t in (2, 5, 9))
    emocional = sum(porcentaje_scores[t] for t in (4, 6, 8))

    r = _rank_3({"Práctica": practica, "Analítica": analitica, "Emocional": emocional})
    dom = r["dominante"]

    if dom == "Práctica":
        parrafo = (
            "Predomina la inteligencia PRÁCTICA. Te orientas a resolver y accionar, priorizando "
            "resultados y ejecución sobre la teoría."
        )
    elif dom == "Analítica":
        parrafo = (
            "Predomina la inteligencia ANALÍTICA. Buscas comprender, ordenar y dar sentido antes "
            "de actuar, sosteniendo una mirada racional y estructurada."
        )
    else:
        parrafo = (
            "Predomina la inteligencia EMOCIONAL. Percibes con intensidad el entorno, el vínculo y "
            "las tensiones interpersonales; tu lectura humana guía decisiones."
        )

    return {"titulo": "Inteligencia", "dominante": dom, "parrafo": parrafo, **r}


def bonus_polaridad(porcentaje_scores: dict) -> dict:
    # Activo: 1-2-3-8 | Receptivo: 4-5-6-7 | Neutro: 9
    activo = sum(porcentaje_scores[t] for t in (1, 2, 3, 8))
    receptivo = sum(porcentaje_scores[t] for t in (4, 5, 6, 7))
    neutro = sum(porcentaje_scores[t] for t in (9,))

    r = _rank_3({"Activo (+)": activo, "Receptivo (-)": receptivo, "Neutro (0)": neutro})
    dom = r["dominante"]

    if dom.startswith("Activo"):
        parrafo = (
            "Predomina la polaridad ACTIVA. Tiendes a iniciar, decidir y moverte hacia la acción "
            "antes que esperar. El desafío es regular intensidad y sostener pausas."
        )
    elif dom.startswith("Receptivo"):
        parrafo = (
            "Predomina la polaridad RECEPTIVA. Tiendes a observar, procesar y responder con cautela. "
            "El desafío es sostener iniciativa y no postergar decisiones."
        )
    else:
        parrafo = (
            "Predomina la polaridad NEUTRA. Tiendes a integrar, estabilizar y sostener equilibrio. "
            "El desafío es no diluir tu agenda por evitar fricción."
        )

    return {"titulo": "Polaridad", "dominante": dom, "parrafo": parrafo, **r}


def bonus_triadas(porcentaje_scores: dict) -> dict:
    TRIADAS = {
        "Instintiva": [1, 8, 9],
        "Emocional": [2, 3, 4],
        "Mental": [5, 6, 7],
    }
    vals = {k: sum(porcentaje_scores[t] for t in v) / len(v) for k, v in TRIADAS.items()}
    r = _rank_3(vals)
    dom = r["dominante"]

    if dom == "Instintiva":
        parrafo = (
            "Tu estructura predominante es INSTINTIVA. Tiendes a decidir desde la acción y la reacción corporal. "
            "Percibes el entorno de manera visceral y priorizas autonomía."
        )
    elif dom == "Emocional":
        parrafo = (
            "Tu estructura predominante es EMOCIONAL. Tu pensamiento está atravesado por la imagen, "
            "la validación y el vínculo. Evalúas desde el impacto relacional."
        )
    else:
        parrafo = (
            "Tu estructura predominante es MENTAL. Tu mente anticipa escenarios, analiza riesgos "
            "y busca comprender antes de actuar."
        )

    return {"titulo": "Tríadas", "dominante": dom, "parrafo": parrafo, **r}


def bonus_expresion(porcentaje_scores: dict) -> dict:
    # Operatividad (como tu tabla)
    # Manifiesto: Acción 8-9-1 | Sensibilidad 2-3-4 | Pensamiento 5-6-7 (pero en tu tabla se usa 8,2,5; 9,3,6; 1,4,7)
    manifest = porcentaje_scores[8] + porcentaje_scores[2] + porcentaje_scores[5]
    oculto = porcentaje_scores[9] + porcentaje_scores[3] + porcentaje_scores[6]
    diversif = porcentaje_scores[1] + porcentaje_scores[4] + porcentaje_scores[7]

    r = _rank_3({"Manifiesto": manifest, "Oculto": oculto, "Diversificado": diversif})
    dom = r["dominante"]

    if dom == "Manifiesto":
        parrafo = (
            "Tu expresión tiende a ser MANIFIESTA. Lo predominante en tu estructura se percibe con claridad "
            "en tus decisiones, energía y forma de actuar."
        )
    elif dom == "Oculto":
        parrafo = (
            "Tu expresión tiende a ser OCULTA. Parte importante de tu estructura opera internamente y "
            "no siempre se ve desde afuera con la misma intensidad."
        )
    else:
        parrafo = (
            "Tu expresión tiende a ser DIVERSIFICADA. Distribuyes tu energía en varios registros, lo que te "
            "vuelve adaptable, aunque puede dificultar priorizar."
        )

    return {"titulo": "Expresión", "dominante": dom, "parrafo": parrafo, **r}


def bonus_vincularidad(porcentaje_scores: dict) -> dict:
    # Enfrentar: 1-3-8 | Acercar: 2-6-7 | Alejar: 4-5-9
    enfrentar = sum(porcentaje_scores[t] for t in (1, 3, 8))
    acercar = sum(porcentaje_scores[t] for t in (2, 6, 7))
    alejar = sum(porcentaje_scores[t] for t in (4, 5, 9))

    r = _rank_3({"Enfrentar": enfrentar, "Acercar": acercar, "Alejar": alejar})
    dom = r["dominante"]

    if dom == "Enfrentar":
        parrafo = "En vínculos predomina ENFRENTAR. Tiendes a abordar tensiones de forma directa antes que evitarlas."
    elif dom == "Acercar":
        parrafo = "En vínculos predomina ACERCAR. Tiendes a generar puente, cuidar el clima y buscar encuentro."
    else:
        parrafo = "En vínculos predomina ALEJAR. Tiendes a tomar distancia para regularte y proteger tu energía."

    return {"titulo": "Vincularidad", "dominante": dom, "parrafo": parrafo, **r}


def bonus_conflictos_internos(porcentaje_scores: dict) -> dict:
    # Combativos: 3-7-8 | Sumisos: 1-2-6 | Retirados: 4-5-9
    comb = sum(porcentaje_scores[t] for t in (3, 7, 8))
    sumis = sum(porcentaje_scores[t] for t in (1, 2, 6))
    reti = sum(porcentaje_scores[t] for t in (4, 5, 9))

    r = _rank_3({"Combativos": comb, "Sumisos": sumis, "Retirados": reti})
    dom = r["dominante"]

    if dom == "Combativos":
        parrafo = "Ante conflictos internos predomina lo COMBATIVO: tiendes a intensificar energía y empujar resolución."
    elif dom == "Sumisos":
        parrafo = "Ante conflictos internos predomina lo SUMISO: tiendes a adaptarte y ceder para sostener estabilidad."
    else:
        parrafo = "Ante conflictos internos predomina lo RETIRADO: tiendes a desconectarte, observar y procesar en silencio."

    return {"titulo": "Conflictos internos", "dominante": dom, "parrafo": parrafo, **r}


def bonus_reaccion_problemas(porcentaje_scores: dict) -> dict:
    # Reactivos: 6-4-8 | Eficaces: 3-1-5 | Optimistas: 9-2-7
    react = sum(porcentaje_scores[t] for t in (6, 4, 8))
    eficaz = sum(porcentaje_scores[t] for t in (3, 1, 5))
    optim = sum(porcentaje_scores[t] for t in (9, 2, 7))

    r = _rank_3({"Reactivos": react, "Eficaces": eficaz, "Optimistas": optim})
    dom = r["dominante"]

    if dom == "Reactivos":
        parrafo = (
            "Ante problemas predomina la REACTIVIDAD. Respondes rápido e intensamente; puede ser útil en urgencias, "
            "pero requiere regulación para no sobrerreaccionar."
        )
    elif dom == "Eficaces":
        parrafo = "Ante problemas predomina lo EFICAZ. Tiendes a resolver con foco práctico, priorizando solución y avance."
    else:
        parrafo = "Ante problemas predomina lo OPTIMISTA. Tiendes a alivianar, relativizar y buscar alternativas positivas."

    return {"titulo": "Reacción ante problemas", "dominante": dom, "parrafo": parrafo, **r}


def build_bonus_estructura_pensamiento(porcentaje_scores: dict) -> dict:
    pensamiento = bonus_pensamiento(porcentaje_scores)
    inteligencia = bonus_inteligencia(porcentaje_scores)
    polaridad = bonus_polaridad(porcentaje_scores)
    triadas = bonus_triadas(porcentaje_scores)
    expresion = bonus_expresion(porcentaje_scores)
    vincularidad = bonus_vincularidad(porcentaje_scores)
    conflictos = bonus_conflictos_internos(porcentaje_scores)
    reaccion = bonus_reaccion_problemas(porcentaje_scores)

    sintesis = [
        (
            f"Tu estructura muestra un pensamiento {pensamiento['dominante']}, una inteligencia {inteligencia['dominante']} "
            f"y una polaridad {polaridad['dominante']}."
        ),
        (
            f"Tu tríada dominante es {triadas['dominante']}, y tu forma de expresión tiende a ser {expresion['dominante']}."
        ),
        (
            f"En lo vincular predomina {vincularidad['dominante']}, en conflictos internos {conflictos['dominante']}, "
            f"y frente a problemas {reaccion['dominante']}."
        ),
    ]

    return {
        "estructura": {
            "pensamiento": pensamiento,
            "inteligencia": inteligencia,
            "polaridad": polaridad,
            "triadas": triadas,
            "expresion": expresion,
            "vincularidad": vincularidad,
            "conflictos_internos": conflictos,
            "reaccion_problemas": reaccion,
        },
        "sintesis": sintesis,
    }
    
def generar_radar_image(resultados: dict):
    """
    resultados: {"1": 12.3, "2": 8.4, ...}
    devuelve: BytesIO con imagen PNG
    """

    labels = [str(i) for i in range(1, 10)]
    values = [resultados.get(str(i), 0) for i in range(1, 10)]

    # Cerrar el círculo
    values += values[:1]
    angles = np.linspace(0, 2 * np.pi, 9, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

    ax.plot(angles, values)
    ax.fill(angles, values, alpha=0.25)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    mx = max(values) if values else 0
    ax.set_ylim(0, mx + 5) 


    ax.set_title("Radar Eneagrama", pad=20)

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    img_buffer.seek(0)

    return img_buffer
    
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
Base = declarative_base()
DBSession = sessionmaker(bind=engine) if engine else None

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Carátula
    owner_name = Column(String(200))
    owner_email = Column(String(200))
    owner_data = Column(JSON)          # dict completo de carátula
    test_date_iso = Column(String(50)) # fecha_test guardada como ISO

    # Resultados
    porcentaje_scores = Column(JSON)   # % por tipo
    top_types = Column(JSON)           # lista tipos top

    # Informe (texto o JSON)
    report_json = Column(JSON)         # secciones para rearmar PDF
    report_text = Column(Text)         # opcional: texto plano (si querés)

    # para monetizar después
    paid = Column(Boolean, default=False)


if engine is not None:
    Base.metadata.create_all(engine)
    
def build_pdf_from_payload(payload: dict) -> bytes:
    buffer = io.BytesIO()
    desarrollo = payload.get("desarrollo", {})  # ← UNA VEZ ACÁ ARRIBA
    top_types = payload.get("graficos_anexos", {}).get("top_types", [])
    eneatipo_data_raw = desarrollo.get("eneatipo_textos", {})
    eneatipo_data = {int(k): v for k, v in eneatipo_data_raw.items()}    
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=3*cm,
        bottomMargin=2*cm,
        title=payload.get("titulo", "Informe")
    )

    styles = getSampleStyleSheet()
    
    styles.add(
    ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        alignment=TA_JUSTIFY,
        leading=15,
        spaceAfter=8
    )
)
    

    styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], alignment=TA_JUSTIFY, spaceAfter=12))
    styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], alignment=TA_JUSTIFY, spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyPro", parent=styles["Body"], fontSize=11, leading=15))
    styles.add(ParagraphStyle(name="H3", parent=styles["Heading3"], spaceAfter=6))
    
    story = []

    logo_path = os.path.join(current_app.root_path, "static", "img", "logo_az.png")

    # ---------------------------------
    # PORTADA
    # ---------------------------------
    
    logo_path = os.path.join(current_app.root_path, "static", "img", "logo_az.png")
    
    logo = Image(logo_path)
    logo.drawHeight = 4 * cm
    logo.drawWidth = 4 * cm
    
    story.append(Spacer(1, 6*cm))
    story.append(logo)
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(payload.get("titulo", ""), styles["H1"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Eneagrama evolutivo integral", styles["H2"]))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Informe confidencial", styles["H2"]))    
    story.append(PageBreak()) 

    # Título
    story.append(Paragraph(payload.get("titulo", "Informe profundo de autoconocimiento"), styles["H1"]))
    story.append(Paragraph(f"Analista: {payload.get('analista', '')}", styles["Body"]))

    # Propietario + fecha
    propietario = payload.get("propietario", {}) or {}
    fecha_test = payload.get("fecha_test") or propietario.get("fecha_test", "")

    story.append(Spacer(1, 8))
    story.append(Paragraph("Propietario del eneagrama", styles["H2"]))
    story.append(Paragraph(f"Nombre: {propietario.get('nombre','')}", styles["Body"]))
    story.append(Paragraph(f"Email: {propietario.get('email','')}", styles["Body"]))
    story.append(Paragraph(f"Sexo: {propietario.get('sexo','')}", styles["Body"]))
    story.append(Paragraph(f"Fecha nacimiento: {propietario.get('fecha_nacimiento','')}", styles["Body"]))
    story.append(Paragraph(f"Hora nacimiento: {propietario.get('hora_nacimiento') or 'Desconocida'}", styles["Body"]))
    story.append(Paragraph(f"Fecha del test: {fecha_test}", styles["Body"]))

    # Introducción
    story.append(Spacer(1, 10))
    story.append(Paragraph("Introducción", styles["H2"]))
    intro = (
        "A continuación verás los resultados de tu test de autoidentificación personal. "
        "Esta información te ayudará a desarrollar y potenciar tu perfil personal, profesional y vocacional. "
        "Recordá que el eneagrama es dinámico: repetirlo anualmente te permitirá observar tu evolución hacia "
        "un mayor equilibrio y bienestar."
    )
    story.append(Paragraph(intro, styles["Body"]))

    # ---------------------------------
    # DESARROLLO
    # ---------------------------------
    story.append(Spacer(1, 12))
    story.append(Paragraph("Desarrollo", styles["H2"]))
    
    # ---------------------------------
    # Afirmaciones marcadas (como web)
    # ---------------------------------
    total_marked = payload.get("desarrollo", {}).get("total_marked", 0)
    total_preguntas = 270
    
    porcentaje_total = round((total_marked / total_preguntas) * 100, 1) if total_marked else 0
    
    texto_afirmaciones = (
        f"<b>Afirmaciones marcadas:</b> {total_marked} de {total_preguntas} — {porcentaje_total}%"
    )
    
    story.append(Paragraph(texto_afirmaciones, styles["BodyPro"]))
    story.append(Spacer(1, 6))
    
    # Mensaje condicional (igual que la web)
    if porcentaje_total > 30:
        mensaje = "📣 <b>No tienes problema en mostrarte.</b>"
    else:
        mensaje = "🤫 <b>Eres más bien reservado, te cuesta mostrarte.</b>"
    
    story.append(Paragraph(mensaje, styles["BodyPro"]))
    story.append(Spacer(1, 12))

    # ---------------------------------
    # Eneatipo principal
    # ---------------------------------
    desarrollo = payload.get("desarrollo", {})
    eneatipo_data = desarrollo.get("eneatipo_textos", {})
    top_types = payload.get("graficos_anexos", {}).get("top_types", [])
    
    if top_types:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Eneatipo principal", styles["H2"]))
    
        for tipo in top_types:
            data = eneatipo_data.get(tipo) or eneatipo_data.get(str(tipo))
            if not data:
                continue
    
            story.append(Spacer(1, 6))
            story.append(Paragraph(data["titulo"], styles["H2"]))
            story.append(Paragraph(data["descripcion"], styles["Body"]))
            story.append(Paragraph(data["caracteristicas"], styles["Body"]))
    
            story.append(Spacer(1, 6))
            story.append(Paragraph("Orientación vocacional", styles["H3"]))
            story.append(Paragraph(data["orientacion"], styles["Body"]))
    
            story.append(Spacer(1, 6))
            story.append(Paragraph("Claves de mejora", styles["H3"]))
            story.append(Paragraph(data["mejorar"], styles["Body"]))
  
    # Ala
    ala_textos = payload.get("ala_textos", [])
    if ala_textos:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Ala", styles["H2"]))
        for txt in ala_textos:
            story.append(Paragraph(txt, styles["Body"]))
    
    # Camino evolutivo
    camino = payload.get("desarrollo", {}).get("camino_evolucion", [])
    if camino:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Camino evolutivo", styles["H2"]))
        for tipo, pct, texto in camino:
            story.append(Paragraph(f"{texto}", styles["Body"]))
    
    desarrollo = payload.get("desarrollo", {})
    
    # Afinidades
    if desarrollo.get("afinidades_parrafos"):
        story.append(Spacer(1, 8))
        story.append(Paragraph("Ejes de Afinidad", styles["H2"]))
    
        for p in desarrollo.get("afinidades_parrafos", []):
            story.append(Paragraph(p, styles["Body"]))
    
    # ---------------------------------
    # Síntesis de Afinidades
    # ---------------------------------
    sintesis_afinidades = desarrollo.get("sintesis_afinidades", [])
    if sintesis_afinidades:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Síntesis de afinidades", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in sintesis_afinidades:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # ---------------------------------
    # Opuestos Complementarios
    # ---------------------------------
    opuestos_parrafos = desarrollo.get("opuestos_parrafos", [])
    if opuestos_parrafos:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Opuestos complementarios", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in opuestos_parrafos:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # ---------------------------------
    # Síntesis de Opuestos
    # ---------------------------------
    opuestos_sintesis = desarrollo.get("opuestos_sintesis", [])
    if opuestos_sintesis:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Síntesis de opuestos", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in opuestos_sintesis:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # ---------------------------------
    # Análisis de Ejes
    # ---------------------------------
    analisis_ejes = desarrollo.get("analisis_ejes", [])
    if analisis_ejes:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Análisis de ejes", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in analisis_ejes:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # ---------------------------------
    # Síntesis Evolutiva
    # ---------------------------------
    sintesis_evolutiva = desarrollo.get("sintesis_evolutiva", [])
    if sintesis_evolutiva:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Síntesis evolutiva", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in sintesis_evolutiva:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # ---------------------------------
    # Estructura del pensamiento
    # ---------------------------------
    desarrollo = payload.get("desarrollo", {})
    bonus = desarrollo.get("bonus_estructura", {})
    bonus_sintesis = desarrollo.get("bonus_sintesis", [])
    
    if bonus:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Estructura del pensamiento", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for value in bonus.values():
            if isinstance(value, dict) and "parrafo" in value:
                story.append(Paragraph(value["parrafo"], styles["Body"]))
    
    
    if bonus_sintesis:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Síntesis estructura del pensamiento", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for linea in bonus_sintesis:
            story.append(Paragraph(linea, styles["Body"]))

    # ---------------------------------
    # CONCLUSIONES FINALES
    # ---------------------------------
    story.append(Spacer(1, 12))
    story.append(PageBreak())
    story.append(Paragraph("🏁 Conclusiones", styles["H2"]))
    story.append(Spacer(1, 6))
    
    desarrollo = payload.get("desarrollo", {})
    
    # -------------------------
    # Eneatipo principal
    # -------------------------
    top_types = payload.get("graficos_anexos", {}).get("top_types", [])
    eneatipo_data = desarrollo.get("eneatipo_textos", {})
    
    if top_types:
        for tipo in top_types:
            data = eneatipo_data.get(tipo) or eneatipo_data.get(str(tipo))
            if not data:
                continue
    
            story.append(Spacer(1, 6))
            story.append(Paragraph(data["titulo"], styles["H2"]))
            story.append(Paragraph(data["descripcion"], styles["Body"]))
    
    
    # -------------------------
    # Ala
    # -------------------------
    ala_textos = desarrollo.get("ala_textos", [])
    if ala_textos:
        story.append(Spacer(1, 8))
        story.append(Paragraph("🪽 Tu Ala", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for txt in ala_textos:
            story.append(Paragraph(txt, styles["Body"]))
    
    
    # -------------------------
    # Síntesis Evolutiva
    # -------------------------
    sintesis_evolutiva = desarrollo.get("sintesis_evolutiva", [])
    if sintesis_evolutiva:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Síntesis Evolutiva", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in sintesis_evolutiva:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # -------------------------
    # Síntesis de Afinidades
    # -------------------------
    sintesis_afinidades = desarrollo.get("sintesis_afinidades", [])
    if sintesis_afinidades:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Síntesis de Afinidades", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in sintesis_afinidades:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # -------------------------
    # Síntesis de Opuestos
    # -------------------------
    opuestos_sintesis = desarrollo.get("opuestos_sintesis", [])
    if opuestos_sintesis:
        story.append(Spacer(1, 8))
        story.append(Paragraph("🧩 Síntesis de Opuestos complementarios", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for p in opuestos_sintesis:
            story.append(Paragraph(p, styles["Body"]))
    
    
    # -------------------------
    # Síntesis estructural
    # -------------------------
    bonus_sintesis = desarrollo.get("bonus_sintesis", [])
    if bonus_sintesis:
        story.append(Spacer(1, 8))
        story.append(Paragraph("🧠 Síntesis estructural", styles["H2"]))
        story.append(Spacer(1, 4))
    
        for linea in bonus_sintesis:
            story.append(Paragraph(linea, styles["Body"]))


    # ---------------------------------
    # 7️⃣ GRÁFICOS ANEXOS
    # ---------------------------------
    # Resultados por tipo
    story.append(PageBreak())
    story.append(Paragraph("Gráficos anexos", styles["H1"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Resultados por eneatipo (%):", styles["Body"]))
    
    resultados = payload.get("graficos_anexos", {}).get("resultados", {})
    for t in range(1, 10):
        pct = resultados.get(str(t), 0)
        story.append(Paragraph(f"• Tipo {t}: {pct}%", styles["Body"]))
    
   
    resultados = payload.get("graficos_anexos", {}).get("resultados", {})
    if resultados:
        radar_img = generar_radar_image(resultados)
    
        img = Image(radar_img)
        img.drawHeight = 12 * cm
        img.drawWidth = 12 * cm
    
        story.append(img)
    
    # Mensaje final
    story.append(Spacer(1, 10))
    story.append(PageBreak())
    story.append(Paragraph("Mensaje final", styles["H2"]))
    story.append(Paragraph(payload.get("mensaje_final", ""), styles["Body"]))

    doc.build(
        story,
        onFirstPage=lambda c, d: None,
        onLaterPages=add_header_footer
    )
    
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


@app.get("/pdf/<int:report_id>")
def download_pdf(report_id):

    if not DBSession:
        return redirect(url_for("index"))

    db = DBSession()
    try:
        r = db.get(Report, report_id)
        if not r:
            return redirect(url_for("index"))

        payload = r.report_json
    finally:
        db.close()

    pdf_bytes = build_pdf_from_payload(payload)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Informe profundo de autoconocimiento.pdf",
    )
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/quiz")
def quiz_get():
    if not session.get("pago_ok"):
        return redirect(url_for("index"))
    questions_all = load_questions()
    page = int(request.args.get("page") or 1)

    per_page = 30
    total_pages = (len(questions_all) + per_page - 1) // per_page

    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    chunk = questions_all[start:end]

    answers = session.get("answers", {})

    return render_template(
        "quiz.html",
        questions=chunk,
        page=page,
        total_pages=total_pages,
        answers=answers,
    )

@app.post("/crear_preferencia")
def crear_preferencia():
    # Guardar datos del usuario en sesión antes del pago
    session["usuario"] = {
        "nombre": request.form.get("nombre"),
        "email": request.form.get("email"),
        "sexo": request.form.get("sexo"),
        "fecha_nacimiento": request.form.get("fecha_nacimiento"),
        "hora_nacimiento": None if request.form.get("hora_desconocida") == "1" else request.form.get("hora_nacimiento"),
        "hora_desconocida": request.form.get("hora_desconocida") == "1",
        "fecha_test": datetime.utcnow().isoformat(),
    }
    session["answers"] = {}

    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

    preference_data = {
        "items": [{
            "title": "Informe profundo de autoconocimiento",
            "quantity": 1,
            "unit_price": 1000,  # ← precio en pesos ARS
            "currency_id": "ARS",
        }],
        "payer": {
            "email": session["usuario"]["email"],
        },
        "back_urls": {
            "success": f"{APP_URL}/pago_exitoso",
            "failure": f"{APP_URL}/pago_fallido",
            "pending": f"{APP_URL}/pago_pendiente",
        },
        "auto_return": "approved",
        "external_reference": session["usuario"]["email"],
    }

    result = sdk.preference().create(preference_data)
    preference = result["response"]

    return redirect(preference["init_point"])  # redirige a MP


@app.get("/pago_exitoso")
def pago_exitoso():
    # Mercado Pago redirige aquí con ?status=approved
    status = request.args.get("status")
    if status == "approved":
        session["pago_ok"] = True
        return redirect(url_for("quiz_get", page=1))
    return redirect(url_for("pago_fallido"))


@app.get("/pago_fallido")
def pago_fallido():
    return render_template("pago_fallido.html")


@app.get("/pago_pendiente")
def pago_pendiente():
    return render_template("pago_pendiente.html")

@app.post("/quiz")
def quiz_post():
    if not session.get("pago_ok"):
        return redirect(url_for("index"))
    questions_all = load_questions()
    page = int(request.args.get("page") or 1)

    per_page = 30
    total_pages = (len(questions_all) + per_page - 1) // per_page

    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    chunk = questions_all[start:end]

    # guardar respuestas de esta página
    answers = session.get("answers", {})

    for q in chunk:
        qid = str(q["id"])
        answers[qid] = (request.form.get(f"q_{qid}") == "1")

    session["answers"] = answers

    # si no es última página → siguiente page
    if page < total_pages:
        return redirect(url_for("quiz_get", page=page + 1))

    # si es última → resultado
    return redirect(url_for("result"))


@app.get("/reset")
def reset():
    session.pop("answers", None)
    return redirect(url_for("index"))

def clasificar_eje(valor_redondeado_1d: float) -> str:
    """
    Regla: equilibrado SOLO si da 11.1 (con redondeo a 1 decimal).
    """
    v = valor_redondeado_1d
    if v < 8:
        return "no_desarrollado"
    if 8 <= v <= 10.9:
        return "bajo_leve"
    if abs(v - 11.1) <= 0.1:
        return "equilibrado"
    if 11.2 <= v <= 14:
        return "alto_leve"
    if 14 < v <= 20:
        return "elevado"
    return "excesivo"


def juntar_lista_humana(items):
    items = [x for x in items if x]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} y {items[1]}"
    return ", ".join(items[:-1]) + f" y {items[-1]}"




ENEATIPO_TEXTOS = {
    1: {
        "titulo": "🟡 Tipo 1 — El Reformador",
        "descripcion": """Personas éticas, con fuerte sentido del bien y del mal, buscan mejorar el mundo y la perfección. 
         Son responsables, disciplinadas, y muy exigentes consigo mismas y con los demás. 
         Tienden a autocriticarse y a querer que todo sea “lo correcto”.""",
    "caracteristicas": """El valor del eneatipo 1 radica en la EXCELENCIA. Acción (orden práctico).
    
    Su mayor contribución es localizar errores, pulir y perfeccionar. Es un FINALIZADOR. Posee buena orientación al detalle, es reacio a delegar, y puede desarrollar una preocupación excesiva. Es prolijo y ordenado; no le gusta que le cambien de lugar sus cosas.
    
    Sus conductas recurrentes pueden ser: controlar, corregir, juzgar, criticar. Desarrolla hábitos como buscar culpables, corregir errores y tener la razón. El resultado de estas conductas y hábitos es un predominio del deber sobre el placer.
    
    La creencia arraigada en su interior es: "el mundo es un lugar imperfecto para perfeccionar". El miedo básico es ser corrupto, defectuoso o moralmente incorrecto. Su miedo constitutivo a no poder le genera la necesidad de ser fuerte, y la reacción ante este miedo es controlar.
    
    Sus principales fortalezas son ser ético, disciplinado, responsable y justo. Sus principales áreas de mejora radican en ser crítico, rígido, autoexigente e intolerante. El pecado capital del eneatipo 1 es la ira (reprimida).
    
    En su lado luz representa integridad, mejora del mundo y coherencia. En su lado sombra desarrolla un juicio constante y un perfeccionismo paralizante.
    
    Para lograr su evolución es aconsejable incorporar espontaneidad, alegría y flexibilidad, evitando emocionalidad, resentimiento y melancolía. Las actitudes que equilibran a la esencia 1 son ser más calmado y más servicial.
    
    El desarrollo de estas características le permite adquirir ecuanimidad, empatía y colaboración con la gente real (y no sólo por principios y normas: "lo correcto"). Busca el orden y la superación con paciencia, tolerancia, comprensión y amorosidad.
    
    Cuando no se desarrollan, el eneatipo 1 tiende a caer en el pesimismo total ("nada va a cambiar") y/o no se atiende a sí mismo: no toma vacaciones, no descansa, atiende las responsabilidades que asume y no sus necesidades.
    
    Otra de las áreas de expansión es su punto ciego: tomar riesgos, mostrarse, exponerse. La esencia 1 se encuentra dentro de la tríada instintiva (área de la acción o visceral, expresión). Dosifica planificadamente su energía. Es detallista, vive en el presente y tiene necesidad de autonomía.
    
    Cabe destacar que existen 3 subtipos:
    🏠 1 Conservación: busca seguridad, recursos y estabilidad. Puede desarrollar ansiedad. Preocupado por hacerlo todo correctamente. Muy autoexigente. Controla detalles, orden y responsabilidad personal.
    👥 1 Social: busca grupo, pertenencia e imagen social. Puede desarrollar rigidez. Defiende reglas y principios. Moralista, crítico con el entorno. Siente que debe mejorar el mundo.
    ❤️ 1 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Puede desarrollar celo. Más intenso y emocional. Puede ser crítico pero también apasionado. Busca “corregir” al otro.""",

    "orientacion":"""    
    🎯 Vocación base
    
    - Derecho / justicia
    - Ingeniería de procesos / calidad
    - Docencia
    - Gestión institucional
    - Medio ambiente
    - Auditoría
    
    Trabajos donde puedan mejorar sistemas.
    
    🔁 Según subtipo
    
    🟢 Conservación (perfeccionista silencioso)
    – Contabilidad
    – Ingeniería industrial
    – Normativas / compliance
    – Medicina clínica
    
    🔵 Social (idealista moral)
    – Política pública
    – ONG
    – Educación
    – Dirección institucional
    
    🔴 Sexual (intenso reformador)
    – Activismo
    – Liderazgo de cambios
    – Coaching transformacional
    
    🌱 Clave evolutiva
    
    Aprender trabajos donde haya margen de error y creatividad.""",        
    "mejorar": """Tener presente que "SIEMPRE no es realmente siempre y NUNCA no son todas las veces".

    • Desarrollar tareas creativas que te incentiven.
    • Darte tiempo libre para el placer y la relajación, sintiendo el disfrute.
    • Focalizarte en un ideal de vida: poner las formas en función del fondo.
    • Recordar que todos somos uno y perfectos tal como somos.
    • Comprender que hay más de una manera correcta de hacer las cosas.
    • Practicar el perdón con uno mismo y con los demás. Tratarte con menos rigor.
    • Parar y darte tiempos. Soltarte y soltar.
    • Dejarte llevar por la corriente.
    • Confiar en las buenas intenciones de los demás.
    • Apreciar a las demás personas y atender sus deseos genuinamente.
    • Ayudar a los demás a tomar decisiones.
    
    El objetivo de la vida es ser humano, no perfecto.""",
      
},       
2: {
    "titulo": "🔵 Tipo 2 — El Ayudador",
    "descripcion": """Empáticos, cálidos y orientados a servir a otros. 
    Encuentran satisfacción ayudando y siendo necesarios para quienes quieren. 
    Pueden descuidar sus propias necesidades al priorizar las de otros.""",

    "caracteristicas": """El valor del eneatipo 2 radica en la CONEXIÓN EMOCIONAL. Dar.

    Su mayor contribución es identificar el talento, delegar eficazmente y entregar feedback. Es un COORDINADOR.

    Sus conductas recurrentes pueden ser agradar, ayudar, adular y buscar. Desarrolla hábitos como el descuido de las propias necesidades y la dificultad para poner límites. El resultado de estas conductas y hábitos es sentirse usado, vacío y frustrado.

    La creencia arraigada en su interior es: "el mundo es un lugar donde es necesario dar para recibir". El miedo básico es no ser amado o necesario. El miedo constitutivo es al rechazo, esto le genera una necesidad de aceptación que satisface dando, lo que lo lleva a desarrollar una adicción por los otros. 

    Sus principales fortalezas son ser generoso, empático y afectuoso. Sus áreas de mejora radican en la dependencia, la complacencia y la manipulación sutil. Puede crear una atmósfera negativa, manipular y estar orientado a los conflictos. El pecado capital del eneatipo 2 es la soberbia u orgullo.

    En su lado luz representa amor genuino y servicio desinteresado. Sin embargo, en su lado sombra desarrolla un dar para recibir e invasión emocional.

    Para lograr su evolución es aconsejable incorporar autenticidad emocional, implica aprender a reconocer sus propias necesidades sin culpa, sin manipulación, equilibrar el dar con el recibir, desarrollar una identidad propia más allá de ser “el que ayuda”. Se permite sentir sin actuar para agradar, amar sin invadir, decir "hoy yo necesito".  Debe evitar actitudes de control, enojo o agresividad, reclamar reconocimiento, endurecerse emocionalmente, manipular, exigir afecto o imponer ayuda.

    Las actitudes que lo equilibran son la honestidad, aceptar las cosas como son, sin adular, sin endulzar; el orden, la claridad, la acción y la concreción, aprende a manejar lo material y el dinero, con lo cual se vuelve una persona práctica, concreta que dice las cosas con firmeza y claridad. Cuando estas cualidades no se desarrollan, puede caer en la sobreentrega, el resentimiento silencioso y la sensación de no ser valorado. La persona se vuelve rígida moralmente, marcando los defectos de los demás, con una actitud crítica al mundo, puede engañar tratando de ganarse al otro vendiendole una imagen y diciendo lo que le conviene para lograr lo que quiere. 

    Otra de las áreas de expansión es su punto ciego: tomar distancia, dejando que otros ocupen sus roles, cambiar la vista de observador a tercera persona, imparcial, sin involucrarse. El eneatipo 2 pertenece a la triada de la emoción, vive en el pasado y tiene una fuerte necesidad de relación. La esencia 2 se encuentra dentro de la tríada emocional (área del sentimiento y la vinculación).

    Cabe destacar que existen 3 subtipos:
    🏠 2 Conservación: busca seguridad, recursos y estabilidad. Puede desarrollar privilegio. Busca ser indispensable. Ayuda para asegurarse amor y protección.
    👥 2 Social: busca grupo, pertenencia e imagen social. Puede desarrollar ambición. Quiere ser querido y reconocido socialmente. Seductor social.
    ❤️ 2 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Puede desarrollar conquista. Más intenso y posesivo. Seduce para asegurar vínculo exclusivo.""",
    "orientacion":"""    
    🎯 Vocación base
    
    - Psicología
    - Enfermería
    - Recursos Humanos
    - Coaching
    - Organización de eventos
    - Trabajo social
    
    🔁 Según subtipo
    
    🟢 Conservación (cuidador protector)
    – Enfermería
    – Nutrición
    – Estética / bienestar
    
    🔵 Social (conector comunitario)
    – Relaciones públicas
    – ONG
    – Gestión de comunidades
    
    🔴 Sexual (seductor emocional)
    – Coaching motivacional
    – Ventas relacionales
    – Marketing experiencial
    
    🌱 Clave evolutiva
    
    Profesiones donde aprendan a poner límites.""",
    "mejorar": """Aprender a decir que NO con asertividad. 
    
    • Comprendiendo que todos somos amados por lo que somos, no por lo que damos y que en último término las personas siempre satisfacen sus necesidades.
    • Comprendiendo que ser amado no depende de cambiar para complacer a los demás.
    • Mantener claro quién eres realmente.
    • Prestar atención a tus deseos y necesidades y atenderlos.
    • Reconocer que no eres indispensable y que eso está bien.
    • No ayudar cuando la persona no lo pide.
    • Permitir que te ayuden.
    • Aprender que existe un orden del cual eres parte.
    • Conseguir grandes cosas atendiendo proyectos propios.
    • Realizando actividades creativas para encontrarse a sí mismo (retiros, libros, rompecabezas).
    
    Dejar de estar excesivamente pendiente de las necesidades ajenas.""",
},
  
3: {
    "titulo": "🟢 Tipo 3 — El Triunfador",
    "descripcion": """Energéticos, adaptables y orientados al éxito.
    Se enfocan en metas, logros y reconocimiento.
    Suelen inspirar a otros con su energía, aunque pueden priorizar imagen y resultados.""",

    "caracteristicas": """El valor del eneatipo 3 radica en el LOGRO y la EFICIENCIA. Hacer visible el éxito. Es un IMPULSOR hacia el TRIUNFO. 

    Su mayor contribución es su capacidad de adaptación, productividad y motivación. Es eficiente, dinámico y orientado a resultados concretos. Inspira a otros con su energía y ejemplo de superación. Es retador, trabaja bien bajo presión, tiene iniciativa y coraje para superar obstáculos. Puede ser muy exigente con el equipo, no reconocer sus debilidades y no asumir fracasos. 

    Sus conductas recurrentes pueden centrarse en el rendimiento trabajando compulsivamente, la competencia, buscar el éxito y la imagen. Puede ocultar su sensibilidad para no quedar expuesto, priorizando la apariencia por sobre la autenticidad. Los hábitos que tiene son desconexión emocional y negación del error que como resultado derivan en un vacío existencial y desvitalización de vínculos. 

    La creencia arraigada en su interior es que el valor personal depende de lo que se logra. "El mundo es un lugar de ganadores, se premia al exitoso". El miedo básico es ser un fracaso o no valer. El miedo constitutivo es al rechazo, lo que genera una necesidad de aceptación que se cubre logrando y puede derivar en una adicción al éxito.

    Sus principales fortalezas son ser eficiente, adaptable y motivador. Sus áreas de mejora radican en la vanidad, la competitividad excesiva y la desconexión emocional. El pecado capital del eneatipo 3 es la vanidad.

    En su lado luz es inspirador, productivo y ejemplo de superación. Sin embargo, en su lado sombra puede basar su identidad exclusivamente en la imagen y los resultados.

    Las actitudes que potencian su evolución son: dejar de competir y colaborar, aprender a trabajar en equipo, permitirse mostrar inseguridades, conectar con valores reales, actuar con compromiso, lealtad y coherencia. En contraposición, las actitudes que debe evitar son: dejar proyectos a medias por miedo a fracasar, desconectarse, postergar, evitar conflictos, la apatía. Las cualidades que lo equilibran son exteriorizar su sensibilidad, apertura y empatía, aspiraciones al servicio del otro, pensar en los anhelos de su alma, dar sentido profundo a lo que hace, encontrar valores más allá de ganar, poner interés a lo que es verdaderamente importante. Cuando logra incorporar estas actitudes se vuelve una persona sensible, auténtica y madura. 

    Cuando estas actitudes no se desarrollan se siente imprescindible, adoptando una actitud de soberdia y superioridad, comienza a compararse y ser competitivo, y ganar a cualquier precio. 
    
    Necesidad central: reconocimiento y validación. Vive en el pasado. Pertenece a la tríada emocional (imagen).

    Otra de las áreas de expansión es su punto ciego: no tiene claro un orden de prioridades. Para comprender esto, la persona podría imaginar su propio funeral: ¿qué escribirían sus afectos en la lápida?. El eneatipo 3 pertenece a la triada de la emoción, vive en el pasado y tiene una fuerte necesidad de relación

    Cabe destacar que existen 3 subtipos:

    🏠 3 Conservación: busca seguridad, recursos y estabilidad. Puede desarrollar seguridad. Trabajador incansable. Se enfoca en resultados concretos.

    👥 3 Social: busca grupo, pertenencia e imagen social. Puede desarrollar prestigio. Muy pendiente de imagen y estatus. Quiere destacar públicamente.

    ❤️ 3 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Puede ser atractivo. Encantador y competitivo en relaciones. Busca admiración personal.""",

    "orientacion": """    
    🎯 Vocación base

    - Marketing
    - Dirección empresarial
    - Ventas
    - Emprendimiento
    - Comunicación estratégica

    🔁 Según subtipo

    🟢 Conservación (trabajador eficiente)
    – Gestión de proyectos
    – Administración

    🔵 Social (imagen pública)
    – Política
    – Comunicación
    – Influencer / marca personal

    🔴 Sexual (competidor carismático)
    – Liderazgo comercial
    – Representación
    – Startups disruptivas

    🌱 Clave evolutiva

    Trabajos donde el éxito no sea solo externo.""",

    "mejorar": """Ninguna persona puede silbar una sinfonía, se necesita una ORQUESTA para poder interpretarla.

    • Centrando tu atención en tus valores internos en lugar de la imagen.
    • Practicando la autenticidad sobre la apariencia.
    • Valorando tus logros sin depender de la aprobación externa.
    • Fomentando la empatía y la conexión genuina.
    • Permitirte descansar sin sentir culpa.
    • Equilibrar productividad con presencia y gratitud.
    • Realizando tareas cooperativas que fomenten la sensación de pertenencia en el equipo. 
    • Equilibrar productividad con presencia y gratitud.
    • Permitir que las personas te abracen y demuestren el afecto por lo que eres, comprendiendo que no debes ganártelo.""",
},

        
4: {
    "titulo": "🔴 Tipo 4 — El Individualista",
    "descripcion": """Creativos, sensibles y emocionalmente profundos.
    Se sienten únicos e intensos, valoran la autenticidad.
    Tienden a ser introspectivos y a explorar su mundo interior con profundidad.""",

    "caracteristicas": """El valor del eneatipo 4 radica en la AUTENTICIDAD, IDENTIDAD y la PROFUNDIDAD EMOCIONAL.

    Su mayor contribución es aportar sensibilidad, creatividad y capacidad de expresar lo que otros no logran nombrar. Posee una conexión profunda con la emoción y la estética. Es imaginativo y un librepensador. Es el CEREBRO. Se siente diferente al resto, puede ser impredecible e individualista. 

    Sus conductas recurrentes pueden incluir la comparación constante, la intensidad emocional y la tendencia a dramatizar experiencias, quejarse y victimizarse. Puede oscilar entre sentirse especial o defectuoso. Los hábitos en los que cae son buscar salvadores, enfermarse para llamar la atención, y como resultado puede quedarse aislado, ser rechazado o sentirse diferente. 

    La creencia arraigada en su interior es que algo esencial le falta o que es diferente. Algo que los demás tienen y él no. El miedo básico es no tener identidad o significado. El miedo constitutivo es al rechazo, lo que le genera una necesidad de aceptación que la cubre necesitando que lo valoren por lo que es, es decir, creando y haciendo cosas exéntricas. Esto lo lleva a una adicción a sí mismo.

    Sus principales fortalezas son ser creativo, sensible y profundo. Sus áreas de mejora radican en la melancolía, la comparación y el dramatismo. El pecado capital del eneatipo 4 es la envidia.

    En su lado luz se expresa con autenticidad emocional profunda.Sin embargo, en su lado sombra puede caer en victimismo o aislamiento.

    Las cualidades que le permiten evolucionar son: incorporar disciplina, orden y objetividad. Canalizar su sensibilidad en acción concreta y estructura. Transformar emoción en propósito. Por el contrario, las actitudes que lo llevan a una involución son: volverse dependiente emocionalmente, buscar validación afectiva intensa, volverse demandante o manipulador desde la herida emocional. Lo que lo mantiene equilibrado es estar más orientado al logro, tener una necesidad de una base económica y de activarse para desplegar su creatividad, bajar a la realidad, a lo concreto y práctico y ser más introspectivo y cerebral, percibir la realidad sin adornos ni dramatismo, buscar objetividad.

    Cuando estas características no se desarrollan la persona cae en una bipolaridad entre soy el mejor y soy el peor. La imagen (apariencia) y el drama.  
    
    Otro de las oportunidades de evolución es el punto ciego: ver lo que sí tiene. Pertenece a la tríada emocional (sentimiento). Vive en el pasado y su necesidad es vincularse. 

    Cabe destacar que existen 3 subtipos:

    🏠 4 Conservación: busca seguridad, recursos y estabilidad. Puede desarrollar tenacidad. Sufre en silencio. Resistente, aguanta dolor sin mostrarse débil.

    👥 4 Social: busca grupo, pertenencia e imagen social. Puede desarrollar vergüenza. Se siente diferente y expuesto. Comparación constante.

    ❤️ 4 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Puede desarrollar competencia. Intenso, celoso, apasionado. Busca intensidad emocional.""",

    "orientacion": """    
    🎯 Vocación base

    - Arte
    - Escritura
    - Diseño
    - Música
    - Terapias expresivas

    🔁 Según subtipo

    🟢 Conservación (sufridor resiliente)
    – Arte terapéutico
    – Psicología profunda

    🔵 Social (comparativo creativo)
    – Diseño de marca
    – Moda
    – Imagen pública

    🔴 Sexual (intenso romántico)
    – Cine
    – Dirección artística
    – Literatura pasional

    🌱 Clave evolutiva

    Estructura y disciplina profesional.""",

    "mejorar": """No soy una persona importante, soy importante como persona, que es distinto.

    • Cultivando la disciplina personal y la estructura.
    • Aprendiendo a aceptar tus emociones sin quedarte atrapado en ellas.
    • Fomentando la creatividad con propósito.
    • Practicando gratitud y conexión con otros.
    • Explorando logros tangibles además del mundo interior.
    • Centrarse físicamente, bioenergía, danza. Focalizarse en un ideal de vida ya que es un fluir de sensaciones en abanico.
    • Animarme a mantener la atención en lo positivo del presente.""",
},


5: {
    "titulo": "🟣 Tipo 5 — El Investigador",
    "descripcion": """Curiosos, observadores y analíticos.
    Buscan conocimiento, comprensión y autonomía.
    Prefieren observar antes que participar y disfrutan de profundizar en temas complejos.""",

    "caracteristicas": """El valor del eneatipo 5 radica en la PRIVACIDAD, el CONOCIMIENTO y la COMPRENSIÓN.

    Su mayor contribución es ser ESPECIALISTA, aportar análisis, claridad mental y profundidad conceptual. Posee una gran capacidad de concentración y pensamiento estratégico. Es independiente y aporta conocimientos específicos. Puede aislarse de los otros miembros, tener información excesiva y ser individualista.

    Sus conductas recurrentes pueden incluir la observación distante, el aislamiento y la acumulación de información antes de actuar. Prefiere observar antes que participar. Puede aislarse y ser hiper analítico. Entre sus hábitos está no pedir para que no le pidan, intolerancia a la invasión, esto resulta en soledad, dificultad para relacionarse. 

    La creencia arraigada en su interior es que el mundo puede invadirlo o demandarle demasiado. "El mundo es una jungla que me agobia". El miedo básico es ser incompetente o incapaz, quedarse sin recursos internos (energía, tiempo, conocimiento), lo que genera una necesidad de autonomía y autosuficiencia. El miedo constitutivo es a la realidad, lo que le genera una necesidad de seguridad, por lo que se aisla de la realidad (la considera problemática), y esto puede generarle una adicción a la soledad. 

    Sus principales fortalezas son ser analítico, observador e independiente. Sus áreas de mejora radican en el aislamiento, la distancia emocional y el retraimiento. El pecado capital del eneatipo 5 es la avaricia (retención).

    En su lado luz se expresa con sabiduría, claridad mental y objetividad. Sin embargo, en su lado sombra puede caer en retraimiento extremo, frialdad o desconexión emocional.

    Las aptitudes que lo evolucionan son desarrollar fuerza, decisión y capacidad de acción. Pasar del análisis a la ejecución. Se vuelve más presente, directo y comprometido con la realidad. Por el contrario, debe evitar dispersarse mentalmente, salta de idea en idea sin profundidad y busca distracción para evitar el vacío interno.
    Las cualidades que lo equilibran son ser más creativo y más precavido y leal. Desarrollar estas cualidades en luz le otorga calidez, acercamiento, presencia, expresión y sensibilidad que lo ayudan a salir de la cueva y compartir con los demás. Es responsable,a bierto, original y sensible.
    Si no las desarrolla o las desarrolla en sombra (negativamente), se cierra en su mente, en sus teorías, le cuesta compartir, es pesimista, se carga de drama, sostiene que la alegría es vulgar, es indeciso, se carga de miedos y cuestionamientos que lo cierran más en si mismo. 

    Otro punto de evolución es su punto ciego: tomar acción decisiva. Pertenece a la triada de la intelectualidad o la mente (percepción), vive en el futuro, su necesidad es de seguridad. Tiene una mente focalizada, dirigida. 

    Cabe destacar que existen tres sub-tipos: 
    🏠 5 Conservación: busca seguridad, recursos y estabilidad. Busca refugio. Muy reservado. Crea espacios privados y autosuficientes.

    👥 5 Social: busca grupo, pertenencia e imagen social. Busca tótem. Comparte conocimiento en grupos específicos. Busca pertenecer intelectualmente.

    ❤️ 5 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Es confidente. Intenso en vínculos selectivos. Se abre solo con pocos.""",
    
    "orientacion": """    
    🎯 Vocación base

    - Investigación
    - Ciencia
    - Tecnología
    - Programación
    - Análisis de datos
    - Docencia universitaria

    🔁 Según subtipo

    🟢 Conservación (observador aislado)
    – Programación
    – Investigación técnica

    🔵 Social (teórico experto)
    – Profesor universitario
    – Think tank

    🔴 Sexual (visionario especializado)
    – Innovación tecnológica
    – Neurociencia

    🌱 Clave evolutiva

    Profesiones donde compartan su conocimiento.""",

    "mejorar": """La soledad es un buen lugar para encontrarse, pero uno malo para quedarse.

    • Integrando acción deliberada y participación social.
    • Cultivando conexiones con otros sin perder tu independencia.
    • Practicando compartir tu conocimiento con humildad.
    • Balanceando reflexión con experiencia directa.
    • Conectarse con la vida que es el mejor libro. 
    • Salir a la naturaleza.""",

},

        
6: {
    "titulo": "🟠 Tipo 6 — El Leal",
    "descripcion": """Personas leales, responsables, cautelosas y con gran sentido de comunidad.
    Valoran la seguridad, la confianza y la previsibilidad.
    Pueden preocuparse por posibles riesgos, pero son muy comprometidos.""",

    "caracteristicas": """El valor del eneatipo 6 radica en la CONFIANZA y la LEALTAD.

    Su mayor contribución es ser un EVALUADOR, COLABORADOR, generar estabilidad, previsión y compromiso dentro de los sistemas y vínculos. Es responsable, confiable y protector. Es estratega, percibe todas las opciones y es hábil en el pensamiento crítico. Puede ser influenciables, contradictorio y pesimista. 

    Sus conductas recurrentes pueden incluir anticipación de riesgos, cuestionamiento constante, búsqueda de garantías y validación externa. Puede oscilar entre la prudencia y la reacción defensiva. Puede tener dificultad para cambiar, desconfiar, dudar y ser negativo. Los hábitos que puede desarrollar son ansiedad, hiperintencionalidad supervigilante,
    orientación teórica, amistad congraciadora, rigidez, acusación de sí mismos y de los demás, ambivalencia y titubeo. Como resultado forman guetos, sostienen vínculos aunque a veces no sean los más sanos. 

    La creencia arraigada en su interior es que el mundo es incierto y potencialmente peligroso. El miedo básico es no tener seguridad ni apoyo. El miedo constitutivo es quedar desamparado o traicionado, lo que genera una necesidad de protección y pertenencia. Tiene miedo a la realidad, por lo que busca seguridad, se cierra en sus vínculos, y su adicción es a la familia (familiariza vínculos).

    Sus principales fortalezas son ser leal, responsable y comprometido. Sus áreas de mejora radican en la ansiedad, la desconfianza y la duda excesiva. El pecado capital del eneatipo 6 es el miedo.

    En su lado luz se expresa con valentía, compromiso y construcción de comunidad. Por el contrario, en su lado sombra puede caer en parálisis por miedo, sospecha constante o reacción defensiva.

    Cuando evoluciona, desarrolla serenidad y confianza interna, aprende a relajarse y a confiar en el flujo de la vida, disminuye la ansiedad y gana estabilidad emocional. Cuando cae en estrés, puede volverse competitivo y obsesionado con el rendimiento, busca validación a través del logro y puede desconectarse emocionalmente para sostener imagen de eficacia.
    Las cualidades que lo mantienen en equilibrio son ser más analítico e introspectivo y más social y adaptable. Equilibrar estas características le otorgan la capacidad de observación objetiva, relajada y optimista de la realidad, pudiendo desplegar mejor sus capacidades sin temor ni cuestionamientos. No se siente a cargo de todo, sale de la mente laberíntica y del cumplimiento. 
    Sin embargo, si no desarrolla estas cualidades, está siempre cuestionándose y cuestionando todo; no tiene paz mental y siente que vino a cumplir y a sostener hasta las situaciones más duras. 

    Otro punto que ayuda a la evolución del eneatipo 6 es reconocer su punto ciego:tiene que vencer el miedo, fortalecerse, confiar en sí mismo, y arriesgar. Pertenece a la tríada mental (pensamiento). Vive en el futuro y su necesidad es la seguridad.  

    Cabe destacar que existen 3 subtipos:
    🏠 6 Conservación: busca seguridad, recursos y estabilidad. Busca calor. Busca seguridad en vínculos cercanos. Protector y precavido.

    👥 6 Social: busca grupo, pertenencia e imagen social. Busca deber. Cumple normas del grupo. Muy responsable y leal.

    ❤️ 6 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Busca fuerza. Contrafóbico. Enfrenta el miedo con valentía aparente.""",
    "orientacion": """    
    🎯 Vocación base

    - Derecho
    - Seguridad
    - Gestión
    - Administración pública
    - Logística

    🔁 Según subtipo

    🟢 Conservación (protector familiar)
    – Administración
    – Salud pública

    🔵 Social (leal institucional)
    – Fuerzas armadas
    – Gobierno

    🔴 Sexual (contrafóbico)
    – Emprendimientos de riesgo
    – Abogacía litigante

    🌱 Clave evolutiva

    Roles con autonomía progresiva.""",

    "mejorar": """Comprendiendo que el miedo termina cuando percibo que mi mente lo creo. 
    
    • Practicando confianza en ti mismo.
    • Cultivando cooperación y apertura.
    • Aprendiendo a discernir riesgos reales de miedos imaginarios.
    • Practicando calma antes que reacción.
    • Construyendo seguridad desde el interior.
    • Demostrándole que puede confiar. 
    • Apuntalando fuertemente su autoestima.""",
},
        
7: {
    "titulo": "🟤 Tipo 7 — El Entusiasta",
    "descripcion": """Activos, optimistas, espontáneos y con deseos de experiencias nuevas.
    Ayudan a otros ver el lado positivo de la vida.
    A veces evitan el dolor y buscan diversión constante.""",

    "caracteristicas": """El valor del eneatipo 7 radica en la ALEGRÍA y la FELICIDAD.

    Su mayor contribución es aportar entusiasmo, creatividad y visión de posibilidades. Es un INVESTIGADOR DE RESURSOS. Es comunicativo, busca oportunidades y desarrolla contactos. Puede desarrollar un optimismo poco realista, no cerrar tareas y no profundizar. Genera energía, ideas y dinamismo en los entornos donde participa.

    Sus conductas recurrentes pueden incluir búsqueda constante de estímulos, dificultad para sostener procesos largos y tendencia a evitar el malestar. Puede dispersarse entre múltiples proyectos. Sus hábitos incluyen negación al dolor, excesos y gula por la vida. El síndrome que desarrolla es el de Peter Pan, todólogos. 

    La creencia arraigada en su interior es que la vida debe ser disfrutada y que el dolor debe evitarse. "El mundo está lleno de opciones, y no me quiero perder ninguna". El miedo básico es sentir dolor o quedar atrapado en el sufrimiento. El miedo constitutivo es quedarse limitado o privado de experiencias, lo que genera una necesidad de libertad y variedad. Miedo a la realidad, le genera una necesidad de seguridad que cubre evadiendo la realidad (es dolorosa), lo cual lo hace adicto al placer. 
    
    Sus principales fortalezas son ser optimista, creativo y versátil. Sus áreas de mejora radican en la dispersión, la impulsividad y la evasión emocional. El pecado capital del eneatipo 7 es la gula (deseo excesivo de experiencias).

    En su lado luz se expresa con alegría genuina, entusiasmo y capacidad de inspirar. En su lado sombra puede evadir el dolor, superficializar experiencias o escapar del compromiso.

    Cuando evoluciona, desarrolla profundidad, foco y capacidad de introspección, aprende a quedarse en una experiencia sin huir, canaliza su energía en conocimiento y concentración. Cuando se pierde a sí mismo, en estrés puede volverse rígido, crítico e irritable, intenta controlar el entorno cuando siente que pierde libertad, puede volverse excesivamente exigente consigo mismo y con los demás.
    Las actitudes que lo equilibran son ser más responsable y comunitario y más decidido y firme. Debe aprender la responsabilidad, la perseverancia, la fidelidad y enfrentar y aprender del dolor, cuestionarse ¿de qué estoy huyendo?, ¿de qué estoy asustado?, aprender a tomar decisiones con firmeza y cumplir sus compromisos. 
    Si desarrolla estas actitudes obtiene la capacidad de ser fiel, perseverante y asumir sus responsabilidades, de tomar decisiones consistentes para enfrentar suss problemas sin diluirlos ni postergarlos. Es consistente, maduro. En cambio, si no las desarrolla, es impulsivo, disperso, le cuesta asumir compromisos y responsabilidades. 

    Otra área de evolución es el punto ciego, es aprender a tener paz, estar presente en el aquí y ahora. Pertenece a la tríada mental (pensamiento) , posee una mente abierta en abanico, es curioso y disperso. Su necesidad central es de seguridad, libertad y experiencias positivas. Vive en el futuro.

    Cabe destacar que existen 3 subtipos:
    🏠 7 Conservación: busca seguridad, recursos y estabilidad. Busca la familia. Busca seguridad en círculo cercano. Más responsable.

    👥 7 Social: busca grupo, pertenencia e imagen social. Busca sacrificio. Puede parecer más idealista y comprometido socialmente.

    ❤️ 7 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Busca sugestión. Seductor, carismático, busca intensidad y novedad.""",

    "orientacion": """    
    🎯 Vocación base

    - Turismo
    - Publicidad
    - Comunicación
    - Eventos
    - Emprendimientos creativos

    🔁 Según subtipo

    🟢 Conservación (estratégico práctico)
    – Negocios digitales
    – Marketing online

    🔵 Social (animador grupal)
    – Oratoria
    – Formación

    🔴 Sexual (apasionado intenso)
    – Producción artística
    – Startups creativas

    🌱 Clave evolutiva

    Proyectos a largo plazo.""",

    "mejorar": """Dónde está la energía, estás vos.

    • Cultivando enfoque y presencia emocional.
    • Aceptando el dolor como parte de la vida.
    • Desarrollando rutinas que equilibren diversión y responsabilidad.
    • Profundizando experiencias en lugar de dispersarlas.
    • Centrarse corporalemente en artes marciales.
    • Ejercicios de respiración llevados a la vida diaria.""",
},
        
8: {
    "titulo": "🔶 Tipo 8 — El Desafiador",
    "descripcion": """Directos, fuertes, protectores y decididos.
    Buscan controlar su entorno y no temen enfrentar conflictos.
    Son líderes naturales, enfocados en la justicia y la acción.""",

    "caracteristicas": """El valor del eneatipo 8 radica en la FUERZA y la PROTECCIÓN.

    Su mayor contribución es liderar, proteger y defender lo que considera justo. Es un IMPLEMENTADOR. Tiene capacidad de acción inmediata, toma decisiones con rapidez y asume responsabilidades en momentos críticos. Transforma las ideas en acciones y organiza el trabajo que debe hacerse. Puede ser inflexible, tener comunicación dura y está orientado a la acción. 

    Sus conductas recurrentes pueden incluir confrontar, imponer, controlar, proteger, dominar, liderar, blanco-negro, "soy el rey/reina". Puede caer en hábitos como acosar, amedrentar, desconfiar y como resultado genera miedo, es un salvador y se siente todopoderoso. Tiende a ir de frente, evitando mostrar debilidad.

    La creencia arraigada en su interior es que el mundo es un lugar donde el fuerte sobrevive y el débil es dominado. El miedo básico es ser vulnerable o controlado. El miedo constitutivo es perder poder o quedar a merced de otros, lo que genera una necesidad intensa de autonomía y dominio y una adicción al poder.

    Sus principales fortalezas son ser valiente, protector, decidido y líder natural. Sus áreas de mejora radican en la dominancia excesiva, la impulsividad y la dificultad para mostrar vulnerabilidad. El pecado capital del eneatipo 8 es la lujuria (exceso de intensidad y energía).

    En su lado luz se expresa con justicia, liderazgo valiente y protección genuina. En su lado sombra puede volverse autoritario, agresivo o insensible. 

    Cuando evoluciona, desarrolla sensibilidad, empatía y capacidad de cuidado, aprende a proteger sin invadir, integra la ternura como fortaleza. Por el contrario, cuando se pierde, en estrés, puede aislarse emocionalmente, se vuelve más desconfiado, frío o retraído y puede cerrarse y desconectarse para no sentirse expuesto.
    Las cualidades que lo equilibran son ser más enérgico, expansivo y emprendedor y ser más calmado, protector y estable. Cuando se desarrollan incorpora comprensión, tolerancia, paciencia y alegría, simpatía, sin severidad, se relaja y modera su energía, es distendido, ecúanime, y de buen humor. Por el contrario, cuando no se desarrolla, cae en la superficialidad y la terquedad, es agresivo, no razona, discute por discutir, busca motivos para confrontar, es intolerante, impaciente, serio y con poco sentido del humor. 

    Otro punto de evolución es el punto ciego, es el compartir, trabajar las formas, consensuar, medir las consecuencias de sus palabras, reflexionar y trabajar en equipo. Debe dejar de creer que mostrar vulnerabilidad es sinónimo de debilidad. Pertenece a la triada de la acción, vive en el presente y su necesidad es de autonomía. 

    Cabe destacar que existen 3 subtipos:
    🏠 8 Conservación: busca seguridad, recursos y estabilidad. Busca satisfacción. Protector de recursos y territorio. Fuerte y directo.

    👥 8 Social: busca grupo, pertenencia e imagen social. Es solidario. Defiende al grupo. Líder protector.

    ❤️ 8 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Busca posesión. Muy intenso, dominante en relaciones.""",

    "orientacion": """    
    🎯 Vocación base

    - Dirección empresarial
    - Abogacía
    - Emprendimiento
    - Política
    - Deportes

    🔁 Según subtipo

    🟢 Conservación (protector territorial)
    – Empresa familiar
    – Seguridad

    🔵 Social (líder comunitario)
    – Política
    – Dirección institucional

    🔴 Sexual (intenso dominante)
    – Negociación
    – Liderazgo de alto impacto

    🌱 Clave evolutiva

    Aprender liderazgo consciente.""",
    
    "mejorar": """No digas todo lo que piensas, pero piensa TODO lo que DICES. 
    
     • Practicando empatía sin perder firmeza. 
     • Abrazando vulnerabilidad como fuerza interna. 
     • Equilibrando poder con compasión. 
     • Construyendo confianza sin confrontación innecesaria.
     • Descargar energía físicamente. 
     • Orientar su energía, darle que haga algo.""",
},
        
9: {
    "titulo": "🔷 Tipo 9 — El Pacificador",
    "descripcion": """Calmados, tranquilos, atentos y conciliadores.
    Valoran la paz y evitan confrontaciones.
    Pueden perder su propia agenda personal para mantener la armonía.""",

    "caracteristicas": """El valor del eneatipo 9 radica en la ARMONÍA y la PRESENCIA.

    Su mayor contribución es ser COHESIONADOR, mediar, integrar y generar paz en los entornos. Tiene capacidad de escuchar, contener y equilibrar posiciones opuestas. Es cooperador, perceptivo y diplomático. Escucha e impide los enfrentamientos.

    Sus conductas recurrentes pueden incluir postergación, evitación del conflicto y adaptación excesiva. Tiende a minimizar sus propias necesidades para mantener la calma externa, volviendose indeciso. Busca pasar inadvertido, no adquiere compromiso. Puede tener hábitos como la inercia psicológica, sobreadaptación, resignación, poco interés
    por sobresalir, propensión a hábitos robóticos, distracción, amistosa sociabilización y como resultado, desarrolla el síndrome del buen tipo, con una actitud pasiva que se relega. 

    La creencia arraigada en su interior es que el conflicto rompe el vínculo y debe evitarse. "El mundo no me toma en cuenta, es mejor pasar inadvertido". El miedo básico es la pérdida de conexión y el conflicto. El miedo constitutivo es a no poder, quedar excluido o desconectado, lo que genera una necesidad profunda de pertenencia y estabilidad y de ser fuerte. Se siente fuerte no haciendo, lo que deriva en una adicción a la comodidad.

    Sus principales fortalezas son ser mediador, paciente, estable y conciliador. Sus áreas de mejora radican en la indecisión, la pasividad y la evasión de confrontaciones necesarias. El pecado capital del eneatipo 9 es la pereza (inercia interior o adormecimiento de sí mismo).

    En su lado luz se expresa con armonía, serenidad y presencia equilibrada. En su lado sombra puede desconectarse de sí mismo, anestesiar sus deseos o diluir su identidad. Cuando evoluciona, desarrolla determinación, foco y acción, aprende a priorizar sus metas personales, integra dinamismo sin perder serenidad. En estrés puede volverse ansioso, desconfiado o temeroso, puede anticipar problemas y perder su calma característica.
    Las actitudes que lo equilibran son ser más firme, protector y práctico y ser más idealista, organizado y correcto. Si logra el equilibrio, obtiene la capacidad de activarse para expresar y decidir, según lo que desea, piensa y siente, saliendo de la comodidad y el dejarse estar. Se compromete y decide con firmeza en función de un ideal de vida. 
    Si no las desarrolla, es intolerante, impaciente, serio, con poco sentido del humor. Le cuesta activarse, espera que los demás le ayuden o hagan por él lo que se debe hacer.

    Otro de los caminos de evolución es identificar el punto ciego: creer que para ser amado debe desaparecer o adaptarse totalmente, tiene que aprender a decir lo que piensa y siente. Pertenece a la tríada instintiva (acción), su necesidad central es la autonomía, armonía y estabilidad. Vive en el presente. Guarda su capacidad de acción evitando el conflicto.  

    Cabe destacar que existen 3 subtipos:
    🏠 9 Conservación: busca seguridad, recursos y estabilidad. Desarrolla apetito. Busca comodidad y bienestar físico. Evita conflicto.

    👥 9 Social: busca grupo, pertenencia e imagen social. Busca participación. se adapta al grupo y busca armonía colectiva.

    ❤️ 9 Sexual: busca intensidad y conexión profunda. Sus relaciones son uno a uno, es selectivo. Busca fusión. Tiende a perderse en el otro. Fuerte necesidad de conexión.""",

    "orientacion": """    
    🎯 Vocación base

    - Mediación
    - Terapias
    - Recursos Humanos
    - Educación
    - Actividades holísticas

    🔁 Según subtipo

    🟢 Conservación (fusionado cómodo)
    – Administración
    – Trabajo estable

    🔵 Social (armonizador grupal)
    – RRHH
    – Coordinación comunitaria

    🔴 Sexual (fusionador intenso)
    – Terapias de pareja
    – Coaching relacional

    🌱 Clave evolutiva

    Trabajos donde tengan voz y decisión.""",

    "mejorar": """No dices nada para evitar conflictos, y vives en conflicto por no decir nada.

    • Practicando afirmación personal sin necesidad de evitar confrontaciones.
    • Cultivando claridad y enfoque.
    • Ejercitando toma de decisiones conscientes.
    • Integrando presencia activa con serenidad interior.
    • Aprendiendo a expresar lo que deseas sin minimizarlo.
    • Motivarse con una causa trascendental, espiritual, solidaria.
    • No presionarse, exigirse o reclamarse. Tampoco permitir que otros lo hagan.""",
},

}


def build_payload_from_scores(porcentaje_scores: dict, nombre: str, email: str, titulo: str = "Informe Eneagrama", mensaje_final: str = "") -> dict:
    """
    Construye el payload completo del informe integral a partir de porcentaje_scores.
    porcentaje_scores: {1: 32.0, 2: 11.0, ...} (claves int, valores float)
    """
    # Ejes de Afinidad
    afinidades = []
    for eje, cfg in EJES_AFINIDAD.items():
        tipos = cfg["tipos"]
        prom = round(sum(porcentaje_scores[t] for t in tipos) / len(tipos), 1)
        estado = clasificar_eje(prom)
        afinidades.append({"eje": eje, "tipos": tipos, "valor": prom, "estado": estado,
                            "descripcion": cfg["descripcion"], "perfil_alto": cfg["perfil_alto"], "perfil_bajo": cfg["perfil_bajo"]})

    afinidades_parrafos = []
    for a in afinidades:
        v = a["valor"]
        txt = a["descripcion"] + "\n\n"
        if es_bajo(v):
            txt += "Este eje aparece por debajo de la media, lo que indica que es un área a desarrollar."
        elif abs(v - 11.1) <= 0.1:
            txt += "Este eje aparece equilibrado, lo que indica que estas cualidades están presentes de forma estable."
        else:
            txt += "Este eje aparece por encima de la media, lo que indica que posees estas características."
        perfil_cfg = EJES_AFINIDAD.get(a["eje"], {})
        perfil = perfil_cfg.get("perfil_bajo" if es_bajo(v) else "perfil_alto", "")
        if perfil:
            txt += "\n\n" + perfil
        afinidades_parrafos.append(txt)

    # Síntesis de afinidades
    ejes_desafio = [a for a in afinidades if es_bajo(a["valor"])]
    ejes_desarrollados = [a for a in afinidades if es_desarrollado(a["valor"])]
    ejes_moderar = [a for a in afinidades if a["estado"] in ("elevado", "excesivo")]
    antidotos_desafio, virtudes_desafio, virtudes_principales = [], [], []
    for x in ejes_desafio:
        for t in x["tipos"]:
            v = VIRTUDES_POR_TIPO[t]
            if es_bajo(porcentaje_scores[t]) and v not in virtudes_desafio:
                virtudes_desafio.append(v)
    for x in ejes_desarrollados:
        for t in x["tipos"]:
            v = VIRTUDES_POR_TIPO[t]
            if es_desarrollado(porcentaje_scores[t]) and v not in virtudes_principales:
                virtudes_principales.append(v)
    sintesis_afinidades_parrafos = []
    ejes_desafio_nombres = [x["eje"] for x in ejes_desafio]
    ejes_principales_nombres = [x["eje"] for x in ejes_desarrollados if x["estado"] in ("equilibrado", "alto_leve")]
    if ejes_desafio_nombres:
        p = (f"Aquí se encuentra tu principal desafío evolutivo en los ejes de {juntar_lista_humana(ejes_desafio_nombres)}. "
             f"Las virtudes a desarrollar son {juntar_lista_humana(virtudes_desafio)}, "
             f"integrando profundidad interior con expresión auténtica.")
        sintesis_afinidades_parrafos.append(p)
    if virtudes_principales:
        sintesis_afinidades_parrafos.append(f"Tus principales virtudes son {juntar_lista_humana(virtudes_principales)}.")
    if ejes_moderar:
        sintesis_afinidades_parrafos.append("Estas cualidades constituyen pilares de tu estructura personal, aunque será importante moderarlas cuando se intensifiquen en exceso.")

    # Opuestos complementarios
    opuestos = []
    opuestos_parrafos = []
    for eje, cfg in OPUESTOS_COMPLEMENTARIOS.items():
        tipos = cfg["tipos"]
        prom = round(sum(porcentaje_scores[t] for t in tipos) / len(tipos), 1)
        estado = clasificar_eje(prom)
        opuestos.append({"eje": eje, "valor": prom, "estado": estado, "tipos": tipos, "virtudes": cfg.get("virtudes", {})})
        txt = cfg["descripcion"] + "\n\n"
        if es_bajo(prom):
            txt += cfg["msg_bajo"]
        elif abs(prom - 11.1) <= 0.1:
            txt += cfg["msg_equilibrado"]
        else:
            txt += cfg["msg_alto"]
        txt += "\n\n" + cfg["luz"] + "\n" + cfg["sombra"]
        opuestos_parrafos.append(txt)

    ejes_bajo_op = [o["eje"] for o in opuestos if es_bajo(o["valor"])]
    ejes_exceso_op = [o["eje"] for o in opuestos if o["estado"] in ("elevado", "excesivo")]
    virtudes_desafio_op, virtudes_ok_op = [], []
    for o in opuestos:
        for t in o["tipos"]:
            palabra = o["virtudes"].get(t)
            if not palabra:
                continue
            if es_bajo(porcentaje_scores[t]):
                if palabra not in virtudes_desafio_op:
                    virtudes_desafio_op.append(palabra)
            else:
                if palabra not in virtudes_ok_op:
                    virtudes_ok_op.append(palabra)
    opuestos_sintesis = []
    if ejes_bajo_op:
        opuestos_sintesis.append(f"Aquí se encuentra tu principal desafío evolutivo en los ejes del {juntar_lista_humana(ejes_bajo_op)}. Las virtudes a desarrollar son {juntar_lista_humana(virtudes_desafio_op)}.")
    if virtudes_ok_op:
        opuestos_sintesis.append(f"Tus principales virtudes son {juntar_lista_humana(virtudes_ok_op)}.")
    if ejes_exceso_op:
        opuestos_sintesis.append("Estas cualidades constituyen pilares de tu estructura personal, aunque será importante moderarlas cuando se intensifiquen en exceso.")

    # Análisis de ejes de simetría
    ejes_sim = []
    for eje in ORDEN_EJES:
        cfg = EJES_SIMETRIA[eje]
        tipos = cfg["tipos"]
        antidoto = cfg["antidoto"]
        prom = round(sum(porcentaje_scores[t] for t in tipos) / len(tipos), 1)
        estado = clasificar_eje(prom)
        ejes_sim.append({"eje": eje, "valor": prom, "estado": estado, "antidoto": antidoto,
                         "virtudes": [VIRTUDES_POR_TIPO[t] for t in tipos], "tipos": tipos})

    analisis_ejes_parrafos = []
    for item in ejes_sim:
        eje = item["eje"]
        v = item["valor"]
        est = item["estado"]
        antidoto = item["antidoto"]
        if eje == "HACER":
            if es_bajo(v):
                base = (f"El eje del HACER aparece por debajo de la media, lo que indica que hay algo urgente que necesita ponerse en acción. En esta etapa, el desafío es dejar de evaluar o postergar y hacer lo que debas hacer para avanzar. Antídoto: {antidoto}.")
            else:
                base = ("El eje del HACER se encuentra por encima de la media, indicando una marcada orientación a la acción, ejecución y control. En su luz, esto implica claridad sobre tu ideal de vida y capacidad de concretar; en su sombra, puede traducirse en controlarte y controlar el entorno de forma permanente.")
                if est in ("elevado", "excesivo"):
                    base += f" Si esta energía se intensifica, conviene moderarla. Antídoto: {antidoto}."
        elif eje == "COMUNICAR":
            if es_bajo(v):
                base = (f"El eje del COMUNICAR aparece por debajo de la media, lo que indica que hay algo importante que no estás diciendo o expresando. Esto se vincula con tu mundo interno: aunque tema las consecuencias, comunicar lo esencial es parte de tu sanación. Antídoto: {antidoto}.")
            else:
                base = ("El eje del COMUNICAR se encuentra por encima de la media. En su luz, indica fluidez expresiva, capacidad de vincularse y articular ideas con claridad; en su sombra, puede traducirse en verborragia, manipulación sutil o evasión emocional a través de las palabras.")
                if est in ("elevado", "excesivo"):
                    base += f" Si se intensifica, practicá escucha activa. Antídoto: {antidoto}."
        elif eje == "TENER":
            if es_bajo(v):
                base = (f"El eje del TENER aparece por debajo de la media, lo que sugiere una carencia en la forma de sostener recursos, seguridad y valoración interna. Antídoto: {antidoto}.")
            else:
                base = ("El eje del TENER se encuentra por encima de la media. En su luz, indica capacidad para trabajar, lograr y alcanzar lo que querés, con decisión y empuje; en su sombra, puede llevar a desatender lo afectivo, lo físico o lo espiritual por una preocupación excesiva por el tener.")
                if est in ("elevado", "excesivo"):
                    base += f" Si se intensifica, practicá moderación. Antídoto: {antidoto}."
        elif eje == "SER":
            if es_bajo(v):
                base = (f"El eje del SER aparece por debajo de la media, indicando que hay un llamado a profundizar: mirarte a vos misma y a tu realidad con más honestidad y reflexión. No se trata de aislarse, sino de hacer un trabajo de introspección que te devuelva claridad y sentido. Antídoto: {antidoto}.")
            else:
                base = ("El eje del SER se encuentra por encima de la media. En su luz, indica profundidad y reflexión, una buena mirada de la vida y de vos misma; en su sombra, puede traducirse en encerrarte, aislarte o esconderte, evitando mirar una parte de tu realidad que no te gusta.")
                if est in ("elevado", "excesivo"):
                    base += f" Si se intensifica, cuidá no aislarte. Antídoto: {antidoto}."
        elif eje == "ESTAR":
            if es_bajo(v):
                base = (f"El eje del ESTAR aparece por debajo de la media, indicando dificultad para habitar el presente: podés estar pendiente del pasado o del futuro, o viviendo con tensión. El desafío evolutivo es aprender a estar aquí y ahora, sosteniendo tu centro. Antídoto: {antidoto}.")
            else:
                base = ("El eje del ESTAR se encuentra por encima de la media. En su luz, indica presencia, calma y capacidad de sostener el momento; en su sombra, puede traducirse en inercia, falta de iniciativa o exceso de conformismo.")
                if est in ("elevado", "excesivo"):
                    base += f" Si se intensifica, cultivá iniciativa. Antídoto: {antidoto}."
        else:
            base = f"Eje {eje}: valor {v}."
        analisis_ejes_parrafos.append(base)

    # Síntesis evolutiva
    ejes_desafio_ev = [x for x in ejes_sim if es_bajo(x["valor"])]
    ejes_desarrollados_ev = [x for x in ejes_sim if es_desarrollado(x["valor"]) and x["estado"] in ("equilibrado", "alto_leve")]
    ejes_moderar_ev = [x for x in ejes_sim if x["estado"] in ("elevado", "excesivo")]
    antidotos_desafio_ev, virtudes_desafio_ev, virtudes_principales_ev = [], [], []
    for x in ejes_desafio_ev:
        antidotos_desafio_ev.append(x["antidoto"])
        for t in x["tipos"]:
            v = VIRTUDES_POR_TIPO[t]
            if es_bajo(porcentaje_scores[t]) and v not in virtudes_desafio_ev:
                virtudes_desafio_ev.append(v)
    for x in ejes_desarrollados_ev:
        for t in x["tipos"]:
            v = VIRTUDES_POR_TIPO[t]
            if es_desarrollado(porcentaje_scores[t]) and v not in virtudes_principales_ev:
                virtudes_principales_ev.append(v)
    sintesis_parrafos = []
    ejes_desafio_ev_nombres = [x["eje"] for x in ejes_desafio_ev]
    if ejes_desafio_ev_nombres:
        p1 = (f"Aquí se encuentra tu principal desafío evolutivo en los ejes del {juntar_lista_humana(ejes_desafio_ev_nombres)}. "
              f"Las virtudes a desarrollar son {juntar_lista_humana(virtudes_desafio_ev)}, integrando profundidad interior con expresión auténtica."
              f" Antídotos: {juntar_lista_humana(list(dict.fromkeys(antidotos_desafio_ev)))}.")
        sintesis_parrafos.append(p1)
    if virtudes_principales_ev:
        sintesis_parrafos.append(f"Tus principales virtudes son {juntar_lista_humana(virtudes_principales_ev)}.")
    if ejes_moderar_ev:
        sintesis_parrafos.append("Estas cualidades constituyen pilares de tu estructura personal, aunque será importante moderarlas cuando se intensifiquen en exceso.")

    # Eneatipo principal y ala
    scores_raw = {t: int(round(porcentaje_scores[t])) for t in range(1, 10)}
    max_score = max(scores_raw.values())
    top_types = [t for t, s in scores_raw.items() if s == max_score and max_score > 0]
    if len(top_types) > 1:
        mejor_tipo, mejor_val = None, -1
        for tipo in top_types:
            ala_izq, ala_der = ALAS[tipo]
            val = max(porcentaje_scores.get(ala_izq, 0), porcentaje_scores.get(ala_der, 0))
            if val > mejor_val:
                mejor_val = val
                mejor_tipo = tipo
        top_types = [mejor_tipo]

    sorted_scores = sorted(scores_raw.items(), key=lambda x: x[1], reverse=True)
    sorted_porcentajes = [(t, porcentaje_scores[t]) for t, _ in sorted_scores]

    ala_textos = []
    if top_types:
        principal = top_types[0]
        izq, der = ALAS[principal]
        pct_izq = porcentaje_scores.get(izq, 0)
        pct_der = porcentaje_scores.get(der, 0)
        if pct_izq > pct_der:
            clave = f"{principal}w{izq}"
        elif pct_der > pct_izq:
            clave = f"{principal}w{der}"
        else:
            for c in [f"{principal}w{izq}", f"{principal}w{der}"]:
                t = DESCRIPCION_ALAS.get(c)
                if t:
                    ala_textos.append(t)
            clave = None
        if clave:
            t = DESCRIPCION_ALAS.get(clave)
            if t:
                ala_textos = [t]

    # Camino evolutivo
    creencias_limitantes = {
        1: "Miedo a PERDER LA LIBERTAD por quedar atrapado en estructuras o situaciones que me asfixian (trabajo, pareja, etc).",
        2: "Miedo a ABRIRME AFECTIVAMENTE, por que puedo sufrir.",
        3: "Miedo a FRACASAR, por lo que no estoy haciendo lo que tengo que hacer para lograr el desarrollo personal.",
        4: "Miedo a MIRARME A MI MISMO, porque hay algo de mí que no me gusta ver, o que no puedo cambiar (culpa del pasado, baja autoestima, etc).",
        5: "Miedo a SUFRIR POR ALGO QUE NO QUIERO O NO PUEDO VER O ACEPTAR, algo de mi realidad que me duele, no está superado, o no sé qué es, pero me molesta.",
        6: "Miedo a PERDER LA LIBERTAD por quedar atrapado en obligaciones o compromisos que se ha creado uno mismo.",
        7: "Miedo a DISFRUTAR, por no poder soltar cosas o situaciones por exceso de responsabilidades y por temor a perder el control (mal concepto de la alegría).",
        8: "Miedo a TOMAR UNA DECISIÓN, por las consecuencias que va atraer o traerme y no saber decir que basta o que no. Hay algo a lo cual no le estoy diciendo que no.",
        9: "Miedo a PARAR, porque si paro, ¿quién se hace cargo de todo lo que me hago cargo yo?, es una manera de seguir adicto a la actividad.",
    }
    low3 = sorted(porcentaje_scores.items(), key=lambda x: (x[1], x[0]))[:3]
    camino_evolucion = [(tipo, pct, creencias_limitantes[tipo]) for tipo, pct in low3]

    # Bonus estructura del pensamiento
    bonus_data = build_bonus_estructura_pensamiento(porcentaje_scores)

    return {
        "titulo": titulo,
        "analista": "AZ Consultora",
        "propietario": {"nombre": nombre, "email": email},
        "fecha_test": "manual",
        "ala_textos": ala_textos,

        "desarrollo": {
            "top_types": top_types,
            "total_marked": 100,
            "max_score": max_score,
            "eneatipo_textos": ENEATIPO_TEXTOS,
            "ala_textos": ala_textos,
            "camino_evolucion": camino_evolucion,
            "afinidades_parrafos": afinidades_parrafos,
            "sintesis_afinidades": sintesis_afinidades_parrafos,
            "opuestos_parrafos": opuestos_parrafos,
            "opuestos_sintesis": opuestos_sintesis,
            "analisis_ejes": analisis_ejes_parrafos,
            "sintesis_evolutiva": sintesis_parrafos,
            "bonus_estructura": bonus_data["estructura"],
            "bonus_sintesis": bonus_data["sintesis"],
        },

        "conclusiones": {
            "max_score": max_score,
            "eneatipo_textos": ENEATIPO_TEXTOS,
            "ala_textos": ala_textos,
            "sintesis_afinidades": sintesis_afinidades_parrafos,
            "opuestos_sintesis": opuestos_sintesis,
            "sintesis_evolutiva": sintesis_parrafos,
            "bonus_sintesis": bonus_data["sintesis"],
        },

        "graficos_anexos": {
            "resultados": {str(k): v for k, v in porcentaje_scores.items()},
            "sorted_porcentajes": sorted_porcentajes,
            "top_types": top_types,
        },

        "mensaje_final": mensaje_final or "Informe generado manualmente",
    }


@app.get("/result")
def result():
    if not session.get("pago_ok"):
        return redirect(url_for("index"))
    questions = load_questions()
    answers = session.get("answers", {})

    # Contar cuántas respuestas marcaste en total
    total_marked = sum(1 for qid, val in answers.items() if val)

    # Calcular scores por tipo
    scores = {t: 0 for t in range(1, 10)}
    for q in questions:
        qid = str(q["id"])
        if answers.get(qid):
            scores[q["type"]] += 1

    # Transformar a porcentajes (sobre total_marked)
    porcentaje_scores = {}
    for tipo, score in scores.items():
        porcentaje = (score / total_marked * 100) if total_marked > 0 else 0
        porcentaje_scores[tipo] = round(porcentaje, 1)
       
    # ✅ NUEVO: labels/values para el radar (en orden 1..9)
    labels = [str(i) for i in range(1, 10)]
    values = [porcentaje_scores[i] for i in range(1, 10)]
    

    # -----------------------------
    # Ejes de Afinidad
    # -----------------------------
    afinidades = []

    for eje, cfg in EJES_AFINIDAD.items():
        tipos = cfg["tipos"]
        prom = round(sum(porcentaje_scores[t] for t in tipos) / len(tipos), 1)
        estado = clasificar_eje(prom)
    
        afinidades.append({
            "eje": eje,
            "tipos": tipos,   # ✅ AGREGAR ESTA LÍNEA
            "valor": prom,
            "estado": estado,
            "descripcion": cfg["descripcion"],
            "perfil_alto": cfg["perfil_alto"],
            "perfil_bajo": cfg["perfil_bajo"],
        })


    
    # -----------------------------
    # Texto: Ejes de Afinidad (como lo indicaste)
    # -----------------------------
    afinidades_parrafos = []
    
    for a in afinidades:
        eje = a["eje"]
        v = a["valor"]
    
        txt = a["descripcion"] + "\n\n"
    
        # estado
        if es_bajo(v):
            txt += "Este eje aparece por debajo de la media, lo que indica que es un área a desarrollar."
        elif abs(v - 11.1) <= 0.1:
            txt += "Este eje aparece equilibrado, lo que indica que estas cualidades están presentes de forma estable."
        else:
            txt += "Este eje aparece por encima de la media, lo que indica que posees estas características."
    
        # ✅ NUEVO: perfiles (sin tocar nada de arriba)
        perfil_cfg = EJES_AFINIDAD.get(eje, {})
        if es_bajo(v):
            perfil = perfil_cfg.get("perfil_bajo", "")
        else:
            perfil = perfil_cfg.get("perfil_alto", "")
    
        if perfil:
            txt += "\n\n" + perfil
    
        afinidades_parrafos.append(txt)


    
    # -----------------------------
    # Síntesis de Afinidades (mismo formato que tu síntesis)
    # -----------------------------
    ejes_afinidad_bajos = [a for a in afinidades if es_bajo(a["valor"])]
    ejes_afinidad_ok = [a for a in afinidades if not es_bajo(a["valor"])]
    
    # palabras por tipos bajo / ok
    palabras_desafio = []
    for a in ejes_afinidad_bajos:
        for t in a["tipos"]:
            p = PALABRAS_AFINIDAD_POR_TIPO.get(t)
            if p and p not in palabras_desafio:
                palabras_desafio.append(p)
    
    palabras_virtudes = []
    for a in ejes_afinidad_ok:
        for t in a["tipos"]:
            p = PALABRAS_AFINIDAD_POR_TIPO.get(t)
            if p and p not in palabras_virtudes:
                palabras_virtudes.append(p)
    
    sintesis_afinidades_parrafos = []
    
    if ejes_afinidad_bajos:
        nombres_bajos = [a["eje"] for a in ejes_afinidad_bajos]
        p1 = (
            f"Aquí se encuentra tu principal desafío evolutivo en los ejes de "
            f"{juntar_lista_humana(nombres_bajos)}. "
            f"Las virtudes a desarrollar son {juntar_lista_humana(palabras_desafio)}."
        )
        sintesis_afinidades_parrafos.append(p1)
    
    if ejes_afinidad_ok:
        p2 = f"Tus principales virtudes son {juntar_lista_humana(palabras_virtudes)}."
        sintesis_afinidades_parrafos.append(p2)
    
    # tal como lo pediste (frase fija)
    sintesis_afinidades_parrafos.append(
        "Estas cualidades constituyen pilares de tu estructura personal, aunque será importante moderarlas cuando se intensifiquen en exceso."
    )
    
    opuestos = []
    opuestos_parrafos = []
    
    for eje, cfg in OPUESTOS_COMPLEMENTARIOS.items():
        tipos = cfg["tipos"]
        prom = round(sum(porcentaje_scores[t] for t in tipos) / len(tipos), 1)
        estado = clasificar_eje(prom)
    
        opuestos.append({
            "eje": eje,
            "valor": prom,
            "estado": estado,
            "tipos": tipos,
            "virtudes": cfg.get("virtudes", {}),
        })
    
        txt = cfg["descripcion"] + "\n\n"
    
        if es_bajo(prom):
            txt += cfg["msg_bajo"]
        elif abs(prom - 11.1) <= 0.1:
            txt += cfg["msg_equilibrado"]
        else:
            txt += cfg["msg_alto"]
    
        # Luz / sombra del eje (siempre visible)
        txt += "\n\n" + cfg["luz"]
        txt += "\n" + cfg["sombra"]
    
        opuestos_parrafos.append(txt)

    ejes_bajo = [o["eje"] for o in opuestos if es_bajo(o["valor"])]
    ejes_exceso = [o["eje"] for o in opuestos if o["estado"] in ("elevado", "excesivo")]
    
    virtudes_desafio = []
    virtudes_ok = []
    
    for o in opuestos:
        for t in o["tipos"]:
            palabra = o["virtudes"].get(t)
            if not palabra:
                continue
            if es_bajo(porcentaje_scores[t]):
                if palabra not in virtudes_desafio:
                    virtudes_desafio.append(palabra)
            else:
                if palabra not in virtudes_ok:
                    virtudes_ok.append(palabra)
    
    opuestos_sintesis = []
    
    if ejes_bajo:
        opuestos_sintesis.append(
            f"Aquí se encuentra tu principal desafío evolutivo en los ejes del {juntar_lista_humana(ejes_bajo)}. "
            f"Las virtudes a desarrollar son {juntar_lista_humana(virtudes_desafio)}."
        )
    
    if virtudes_ok:
        opuestos_sintesis.append(
            f"Tus principales virtudes son {juntar_lista_humana(virtudes_ok)}."
        )
    
    if ejes_exceso:
        opuestos_sintesis.append(
            "Estas cualidades constituyen pilares de tu estructura personal, aunque será importante moderarlas cuando se intensifiquen en exceso."
        )

    
    # -----------------------------
    # Ejes de equilibrio (promedio)
    # -----------------------------
    ejes = []
    for eje in ORDEN_EJES:
        cfg = EJES_SIMETRIA[eje]
        tipos = cfg["tipos"]
        antidoto = cfg["antidoto"]

        # promedio de porcentajes (regla tuya)
        prom = sum(porcentaje_scores[t] for t in tipos) / len(tipos)
        prom = round(prom, 1)

        estado = clasificar_eje(prom)

        virtudes = [VIRTUDES_POR_TIPO[t] for t in tipos]
        ejes.append({
            "eje": eje,
            "valor": prom,
            "estado": estado,
            "antidoto": antidoto,
            "virtudes": virtudes,
            "tipos": tipos,
        })

    # -----------------------------
    # Texto: Análisis de Ejes
    # -----------------------------
    analisis_ejes_parrafos = []
    for item in ejes:
        eje = item["eje"]
        v = item["valor"]
        est = item["estado"]
        antidoto = item["antidoto"]

        if eje == "HACER":
            if es_bajo(v):
                base = (
                    "El eje del HACER aparece por debajo de la media, lo que indica que "
                    "hay algo urgente que necesita ponerse en acción. En esta etapa, el desafío es "
                    "dejar de evaluar o postergar y hacer lo que debas hacer para avanzar."
                    f" Antídoto: {antidoto}."
                )
            else:
                base = (
                    "El eje del HACER se encuentra por encima de la media, indicando una marcada orientación "
                    "a la acción, ejecución y control. En su luz, esto implica claridad sobre tu ideal de vida "
                    "y capacidad de concretar; en su sombra, puede traducirse en controlarte y controlar el entorno "
                    "de forma permanente."
                )
                if est in ("elevado", "excesivo"):
                    base += f" Si esta energía se intensifica, conviene moderarla. Antídoto: {antidoto}."
            analisis_ejes_parrafos.append(base)
            continue
    
        if eje == "COMUNICAR":
            if es_bajo(v):
                base = (
                  "El eje del COMUNICAR aparece por debajo de la media, lo que indica que "
                  "hay algo importante que no estás diciendo o expresando. Esto se vincula con tu mundo interno: "
                  "aunque tema las consecuencias, comunicar lo esencial es parte de tu sanación."
                  f" Antídoto: {antidoto}."
                )
            else:
                base = (
                  "El eje del COMUNICAR se encuentra por encima de la media. En su luz, "
                  "indica una buena capacidad de comunicación: saber escuchar, llegar al otro y conectar con empatía; "
                  "en su sombra, puede aparecer hablar mucho sin decir lo esencial."
                )
                # si está muy alto, sugerimos moderar
                if item["estado"] in ("elevado", "excesivo"):
                    base += f" Antídoto: {antidoto}."
            analisis_ejes_parrafos.append(base)
            continue
    
    
        if eje == "TENER":
            if es_bajo(v):
                base = (
                    "El eje del TENER aparece por debajo de la media, lo que sugiere una carencia en la forma "
                    "de sostener recursos, seguridad y valoración interna. Esto puede expresarse como dificultad "
                    "para reconocer tu propio valor, ordenar prioridades, poner precio/cobrar, administrar o pedir lo "
                    "que necesitás sin culpa."
                    f" Antídoto: {antidoto}."
                )
            else:
                base = (
                    "El eje del TENER se encuentra por encima de la media. En su luz, indica capacidad para trabajar, "
                    "lograr y alcanzar lo que querés, con decisión y empuje; en su sombra, puede llevar a desatender lo "
                    "afectivo, lo físico o lo espiritual por una preocupación excesiva por el tener."
                )
                if est in ("elevado", "excesivo"):
                    base += f" Si se intensifica, practicá moderación. Antídoto: {antidoto}."
            analisis_ejes_parrafos.append(base)
            continue
    
    
        if eje == "SER":
            if es_bajo(v):
                base = (
                    "El eje del SER aparece por debajo de la media, indicando que hay un llamado a profundizar: "
                    "mirarte a vos misma y a tu realidad con más honestidad y reflexión. No se trata de aislarse, "
                    "sino de hacer un trabajo de introspección que te devuelva claridad y sentido."
                    f" Antídoto: {antidoto}."
                )
            else:
                base = (
                    "El eje del SER se encuentra por encima de la media. En su luz, indica profundidad y reflexión, "
                    "una buena mirada de la vida y de vos misma; en su sombra, puede traducirse en encerrarte, "
                    "aislarte o esconderte, evitando mirar una parte de tu realidad que no te gusta."
                )
                if est in ("elevado", "excesivo"):
                    base += f" Si se intensifica, cuidá no aislarte. Antídoto: {antidoto}."
            analisis_ejes_parrafos.append(base)
            continue
    
        if eje == "ESTAR":
            if es_bajo(v):
                base = (
                    "El eje del ESTAR aparece por debajo de la media, indicando dificultad para habitar el presente: "
                    "podés estar pendiente del pasado o del futuro, o viviendo con tensión. El desafío evolutivo es "
                    "aprender a estar aquí y ahora, sosteniendo tu centro."
                    f" Antídoto: {antidoto}."
                )
            else:
                base = (
                    "El eje del ESTAR se encuentra por encima de la media. En su luz, indica presencia y capacidad de "
                    "vivir el presente con intensidad; en su sombra, puede aparecer una forma de 'estar sin estar': "
                    "se evita el conflicto o se busca que no haya problemas, pero internamente no hay presencia real."
                )
                if est in ("elevado", "excesivo"):
                    base += f" Si se intensifica, buscá presencia genuina. Antídoto: {antidoto}."
            analisis_ejes_parrafos.append(base)
            continue


    # -----------------------------
    # Texto: Síntesis Evolutiva
    # -----------------------------
    ejes_bajos = [x for x in ejes if x["valor"] < MEDIA_TEO]
    ejes_virtud = [x for x in ejes if x["valor"] >= MEDIA_TEO and x["estado"] in ("equilibrado", "alto_leve")]
    ejes_moderar = [x for x in ejes if x["estado"] in ("elevado", "excesivo")]

    # virtudes de desafío (sin repetir, manteniendo orden)
    # ejes bajos (por promedio del eje)
    ejes_bajos = [x for x in ejes if es_bajo(x["valor"])]
    
    virtudes_desafio = []
    antidotos_desafio = []
    ejes_desafio_nombres = []

    for x in ejes_bajos:
        ejes_desafio_nombres.append(x["eje"])
        antidotos_desafio.append(x["antidoto"])
    
        # ✅ SOLO virtudes de los TIPOS que están por debajo de la media
        for t in x["tipos"]:
            if es_bajo(porcentaje_scores[t]):
                v = VIRTUDES_POR_TIPO[t]
                if v not in virtudes_desafio:
                    virtudes_desafio.append(v)


    virtudes_principales = []
    ejes_principales_nombres = []
    
    for x in ejes:
        # desarrollados = >= media (incluye equilibrado)
        if es_desarrollado(x["valor"]) and x["estado"] in ("equilibrado", "alto_leve"):
            ejes_principales_nombres.append(x["eje"])
    
        # ✅ virtudes por TIPO desarrollado (no por eje)
        for t in x["tipos"]:
            if es_desarrollado(porcentaje_scores[t]):
                v = VIRTUDES_POR_TIPO[t]
                if v not in virtudes_principales:
                    virtudes_principales.append(v)


    # moderación
    antidotos_moderar = []
    ejes_moderar_nombres = []
    for x in ejes_moderar:
        ejes_moderar_nombres.append(x["eje"])
        antidotos_moderar.append(x["antidoto"])

    sintesis_parrafos = []

    if ejes_desafio_nombres:
        p1 = (
            f"Aquí se encuentra tu principal desafío evolutivo en los ejes del "
            f"{juntar_lista_humana(ejes_desafio_nombres)}. "
            f"Las virtudes a desarrollar son {juntar_lista_humana(virtudes_desafio)}, "
            f"integrando profundidad interior con expresión auténtica."
        )
        # Antídotos oficiales del modelo
        p1 += f" Antídotos: {juntar_lista_humana(list(dict.fromkeys(antidotos_desafio)))}."
        sintesis_parrafos.append(p1)

    if ejes_principales_nombres:
        p2 = (
            f"Tus principales virtudes son {juntar_lista_humana(virtudes_principales)}."
        )
        sintesis_parrafos.append(p2)

    if ejes_moderar_nombres:
        p3 = (
            f"Estas cualidades constituyen pilares de tu estructura personal, "
            f"aunque será importante moderarlas cuando se intensifiquen en exceso. "
            )
        sintesis_parrafos.append(p3)

    
    # Eneatipo principal
    max_score = max(scores.values()) if scores else 0
    top_types = [t for t, s in scores.items() if s == max_score and max_score > 0]
    
    # 🔥 NUEVA LÓGICA DE DESEMPATE POR ALA
    if len(top_types) > 1:
        mejor_tipo = None
        mejor_valor_ala = -1
    
        for tipo in top_types:
            ala_izq, ala_der = ALAS[tipo]
            valor_ala = max(
                porcentaje_scores.get(ala_izq, 0),
                porcentaje_scores.get(ala_der, 0)
            )
    
            if valor_ala > mejor_valor_ala:
                mejor_valor_ala = valor_ala
                mejor_tipo = tipo
    
        top_types = [mejor_tipo]
    
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    sorted_porcentajes = [(t, porcentaje_scores[t]) for (t, _) in sorted_scores]

    # -----------------------------
    # Ala (Wing) del tipo principal
    # -----------------------------
    ala_textos = []
    
    if top_types:
        principal = top_types[0]
    
        izq, der = ALAS[principal]
        pct_izq = porcentaje_scores.get(izq, 0)
        pct_der = porcentaje_scores.get(der, 0)
    
        if pct_izq > pct_der:
            clave = f"{principal}w{izq}"
            txt = DESCRIPCION_ALAS.get(clave)
            if txt:
                ala_textos = [txt]
        elif pct_der > pct_izq:
            clave = f"{principal}w{der}"
            txt = DESCRIPCION_ALAS.get(clave)
            if txt:
                ala_textos = [txt]
        else:
            # empate -> mostrar ambas descripciones (una por línea)
            clave1 = f"{principal}w{izq}"
            clave2 = f"{principal}w{der}"
            txt1 = DESCRIPCION_ALAS.get(clave1)
            txt2 = DESCRIPCION_ALAS.get(clave2)
            ala_textos = [t for t in (txt1, txt2) if t]



    
    eneatipo_textos = ENEATIPO_TEXTOS

    creencias_limitantes = {
        1: "Miedo a PERDER LA LIBERTAD por quedar atrapado en estructuras o situaciones que me asfixian (trabajo, pareja, etc).",
        2: "Miedo a ABRIRME AFECTIVAMENTE, por que puedo sufrir.",
        3: "Miedo a FRACASAR, por lo que no estoy haciendo lo que tengo que hacer para lograr el desarrollo personal.",
        4: "Miedo a MIRARME A MI MISMO, porque hay algo de mí que no me gusta ver, o que no puedo cambiar (culpa del pasado, baja autoestima, etc).",
        5: "Miedo a SUFRIR POR ALGO QUE NO QUIERO O NO PUEDO VER O ACEPTAR, algo de mi realidad que me duele, no está superado, o no sé qué es, pero me molesta.",
        6: "Miedo a PERDER LA LIBERTAD por quedar atrapado en obligaciones o compromisos que se ha creado uno mismo.",
        7: "Miedo a DISFRUTAR, por no poder soltar cosas o situaciones por exceso de responsabilidades y por temor a perder el control (mal concepto de la alegría).",
        8: "Miedo a TOMAR UNA DECISIÓN, por las consecuencias que va atraer o traerme y no saber decir que basta o que no. Hay algo a lo cual no le estoy diciendo que no.",
        9: "Miedo a PARAR, porque si paro, ¿quién se hace cargo de todo lo que me hago cargo yo?, es una manera de seguir adicto a la actividad.",
    }

    # Ranking de los 3 tipos con menor porcentaje
    # (si total_marked == 0, todos dan 0; en ese caso igual mostramos 1..9 ordenados)
    low3 = sorted(porcentaje_scores.items(), key=lambda x: (x[1], x[0]))[:3]

    # Lista lista para el template: [(tipo, porcentaje, texto), ...]
    camino_evolucion = [
        (tipo, pct, creencias_limitantes[tipo]) for tipo, pct in low3
    ]
    
    bonus_data = build_bonus_estructura_pensamiento(porcentaje_scores) 
    bonus_estructura = bonus_data["estructura"] 
    bonus_sintesis = bonus_data["sintesis"]

    # ✅ Armar payload del informe (guardamos secciones para el PDF)
    usuario = session.get("usuario", {})
    report_payload = {
        "titulo": "Informe profundo de autoconocimiento",
        "analista": "AZ Consultora @az_coaching.terapeutico / +542975203761",
        "propietario": usuario,
        "fecha_test": usuario.get("fecha_test"),
    
        "desarrollo": {
            "top_types": top_types,
            "total_marked": total_marked,
            "max_score": max_score,
            "eneatipo_textos": eneatipo_textos,
            "ala_textos": ala_textos,
            "camino_evolucion": camino_evolucion,
            "afinidades_parrafos": afinidades_parrafos,
            "sintesis_afinidades": sintesis_afinidades_parrafos,
            "opuestos_parrafos": opuestos_parrafos,
            "opuestos_sintesis": opuestos_sintesis,
            "analisis_ejes": analisis_ejes_parrafos,
            "sintesis_evolutiva": sintesis_parrafos,
            "bonus_estructura": bonus_estructura,
            "bonus_sintesis": bonus_sintesis,
        },

        "conclusiones": {
            "max_score": max_score,
            "eneatipo_textos": eneatipo_textos,
            "ala_textos": ala_textos,
            "sintesis_afinidades": sintesis_afinidades_parrafos,
            "opuestos_sintesis": opuestos_sintesis,
            "sintesis_evolutiva": sintesis_parrafos,
            "bonus_sintesis": bonus_sintesis,
        },

        "graficos_anexos":  {
            "resultados": {str(k): v for k, v in porcentaje_scores.items()},
            "sorted_porcentajes": sorted_porcentajes,
            "top_types": top_types,
        },  
            
        "mensaje_final": (
            "Para una consulta personalizada o exploración de otras herramientas "
            "de autoconocimiento contactar a AZ Consultora @az_coaching.terapeutico "
            "o WhatsApp +54-2975203761."
        ),
    }
    
   
    # ✅ Guardar en BD
    if DBSession:
        db = DBSession()
        try:
            r = Report(
                owner_name=usuario.get("nombre"),
                owner_email=usuario.get("email"),
                owner_data=usuario,
                test_date_iso=usuario.get("fecha_test"),
                porcentaje_scores={str(k): v for k, v in porcentaje_scores.items()},
                top_types=top_types,
                report_json=report_payload,
                report_text="\n".join(sintesis_parrafos)  # opcional
            )
            db.add(r)
            db.commit()
            session["report_id"] = r.id
        finally:
            db.close()
    
    return render_template(
            "result.html",
            sorted_scores=sorted_scores,
            sorted_porcentajes=sorted_porcentajes,
            top_types=top_types,
            max_score=max_score,
            total_marked=total_marked,
            eneatipo_textos=eneatipo_textos,
            ala_textos=ala_textos,
            labels=labels,
            values=values,
            camino_evolucion=camino_evolucion,
            analisis_ejes_parrafos=analisis_ejes_parrafos,
            sintesis_parrafos=sintesis_parrafos,
            afinidades_parrafos=afinidades_parrafos,
            sintesis_afinidades_parrafos=sintesis_afinidades_parrafos,
            opuestos_parrafos=opuestos_parrafos,
            opuestos_sintesis=opuestos_sintesis,
            bonus_estructura=bonus_estructura,
            bonus_sintesis= bonus_sintesis,
            report_id=session.get("report_id")  # 👈 AGREGAR ESTO
    
        )

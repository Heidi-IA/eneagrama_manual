import json
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_JUSTIFY
from flask import send_file
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from flask import current_app
import mercadopago

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
APP_URL = os.environ.get("APP_URL", "http://localhost:5000")

DATA_PATH = Path("data/questions.json")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

ALAS = {
    1: (9, 2), 2: (1, 3), 3: (2, 4), 4: (3, 5),
    5: (4, 6), 6: (5, 7), 7: (6, 8), 8: (7, 9), 9: (8, 1),
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

ENEATIPO_TEXTOS = {
    1: {
        "titulo": "Tipo 1 — El Reformador",
        "descripcion": (
            "Personas éticas, con fuerte sentido del bien y del mal, buscan mejorar el mundo y la perfección. "
            "Son responsables, disciplinadas, y muy exigentes consigo mismas y con los demás. "
            "Tienden a autocriticarse y a querer que todo sea 'lo correcto'."
        ),
        "orientacion": (
            "Vocación base: Derecho / justicia, Ingeniería de procesos / calidad, Docencia, "
            "Gestión institucional, Medio ambiente, Auditoría. "
            "Trabajos donde puedan mejorar sistemas.\n\n"
            "Clave evolutiva: Aprender trabajos donde haya margen de error y creatividad."
        ),
    },
    2: {
        "titulo": "Tipo 2 — El Ayudador",
        "descripcion": (
            "Empáticos, cálidos y orientados a servir a otros. "
            "Encuentran satisfacción ayudando y siendo necesarios para quienes quieren. "
            "Pueden descuidar sus propias necesidades al priorizar las de otros."
        ),
        "orientacion": (
            "Vocación base: Psicología, Enfermería, Recursos Humanos, Coaching, "
            "Organización de eventos, Trabajo social.\n\n"
            "Clave evolutiva: Profesiones donde aprendan a poner límites."
        ),
    },
    3: {
        "titulo": "Tipo 3 — El Triunfador",
        "descripcion": (
            "Energéticos, adaptables y orientados al éxito. "
            "Se enfocan en metas, logros y reconocimiento. "
            "Suelen inspirar a otros con su energía, aunque pueden priorizar imagen y resultados."
        ),
        "orientacion": (
            "Vocación base: Marketing, Dirección empresarial, Ventas, Emprendimiento, "
            "Comunicación estratégica.\n\n"
            "Clave evolutiva: Trabajos donde el éxito no sea solo externo."
        ),
    },
    4: {
        "titulo": "Tipo 4 — El Individualista",
        "descripcion": (
            "Creativos, sensibles y emocionalmente profundos. "
            "Se sienten únicos e intensos, valoran la autenticidad. "
            "Tienden a ser introspectivos y a explorar su mundo interior con profundidad."
        ),
        "orientacion": (
            "Vocación base: Arte, Escritura, Diseño, Música, Terapias expresivas.\n\n"
            "Clave evolutiva: Estructura y disciplina profesional."
        ),
    },
    5: {
        "titulo": "Tipo 5 — El Investigador",
        "descripcion": (
            "Curiosos, observadores y analíticos. "
            "Buscan conocimiento, comprensión y autonomía. "
            "Prefieren observar antes que participar y disfrutan de profundizar en temas complejos."
        ),
        "orientacion": (
            "Vocación base: Investigación, Ciencia, Tecnología, Programación, "
            "Análisis de datos, Docencia universitaria.\n\n"
            "Clave evolutiva: Profesiones donde compartan su conocimiento."
        ),
    },
    6: {
        "titulo": "Tipo 6 — El Leal",
        "descripcion": (
            "Personas leales, responsables, cautelosas y con gran sentido de comunidad. "
            "Valoran la seguridad, la confianza y la previsibilidad. "
            "Pueden preocuparse por posibles riesgos, pero son muy comprometidos."
        ),
        "orientacion": (
            "Vocación base: Derecho, Seguridad, Gestión, Administración pública, Logística.\n\n"
            "Clave evolutiva: Roles con autonomía progresiva."
        ),
    },
    7: {
        "titulo": "Tipo 7 — El Entusiasta",
        "descripcion": (
            "Activos, optimistas, espontáneos y con deseos de experiencias nuevas. "
            "Ayudan a otros ver el lado positivo de la vida. "
            "A veces evitan el dolor y buscan diversión constante."
        ),
        "orientacion": (
            "Vocación base: Turismo, Publicidad, Comunicación, Eventos, Emprendimientos creativos.\n\n"
            "Clave evolutiva: Proyectos a largo plazo."
        ),
    },
    8: {
        "titulo": "Tipo 8 — El Desafiador",
        "descripcion": (
            "Directos, fuertes, protectores y decididos. "
            "Buscan controlar su entorno y no temen enfrentar conflictos. "
            "Son líderes naturales, enfocados en la justicia y la acción."
        ),
        "orientacion": (
            "Vocación base: Dirección empresarial, Abogacía, Emprendimiento, Política, Deportes.\n\n"
            "Clave evolutiva: Aprender liderazgo consciente."
        ),
    },
    9: {
        "titulo": "Tipo 9 — El Pacificador",
        "descripcion": (
            "Calmados, tranquilos, atentos y conciliadores. "
            "Valoran la paz y evitan confrontaciones. "
            "Pueden perder su propia agenda personal para mantener la armonía."
        ),
        "orientacion": (
            "Vocación base: Mediación, Terapias, Recursos Humanos, Educación, Actividades holísticas.\n\n"
            "Clave evolutiva: Trabajos donde tengan voz y decisión."
        ),
    },
}

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
Base = declarative_base()
DBSession = sessionmaker(bind=engine) if engine else None


class Report(Base):
    __tablename__ = "reports_esencial"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_name = Column(String(200))
    owner_email = Column(String(200))
    owner_data = Column(JSON)
    test_date_iso = Column(String(50))
    porcentaje_scores = Column(JSON)
    top_types = Column(JSON)
    report_json = Column(JSON)
    paid = Column(Boolean, default=False)


if engine is not None:
    Base.metadata.create_all(engine)


def load_questions():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [q for q in data["questions"] if q.get("type") in range(1, 10)]


def generar_radar_image(resultados: dict):
    labels = [str(i) for i in range(1, 10)]
    values = [resultados.get(str(i), 0) for i in range(1, 10)]
    values_plot = values + values[:1]
    angles = np.linspace(0, 2 * np.pi, 9, endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, values_plot)
    ax.fill(angles, values_plot, alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    mx = max(values) if values else 0
    ax.set_ylim(0, mx + 5)
    ax.set_title("Radar Eneagrama", pad=20)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def add_header_footer(canvas, doc):
    canvas.saveState()
    logo_path = os.path.join(current_app.root_path, "static", "img", "logo_az.png")
    canvas.drawImage(logo_path, 2*cm, A4[1]-2.2*cm,
                     width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
    canvas.setFont("Helvetica", 8)
    text_obj = canvas.beginText(A4[0]-7*cm, A4[1]-1.8*cm)
    for line in ["AZ Consultora", "@az_coaching.terapeutico", "+54 2975203761"]:
        text_obj.textLine(line)
    canvas.drawText(text_obj)
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0]-2*cm, 1.5*cm, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def build_pdf(payload: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=3*cm, bottomMargin=2*cm,
                            title="Eneagrama Esencial")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Body2", parent=styles["BodyText"],
                              alignment=TA_JUSTIFY, leading=15, spaceAfter=8))
    styles.add(ParagraphStyle("H1b", parent=styles["Heading1"],
                              alignment=TA_JUSTIFY, spaceAfter=12))
    styles.add(ParagraphStyle("H2b", parent=styles["Heading2"],
                              alignment=TA_JUSTIFY, spaceAfter=8))

    story = []
    logo_path = os.path.join(current_app.root_path, "static", "img", "logo_az.png")

    # Portada
    logo = Image(logo_path)
    logo.drawHeight = 4*cm
    logo.drawWidth = 4*cm
    story += [Spacer(1, 5*cm), logo, Spacer(1, 1*cm),
              Paragraph("Eneagrama Esencial", styles["H1b"]),
              Paragraph("Diagnóstico inicial profesional", styles["H2b"]),
              Spacer(1, 0.5*cm),
              Paragraph("Informe confidencial", styles["H2b"]),
              PageBreak()]

    # Encabezado informe
    propietario = payload.get("propietario", {})
    story += [
        Paragraph("Eneagrama Esencial — Diagnóstico inicial profesional", styles["H1b"]),
        Paragraph(f"Analista: {payload.get('analista', '')}", styles["Body2"]),
        Spacer(1, 8),
        Paragraph("Propietario del eneagrama", styles["H2b"]),
        Paragraph(f"Nombre: {propietario.get('nombre', '')}", styles["Body2"]),
        Paragraph(f"Email: {propietario.get('email', '')}", styles["Body2"]),
        Paragraph(f"Fecha del test: {payload.get('fecha_test', '')}", styles["Body2"]),
        Spacer(1, 10),
        Paragraph("Introducción", styles["H2b"]),
        Paragraph(
            "A continuación verás los resultados de tu test de autoidentificación personal. "
            "Esta información te ayudará a conocer tu eneatipo dominante, tu orientación vocacional "
            "y las claves evolutivas para tu desarrollo personal y profesional. "
            "Recordá que el eneagrama es dinámico: repetirlo anualmente te permitirá observar tu evolución.",
            styles["Body2"]),
        Spacer(1, 10),
    ]

    total_marked = payload.get("total_marked", 0)
    porcentaje_total = round((total_marked / 108) * 100, 1)
    story.append(Paragraph(
        f"<b>Afirmaciones marcadas:</b> {total_marked} de 108 — {porcentaje_total}%",
        styles["Body2"]))
    story.append(Spacer(1, 12))

    # Eneatipo principal
    top_types = payload.get("top_types", [])
    if top_types:
        principal = top_types[0]
        txt = ENEATIPO_TEXTOS.get(principal, {})
        story += [
            Paragraph("Tu Eneatipo Principal", styles["H2b"]),
            Spacer(1, 6),
            Paragraph(txt.get("titulo", ""), styles["H2b"]),
            Paragraph(txt.get("descripcion", ""), styles["Body2"]),
        ]

    # Ala
    for t in payload.get("ala_textos", []):
        story += [Spacer(1, 8), Paragraph("Tu Ala", styles["H2b"]), Paragraph(t, styles["Body2"])]

    # Orientación vocacional
    if top_types:
        txt = ENEATIPO_TEXTOS.get(top_types[0], {})
        story.append(Spacer(1, 8))
        story.append(Paragraph("Orientación Vocacional", styles["H2b"]))
        for line in txt.get("orientacion", "").split("\n"):
            if line.strip():
                story.append(Paragraph(line, styles["Body2"]))

    # Gráfico
    story.append(PageBreak())
    story.append(Paragraph("Gráfico Radial — Resultados por Eneatipo (%)", styles["H2b"]))
    story.append(Spacer(1, 8))
    resultados = payload.get("resultados", {})
    radar_img = generar_radar_image(resultados)
    img = Image(radar_img)
    img.drawHeight = 12*cm
    img.drawWidth = 12*cm
    story.append(img)
    story.append(Spacer(1, 10))
    for t in range(1, 10):
        story.append(Paragraph(f"• Tipo {t}: {resultados.get(str(t), 0)}%", styles["Body2"]))

    story += [
        Spacer(1, 20),
        Paragraph(
            "Para una consulta personalizada o exploración de otras herramientas de autoconocimiento "
            "contactar a AZ Consultora @az_coaching.terapeutico o WhatsApp +54-2975203761.",
            styles["Body2"]),
    ]

    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=add_header_footer)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/crear_preferencia")
def crear_preferencia():
    session["usuario"] = {
        "nombre": request.form.get("nombre"),
        "email": request.form.get("email"),
        "fecha_test": datetime.utcnow().isoformat(),
    }
    session["answers"] = {}
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    preference_data = {
        "items": [{
            "title": "Eneagrama Esencial — Diagnóstico inicial profesional",
            "quantity": 1,
            "unit_price": 1000,
            "currency_id": "ARS",
        }],
        "payer": {"email": session["usuario"]["email"]},
        "back_urls": {
            "success": f"{APP_URL}/pago_exitoso",
            "failure": f"{APP_URL}/pago_fallido",
            "pending": f"{APP_URL}/pago_pendiente",
        },
        "auto_return": "approved",
        "external_reference": session["usuario"]["email"],
    }
    result = sdk.preference().create(preference_data)
    return redirect(result["response"]["init_point"])


@app.get("/pago_exitoso")
def pago_exitoso():
    if request.args.get("status") == "approved":
        session["pago_ok"] = True
        return redirect(url_for("quiz_get", page=1))
    return redirect(url_for("pago_fallido"))


@app.get("/pago_fallido")
def pago_fallido():
    return render_template("pago_fallido.html")


@app.get("/pago_pendiente")
def pago_pendiente():
    return render_template("pago_pendiente.html")


@app.get("/quiz")
def quiz_get():
    if not session.get("pago_ok"):
        return redirect(url_for("index"))
    questions_all = load_questions()
    page = int(request.args.get("page") or 1)
    per_page = 30
    total_pages = (len(questions_all) + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    chunk = questions_all[(page-1)*per_page:page*per_page]
    return render_template("quiz.html", questions=chunk, page=page,
                           total_pages=total_pages, answers=session.get("answers", {}))


@app.post("/quiz")
def quiz_post():
    if not session.get("pago_ok"):
        return redirect(url_for("index"))
    questions_all = load_questions()
    page = int(request.args.get("page") or 1)
    per_page = 30
    total_pages = (len(questions_all) + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    chunk = questions_all[(page-1)*per_page:page*per_page]
    answers = session.get("answers", {})
    for q in chunk:
        answers[str(q["id"])] = (request.form.get(f"q_{q['id']}") == "1")
    session["answers"] = answers
    if page < total_pages:
        return redirect(url_for("quiz_get", page=page + 1))
    return redirect(url_for("result"))


@app.get("/result")
def result():
    if not session.get("pago_ok"):
        return redirect(url_for("index"))
    questions = load_questions()
    answers = session.get("answers", {})
    total_marked = sum(1 for v in answers.values() if v)
    scores = {t: 0 for t in range(1, 10)}
    for q in questions:
        if answers.get(str(q["id"])):
            scores[q["type"]] += 1

    porcentaje_scores = {
        t: round((s / total_marked * 100) if total_marked > 0 else 0, 1)
        for t, s in scores.items()
    }
    labels = [str(i) for i in range(1, 10)]
    values = [porcentaje_scores[i] for i in range(1, 10)]

    max_score = max(scores.values()) if scores else 0
    top_types = [t for t, s in scores.items() if s == max_score and max_score > 0]
    if len(top_types) > 1:
        mejor_tipo, mejor_val = None, -1
        for tipo in top_types:
            ala_izq, ala_der = ALAS[tipo]
            val = max(porcentaje_scores.get(ala_izq, 0), porcentaje_scores.get(ala_der, 0))
            if val > mejor_val:
                mejor_val = val
                mejor_tipo = tipo
        top_types = [mejor_tipo]

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
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

    usuario = session.get("usuario", {})
    report_payload = {
        "analista": "AZ Consultora @az_coaching.terapeutico / +542975203761",
        "propietario": usuario,
        "fecha_test": usuario.get("fecha_test"),
        "total_marked": total_marked,
        "top_types": top_types,
        "ala_textos": ala_textos,
        "resultados": {str(k): v for k, v in porcentaje_scores.items()},
    }

    if DBSession:
        db = DBSession()
        try:
            r = Report(owner_name=usuario.get("nombre"), owner_email=usuario.get("email"),
                       owner_data=usuario, test_date_iso=usuario.get("fecha_test"),
                       porcentaje_scores={str(k): v for k, v in porcentaje_scores.items()},
                       top_types=top_types, report_json=report_payload)
            db.add(r)
            db.commit()
            session["report_id"] = r.id
        finally:
            db.close()

    return render_template("result.html",
                           sorted_scores=sorted_scores,
                           sorted_porcentajes=sorted_porcentajes,
                           top_types=top_types, max_score=max_score,
                           total_marked=total_marked,
                           eneatipo_textos=ENEATIPO_TEXTOS,
                           ala_textos=ala_textos,
                           labels=labels, values=values,
                           report_id=session.get("report_id"))


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
    pdf_bytes = build_pdf(payload)
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                     as_attachment=True, download_name="Eneagrama_Esencial.pdf")


@app.get("/reset")
def reset():
    session.pop("answers", None)
    session.pop("pago_ok", None)
    return redirect(url_for("index"))

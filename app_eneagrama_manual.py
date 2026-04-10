from flask import Flask, render_template, request, send_file
import io

from app_integral import build_pdf_from_payload as build_integral_pdf
from app_integral import build_payload_from_scores

from app_esencial import build_pdf as build_esencial_pdf
from app_esencial import ENEATIPO_TEXTOS as ENEATIPO_ESENCIAL

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        modelo = request.form.get("modelo")
        nombre = request.form.get("nombre")
        email = request.form.get("email")

        porcentaje_scores = {
            i: float(request.form.get(f"t{i}", 0))
            for i in range(1, 10)
        }

        # -------------------------
        # MODELO ESENCIAL
        # -------------------------
        if modelo == "esencial":

            payload = {
                "analista": "AZ Consultora",
                "propietario": {
                    "nombre": nombre,
                    "email": email
                },
                "fecha_test": "manual",
                "total_marked": 100,
                "top_types": [max(porcentaje_scores, key=porcentaje_scores.get)],
                "ala_textos": [],
                "resultados": {str(k): v for k, v in porcentaje_scores.items()},
            }

            pdf_bytes = build_esencial_pdf(payload)

        # -------------------------
        # MODELO INTEGRAL
        # -------------------------
        else:

            payload = build_payload_from_scores(
                porcentaje_scores=porcentaje_scores,
                nombre=nombre,
                email=email,
                titulo="Informe profundo de autoconocimiento",
                mensaje_final="Para una consulta personalizada o exploración de otras herramientas de autoconocimiento contactar a AZ Consultora @az_coaching.terapeutico o WhatsApp +54-2975203761",
            )

            pdf_bytes = build_integral_pdf(payload)

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"informe_{modelo}.pdf"
        )

    return render_template("manual.html")

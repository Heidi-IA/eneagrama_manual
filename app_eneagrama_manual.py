from flask import Flask, render_template, request, send_file
import io

# 🔥 IMPORTAMOS LO QUE YA TENÉS
# (esto reutiliza tu lógica existente)
from app_integral import build_pdf_from_payload as build_integral_pdf
from app_integral import build_bonus_estructura_pensamiento
from app_integral import ENEATIPO_TEXTOS as ENEATIPO_INTEGRAL

from app_esencial import build_pdf as build_esencial_pdf
from app_esencial import ENEATIPO_TEXTOS as ENEATIPO_ESENCIAL

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        modelo = request.form.get("modelo")

        nombre = request.form.get("nombre")
        email = request.form.get("email")

        # porcentajes manuales
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

            bonus_data = build_bonus_estructura_pensamiento(porcentaje_scores)

            payload = {
                "titulo": "Informe Eneagrama Manual",
                "analista": "AZ Consultora",
                "propietario": {
                    "nombre": nombre,
                    "email": email
                },
                "fecha_test": "manual",

                "desarrollo": {
                    "top_types": [max(porcentaje_scores, key=porcentaje_scores.get)],
                    "total_marked": 100,
                    "eneatipo_textos": ENEATIPO_INTEGRAL,
                    "bonus_estructura": bonus_data["estructura"],
                    "bonus_sintesis": bonus_data["sintesis"],
                },

                "graficos_anexos": {
                    "resultados": {str(k): v for k, v in porcentaje_scores.items()},
                    "top_types": [max(porcentaje_scores, key=porcentaje_scores.get)],
                },

                "mensaje_final": "Informe generado manualmente",
            }

            pdf_bytes = build_integral_pdf(payload)

        # 👉 devolver PDF directo
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"informe_{modelo}.pdf"
        )

    return render_template("manual.html")

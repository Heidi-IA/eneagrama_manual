from flask import Flask, render_template, request, send_file
import io

from app_integral import build_pdf_from_payload as build_integral_pdf
from app_integral import build_payload_from_scores

from app_esencial import build_pdf as build_esencial_pdf
from app_esencial import ENEATIPO_TEXTOS as ENEATIPO_ESENCIAL
from app_esencial import ALAS, DESCRIPCION_ALAS

app = Flask(__name__)


def calcular_ala_esencial(porcentaje_scores: dict, top_types: list) -> list:
    """Calcula el ala dominante para el modelo esencial."""
    if not top_types:
        return []
    principal = top_types[0]
    izq, der = ALAS[principal]
    pct_izq = porcentaje_scores.get(izq, 0)
    pct_der = porcentaje_scores.get(der, 0)
    if pct_izq > pct_der:
        clave = f"{principal}w{izq}"
    elif pct_der > pct_izq:
        clave = f"{principal}w{der}"
    else:
        # empate: devolver ambas
        ala_textos = []
        for c in [f"{principal}w{izq}", f"{principal}w{der}"]:
            t = DESCRIPCION_ALAS.get(c)
            if t:
                ala_textos.append(t)
        return ala_textos
    t = DESCRIPCION_ALAS.get(clave)
    return [t] if t else []


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        modelo = request.form.get("modelo")
        nombre = request.form.get("nombre")
        email = request.form.get("email")
        sexo = request.form.get("sexo", "")
        fecha_nacimiento = request.form.get("fecha_nacimiento", "")
        hora_desconocida = request.form.get("hora_desconocida")
        hora_nacimiento = "Desconocida" if hora_desconocida else request.form.get("hora_nacimiento", "")
        fecha_test = request.form.get("fecha_test", "manual")
        total_marked = int(request.form.get("total_marked", 100))

        porcentaje_scores = {
            i: float(request.form.get(f"t{i}", 0))
            for i in range(1, 10)
        }

        # -------------------------
        # MODELO ESENCIAL
        # -------------------------
        if modelo == "esencial":

            top_types = [max(porcentaje_scores, key=porcentaje_scores.get)]
            ala_textos = calcular_ala_esencial(porcentaje_scores, top_types)

            payload = {
                "analista": "AZ Consultora",
                "propietario": {
                    "nombre": nombre,
                    "email": email,
                    "sexo": sexo,
                    "fecha_nacimiento": fecha_nacimiento,
                    "hora_nacimiento": hora_nacimiento,
                },
                "fecha_test": fecha_test,
                "total_marked": total_marked,          # raíz del payload — así lo lee build_pdf
                "top_types": top_types,
                "ala_textos": ala_textos,              # ala calculada
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
                mensaje_final="Informe generado manualmente",
            )

            # Completar datos personales y total_marked
            payload["propietario"]["sexo"] = sexo
            payload["propietario"]["fecha_nacimiento"] = fecha_nacimiento
            payload["propietario"]["hora_nacimiento"] = hora_nacimiento
            payload["fecha_test"] = fecha_test
            payload["desarrollo"]["total_marked"] = total_marked

            pdf_bytes = build_integral_pdf(payload)

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"informe_{modelo}.pdf"
        )

    return render_template("manual.html")

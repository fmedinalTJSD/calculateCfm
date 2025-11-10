from flask import Flask, render_template, request, redirect, url_for, flash
from decimal import Decimal, InvalidOperation
import copy

app = Flask(__name__)
app.secret_key = "cambiar_esta_clave_secreta_en_produccion"

DEFAULT_CFM_PER_TON = 400
DEFAULT_SQFT_PER_TON = 500
MARGIN = 0.10  # 10%

DEFAULT_SUPPLY_TABLE = {
    5:  {"Flex": 45,  "Sheet": 65},
    6:  {"Flex": 65,  "Sheet": 110},
    7:  {"Flex": 110, "Sheet": 160},
    8:  {"Flex": 150, "Sheet": 230},
    9:  {"Flex": 200, "Sheet": 325},
    10: {"Flex": 270, "Sheet": 425},
    12: {"Flex": 440, "Sheet": 700},
    14: {"Flex": 650, "Sheet": 1000},
    16: {"Flex": 900, "Sheet": 1500},
    18: {"Flex": 1300,"Sheet": 2000},
    20: {"Flex": 1700,"Sheet": 2600},
}

DEFAULT_RETURN_TABLE = {
    5:  {"Flex": None, "Sheet": 45},
    6:  {"Flex": 45,   "Sheet": 75},
    7:  {"Flex": 70,   "Sheet": 110},
    8:  {"Flex": 100,  "Sheet": 160},
    9:  {"Flex": 140,  "Sheet": 220},
    10: {"Flex": 200,  "Sheet": 300},
    12: {"Flex": 300,  "Sheet": 475},
    14: {"Flex": 450,  "Sheet": 700},
    16: {"Flex": 620,  "Sheet": 1000},
    18: {"Flex": 900,  "Sheet": 1400},
    20: {"Flex": 1200, "Sheet": 1800},
}

DIAMETERS = [5,6,7,8,9,10,12,14,16,18,20]

TRANSLATIONS = {
    "en": {
        "title": "CFM Duct Calculator",
        "subtitle": "Enter Supply and Return ducts, quantities and equipment tons. CFM per ton default = 400.",
        "supply": "Supply",
        "return": "Return",
        "diameter": "Diameter",
        "type": "Type",
        "qty": "Quantity",
        "add_supply": "Add Supply",
        "add_return": "Add Return",
        "remove": "Remove",
        "equipment": "Equipment",
        "tons": "Tons",
        "calculate": "Calculate",
        "note_return": "Note: some diameter/type combos may not exist for Return (e.g., 5\" Flex).",
        "result_title": "Calculation Result",
        "required_cfm": "Required CFM",
        "acceptable_range": "Acceptable range (±10%)",
        "total_cfm": "System total CFM",
        "verdict": "Verdict",
        "new_calc": "New calculation",
        "no_ducts": "No valid ducts with quantity > 0 were found.",
        "enter_tons": "Enter equipment tons.",
        "tons_positive": "Tons must be a number greater than 0.",
        "tons_invalid": "Invalid tons format.",
        "error_calc": "An error occurred during calculation. Check inputs and try again.",
        "cfm_per_unit": "CFM/unit",
        "subtotal": "Subtotal",
        "note": "Note",
        "settings": "Settings",
        "cfm_per_ton": "CFM per Ton",
        "save_note": "Values apply to this calculation only",
        "house_size": "House size",
        "use_house_size": "Use house size to estimate tons",
        "sqft_per_ton": "Sqft per Ton (divisor)",
        "estimated_tons": "Estimated Tons",
        "settings_button": "Settings",
        "current_tons_label": "Current Tons / Tonelage Actual",
        "supply_total_label": "Supply total CFM",
        "return_total_label": "Return total CFM"
    },
    "es": {
        "title": "Calculadora CFM Ductos",
        "subtitle": "Ingrese los ductos Supply y Return, cantidades y las toneladas del equipo. CFM por tonelada por defecto = 400.",
        "supply": "Supply",
        "return": "Return",
        "diameter": "Diámetro",
        "type": "Tipo",
        "qty": "Cantidad",
        "add_supply": "Agregar Supply",
        "add_return": "Agregar Return",
        "remove": "Remover",
        "equipment": "Equipo",
        "tons": "Toneladas",
        "calculate": "Calcular",
        "note_return": "Nota: algunos diámetros/tipos pueden no existir para Return (por ejemplo 5\" Flex).",
        "result_title": "Resultado del cálculo",
        "required_cfm": "CFM requerido",
        "acceptable_range": "Rango aceptable (±10%)",
        "total_cfm": "CFM total sistema",
        "verdict": "Veredicto",
        "new_calc": "Nuevo cálculo",
        "no_ducts": "No se encontraron ductos válidos con cantidad mayor a 0.",
        "enter_tons": "Ingrese las toneladas del equipo.",
        "tons_positive": "Las toneladas deben ser un número mayor que 0.",
        "tons_invalid": "Formato de toneladas inválido.",
        "error_calc": "Ocurrió un error durante el cálculo. Revise los datos e intente de nuevo.",
        "cfm_per_unit": "CFM/unidad",
        "subtotal": "Subtotal",
        "note": "Nota",
        "settings": "Ajustes",
        "cfm_per_ton": "CFM por Tonelada",
        "save_note": "Los valores se aplican solo a este cálculo",
        "house_size": "Tamaño casa (sqft)",
        "use_house_size": "Usar tamaño de casa para estimar toneladas",
        "sqft_per_ton": "Sqft por Tonelada (divisor)",
        "estimated_tons": "Toneladas estimadas",
        "settings_button": "Ajustes",
        "current_tons_label": "Tonelaje Actual / Current Tons",
        "supply_total_label": "CFM total Supply",
        "return_total_label": "CFM total Return"
    }
}

def get_translations(lang_code):
    return TRANSLATIONS.get(lang_code, TRANSLATIONS["en"])

def safe_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def safe_decimal(val, default=None):
    try:
        return Decimal(val)
    except (TypeError, InvalidOperation):
        return default

def build_tables_from_form(form):
    supply_table = copy.deepcopy(DEFAULT_SUPPLY_TABLE)
    return_table = copy.deepcopy(DEFAULT_RETURN_TABLE)

    cfm_per_ton = safe_decimal(form.get("cfm_per_ton", ""), default=Decimal(DEFAULT_CFM_PER_TON))
    if cfm_per_ton is None:
        cfm_per_ton = Decimal(DEFAULT_CFM_PER_TON)

    for d in DIAMETERS:
        for t in ("Flex", "Sheet"):
            key_s = f"supply_{d}_{t}"
            val_s = form.get(key_s, "").strip()
            if val_s != "":
                v = safe_int(val_s, default=None)
                if v is not None:
                    supply_table.setdefault(d, {})[t] = v

            key_r = f"return_{d}_{t}"
            val_r = form.get(key_r, "").strip()
            if val_r != "":
                if val_r.lower() == "xx":
                    return_table.setdefault(d, {})[t] = None
                else:
                    v = safe_int(val_r, default=None)
                    if v is not None:
                        return_table.setdefault(d, {})[t] = v

    return supply_table, return_table, int(cfm_per_ton)

def lookup_cfm(diagonal:int, duct_type:str, table:dict):
    if diagonal not in table:
        return None
    value = table[diagonal].get(duct_type)
    if value is None:
        return None
    return value

@app.route("/")
def index():
    lang = request.args.get("lang", "en")
    if lang not in TRANSLATIONS:
        lang = "en"
    trans = get_translations(lang)
    return render_template("index.html",
                           diameters=DIAMETERS,
                           lang=lang,
                           trans=trans,
                           default_supply=DEFAULT_SUPPLY_TABLE,
                           default_return=DEFAULT_RETURN_TABLE,
                           default_cfm_per_ton=DEFAULT_CFM_PER_TON,
                           default_sqft_per_ton=DEFAULT_SQFT_PER_TON)

@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        lang = request.form.get("lang", "en")
        if lang not in TRANSLATIONS:
            lang = "en"
        trans = get_translations(lang)

        supply_table, return_table, cfm_per_ton = build_tables_from_form(request.form)

        use_house = request.form.get("use_house_size") == "on"
        house_size_raw = request.form.get("house_size", "").strip()
        sqft_per_ton_raw = request.form.get("sqft_per_ton", "").strip()
        sqft_per_ton = safe_decimal(sqft_per_ton_raw, default=Decimal(DEFAULT_SQFT_PER_TON))
        if sqft_per_ton is None or sqft_per_ton <= 0:
            sqft_per_ton = Decimal(DEFAULT_SQFT_PER_TON)

        tons = None
        tons_source = None
        tonsActual = request.form.get("tons", "").strip() 
        if use_house and house_size_raw != "":
            hs = safe_decimal(house_size_raw, default=None)
            if hs is not None and hs > 0:
                estimated_tons = (hs / sqft_per_ton).quantize(Decimal("0.01"))
                tons = estimated_tons
                tons_source = "house"
            else:
                tons = None

        if tons is None:
            tons_raw = request.form.get("tons", "").strip()
            if tons_raw == "":
                flash(trans["enter_tons"], "danger")
                return redirect(url_for("index", lang=lang))
            try:
                tons = Decimal(tons_raw)
                if tons <= 0:
                    flash(trans["tons_positive"], "danger")
                    return redirect(url_for("index", lang=lang))
                tons_source = "manual"
            except InvalidOperation:
                flash(trans["tons_invalid"], "danger")
                return redirect(url_for("index", lang=lang))

        total_cfm_supply = Decimal(0)
        total_cfm_return = Decimal(0)

        def process_group(prefix, table_name, table):
            nonlocal total_cfm_supply, total_cfm_return
            diameters = request.form.getlist(f"{prefix}_diameter[]")
            types = request.form.getlist(f"{prefix}_type[]")
            qtys = request.form.getlist(f"{prefix}_qty[]")
            entries = []
            for d_raw, t_raw, q_raw in zip(diameters, types, qtys):
                if not d_raw:
                    continue
                try:
                    d = int(d_raw)
                except ValueError:
                    continue
                t = t_raw if t_raw in ("Flex","Sheet") else "Flex"
                q = safe_int(q_raw, default=0)
                if q <= 0:
                    continue
                cfm_unit = lookup_cfm(d, t, table)
                if cfm_unit is None:
                    entries.append({
                        "side": table_name,
                        "diameter": d,
                        "type": t,
                        "qty": q,
                        "cfm_per_unit": None,
                        "subtotal": None,
                        "error": f"No {t} for {d}\" in {table_name} table"
                    })
                    continue
                subtotal = Decimal(cfm_unit) * Decimal(q)
                if table_name == "supply":
                    total_cfm_supply += subtotal
                else:
                    total_cfm_return += subtotal
                entries.append({
                    "side": table_name,
                    "diameter": d,
                    "type": t,
                    "qty": q,
                    "cfm_per_unit": int(cfm_unit),
                    "subtotal": int(subtotal),
                    "error": None
                })
            return entries

        supply_entries = process_group("supply", "supply", supply_table)
        return_entries = process_group("return", "return", return_table)

        total_cfm = total_cfm_supply + total_cfm_return
        required_cfm = tons * Decimal(cfm_per_ton)

        lower = required_cfm * (Decimal(1) - Decimal(MARGIN))
        upper = required_cfm * (Decimal(1) + Decimal(MARGIN))

        if total_cfm == 0:
            flash(trans["no_ducts"], "danger")
            return redirect(url_for("index", lang=lang))

        def verdict_for(value):
            if value >= lower and value <= upper:
                return ("Bien" if lang == "es" else "Good", "green")
            elif value < lower:
                return ("Subdimensionado" if lang == "es" else "Undersized", "red")
            else:
                return ("Sobredimensionado" if lang == "es" else "Oversized", "yellow")

        supply_verdict, supply_color = verdict_for(total_cfm_supply)
        return_verdict, return_color = verdict_for(total_cfm_return)

        breakdown = {"supply": supply_entries, "return": return_entries}

        result = {
            "total_cfm": int(total_cfm),
            "total_cfm_supply": int(total_cfm_supply),
            "total_cfm_return": int(total_cfm_return),
            "required_cfm": int(required_cfm),
            "lower_bound": int(lower.quantize(Decimal("1"))),
            "upper_bound": int(upper.quantize(Decimal("1"))),
            "verdict_supply": supply_verdict,
            "color_supply": supply_color,
            "verdict_return": return_verdict,
            "color_return": return_color,
            "entries": supply_entries + return_entries,
            "breakdown": breakdown,
            "tons": str(tons),
            "tonsActual": str(tonsActual),
            "tons_source": tons_source,
            "lang": lang,
            "trans": trans,
            "cfm_per_ton_used": cfm_per_ton,
            "supply_table_used": supply_table,
            "return_table_used": return_table,
            "house_size": house_size_raw,
            "sqft_per_ton_used": int(sqft_per_ton)
        }

        return render_template("result.html", result=result)
    except Exception:
        lang = request.form.get("lang", "en")
        if lang not in TRANSLATIONS:
            lang = "en"
        trans = get_translations(lang)
        flash(trans["error_calc"], "danger")
        return redirect(url_for("index", lang=lang))

if __name__ == "__main__":
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



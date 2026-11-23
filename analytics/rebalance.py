# Simulación del rebalanceo mínimo para que el portafolio quede alineado con el perfil

# Nivel de riesgo que corresponde a cada perfil
PROFILE_LEVELS = {"CONSERVADOR": "bajo", "MODERADO": "medio", "AGRESIVO": "alto"}

# Puntaje de cada nivel (el mismo de sql/asset-risk.sql)
LEVEL_SCORES = {"bajo": 1, "medio": 2, "alto": 3}


# Nivel de un puntaje promedio (igual que la función nivel_por_puntaje de sql/client-risk.sql)
def level_for_score(score):
    score = round(score, 2)
    if score < 1.5:
        return "bajo"
    if score < 2.5:
        return "medio"
    return "alto"


# Puntaje al que hay que llegar: el borde más cercano del rango del perfil.
# Los rangos son los de nivel_por_puntaje: bajo < 1.5, medio < 2.5, alto >= 2.5
def target_score(current_score, profile_score):
    if current_score > profile_score:
        # Hay que bajar el riesgo: 1.49 para conservador y 2.49 para moderado
        return profile_score + 0.49
    # Hay que subir el riesgo: 1.5 para moderado y 2.5 para agresivo
    return profile_score - 0.5


# Calcula cuánto trasladar de cada activo hacia activos del nivel del perfil.
# positions: lista de diccionarios con "activo", "valor", "nivel_riesgo" y "puntaje_riesgo".
# Devuelve None si el cliente no tiene un perfil único o no tiene activos clasificados.
def suggest_rebalance(positions, profile):
    if profile not in PROFILE_LEVELS:
        return None

    # Solo se usan los activos que tienen nivel de riesgo
    classified = [p for p in positions if p["puntaje_riesgo"] is not None]
    total = sum(float(p["valor"]) for p in classified)
    if total == 0:
        return None

    profile_level = PROFILE_LEVELS[profile]
    profile_score = LEVEL_SCORES[profile_level]
    current_score = sum(float(p["valor"]) * p["puntaje_riesgo"] for p in classified) / total

    result = {
        "profile_level": profile_level,
        "current_score": round(current_score, 2),
        "moves": [],
        "total_to_move": 0,
        "pct_to_move": 0,
    }

    # Si el puntaje ya está en el rango del perfil no hay nada que mover
    if level_for_score(current_score) == profile_level:
        result["target_score"] = round(current_score, 2)
        return result

    target = target_score(current_score, profile_score)
    result["target_score"] = target

    # Puntos de riesgo que hay que quitar (o sumar) al portafolio
    points_needed = abs(current_score - target) * total

    # Activos que alejan al portafolio del perfil, primero los del nivel más lejano y los de mayor saldo
    if current_score > profile_score:
        sources = [p for p in classified if p["puntaje_riesgo"] > profile_score]
    else:
        sources = [p for p in classified if p["puntaje_riesgo"] < profile_score]
    sources.sort(key=lambda p: (-abs(p["puntaje_riesgo"] - profile_score), -float(p["valor"])))

    for position in sources:
        if points_needed <= 0:
            break
        # Cada peso trasladado mueve el puntaje según la distancia entre los dos niveles
        distance = abs(position["puntaje_riesgo"] - profile_score)
        amount = min(float(position["valor"]), points_needed / distance)
        points_needed -= amount * distance
        result["moves"].append({
            "activo": position["activo"],
            "nivel_riesgo": position["nivel_riesgo"],
            "valor": float(position["valor"]),
            "monto": round(amount, 2),
            "pct_del_activo": round(amount / float(position["valor"]) * 100, 2),
        })

    result["total_to_move"] = round(sum(move["monto"] for move in result["moves"]), 2)
    result["pct_to_move"] = round(result["total_to_move"] / total * 100, 2)
    return result

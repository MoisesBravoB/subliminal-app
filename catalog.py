"""Catálogo de mensajes subliminales organizados por categorías."""

CUSTOM_CATEGORY_KEY = "Mis mensajes"

CATALOG: dict[str, list[str]] = {
    "Enfoque y Productividad": [
        "Mi mente está clara y enfocada",
        "Avanzo con precisión en lo importante",
        "Elimino distracciones con facilidad",
        "Termino cada tarea que comienzo",
        "Mi concentración es profunda y constante",
        "Aprovecho cada minuto con inteligencia",
        "Trabajo con calma y máxima eficiencia",
        "Priorizo lo esencial con claridad",
        "Fluyo con facilidad en mis proyectos",
        "Hoy soy altamente productivo",
    ],
    "Confianza y Autoestima": [
        "Confío plenamente en mis capacidades",
        "Me valoro y respeto profundamente",
        "Merezco éxito, paz y bienestar",
        "Hablo y actúo con seguridad",
        "Soy suficiente tal como soy",
        "Supero cualquier desafío con firmeza",
        "Creo en mí y en mi potencial",
        "Irradio seguridad y autenticidad",
        "Cada paso fortalece mi confianza",
        "Me siento orgulloso de mi progreso",
    ],
    "Calma y Anti-estrés": [
        "Respiro profundo y suelto la tensión",
        "Estoy en paz en este momento",
        "Mi mente está tranquila y serena",
        "Elijo la calma ante cualquier situación",
        "Mi cuerpo se relaja y se renueva",
        "Todo se resuelve a su debido tiempo",
        "Mantengo el equilibrio y la serenidad",
        "Dejo ir lo que no puedo controlar",
        "La paz interior guía mis decisiones",
        "Siento claridad y tranquilidad mental",
    ],
    "Disciplina y Hábitos": [
        "Soy disciplinado y constante cada día",
        "Cumplo mis promesas conmigo mismo",
        "Actúo incluso cuando no tengo ganas",
        "Mis hábitos diarios construyen mi futuro",
        "Elijo la constancia sobre la excusa",
        "Pequeñas acciones diarias crean grandes cambios",
        "Tengo control total sobre mis decisiones",
        "Me enfoco en el progreso constante",
        "Soy responsable de mis resultados",
        "Cada día soy más fuerte y constante",
    ],
    "Estudio y Memoria": [
        "Aprendo rápido y con claridad",
        "Mi memoria es ágil y precisa",
        "Comprendo conceptos complejos con facilidad",
        "Disfruto aprender cosas nuevas",
        "Retengo la información importante sin esfuerzo",
        "Mi mente conecta ideas con rapidez",
        "Estudio con atención plena y disfrute",
        "Cada sesión de estudio me hace más capaz",
        "Recuerdo lo que necesito en el momento justo",
        "Mi curiosidad impulsa mi inteligencia",
    ],
    "Abundancia y Éxito": [
        "Atraigo oportunidades positivas cada día",
        "Creo valor y recibo prosperidad",
        "Estoy abierto a nuevas fuentes de éxito",
        "Tomo decisiones financieras inteligentes",
        "El éxito es el resultado natural de mi esfuerzo",
        "Reconozco y aprovecho buenas oportunidades",
        "Merezco prosperidad y crecimiento",
        "Pienso en grande y actúo con estrategia",
        "Mi talento abre puertas importantes",
        "Avanzo con seguridad hacia mis metas",
    ],
    "Salud y Energía": [
        "Mi cuerpo está lleno de energía vital",
        "Elijo hábitos que nutren mi salud",
        "Me siento fuerte, ágil y renovado",
        "Cuido mi cuerpo y descanso bien",
        "Cada día tengo más vitalidad y fuerza",
        "Respiro energía limpia y positiva",
        "Mi mente y cuerpo trabajan en armonía",
        "Elijo bienestar en cada decisión",
        "Siento ligereza, salud y equilibrio",
        "Mi energía se renueva constantemente",
    ],
    "Creatividad e Inspiración": [
        "Las ideas brillantes fluyen hacia mí",
        "Veo soluciones originales donde otros ven límites",
        "Mi creatividad crece cada día",
        "Me permito imaginar y crear libremente",
        "Conecto ideas de formas innovadoras",
        "La inspiración llega en el momento perfecto",
        "Confío en mi visión creativa",
        "Transformo ideas en realidades concretas",
        "Mi mente es flexible, curiosa e ingeniosa",
        "Disfruto experimentar y crear",
    ],
}


def get_category_names() -> list[str]:
    return list(CATALOG.keys())


def get_category_messages(category: str) -> list[str]:
    return list(CATALOG.get(category, []))

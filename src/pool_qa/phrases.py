REFUSAL = {
    "en": "I can only answer questions about pool equipment covered by the available documents.",
    "fr": "Je ne peux répondre qu'aux questions sur l'équipement de piscine couvertes par les documents disponibles.",
    "es": "Solo puedo responder preguntas sobre equipos de piscina incluidas en los documentos disponibles.",
    "it": "Posso rispondere solo a domande sulle attrezzature per piscine trattate nei documenti disponibili.",
    "de": "Ich kann nur Fragen zu Poolausrüstung beantworten, die in den verfügbaren Dokumenten behandelt werden.",
    "pt": "Só posso responder a perguntas sobre equipamentos de piscina abrangidos pelos documentos disponíveis.",
    "el": "Μπορώ να απαντώ μόνο σε ερωτήσεις για εξοπλισμό πισίνας που καλύπτονται από τα διαθέσιμα έγγραφα.",
    "ru": "Я могу отвечать только на вопросы об оборудовании для бассейнов, описанном в доступных документах.",
    "ar": "يمكنني الإجابة فقط عن الأسئلة المتعلقة بمعدات حمامات السباحة الواردة في المستندات المتاحة.",
}

ABSTENTION = {
    "en": "I could not find enough verified information in the documents to answer this question.",
    "fr": "Je n'ai pas trouvé suffisamment d'informations vérifiées dans les documents pour répondre à cette question.",
    "es": "No he encontrado suficiente información verificada en los documentos para responder a esta pregunta.",
    "it": "Non ho trovato informazioni verificate sufficienti nei documenti per rispondere a questa domanda.",
    "de": "Ich habe in den Dokumenten nicht genügend überprüfte Informationen gefunden, um diese Frage zu beantworten.",
    "pt": "Não encontrei informações verificadas suficientes nos documentos para responder a esta pergunta.",
    "el": "Δεν βρήκα επαρκείς επαληθευμένες πληροφορίες στα έγγραφα για να απαντήσω σε αυτή την ερώτηση.",
    "ru": "Я не нашёл в документах достаточно проверенной информации, чтобы ответить на этот вопрос.",
    "ar": "لم أجد في المستندات معلومات موثقة كافية للإجابة عن هذا السؤال.",
}

LANGUAGES = tuple(REFUSAL)


def refusal(language: str) -> str:
    return REFUSAL.get(language, REFUSAL["en"])


def abstention(language: str) -> str:
    return ABSTENTION.get(language, ABSTENTION["en"])

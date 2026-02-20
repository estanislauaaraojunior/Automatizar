def aggregate_responses(responses, scores):
    # Exemplo simples: retorna o texto do agente com maior score
    best_agent = max(scores, key=scores.get)
    for resp in responses:
        if resp["agent"] == best_agent:
            return resp["text"]
    return ""

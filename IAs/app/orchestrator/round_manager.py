async def execute_rounds(prompt, agents, total_rounds):
    context = {"prompt_original": prompt, "history": []}
    for round_number in range(total_rounds):
        responses = []
        for agent in agents:
            response = await agent.generate(context)
            responses.append(response)
        context["history"].append({
            "round": round_number,
            "responses": responses
        })
    return context
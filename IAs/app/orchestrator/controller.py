from app.orchestrator.round_manager import execute_rounds
from app.models.response_models import ProcessResponse

async def process_prompt(request):
    from app.agents.agent_openrouter import OpenRouterAgent
    from app.consensus.scoring import calculate_scores
    from app.consensus.aggregator import aggregate_responses

    agents = [OpenRouterAgent(f"Agent_{i+1}") for i in range(request.agents)]
    context = await execute_rounds(request.prompt, agents, request.rounds)
    last_round = context["history"][-1]["responses"] if context["history"] else []
    scores = calculate_scores(last_round) if last_round else {}
    final_report = aggregate_responses(last_round, scores) if last_round else ""
    return ProcessResponse(rounds=context["history"], final_report=final_report, scores=scores)
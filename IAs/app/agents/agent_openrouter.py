import httpx
from app.agents.base_agent import BaseAgent
from app.config import OPENROUTER_API_KEY

class OpenRouterAgent(BaseAgent):
    async def generate(self, context):
        payload = {
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {"role": "system", "content": "Você é um analista crítico."},
                {"role": "user", "content": str(context)}
            ]
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json=payload
            )
        return {
            "agent": self.name,
            "text": response.json()["choices"][0]["message"]["content"]
        }
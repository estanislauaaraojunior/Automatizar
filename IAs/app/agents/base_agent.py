class BaseAgent:
    def __init__(self, name):
        self.name = name
    async def generate(self, context):
        raise NotImplementedError
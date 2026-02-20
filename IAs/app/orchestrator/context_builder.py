# Funções utilitárias para construir e atualizar o contexto das rodadas

def build_context(prompt, history):
    return {
        "prompt_original": prompt,
        "history": history
    }

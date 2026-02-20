from .similarity import cosine_similarity_matrix
import numpy as np

def calculate_scores(responses):
    sim_matrix = cosine_similarity_matrix(responses)
    scores = np.mean(sim_matrix, axis=1)
    return {resp["agent"]: float(score) for resp, score in zip(responses, scores)}

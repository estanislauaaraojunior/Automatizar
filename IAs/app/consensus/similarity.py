from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

def cosine_similarity_matrix(responses):
    embeddings = model.encode([r["text"] for r in responses])
    sim_matrix = util.pytorch_cos_sim(embeddings, embeddings)
    return sim_matrix.numpy()

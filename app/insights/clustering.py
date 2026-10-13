import logging
from collections import Counter
from typing import Dict, List

import numpy as np
from sklearn.cluster import DBSCAN

from app.core.embeddings import initialize_embeddings
from app.insights.distributions import calculate_distribution


def _group_answers_with_vectors(answers: List[str], threshold: float = 0.75) -> Dict[str, float]:
    if not answers: return {}
    embeddings_model = initialize_embeddings()
    unique_answers = list(set(answers))
    if len(unique_answers) < 2: return calculate_distribution(answers)

    try:
        vectors = embeddings_model.embed_documents(unique_answers)
        vectors = np.array(vectors)
        clustering = DBSCAN(eps=1-threshold, min_samples=1, metric='cosine').fit(vectors)
        labels = clustering.labels_
        
        cluster_map = {}
        for i, label in enumerate(labels):
            if label not in cluster_map: cluster_map[label] = []
            cluster_map[label].append(unique_answers[i])
            
        total_counts = Counter(answers)
        cluster_to_repr = {}
        for label, group_members in cluster_map.items():
            repr_word = max(group_members, key=lambda x: (total_counts[x], -len(x)))
            cluster_to_repr[label] = repr_word
            
        ans_to_label = {ans: labels[i] for i, ans in enumerate(unique_answers)}
        mapped_answers = [cluster_to_repr[ans_to_label[ans]] for ans in answers]
            
        return calculate_distribution(mapped_answers)
    except Exception as e:
        logging.error(f"벡터 클러스터링 실패: {e}", exc_info=True)
        return calculate_distribution(answers)

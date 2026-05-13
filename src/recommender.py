import os

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


class Recommender:
    """
    Cold-start hybrid recommender.

    Accepts ad-hoc user ratings (no pre-existing user ID required) and
    returns personalised recommendations by combining:
      - Content-based filtering  : genre cosine similarity
      - ALS cold-start           : item-factor averaging from the pre-trained model
    """

    def __init__(self, spark: SparkSession, movies_df: DataFrame, model_dir: str):
        self._spark     = spark
        self._model_dir = model_dir
        self._ratings_df: DataFrame | None = None

        # ── Movie metadata (pandas for fast in-process lookup) ─────────────
        movies_pd = movies_df.select("movieId", "title_clean", "genres").toPandas()
        self._movies = movies_pd.set_index("movieId")

        # ── Genre feature matrix ───────────────────────────────────────────
        movies_pd["genre_list"] = movies_pd["genres"].str.split("|")
        mlb = MultiLabelBinarizer()
        genre_matrix = mlb.fit_transform(movies_pd["genre_list"])
        self._genre_matrix = pd.DataFrame(
            genre_matrix,
            index=movies_pd["movieId"],
            columns=mlb.classes_,
        )
        self._genres: list[str] = sorted(
            [g for g in mlb.classes_ if g != "(no genres listed)"]
        )

        # ── ALS item factors ───────────────────────────────────────────────
        factors_path = os.path.join(model_dir, "item_factors.parquet")
        if os.path.exists(factors_path):
            factors_pd = spark.read.parquet(factors_path).toPandas()
            self._item_factors: dict[int, np.ndarray] = {
                int(row["id"]): np.array(row["features"], dtype=float)
                for _, row in factors_pd.iterrows()
            }
            print(f"  Loaded item factors for {len(self._item_factors):,} movies.")
        else:
            self._item_factors = {}
            print("  Warning: item_factors.parquet not found — run train.py first.")

    # ── Called by API layer after data is loaded ───────────────────────────

    def set_ratings(self, ratings_df: DataFrame) -> None:
        self._ratings_df = ratings_df

    # ── Public API ─────────────────────────────────────────────────────────

    def get_all_genres(self) -> list[str]:
        return self._genres

    def get_movies_by_genres(self, genres: list[str], n: int = 12) -> list[dict]:
        """
        Return popular movies that belong to at least one of the selected genres.
        Used to show the user a set of movies to rate before recommending.
        """
        valid_genres = [g for g in genres if g in self._genre_matrix.columns]
        if not valid_genres:
            return []

        mask        = self._genre_matrix[valid_genres].any(axis=1)
        filtered_ids = self._genre_matrix[mask].index.tolist()

        if self._ratings_df is not None:
            rows = (
                self._ratings_df
                .filter(F.col("movieId").isin(filtered_ids))
                .groupBy("movieId")
                .agg(
                    F.count("rating").alias("num_ratings"),
                    F.round(F.mean("rating"), 2).alias("avg_rating"),
                )
                .orderBy(F.desc("num_ratings"))
                .limit(n)
                .collect()
            )
        else:
            rows = [
                {"movieId": mid, "num_ratings": 0, "avg_rating": 0.0}
                for mid in filtered_ids[:n]
            ]

        result = []
        for row in rows:
            mid = int(row["movieId"])
            if mid not in self._movies.index:
                continue
            movie = self._movies.loc[mid]
            result.append({
                "movieId":     mid,
                "title":       movie["title_clean"],
                "genres":      movie["genres"],
                "num_ratings": int(row["num_ratings"]),
                "avg_rating":  float(row["avg_rating"]),
            })
        return result

    def recommend(
        self,
        user_ratings: list[dict],
        top_n: int = 10,
        alpha: float = 0.6,
    ) -> list[dict]:
        """
        Generate hybrid recommendations.

        Args:
            user_ratings : [{"movieId": int, "rating": float}, ...]
            top_n        : number of results to return
            alpha        : ALS weight (0 = pure content-based, 1 = pure ALS)

        Returns:
            List of movie dicts ordered by hybrid score descending.
        """
        if not user_ratings:
            return []

        rated_ids     = {r["movieId"] for r in user_ratings}
        candidate_ids = [mid for mid in self._movies.index if mid not in rated_ids]

        cb_scores  = self._content_based_scores(user_ratings, candidate_ids)
        als_scores = self._als_scores(user_ratings, candidate_ids)

        cb_norm  = _normalise(cb_scores)
        als_norm = _normalise(als_scores)

        all_ids = set(cb_norm) | set(als_norm)
        hybrid  = {
            mid: alpha * als_norm.get(mid, 0.0) + (1 - alpha) * cb_norm.get(mid, 0.0)
            for mid in all_ids
        }

        top_ids = sorted(hybrid, key=lambda x: hybrid[x], reverse=True)[:top_n]

        results = []
        for mid in top_ids:
            if mid not in self._movies.index:
                continue
            movie = self._movies.loc[mid]
            results.append({
                "movieId":       int(mid),
                "title":         str(movie["title_clean"]),
                "genres":        str(movie["genres"]),
                "hybrid_score":  round(float(hybrid[mid]),              4),
                "als_score":     round(float(als_norm.get(mid,  0.0)),  4),
                "content_score": round(float(cb_norm.get(mid,   0.0)),  4),
            })
        return results

    # ── Private ────────────────────────────────────────────────────────────

    def _content_based_scores(
        self,
        user_ratings: list[dict],
        candidate_ids: list[int],
    ) -> dict[int, float]:
        """Weighted genre profile → cosine similarity against all candidates."""
        valid = [
            (r["movieId"], r["rating"]) for r in user_ratings
            if r["movieId"] in self._genre_matrix.index
        ]
        if not valid:
            return {}

        ids, ratings = zip(*valid)
        weights       = np.array(ratings, dtype=float)
        rated_vectors = self._genre_matrix.loc[list(ids)].values
        user_profile  = (rated_vectors * weights[:, None]).sum(axis=0, keepdims=True)

        valid_candidates = [mid for mid in candidate_ids if mid in self._genre_matrix.index]
        if not valid_candidates:
            return {}

        candidate_vectors = self._genre_matrix.loc[valid_candidates].values
        sims = cosine_similarity(user_profile, candidate_vectors)[0]
        return dict(zip(valid_candidates, sims.tolist()))

    def _als_scores(
        self,
        user_ratings: list[dict],
        candidate_ids: list[int],
    ) -> dict[int, float]:
        """
        ALS cold-start: average the item vectors of rated movies (weighted by
        rating) to form a pseudo user-vector, then score candidates by cosine
        similarity in the latent space.
        """
        if not self._item_factors:
            return {}

        valid = [
            (r["movieId"], r["rating"]) for r in user_ratings
            if r["movieId"] in self._item_factors
        ]
        if not valid:
            return {}

        ids, ratings = zip(*valid)
        weights      = np.array(ratings, dtype=float)
        weights      = weights / weights.sum()
        vectors      = np.array([self._item_factors[mid] for mid in ids])
        user_vector  = (vectors * weights[:, None]).sum(axis=0, keepdims=True)

        valid_candidates = [mid for mid in candidate_ids if mid in self._item_factors]
        if not valid_candidates:
            return {}

        candidate_vectors = np.array([self._item_factors[mid] for mid in valid_candidates])
        sims = cosine_similarity(user_vector, candidate_vectors)[0]
        return dict(zip(valid_candidates, sims.tolist()))


# ── Helpers ────────────────────────────────────────────────────────────────

def _normalise(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    max_v = max(scores.values())
    if max_v == 0:
        return scores
    return {k: v / max_v for k, v in scores.items()}

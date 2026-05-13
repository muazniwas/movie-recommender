"""
ALS Model Training Script
Run once before starting the server:  python train.py

Saves to disk:
  model/als/           — full Spark MLlib ALS model
  model/item_factors.parquet — movie latent vectors (used for cold-start recommendations)
"""

import os

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, IntegerType, FloatType, LongType,
)
from pyspark.ml.recommendation import ALS
from pyspark.ml.evaluation import RegressionEvaluator

DATA_DIR  = "data"
MODEL_DIR = "model"

ALS_PARAMS = dict(
    rank=20,
    maxIter=15,
    regParam=0.1,
    coldStartStrategy="drop",
    nonnegative=True,
    seed=42,
)

_RATINGS_SCHEMA = StructType([
    StructField("userId",    IntegerType(), False),
    StructField("movieId",   IntegerType(), False),
    StructField("rating",    FloatType(),   False),
    StructField("timestamp", LongType(),    False),
])


def main():
    # ── Spark ──────────────────────────────────────────────────────────────
    print("Starting Spark session...")
    spark = (
        SparkSession.builder
        .appName("MovieLens-ALS-Training")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "50")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # ── Load ratings ───────────────────────────────────────────────────────
    print("Loading ratings...")
    ratings = spark.read.csv(
        os.path.join(DATA_DIR, "ratings.dat"),
        sep="::", schema=_RATINGS_SCHEMA, header=False,
    )
    print(f"  {ratings.count():,} ratings loaded.")

    # ── Train / test split ─────────────────────────────────────────────────
    train, test = ratings.randomSplit([0.8, 0.2], seed=42)
    print(f"  Train: {train.count():,}  |  Test: {test.count():,}")

    # ── Train ALS ──────────────────────────────────────────────────────────
    print(f"\nTraining ALS  {ALS_PARAMS} ...")
    model = ALS(
        userCol="userId",
        itemCol="movieId",
        ratingCol="rating",
        **ALS_PARAMS,
    ).fit(train)
    print("  Training complete.")

    # ── Evaluate ───────────────────────────────────────────────────────────
    print("\nEvaluating on test set...")
    preds = model.transform(test)
    rmse = RegressionEvaluator(
        metricName="rmse", labelCol="rating", predictionCol="prediction"
    ).evaluate(preds)
    mae = RegressionEvaluator(
        metricName="mae", labelCol="rating", predictionCol="prediction"
    ).evaluate(preds)
    print(f"  RMSE : {rmse:.4f}")
    print(f"  MAE  : {mae:.4f}")

    # ── Save model ─────────────────────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)

    model_path = os.path.join(MODEL_DIR, "als")
    print(f"\nSaving ALS model → {model_path}/")
    model.write().overwrite().save(model_path)

    factors_path = os.path.join(MODEL_DIR, "item_factors.parquet")
    print(f"Saving item factors → {factors_path}")
    model.itemFactors.write.mode("overwrite").parquet(factors_path)

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Training complete.")
    print(f"  RMSE            : {rmse:.4f}")
    print(f"  MAE             : {mae:.4f}")
    print(f"  Model           : {model_path}/")
    print(f"  Item factors    : {factors_path}")
    print("─" * 40)

    spark.stop()


if __name__ == "__main__":
    main()

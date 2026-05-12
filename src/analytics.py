import os
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, IntegerType, StringType, LongType, FloatType,
)


# ---------------------------------------------------------------------------
# Spark session
# ---------------------------------------------------------------------------

def create_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("MovieLens-Analytics")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "50")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_RATINGS_SCHEMA = StructType([
    StructField("userId",    IntegerType(), False),
    StructField("movieId",   IntegerType(), False),
    StructField("rating",    FloatType(),   False),
    StructField("timestamp", LongType(),    False),
])

_MOVIES_SCHEMA = StructType([
    StructField("movieId", IntegerType(), False),
    StructField("title",   StringType(),  False),
    StructField("genres",  StringType(),  False),
])

_USERS_SCHEMA = StructType([
    StructField("userId",     IntegerType(), False),
    StructField("gender",     StringType(),  False),
    StructField("age",        IntegerType(), False),
    StructField("occupation", IntegerType(), False),
    StructField("zipcode",    StringType(),  False),
])

_AGE_LABELS = {1: "Under 18", 18: "18–24", 25: "25–34",
               35: "35–44", 45: "45–49", 50: "50–55", 56: "56+"}


def load_data(spark: SparkSession, data_dir: str) -> tuple[DataFrame, DataFrame, DataFrame]:
    """Load and cache the three MovieLens 1M .dat files."""
    def _read(filename, schema):
        return spark.read.csv(
            os.path.join(data_dir, filename),
            sep="::", schema=schema, header=False,
        )

    ratings = (
        _read("ratings.dat", _RATINGS_SCHEMA)
        .withColumn("rating_date", F.to_timestamp("timestamp"))
        .withColumn("rating_year",  F.year("rating_date"))
        .withColumn("rating_month", F.month("rating_date"))
        .cache()
    )

    movies = (
        _read("movies.dat", _MOVIES_SCHEMA)
        .withColumn(
            "title_clean",
            F.regexp_replace("title", r"\s*\(\d{4}\)\s*$", ""),
        )
        .withColumn(
            "year",
            F.regexp_extract("title", r"\((\d{4})\)\s*$", 1).cast(IntegerType()),
        )
        .cache()
    )

    age_map_expr = F.create_map(
        *[x for pair in _AGE_LABELS.items() for x in (F.lit(pair[0]), F.lit(pair[1]))]
    )
    users = (
        _read("users.dat", _USERS_SCHEMA)
        .withColumn("age_group", age_map_expr[F.col("age")])
        .cache()
    )

    # Trigger caching
    ratings.count()
    movies.count()
    users.count()

    return ratings, movies, users


# ---------------------------------------------------------------------------
# Analytics functions — each returns a plain dict (JSON-serialisable)
# ---------------------------------------------------------------------------

def rating_distribution(ratings: DataFrame) -> dict:
    rows = (
        ratings.groupBy("rating")
        .count()
        .orderBy("rating")
        .collect()
    )
    total = sum(r["count"] for r in rows)
    stats = ratings.select(
        F.mean("rating").alias("mean"),
        F.stddev("rating").alias("std"),
        F.percentile_approx("rating", 0.5).alias("median"),
    ).collect()[0]

    return {
        "labels":      [float(r["rating"]) for r in rows],
        "counts":      [int(r["count"])    for r in rows],
        "percentages": [round(r["count"] / total * 100, 2) for r in rows],
        "mean":        round(float(stats["mean"]), 3),
        "std":         round(float(stats["std"]),  3),
        "median":      float(stats["median"]),
        "total":       total,
    }


def genre_stats(movies: DataFrame, ratings: DataFrame) -> dict:
    exploded = movies.withColumn("genre", F.explode(F.split("genres", "\\|")))

    counts = (
        exploded.groupBy("genre")
        .agg(F.count("movieId").alias("movie_count"))
        .orderBy(F.desc("movie_count"))
        .collect()
    )

    avg_ratings = (
        exploded.join(ratings, "movieId")
        .groupBy("genre")
        .agg(
            F.round(F.mean("rating"), 3).alias("avg_rating"),
            F.count("rating").alias("rating_count"),
        )
        .filter(F.col("rating_count") >= 1000)
        .orderBy(F.desc("avg_rating"))
        .collect()
    )

    return {
        "by_movie_count": [
            {"genre": r["genre"], "movie_count": int(r["movie_count"])}
            for r in counts
        ],
        "by_avg_rating": [
            {
                "genre":        r["genre"],
                "avg_rating":   float(r["avg_rating"]),
                "rating_count": int(r["rating_count"]),
            }
            for r in avg_ratings
        ],
    }


def top_movies(movies: DataFrame, ratings: DataFrame, n: int = 20) -> dict:
    global_mean = float(ratings.select(F.mean("rating")).collect()[0][0])
    m = 50  # minimum ratings required

    rows = (
        ratings.groupBy("movieId")
        .agg(
            F.count("rating").alias("num_ratings"),
            F.round(F.mean("rating"), 3).alias("avg_rating"),
        )
        .filter(F.col("num_ratings") >= m)
        .withColumn(
            "bayesian_avg",
            F.round(
                (F.col("num_ratings") / (F.col("num_ratings") + m)) * F.col("avg_rating")
                + (m / (F.col("num_ratings") + m)) * F.lit(global_mean),
                4,
            ),
        )
        .join(movies.select("movieId", "title_clean", "genres"), "movieId")
        .orderBy(F.desc("bayesian_avg"))
        .limit(n)
        .collect()
    )

    return {
        "movies": [
            {
                "title":        r["title_clean"],
                "genres":       r["genres"],
                "avg_rating":   float(r["avg_rating"]),
                "num_ratings":  int(r["num_ratings"]),
                "bayesian_avg": float(r["bayesian_avg"]),
            }
            for r in rows
        ]
    }


def user_stats(users: DataFrame, ratings: DataFrame) -> dict:
    activity = (
        ratings.groupBy("userId")
        .agg(F.count("rating").alias("num_ratings"))
        .select(
            F.min("num_ratings").alias("min"),
            F.max("num_ratings").alias("max"),
            F.round(F.mean("num_ratings"), 1).alias("mean"),
            F.percentile_approx("num_ratings", 0.5).alias("median"),
        )
        .collect()[0]
    )

    gender = (
        users.groupBy("gender")
        .count()
        .collect()
    )

    age = (
        users.groupBy("age_group")
        .count()
        .orderBy(F.desc("count"))
        .collect()
    )

    # Ratings per user histogram buckets
    buckets = [0, 20, 50, 100, 200, 500, 1000, 5000]
    bucket_labels = ["1–20", "21–50", "51–100", "101–200", "201–500", "501–1000", "1000+"]
    per_user = ratings.groupBy("userId").agg(F.count("rating").alias("n"))
    histogram = []
    for i, (lo, hi) in enumerate(zip(buckets, buckets[1:])):
        count = per_user.filter((F.col("n") >= lo) & (F.col("n") < hi)).count()
        histogram.append({"bucket": bucket_labels[i], "count": int(count)})

    return {
        "activity": {
            "min":    int(activity["min"]),
            "max":    int(activity["max"]),
            "mean":   float(activity["mean"]),
            "median": int(activity["median"]),
        },
        "gender":    {r["gender"]: int(r["count"]) for r in gender},
        "age_groups": [
            {"age_group": r["age_group"], "count": int(r["count"])} for r in age
        ],
        "activity_histogram": histogram,
    }


def temporal_trends(ratings: DataFrame) -> dict:
    rows = (
        ratings.groupBy("rating_year", "rating_month")
        .agg(
            F.count("rating").alias("num_ratings"),
            F.round(F.mean("rating"), 3).alias("avg_rating"),
        )
        .orderBy("rating_year", "rating_month")
        .collect()
    )

    return {
        "periods":     [f"{r['rating_year']}-{str(r['rating_month']).zfill(2)}" for r in rows],
        "counts":      [int(r["num_ratings"])  for r in rows],
        "avg_ratings": [float(r["avg_rating"]) for r in rows],
    }

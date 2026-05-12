import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.analytics import create_spark_session, load_data
from api.routes import analytics as analytics_routes

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Spark session and loading data...")
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    ratings, movies, users = load_data(spark, DATA_DIR)
    app.state.spark   = spark
    app.state.ratings = ratings
    app.state.movies  = movies
    app.state.users   = users
    print("Data loaded and cached. Server ready.")

    yield

    spark.stop()
    print("Spark session stopped.")


app = FastAPI(title="Movie Recommender", lifespan=lifespan)

app.include_router(analytics_routes.router, prefix="/api/analytics", tags=["analytics"])

# Serve the UI — must be mounted last so API routes take priority
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

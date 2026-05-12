from fastapi import APIRouter, Request, Query, HTTPException

from src.analytics import (
    rating_distribution,
    genre_stats,
    top_movies,
    user_stats,
    temporal_trends,
)

router = APIRouter()


@router.get("/ratings")
def get_rating_distribution(request: Request):
    try:
        return rating_distribution(request.app.state.ratings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/genres")
def get_genre_stats(request: Request):
    try:
        return genre_stats(request.app.state.movies, request.app.state.ratings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-movies")
def get_top_movies(
    request: Request,
    n: int = Query(default=20, ge=5, le=100),
):
    try:
        return top_movies(request.app.state.movies, request.app.state.ratings, n=n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
def get_user_stats(request: Request):
    try:
        return user_stats(request.app.state.users, request.app.state.ratings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
def get_temporal_trends(request: Request):
    try:
        return temporal_trends(request.app.state.ratings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

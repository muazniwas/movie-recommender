from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class GenresRequest(BaseModel):
    genres: list[str]


class UserRating(BaseModel):
    movieId: int
    rating: float = Field(ge=0.5, le=5.0)


class RecommendRequest(BaseModel):
    ratings: list[UserRating]
    top_n: int = Field(default=10, ge=1, le=50)
    alpha: float = Field(default=0.6, ge=0.0, le=1.0)


@router.get("/genres")
def get_genres(request: Request):
    try:
        return {"genres": request.app.state.recommender.get_all_genres()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/movies")
def get_movies_by_genres(body: GenresRequest, request: Request):
    try:
        movies = request.app.state.recommender.get_movies_by_genres(body.genres)
        return {"movies": movies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def recommend(body: RecommendRequest, request: Request):
    try:
        user_ratings = [{"movieId": r.movieId, "rating": r.rating} for r in body.ratings]
        results = request.app.state.recommender.recommend(
            user_ratings=user_ratings,
            top_n=body.top_n,
            alpha=body.alpha,
        )
        return {"recommendations": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

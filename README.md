# Movie Recommender System

IT5612 Big Data Analytics for AI — Mini Project (Part A + Part B)

## Overview

A full-stack big data application built with **PySpark**, **FastAPI**, and **vanilla JS**.

- **Part A** — Big data analytics dashboard: rating distributions, genre trends, user demographics, temporal patterns, and top movies, all computed via PySpark on the MovieLens 1M dataset.
- **Part B** — Movie recommendation system: users rate a few movies and receive personalised recommendations using a hybrid of ALS (Spark MLlib) collaborative filtering and content-based genre similarity.

## Dataset

**MovieLens 1M** — 1,000,209 ratings from 6,040 users across 3,706 movies.  
Source: https://grouplens.org/datasets/movielens/1m/

The dataset is not included in this repository. Download and extract it manually:

```bash
cd data/
curl -O https://files.grouplens.org/datasets/movielens/ml-1m.zip
unzip ml-1m.zip && mv ml-1m/* . && rm -rf ml-1m ml-1m.zip
```

Expected files in `data/`:
```
data/
├── movies.dat
├── ratings.dat
└── users.dat
```

## Project Structure

```
movie-recommender/
├── src/
│   ├── analytics.py       # PySpark analytics functions (Part A)
│   └── recommender.py     # Recommendation logic — ALS + content-based + hybrid (Part B)
├── api/
│   ├── main.py            # FastAPI app, Spark session lifecycle
│   └── routes/
│       ├── analytics.py   # GET /api/analytics/* endpoints
│       └── recommendations.py  # POST /api/recommend endpoint
├── ui/
│   ├── index.html         # Analytics dashboard (Part A)
│   ├── recommend.html     # Recommendation UI (Part B)
│   ├── css/style.css
│   └── js/
│       ├── analytics.js
│       └── recommend.js
├── train.py               # One-time ALS model training script
├── requirements.txt
├── .gitignore
└── README.md
```

## Setup

### 1. Prerequisites

- Python 3.10+
- Java 11 or 17 (required by PySpark)

```bash
java -version
```

### 2. Virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Download the dataset

See the Dataset section above.

### 4. Train the ALS model (Part B only)

Run this once before starting the server. The model is saved to `model/als/`.

```bash
python train.py
```

### 5. Start the server

```bash
uvicorn api.main:app --reload
```

The app will be available at http://localhost:8000.

## Part A — Analytics

The analytics dashboard visualises the following, computed live via PySpark:

- Overall rating distribution
- Genre popularity and average ratings by genre
- Top 20 movies by Bayesian average rating
- User activity distribution and demographics (gender, age group)
- Monthly rating volume and average rating over time

## Part B — Recommendation System

Users do not need an account or an existing user ID. The flow is:

1. Select genres you enjoy
2. Rate a few movies shown from those genres
3. Receive personalised recommendations

**How recommendations are generated:**
- **Content-based:** Builds a genre profile from your ratings and scores unseen movies by cosine similarity
- **ALS (collaborative filtering):** Uses item vectors from the pre-trained ALS model — your rated movies' vectors are averaged to form a user vector, then nearest unrated movies are found in latent space
- **Hybrid:** Weighted combination of both scores (`0.6 × ALS + 0.4 × content-based`)

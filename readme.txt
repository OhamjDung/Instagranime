===================================================
  Instagranime - A Personalized Anime Recommendation Engine
===================================================

Project Overview
----------------

Instagranime is a full-stack web application designed to provide users with a continuous, scrollable reel of personalized anime recommendations. Unlike traditional list-based recommendations, this project uses a "reel" format similar to modern social media apps, presenting users with promotional videos of anime tailored to their unique tastes.

The system is built on a comprehensive data pipeline that collects, processes, and analyzes data from MyAnimeList (MAL) to build a sophisticated recommendation model. New users can get instant recommendations by providing a few examples of anime they like and dislike, and the system learns and adapts to their preferences in real-time as they interact with the reels.


How It Works: The Data & Recommendation Pipeline
----------------------------------------------------

The project is divided into two main phases: a one-time batch process to build the core model, and a real-time process to serve new users.

### Phase 1: Batch Processing & Model Building

This phase collects and processes a large dataset to understand anime properties and existing user tastes.

1.  **Data Acquisition:**
    * **User Discovery:** A large seed list of active MyAnimeList usernames is scraped from the MAL forums.
        * `Script: newspider.py` (inside scrapy/)
    * **Watchlist & Anime Data:** For each discovered user, their public watchlist is fetched via the MAL API. This includes their personal rankings and a list of all anime they've seen. Detailed metadata for each unique anime (studio, genres, themes, etc.) is also collected.
        * `Scripts: animespider.py` (inside scrapy/), `getAnime.js`
    * **Reviews & Video Links:** The official review sections and promotional YouTube video links for each anime are scraped directly from the MAL website.
        * `Script: animespider.py` (inside scrapy/)

2.  **Data Preparation & Feature Engineering:**
    * The collected user reviews for each anime are analyzed to extract a vocabulary of commonly used positive and negative keywords (e.g., "fast-paced," "deep characters," "confusing plot"). This process creates a consensus on the specific, nuanced aspects that people like or dislike about a show.
        * `Script: process_reviews.py`

3.  **Taste Profile Generation:**
    * A "Taste Profile" is constructed for every user in the dataset. This profile is a weighted vector that represents the user's preferences across genres, studios, and the positive/negative keywords derived from their highly-ranked anime. Disliked anime contribute negative weights to the profile.
    * Cosine Similarity is then used to compare all user profiles, allowing the system to find "taste neighbors"—other users with similar preferences.
        * `Script: batch_process_user_profiles.py`

4.  **Database Storage:**
    * All collected and processed data is loaded into a MySQL database for efficient querying. This includes the final user taste profiles, anime metadata, processed reviews, and user watchlist data.
        * `Scripts: import_anime+reviews.js, import_userdata_to_db.js, batch_process_user_profiles.py`

### Phase 2: Real-Time Recommendations for New Users

This phase is handled by the live web application.

1.  **New User Input:** A new user visits the web application and provides three key pieces of information:
    * An optional list of genres they require.
    * A list of anime they like.
    * A list of anime they dislike.

2.  **Real-Time Profile Creation:**
    * The Flask backend takes this input and constructs a new, temporary taste profile on the fly, using the same principles as the batch process.
        * `API Logic: api.py`

3.  **Candidate Scoring & Reel Generation:**
    * The API queries the database for candidate anime, filtering by the user's required genres and excluding anime they've already seen or provided as input.
    * Each candidate anime's keywords are scored against the new user's taste profile.
    * The highest-scoring anime are returned to the frontend, which dynamically creates the scrollable video reel.

4.  **Live Taste Profile Refinement:**
    * As the user interacts with the reels (likes, dislikes, saves, watches for a long time, or skips quickly), these signals are sent back to the API.
    * The API updates the user's taste profile in real-time, re-scores all the anime currently loaded in the user's queue, and intelligently re-orders the upcoming reels to show the new best match next.
        * `Frontend Logic: index.html (JavaScript)`
        * `API Logic: api.py`


Technology Stack
----------------

* **Backend:** Python (Flask), MySQL
* **Frontend:** HTML5, CSS3 (Tailwind CSS), JavaScript
* **Data Science:** Python, Pandas, Scikit-learn (for Cosine Similarity)
* **Data Collection:** Python Web Scraping (Scrapy), MyAnimeList (MAL) API
* **APIs:** YouTube IFrame API


Project Structure
-----------------

    .
    ├── scrapy/                     # Scrapy project for all web scraping (spiders are inside)
    ├── .env                        # Environment variables (DB credentials, API keys)
    ├── api.py                      # Core Flask API for real-time recommendations
    ├── index.html                  # The single-page frontend application
    │
    ├── batch_process_user_profiles.py # Batch script to build all user taste profiles
    ├── process_reviews.py          # Script to perform NLP on reviews and extract keywords
    │
    ├── getAnime.js                 # Node.js script to fetch data from the MAL API
    ├── import_anime+reviews.js     # Node.js script to import scraped data into the DB
    ├── import_userdata_to_db.js    # Node.js script to import API data into the DB
    │
    ├── *.csv                       # Raw data files generated by scrapers/API scripts
    ├── package.json                # Node.js dependencies
    └── requirements.txt            # Python dependencies


Key Scripts
-----------

* `newspider.py` (in `scrapy/`): Scrapes MAL forums for usernames.
* `animespider.py` (in `scrapy/`): Scrapes MAL anime pages for reviews and video links.
* `getAnime.js`: Uses the MAL API to fetch user watchlists and anime metadata.
* `process_reviews.py`: Performs NLP on reviews to extract positive/negative keywords.
* `batch_process_user_profiles.py`: Builds taste profiles for the entire user dataset.
* `import_*.js`: Various scripts to load collected data into the MySQL database.
* `api.py`: The core Flask API that handles real-time requests, profile creation, and scoring.
* `index.html`: The single-page application that contains all the UI and frontend logic for the user experience.
# import os
# import psycopg2
# import psycopg2.extras
# from dotenv import load_dotenv
# import json
# from collections import Counter
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import re

# # --- 1. SETUP ---
# load_dotenv()
# app = Flask(__name__)
# CORS(app)

# # --- 2. DATABASE CONNECTION & CORE LOGIC ---
# def get_db_connection():
#     """Establishes a connection to the PostgreSQL database."""
#     try:
#         # --- MODIFIED: Reads the SSL mode from .env, defaults to 'require' for production ---
#         ssl_mode = os.getenv('DB_SSLMODE', 'require')

#         dsn = (
#             f"dbname='{os.getenv('DB_NAME')}' "
#             f"user='{os.getenv('DB_USER')}' "
#             f"password='{os.getenv('DB_PASSWORD')}' "
#             f"host='{os.getenv('DB_HOST')}' "
#             f"port='{os.getenv('DB_PORT')}' "
#             f"sslmode='{ssl_mode}'"  # Use the variable here
#         )
#         connection = psycopg2.connect(dsn)
#         return connection
#     except psycopg2.OperationalError as err:
#         print(f"Error connecting to database: {err}")
#         return None

# ALL_GENRES = [
#     "Action", "Adventure", "Avant Garde", "Award Winning", "Boys Love", "Comedy",
#     "Drama", "Fantasy", "Girls Love", "Gourmet", "Horror", "Mystery", "Romance",
#     "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Suspense", "Ecchi",
#     "Erotica", "Hentai"
# ]
# EXPLICIT_GENRES = "'Ecchi', 'Erotica', 'Hentai'"

# def get_or_create_user(cursor, username):
#     cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
#     result = cursor.fetchone()
#     if result:
#         return result['user_id']
#     else:
#         cursor.execute("INSERT INTO users (username) VALUES (%s) RETURNING user_id", (username,))
#         new_user_id = cursor.fetchone()['user_id']
#         return new_user_id

# def calculate_initial_taste_profile(cursor, liked_anime_titles, disliked_anime_titles):
#     taste_profile = Counter()
#     if liked_anime_titles:
#         placeholders = ','.join(['%s'] * len(liked_anime_titles))
#         cursor.execute(f"SELECT positive_keywords, negative_keywords FROM animes WHERE title IN ({placeholders})", tuple(liked_anime_titles))
#         for row in cursor.fetchall():
#             if row.get('positive_keywords'):
#                 for keyword in row['positive_keywords'].split(', '):
#                     if keyword: taste_profile[keyword] += 1
#             if row.get('negative_keywords'):
#                 for keyword in row['negative_keywords'].split(', '):
#                     if keyword: taste_profile[keyword] -= 1
#     if disliked_anime_titles:
#         placeholders = ','.join(['%s'] * len(disliked_anime_titles))
#         cursor.execute(f"SELECT positive_keywords, negative_keywords FROM animes WHERE title IN ({placeholders})", tuple(disliked_anime_titles))
#         for row in cursor.fetchall():
#             if row.get('positive_keywords'):
#                 for keyword in row['positive_keywords'].split(', '):
#                     if keyword: taste_profile[keyword] -= 2
#             if row.get('negative_keywords'):
#                 for keyword in row['negative_keywords'].split(', '):
#                     if keyword: taste_profile[keyword] += 2
#     return dict(taste_profile)

# def get_youtube_id_from_url(url):
#     if not url: return None
#     regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
#     match = re.search(regex, url)
#     return match.group(1) if match else None


# # --- FLASK API ENDPOINTS ---
# @app.route('/api/search_genres', methods=['GET'])
# def search_genres():
#     query = request.args.get('q', '').lower()
#     if len(query) < 1: return jsonify([])
#     results = [genre for genre in ALL_GENRES if query in genre.lower()]
#     return jsonify(results[:5])


# @app.route('/api/search_anime', methods=['GET'])
# def search_anime():
#     query = request.args.get('q', '')
#     if len(query) < 2: return jsonify([])
#     connection = get_db_connection()
#     if not connection: return jsonify({"error": "Database connection failed"}), 500
#     cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
#     try:
#         cursor.execute("SELECT title FROM animes WHERE title ILIKE %s AND promo_link IS NOT NULL AND promo_link != '' LIMIT 5", (f"%{query}%",))
#         results = [row['title'] for row in cursor.fetchall()]
#         return jsonify(results)
#     except Exception as e:
#         print(f"An error occurred in /api/search_anime: {e}")
#         return jsonify({"error": "An internal error occurred"}), 500
#     finally:
#         if connection:
#             cursor.close()
#             connection.close()


# @app.route('/api/generate_reel', methods=['POST'])
# def generate_reel():
#     data = request.get_json()
#     username = data.get('username')
#     user_id = data.get('user_id')
#     liked_anime = data.get('liked_anime', [])
#     disliked_anime = data.get('disliked_anime', [])
#     genres = data.get('genres', [])
#     seen_anime_ids = data.get('seen_anime_ids', [])
#     allow_explicit = data.get('allow_explicit', False)

#     if not username and not user_id: return jsonify({"error": "Username or user_id is required."}), 400
    
#     connection = get_db_connection()
#     if not connection: return jsonify({"error": "Database connection failed"}), 500
#     cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

#     try:
#         if user_id:
#             cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
#             result = cursor.fetchone()
#             taste_profile = json.loads(result['taste_profile']) if result and result.get('taste_profile') else {}
#         else:
#             user_id = get_or_create_user(cursor, username)
#             connection.commit()
#             taste_profile = calculate_initial_taste_profile(cursor, liked_anime, disliked_anime)
#             profile_json = json.dumps(taste_profile)
#             # --- MODIFIED: Added last_updated to the query ---
#             cursor.execute("""
#                 INSERT INTO user_taste_profiles (user_id, taste_profile, last_updated) 
#                 VALUES (%s, %s, NOW())
#                 ON CONFLICT (user_id) 
#                 DO UPDATE SET 
#                     taste_profile = EXCLUDED.taste_profile,
#                     last_updated = NOW();
#             """, (user_id, profile_json))
#             connection.commit()
        
#         comprehensive_seen_ids = set(seen_anime_ids)
#         all_interacted_titles = liked_anime + disliked_anime
#         if all_interacted_titles:
#             placeholders = ','.join(['%s'] * len(all_interacted_titles))
#             cursor.execute(f"SELECT anime_id FROM animes WHERE title IN ({placeholders})", tuple(all_interacted_titles))
#             for row in cursor.fetchall():
#                 comprehensive_seen_ids.add(row['anime_id'])

#         # --- FIX: Refactored SQL query for PostgreSQL compatibility ---
#         query_base = """
#             WITH genre_agg AS (
#                 SELECT 
#                     ag.anime_id, 
#                     STRING_AGG(g.name, ', ') as anime_genres
#                 FROM anime_genres ag
#                 JOIN genres g ON ag.genre_id = g.genre_id
#                 GROUP BY ag.anime_id
#             )
#             SELECT a.*, ga.anime_genres
#             FROM animes a
#             LEFT JOIN genre_agg ga ON a.anime_id = ga.anime_id
#         """
#         params = []
#         where_clauses = ["a.promo_link IS NOT NULL AND a.promo_link != ''"]
#         if not allow_explicit:
#             where_clauses.append(f"a.anime_id NOT IN (SELECT ag.anime_id FROM anime_genres ag JOIN genres g ON ag.genre_id = g.genre_id WHERE g.name IN ({EXPLICIT_GENRES}))")
#         if genres:
#             genre_placeholders = ','.join(['%s'] * len(genres))
#             where_clauses.append(f"a.anime_id IN (SELECT ag_inner.anime_id FROM anime_genres ag_inner JOIN genres g_inner ON ag_inner.genre_id = g_inner.genre_id WHERE g_inner.name IN ({genre_placeholders}))")
#             params.extend(genres)
#         if comprehensive_seen_ids:
#             id_placeholders = ','.join(['%s'] * len(comprehensive_seen_ids))
#             where_clauses.append(f"a.anime_id NOT IN ({id_placeholders})")
#             params.extend(list(comprehensive_seen_ids))
        
#         if where_clauses:
#             query_base += " WHERE " + " AND ".join(where_clauses)

#         query = query_base + " ORDER BY a.mean_score DESC NULLS LAST LIMIT 500"
#         cursor.execute(query, tuple(params))
#         candidates = cursor.fetchall()

#         scored_anime = []
#         for anime in candidates:
#             score = 0
#             if anime.get('positive_keywords'):
#                 for keyword in anime.get('positive_keywords', '').split(', '):
#                     if keyword: score += taste_profile.get(keyword, 0)
#             if anime.get('negative_keywords'):
#                 for keyword in anime.get('negative_keywords', '').split(', '):
#                     if keyword: score -= taste_profile.get(keyword, 0)
#             if anime.get('mean_score') and anime['mean_score'] > 8.0: score *= 1.2
#             scored_anime.append({'anime': anime, 'score': score})
        
#         sorted_recommendations = sorted(scored_anime, key=lambda x: x['score'], reverse=True)
#         positive_recommendations = [rec for rec in sorted_recommendations if rec['score'] > 0]
#         final_recommendations = []
#         recommendation_type = "personalized"
#         if positive_recommendations:
#             final_recommendations = positive_recommendations[:15]
#         else:
#             recommendation_type = "fallback"
#             # --- FIX: Also refactor the fallback query for PostgreSQL ---
#             fallback_query_base = """
#                 WITH genre_agg AS (
#                     SELECT 
#                         ag.anime_id, 
#                         STRING_AGG(g.name, ', ') as anime_genres
#                     FROM anime_genres ag
#                     JOIN genres g ON ag.genre_id = g.genre_id
#                     GROUP BY ag.anime_id
#                 )
#                 SELECT a.*, ga.anime_genres
#                 FROM animes a
#                 LEFT JOIN genre_agg ga ON a.anime_id = ga.anime_id
#             """
#             fallback_params = []
#             fallback_where = ["a.promo_link IS NOT NULL AND a.promo_link != ''"]
#             if not allow_explicit:
#                 fallback_where.append(f"a.anime_id NOT IN (SELECT ag.anime_id FROM anime_genres ag JOIN genres g ON ag.genre_id = g.genre_id WHERE g.name IN ({EXPLICIT_GENRES}))")
#             if comprehensive_seen_ids:
#                 id_placeholders = ','.join(['%s'] * len(comprehensive_seen_ids))
#                 fallback_where.append(f"a.anime_id NOT IN ({id_placeholders})")
#                 fallback_params.extend(list(comprehensive_seen_ids))
#             if fallback_where:
#                 fallback_query_base += " WHERE " + " AND ".join(fallback_where)
            
#             fallback_query = fallback_query_base + " ORDER BY a.overal_rank ASC NULLS LAST LIMIT 15"
#             cursor.execute(fallback_query, tuple(fallback_params))
#             fallback_candidates = cursor.fetchall()
#             for anime in fallback_candidates:
#                 final_recommendations.append({'anime': anime, 'score': 0})
        
#         response_data = []
#         for item in final_recommendations:
#             anime = item['anime']
#             cursor.execute("SELECT username, sentiment_polarity, review_text FROM reviews WHERE anime_id = %s ORDER BY RANDOM() LIMIT 3", (anime['anime_id'],))
#             reviews = cursor.fetchall()
#             comments = [{"user": r['username'], "text": r['review_text'][:200] + '...' if r['review_text'] and len(r['review_text']) > 200 else r.get('review_text', ''), "type": "positive" if r['sentiment_polarity'] > 0.1 else "negative"} for r in reviews]
#             response_data.append({"id": anime['anime_id'], "title": anime['title'], "trailerId": get_youtube_id_from_url(anime.get('promo_link')), "score": anime.get('mean_score'), "rank": anime.get('overal_rank'), "genres": anime.get('anime_genres'), "positive_keywords": anime.get('positive_keywords'), "negative_keywords": anime.get('negative_keywords'), "comments": comments, "initial_score": item['score']})

#         return jsonify({"user_id": user_id, "recommendations": response_data, "recommendation_type": recommendation_type, "taste_profile": taste_profile })
#     except Exception as e:
#         print(f"An error occurred in /api/generate_reel: {e}")
#         return jsonify({"error": "An internal error occurred"}), 500
#     finally:
#         if connection:
#             cursor.close()
#             connection.close()


# @app.route('/api/feedback', methods=['POST'])
# def handle_feedback():
#     data = request.get_json()
#     user_id = data.get('user_id')
#     anime_id = data.get('animeId')
#     reason = data.get('reason')
#     connection = get_db_connection()
#     if not connection: return jsonify({"error": "Database connection failed"}), 500
#     cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
#     try:
#         cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
#         result = cursor.fetchone()
#         taste_profile = Counter(json.loads(result['taste_profile'])) if result and result.get('taste_profile') else Counter()
#         cursor.execute("SELECT positive_keywords, negative_keywords FROM animes WHERE anime_id = %s", (anime_id,))
#         anime_keywords = cursor.fetchone()
#         if anime_keywords:
#             if reason == 'like_button': modifier = 1
#             elif reason == 'not_interested_button': modifier = -2
#             elif reason == 'save_to_watchlist': modifier = 0.5
#             else: modifier = 0
#             if modifier != 0:
#                 if anime_keywords.get('positive_keywords'):
#                     for keyword in anime_keywords['positive_keywords'].split(', '):
#                         if keyword: taste_profile[keyword] += modifier
#                 if anime_keywords.get('negative_keywords'):
#                     for keyword in anime_keywords['negative_keywords'].split(', '):
#                         if keyword: taste_profile[keyword] -= modifier
        
#         # --- MODIFIED: Added last_updated to the query ---
#         cursor.execute(
#             """
#             INSERT INTO user_taste_profiles (user_id, taste_profile, last_updated) VALUES (%s, %s, NOW())
#             ON CONFLICT (user_id) DO UPDATE SET 
#                 taste_profile = EXCLUDED.taste_profile,
#                 last_updated = NOW();
#             """,
#             (user_id, json.dumps(dict(taste_profile)))
#         )
#         connection.commit()
#         return jsonify({"status": "success", "taste_profile": dict(taste_profile)}), 200
#     except psycopg2.Error as err:
#         print(f"Database error while logging feedback: {err}")
#         return jsonify({"error": "Database error"}), 500
#     finally:
#         if connection:
#             cursor.close()
#             connection.close()
            
# @app.route('/api/user/<int:user_id>', methods=['DELETE'])
# def delete_user(user_id):
#     connection = get_db_connection()
#     if not connection: return jsonify({"error": "Database connection failed"}), 500
#     cursor = connection.cursor()
#     try:
#         cursor.execute("DELETE FROM user_taste_profiles WHERE user_id = %s", (user_id,))
#         cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
#         connection.commit()
#         return jsonify({"status": "success"}), 200
#     except Exception as e:
#         print(f"An error occurred during user deletion: {e}")
#         return jsonify({"error": "An internal error occurred"}), 500
#     finally:
#         if connection:
#             cursor.close()
#             connection.close()

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import json
from collections import Counter
from flask import Flask, request, jsonify
from flask_cors import CORS
import re

# --- 1. SETUP ---
load_dotenv()
app = Flask(__name__)
CORS(app)

# --- 2. DATABASE CONNECTION & CORE LOGIC ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        ssl_mode = os.getenv('DB_SSLMODE', 'require')
        dsn = (
            f"dbname='{os.getenv('DB_NAME')}' "
            f"user='{os.getenv('DB_USER')}' "
            f"password='{os.getenv('DB_PASSWORD')}' "
            f"host='{os.getenv('DB_HOST')}' "
            f"port='{os.getenv('DB_PORT')}' "
            f"sslmode='{ssl_mode}'"
        )
        connection = psycopg2.connect(dsn)
        return connection
    except psycopg2.OperationalError as err:
        print(f"Error connecting to database: {err}")
        return None

# (The rest of the file is unchanged until search_anime)
ALL_GENRES = ["Action", "Adventure", "Avant Garde", "Award Winning", "Boys Love", "Comedy", "Drama", "Fantasy", "Girls Love", "Gourmet", "Horror", "Mystery", "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Suspense", "Ecchi", "Erotica", "Hentai"]
EXPLICIT_GENRES = "'Ecchi', 'Erotica', 'Hentai'"
def get_or_create_user(cursor, username):
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    if result:
        return result['user_id']
    else:
        cursor.execute("INSERT INTO users (username) VALUES (%s) RETURNING user_id", (username,))
        new_user_id = cursor.fetchone()['user_id']
        return new_user_id
def calculate_initial_taste_profile(cursor, liked_anime_titles, disliked_anime_titles):
    taste_profile = Counter()
    if liked_anime_titles:
        placeholders = ','.join(['%s'] * len(liked_anime_titles))
        # Search both titles to build the profile
        cursor.execute(f"SELECT positive_keywords, negative_keywords FROM animes WHERE title IN ({placeholders}) OR title_english IN ({placeholders})", tuple(liked_anime_titles) * 2)
        for row in cursor.fetchall():
            if row.get('positive_keywords'):
                for keyword in row['positive_keywords'].split(', '):
                    if keyword: taste_profile[keyword] += 1
            if row.get('negative_keywords'):
                for keyword in row['negative_keywords'].split(', '):
                    if keyword: taste_profile[keyword] -= 1
    if disliked_anime_titles:
        placeholders = ','.join(['%s'] * len(disliked_anime_titles))
        cursor.execute(f"SELECT positive_keywords, negative_keywords FROM animes WHERE title IN ({placeholders}) OR title_english IN ({placeholders})", tuple(disliked_anime_titles) * 2)
        for row in cursor.fetchall():
            if row.get('positive_keywords'):
                for keyword in row['positive_keywords'].split(', '):
                    if keyword: taste_profile[keyword] -= 2
            if row.get('negative_keywords'):
                for keyword in row['negative_keywords'].split(', '):
                    if keyword: taste_profile[keyword] += 2
    return dict(taste_profile)
def get_youtube_id_from_url(url):
    if not url: return None
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

# --- FLASK API ENDPOINTS ---
@app.route('/api/search_genres', methods=['GET'])
def search_genres():
    query = request.args.get('q', '').lower()
    if len(query) < 1: return jsonify([])
    results = [genre for genre in ALL_GENRES if query in genre.lower()]
    return jsonify(results[:5])

# --- MODIFIED: This function now searches and returns English titles ---
@app.route('/api/search_anime', methods=['GET'])
def search_anime():
    query = request.args.get('q', '')
    if len(query) < 2: return jsonify([])
    
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database connection failed"}), 500
    
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        search_term = f"%{query}%"
        # Search in both original and English titles
        cursor.execute("""
            SELECT title, title_english 
            FROM animes 
            WHERE (title ILIKE %s OR title_english ILIKE %s) 
            LIMIT 10
        """, (search_term, search_term))
        
        results = []
        seen_titles = set()
        for row in cursor.fetchall():
            # Prioritize the English title if it exists, otherwise use the original
            display_title = row['title_english'] if row['title_english'] else row['title']
            if display_title and display_title not in seen_titles:
                results.append(display_title)
                seen_titles.add(display_title)
            # Stop once we have 5 unique results
            if len(results) >= 5:
                break
                
        return jsonify(results)
    except Exception as e:
        print(f"An error occurred in /api/search_anime: {e}")
        return jsonify({"error": "An internal error occurred"}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()

@app.route('/api/generate_reel', methods=['POST'])
def generate_reel():
    # ... (function is unchanged from the last working version) ...
    data = request.get_json()
    username = data.get('username')
    user_id = data.get('user_id')
    liked_anime = data.get('liked_anime', [])
    disliked_anime = data.get('disliked_anime', [])
    genres = data.get('genres', [])
    seen_anime_ids = data.get('seen_anime_ids', [])
    allow_explicit = data.get('allow_explicit', False)
    if not username and not user_id: return jsonify({"error": "Username or user_id is required."}), 400
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database connection failed"}), 500
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        if user_id:
            cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            taste_profile = json.loads(result['taste_profile']) if result and result.get('taste_profile') else {}
        else:
            user_id = get_or_create_user(cursor, username)
            connection.commit()
            taste_profile = calculate_initial_taste_profile(cursor, liked_anime, disliked_anime)
            profile_json = json.dumps(taste_profile)
            cursor.execute("""
                INSERT INTO user_taste_profiles (user_id, taste_profile) 
                VALUES (%s, %s::jsonb)
                ON CONFLICT (user_id) 
                DO UPDATE SET taste_profile = EXCLUDED.taste_profile;
            """, (user_id, profile_json))
            connection.commit()
        comprehensive_seen_ids = set(seen_anime_ids)
        all_interacted_titles = liked_anime + disliked_anime
        if all_interacted_titles:
            placeholders = ','.join(['%s'] * len(all_interacted_titles))
            cursor.execute(f"SELECT anime_id FROM animes WHERE title IN ({placeholders}) OR title_english IN ({placeholders})", tuple(all_interacted_titles) * 2)
            for row in cursor.fetchall():
                comprehensive_seen_ids.add(row['anime_id'])
        query_base = "WITH genre_agg AS (SELECT ag.anime_id, STRING_AGG(g.name, ', ') as anime_genres FROM anime_genres ag JOIN genres g ON ag.genre_id = g.genre_id GROUP BY ag.anime_id) SELECT a.*, ga.anime_genres FROM animes a LEFT JOIN genre_agg ga ON a.anime_id = ga.anime_id"
        params = []
        where_clauses = ["a.promo_link IS NOT NULL AND a.promo_link != ''"] 
        if not allow_explicit:
            where_clauses.append(f"a.anime_id NOT IN (SELECT ag.anime_id FROM anime_genres ag JOIN genres g ON ag.genre_id = g.genre_id WHERE g.name IN ({EXPLICIT_GENRES}))")
        if genres:
            genre_placeholders = ','.join(['%s'] * len(genres))
            where_clauses.append(f"a.anime_id IN (SELECT ag_inner.anime_id FROM anime_genres ag_inner JOIN genres g_inner ON ag_inner.genre_id = g_inner.genre_id WHERE g_inner.name IN ({genre_placeholders}))")
            params.extend(genres)
        if comprehensive_seen_ids:
            id_placeholders = ','.join(['%s'] * len(comprehensive_seen_ids))
            where_clauses.append(f"a.anime_id NOT IN ({id_placeholders})")
            params.extend(list(comprehensive_seen_ids))
        if where_clauses:
            query_base += " WHERE " + " AND ".join(where_clauses)
        query = query_base + " ORDER BY a.mean_score DESC NULLS LAST LIMIT 500"
        cursor.execute(query, tuple(params))
        candidates = cursor.fetchall()
        scored_anime = []
        for anime in candidates:
            score = 0
            if anime.get('positive_keywords'):
                for keyword in anime.get('positive_keywords', '').split(', '):
                    if keyword: score += taste_profile.get(keyword, 0)
            if anime.get('negative_keywords'):
                for keyword in anime.get('negative_keywords', '').split(', '):
                    if keyword: score -= taste_profile.get(keyword, 0)
            if anime.get('mean_score') and anime['mean_score'] > 8.0: score *= 1.2
            scored_anime.append({'anime': anime, 'score': score})
        sorted_recommendations = sorted(scored_anime, key=lambda x: x['score'], reverse=True)
        positive_recommendations = [rec for rec in sorted_recommendations if rec['score'] > 0]
        final_recommendations = []
        recommendation_type = "personalized"
        if positive_recommendations:
            final_recommendations = positive_recommendations[:15]
        else:
            recommendation_type = "fallback"
            fallback_query_base = "WITH genre_agg AS (SELECT ag.anime_id, STRING_AGG(g.name, ', ') as anime_genres FROM anime_genres ag JOIN genres g ON ag.genre_id = g.genre_id GROUP BY ag.anime_id) SELECT a.*, ga.anime_genres FROM animes a LEFT JOIN genre_agg ga ON a.anime_id = ga.anime_id"
            fallback_params = []
            fallback_where = ["a.promo_link IS NOT NULL AND a.promo_link != ''"]
            if not allow_explicit:
                fallback_where.append(f"a.anime_id NOT IN (SELECT ag.anime_id FROM anime_genres ag JOIN genres g ON ag.genre_id = g.genre_id WHERE g.name IN ({EXPLICIT_GENRES}))")
            if comprehensive_seen_ids:
                id_placeholders = ','.join(['%s'] * len(comprehensive_seen_ids))
                fallback_where.append(f"a.anime_id NOT IN ({id_placeholders})")
                fallback_params.extend(list(comprehensive_seen_ids))
            if fallback_where:
                fallback_query_base += " WHERE " + " AND ".join(fallback_where)
            fallback_query = fallback_query_base + " ORDER BY a.overal_rank ASC NULLS LAST LIMIT 15"
            cursor.execute(fallback_query, tuple(fallback_params))
            fallback_candidates = cursor.fetchall()
            for anime in fallback_candidates:
                final_recommendations.append({'anime': anime, 'score': 0})
        response_data = []
        for item in final_recommendations:
            anime = item['anime']
            cursor.execute("SELECT username, sentiment_polarity, review_text FROM reviews WHERE anime_id = %s ORDER BY RANDOM() LIMIT 3", (anime['anime_id'],))
            reviews = cursor.fetchall()
            comments = [{"user": r['username'], "text": r['review_text'][:200] + '...' if r['review_text'] and len(r['review_text']) > 200 else r.get('review_text', ''), "type": "positive" if r['sentiment_polarity'] > 0.1 else "negative"} for r in reviews]
            response_data.append({"id": anime['anime_id'], "title": anime['title'], "trailerId": get_youtube_id_from_url(anime.get('promo_link')), "score": anime.get('mean_score'), "rank": anime.get('overal_rank'), "genres": anime.get('anime_genres'), "positive_keywords": anime.get('positive_keywords'), "negative_keywords": anime.get('negative_keywords'), "comments": comments, "initial_score": item['score'], "title_english": anime.get('title_english')})
        return jsonify({"user_id": user_id, "recommendations": response_data, "recommendation_type": recommendation_type, "taste_profile": taste_profile })
    except Exception as e:
        print(f"An error occurred in /api/generate_reel: {e}")
        return jsonify({"error": "An internal error occurred"}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()

@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    # ... (function is unchanged from the last working version) ...
    data = request.get_json()
    user_id = data.get('user_id')
    anime_id = data.get('animeId')
    reason = data.get('reason')
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database connection failed"}), 500
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        taste_profile = Counter(json.loads(result['taste_profile'])) if result and result.get('taste_profile') else Counter()
        cursor.execute("SELECT positive_keywords, negative_keywords FROM animes WHERE anime_id = %s", (anime_id,))
        anime_keywords = cursor.fetchone()
        if anime_keywords:
            if reason == 'like_button': modifier = 1
            elif reason == 'not_interested_button': modifier = -2
            elif reason == 'save_to_watchlist': modifier = 0.5
            else: modifier = 0
            if modifier != 0:
                if anime_keywords.get('positive_keywords'):
                    for keyword in anime_keywords['positive_keywords'].split(', '):
                        if keyword: taste_profile[keyword] += modifier
                if anime_keywords.get('negative_keywords'):
                    for keyword in anime_keywords['negative_keywords'].split(', '):
                        if keyword: taste_profile[keyword] -= modifier
        cursor.execute("""
            INSERT INTO user_taste_profiles (user_id, taste_profile) VALUES (%s, %s::jsonb)
            ON CONFLICT (user_id) DO UPDATE SET taste_profile = EXCLUDED.taste_profile;
            """, (user_id, json.dumps(dict(taste_profile))) )
        connection.commit()
        return jsonify({"status": "success", "taste_profile": dict(taste_profile)}), 200
    except psycopg2.Error as err:
        print(f"Database error while logging feedback: {err}")
        return jsonify({"error": "Database error"}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()
            
@app.route('/api/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    # ... (function is unchanged from the last working version) ...
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database connection failed"}), 500
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM user_taste_profiles WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        connection.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"An error occurred during user deletion: {e}")
        return jsonify({"error": "An internal error occurred"}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
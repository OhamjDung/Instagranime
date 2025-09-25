import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# --- 1. SETUP ---
load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- 2. MODEL & ASSET LOADING ---
try:
    print("Loading model and data assets...")
    model = joblib.load('best_model.pkl')
    anime_df = pd.read_pickle('anime_dataframe.pkl')
    feature_matrix = np.load('anime_feature_matrix.npy')
    id_to_index = pd.Series(anime_df.index, index=anime_df['anime_id']).to_dict()
    ALL_GENRES = anime_df['genre_list'].explode().dropna().unique().tolist()
    EXPLICIT_GENRES_SET = {'Ecchi', 'Erotica', 'Hentai'}
    print("✅ Model and core assets loaded successfully.")
    ASSETS_LOADED = True
except FileNotFoundError as e:
    print(f"❌ CRITICAL ERROR: A required asset file was not found: {e.filename}.")
    ASSETS_LOADED = False
except Exception as e:
    print(f"❌ An error occurred while loading assets: {e}")
    ASSETS_LOADED = False

# --- 3. DATABASE CONNECTION & HELPERS ---
def get_db_connection():
    try:
        ssl_mode = os.getenv('DB_SSLMODE', 'require')
        dsn = (f"dbname='{os.getenv('DB_NAME')}' user='{os.getenv('DB_USER')}' "
               f"password='{os.getenv('DB_PASSWORD')}' host='{os.getenv('DB_HOST')}' "
               f"port='{os.getenv('DB_PORT')}' sslmode='{ssl_mode}'")
        return psycopg2.connect(dsn)
    except psycopg2.OperationalError as err:
        print(f"Error connecting to database: {err}")
        return None

def get_or_create_user(cursor, username):
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    if result:
        return result['user_id']
    else:
        cursor.execute("INSERT INTO users (username) VALUES (%s) RETURNING user_id", (username,))
        return cursor.fetchone()['user_id']

def get_youtube_id_from_url(url):
    if not isinstance(url, str): return None
    match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

# --- 4. FLASK API ENDPOINTS ---
# ... (rest of the imports and setup code)

# --- 4. FLASK API ENDPOINTS ---

@app.route('/api/suggest', methods=['POST'])
def suggest_anime():
    """
    Receives a list of liked anime titles and returns the top 3 most similar anime
    based on cosine similarity of their feature vectors.
    """
    # Ensure the model and data assets are loaded before proceeding.
    if not ASSETS_LOADED:
        return jsonify({"error": "API assets are not loaded."}), 503

    data = request.get_json()
    if not data or 'liked_animes' not in data:
        return jsonify({"error": "Invalid request: 'liked_animes' key is missing."}), 400

    liked_anime_titles = data['liked_animes']
    if not liked_anime_titles:
        return jsonify({"suggestions": []}) # Return empty if the input list is empty

    try:
        # --- 1. Convert liked anime titles to their corresponding IDs ---
        title_map = get_title_to_id_map(liked_anime_titles)
        liked_anime_ids = [title_map.get(t) for t in liked_anime_titles if t in title_map]
        
        # --- 2. Get the feature vectors for the liked anime ---
        liked_indices = [id_to_index[anime_id] for anime_id in liked_anime_ids if anime_id in id_to_index]
        if not liked_indices:
            return jsonify({"suggestions": []}) # No matching anime found in our data
            
        # Create an average vector representing the user's taste profile
        user_taste_vector = np.mean([feature_matrix[i] for i in liked_indices], axis=0).reshape(1, -1)
        
        # --- 3. Calculate similarity between the user's taste and all other anime ---
        similarity_scores = cosine_similarity(user_taste_vector, feature_matrix)[0]
        
        # --- 4. Rank anime and get the top suggestions ---
        # Pair each anime index with its similarity score
        scored_indices = list(enumerate(similarity_scores))
        
        # Sort by score in descending order
        sorted_scored_indices = sorted(scored_indices, key=lambda x: x[1], reverse=True)
        
        # --- 5. Filter and format the results ---
        suggestions = []
        # Create a set of liked titles for efficient lookup
        liked_titles_set = set(liked_anime_titles)
        
        for index, score in sorted_scored_indices:
            # Stop when we have 3 suggestions
            if len(suggestions) >= 3:
                break
            
            anime_info = anime_df.iloc[index]
            suggestion_title = anime_info.get('title_english') or anime_info.get('title')
            
            # Ensure the suggestion is not an anime the user has already liked
            if suggestion_title not in liked_titles_set:
                suggestions.append(suggestion_title)

        return jsonify({"suggestions": suggestions})

    except Exception as e:
        print(f"❌ Error in /api/suggest: {e}")
        return jsonify({"error": "An internal error occurred while generating suggestions."}), 500

@app.route('/api/status', methods=['GET'])
def status_check():
    """
    A simple endpoint to check if the API is online.
    """
    if ASSETS_LOADED:
        return jsonify({"status": "online", "message": "API is ready."}), 200
    else:
        return jsonify({"status": "error", "message": "API assets are not loaded."}), 503

@app.route('/api/search_genres', methods=['GET'])
def search_genres():
    query = request.args.get('q', '').lower()
    if not ASSETS_LOADED or len(query) < 1: return jsonify([])
    results = [genre for genre in ALL_GENRES if query in genre.lower() and genre not in EXPLICIT_GENRES_SET]
    return jsonify(results[:5])

@app.route('/api/search_anime', methods=['GET'])
def search_anime():
    query = request.args.get('q', '')
    if len(query) < 2: return jsonify([])
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database connection failed"}), 500
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        search_term = f"%{query}%"
        cursor.execute("SELECT title, title_english FROM animes WHERE (title ILIKE %s OR title_english ILIKE %s) LIMIT 10", (search_term, search_term))
        results = []
        seen_titles = set()
        for row in cursor.fetchall():
            display_title = row['title_english'] if row['title_english'] else row['title']
            if display_title and display_title not in seen_titles:
                results.append(display_title)
                seen_titles.add(display_title)
            if len(results) >= 5: break
        return jsonify(results)
    finally:
        if connection: cursor.close(); connection.close()

@app.route('/api/generate_reel', methods=['POST'])
# UPDATED: generate_reel function with robust filtering.
@app.route('/api/generate_reel', methods=['POST'])
def generate_reel():
    if not ASSETS_LOADED: return jsonify({"error": "Model not available."}), 503
    data = request.get_json()
    username, user_id, liked_anime_titles, allow_explicit, genres_filter = data.get('username'), data.get('user_id'), data.get('liked_anime', []), data.get('allow_explicit', False), data.get('genres', [])
    
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database connection failed"}), 500
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            is_new_user_session = 'username' in data
            if not user_id:
                user_id = get_or_create_user(cursor, username)
                connection.commit()
            cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
            res = cursor.fetchone()
            if res and res['taste_profile']:
                user_profile = res['taste_profile']
                liked_anime_ids = user_profile.get('liked_ids', [])
            else:
                title_map = get_title_to_id_map(liked_anime_titles)
                liked_anime_ids = [title_map.get(t) for t in liked_anime_titles if t in title_map]
                user_profile = {'liked_ids': liked_anime_ids, 'disliked_ids': [], 'scrolled_past_ids': []}
                cursor.execute("INSERT INTO user_taste_profiles (user_id, taste_profile, last_updated) VALUES (%s, %s, NOW()) ON CONFLICT (user_id) DO UPDATE SET taste_profile = EXCLUDED.taste_profile, last_updated = NOW()", (user_id, json.dumps(user_profile)))
                connection.commit()

        seen_from_client = {int(i) for i in data.get('seen_anime_ids', [])}
        liked_from_db = {int(i) for i in user_profile.get('liked_ids', [])}
        disliked_from_db = {int(i) for i in user_profile.get('disliked_ids', [])}
        scrolled_from_db = {int(i) for i in user_profile.get('scrolled_past_ids', [])}
        
        # FIX: Create a single, definitive exclusion set from all sources.
        final_exclusion_set = seen_from_client | liked_from_db | disliked_from_db | scrolled_from_db
        
        if not liked_anime_ids:
            ranked_recs = get_fallback_recommendations(final_exclusion_set, allow_explicit, genres_filter)
            recommendation_type = "fallback_cold_start"
        else:
            liked_indices = [id_to_index[i] for i in liked_anime_ids if i in id_to_index]
            if not liked_indices:
                ranked_recs = get_fallback_recommendations(final_exclusion_set, allow_explicit, genres_filter)
                recommendation_type = "fallback_no_match"
            else:
                user_profile_vector, top_genres, studio_prefs = build_user_profile_from_indices(liked_indices)
                df_pool = anime_df[anime_df['promo_link'].notna() & (anime_df['promo_link'] != '')]
                if not allow_explicit:
                    is_explicit = df_pool['genre_list'].apply(lambda genres: isinstance(genres, list) and not EXPLICIT_GENRES_SET.isdisjoint(genres))
                    df_pool = df_pool[~is_explicit]
                if genres_filter:
                    required_genres = set(genres_filter)
                    df_pool = df_pool[df_pool['genre_list'].apply(lambda g_list: isinstance(g_list, list) and required_genres.issubset(set(g_list)))]

                all_possible_ids = set(df_pool['anime_id'])
                
                # FIX: Explicitly and consistently filter the candidate pool before scoring.
                candidate_ids = list(all_possible_ids - final_exclusion_set)
                
                ranked_recs = predict_scores_for_candidates(candidate_ids, user_profile_vector, top_genres, studio_prefs, limit=15)
                if is_new_user_session and liked_indices:
                    initial_taste_vector = np.mean([feature_matrix[i] for i in liked_indices], axis=0).reshape(1, -1)
                    boosted_recs = []
                    for rec in ranked_recs:
                        rec_id = rec['anime']['anime_id']
                        if rec_id in id_to_index:
                            rec_vector = feature_matrix[id_to_index[rec_id]].reshape(1, -1)
                            similarity = cosine_similarity(initial_taste_vector, rec_vector)[0][0]
                            boost = similarity * 5.0
                            rec['score'] += boost
                            boosted_recs.append(rec)
                    ranked_recs = sorted(boosted_recs, key=lambda x: x['score'], reverse=True)
                recommendation_type = "personalized_model"
        
        final_response = format_response_with_reviews(ranked_recs)
        return jsonify({"user_id": user_id, "recommendations": final_response, "recommendation_type": recommendation_type})
    except Exception as e:
        print(f"Error in generate_reel: {e}")
        return jsonify({"error": "Internal error occurred"}), 500
    finally:
        if connection and not connection.closed: connection.close()

@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    data = request.get_json()
    user_id, anime_id, reason = data.get('user_id'), data.get('animeId'), data.get('reason')
    if not all([user_id, anime_id, reason]): return jsonify({"error": "Missing data"}), 400
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database down"}), 500
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            affected_ids = get_related_anime_ids(cursor, anime_id)
            cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
            res = cursor.fetchone()
            profile = res['taste_profile'] if res and res['taste_profile'] else {}
            liked_ids = profile.get('liked_ids', [])
            disliked_ids = set(profile.get('disliked_ids', []))
            scrolled_past_ids = set(profile.get('scrolled_past_ids', []))
            liked_ids = [i for i in liked_ids if i not in affected_ids]
            disliked_ids.difference_update(affected_ids)
            scrolled_past_ids.difference_update(affected_ids)
            if reason in ('like_button', 'save_to_watchlist', 'watched_10_seconds'):
                liked_ids.extend(affected_ids)
            elif reason == 'super_like_button':
                liked_ids.extend(affected_ids * 3)
            elif reason == 'not_interested_button':
                disliked_ids.update(affected_ids)
            elif reason == 'scrolled_past':
                if not(set(liked_ids).intersection(affected_ids) or disliked_ids.intersection(affected_ids)):
                    scrolled_past_ids.update(affected_ids)
            updated_profile = {'liked_ids': liked_ids, 'disliked_ids': list(disliked_ids), 'scrolled_past_ids': list(scrolled_past_ids)}
            cursor.execute("INSERT INTO user_taste_profiles (user_id, taste_profile, last_updated) VALUES (%s, %s, NOW()) ON CONFLICT (user_id) DO UPDATE SET taste_profile = EXCLUDED.taste_profile, last_updated = NOW()", (user_id, json.dumps(updated_profile)))
            connection.commit()
        return jsonify({"status": "success", "profile": updated_profile, "affected_ids": list(affected_ids)}), 200
    except Exception as e:
        print(f"Error in feedback: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        if connection: connection.close()

@app.route('/api/rescore', methods=['POST'])
def rescore_recommendations():
    if not ASSETS_LOADED: return jsonify({"error": "Model not available"}), 503
    data = request.get_json()
    user_id, anime_ids = data.get('user_id'), [int(i) for i in data.get('anime_ids', [])]
    if not all([user_id, anime_ids]): return jsonify({"error": "Missing data"}), 400
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database down"}), 500
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
            res = cursor.fetchone()
        if not res or not res['taste_profile']: return jsonify({})
        profile = res['taste_profile']
        liked_anime_ids = profile.get('liked_ids', [])
        if not liked_anime_ids: return jsonify({})
        liked_indices = [id_to_index[i] for i in liked_anime_ids if i in id_to_index]
        if not liked_indices: return jsonify({})
        user_profile_vector, top_genres, studio_prefs = build_user_profile_from_indices(liked_indices)
        ranked_recs = predict_scores_for_candidates(anime_ids, user_profile_vector, top_genres, studio_prefs)
        new_scores = {str(rec['anime']['anime_id']): rec['score'] for rec in ranked_recs}
        return jsonify(new_scores)
    except Exception as e:
        print(f"Error in rescore: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        if connection: connection.close()

@app.route('/api/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    connection = get_db_connection()
    if not connection: return jsonify({"error": "Database connection failed"}), 500
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM user_taste_profiles WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        connection.commit()
        return jsonify({"status": "success"}), 200
    finally:
        if connection: cursor.close(); connection.close()

def get_related_anime_ids(cursor, anime_id):
    cursor.execute("SELECT title, title_english FROM animes WHERE anime_id = %s", (anime_id,))
    title_row = cursor.fetchone()
    if not title_row: return [anime_id]
    base_title = (title_row['title_english'] or title_row['title']).split(':')[0].split(' Season')[0].strip()
    cursor.execute("SELECT anime_id FROM animes WHERE title ILIKE %s OR title_english ILIKE %s", (f"{base_title}%", f"{base_title}%"))
    return [row['anime_id'] for row in cursor.fetchall()]

def build_user_profile_from_indices(liked_indices):
    user_profile_vector = np.mean([feature_matrix[i] for i in liked_indices], axis=0)
    user_rated_df = anime_df.iloc[liked_indices]
    top_genres = pd.Series([g for sublist in user_rated_df['genre_list'] if isinstance(sublist, list) for g in sublist]).value_counts().nlargest(5).index.tolist()
    studio_prefs = user_rated_df.groupby('studio').size() / len(user_rated_df)
    return user_profile_vector, top_genres, studio_prefs

def predict_scores_for_candidates(candidate_ids, user_profile_vector, top_genres, studio_prefs, limit=None):
    pred_features, valid_ids = [], []
    for anime_id in candidate_ids:
        if anime_id in id_to_index:
            idx, info = id_to_index[anime_id], anime_df.iloc[id_to_index[anime_id]]
            vector = feature_matrix[idx]
            genres = info['genre_list'] if isinstance(info['genre_list'], list) else []
            g_match = sum(1 for g in genres if g in top_genres) / 5.0 if top_genres else 0
            s_pref = studio_prefs.get(info['studio'], 0)
            i_features = np.array([g_match, s_pref])
            combined = np.concatenate([user_profile_vector, vector, i_features])
            pred_features.append(combined)
            valid_ids.append(anime_id)
    if not pred_features: return []
    scores = model.predict(np.array(pred_features))
    recs_with_scores = sorted(zip(valid_ids, scores), key=lambda x: x[1], reverse=True)
    if limit:
        recs_with_scores = recs_with_scores[:limit]
    return [{'anime': anime_df.iloc[id_to_index[anime_id]].to_dict(), 'score': score} for anime_id, score in recs_with_scores]

def format_response_with_reviews(recommendations):
    if not recommendations: return []
    anime_ids = [rec['anime']['anime_id'] for rec in recommendations]
    reviews_map = {}
    connection = get_db_connection()
    if connection:
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT anime_id, review_text, sentiment_polarity FROM reviews WHERE anime_id = ANY(%s)", (anime_ids,))
                for row in cursor.fetchall():
                    if row['anime_id'] not in reviews_map: reviews_map[row['anime_id']] = []
                    reviews_map[row['anime_id']].append(row)
        except Exception as e: print(f"Error fetching reviews: {e}")
        finally:
            if connection: connection.close()
    final_response = []
    for rec in recommendations:
        anime, anime_id = rec['anime'], rec['anime']['anime_id']
        reviews = reviews_map.get(anime_id, [])
        comments = [{"user": "User", "text": r['review_text'], "type": "positive" if r['sentiment_polarity'] > 0.1 else "negative"} for r in reviews[:2]]
        genre_list = anime.get('genre_list', [])
        if not isinstance(genre_list, list): genre_list = []
        final_response.append({
            "id": anime_id, "title": anime.get('title_english') or anime.get('title'),
            "trailerId": get_youtube_id_from_url(anime.get('promo_link')),
            "score": anime.get('mean_score'), "rank": anime.get('overal_rank'),
            "genres": ', '.join(genre_list), "comments": comments, 
            "initial_score": rec['score'], "positive_keywords": anime.get('positive_keywords'),
            "negative_keywords": anime.get('negative_keywords'), "synopsis": anime.get('synopsis')
        })
    return final_response

def get_title_to_id_map(titles):
    if not titles: return {}
    mask = anime_df['title'].isin(titles) | anime_df['title_english'].isin(titles)
    df_slice = anime_df.loc[mask]
    mapping = {}
    if not df_slice.empty:
        map1 = pd.Series(df_slice.anime_id.values, index=df_slice.title).to_dict()
        map2 = pd.Series(df_slice.anime_id.values, index=df_slice.title_english).dropna().to_dict()
        mapping.update(map1)
        mapping.update(map2)
    return mapping

def get_fallback_recommendations(seen_ids, allow_explicit=False, genres_filter=None):
    df_pool = anime_df[anime_df['promo_link'].notna() & (anime_df['promo_link'] != '')]
    if not allow_explicit:
        is_explicit = df_pool['genre_list'].apply(lambda genres: isinstance(genres, list) and not EXPLICIT_GENRES_SET.isdisjoint(genres))
        df_pool = df_pool[~is_explicit]
    if genres_filter:
        required_genres = set(genres_filter)
        df_pool = df_pool[df_pool['genre_list'].apply(lambda g_list: isinstance(g_list, list) and required_genres.issubset(set(g_list)))]
    fallback_df = df_pool[~df_pool['anime_id'].isin(seen_ids)]
    fallback_df = fallback_df.sort_values('overal_rank', ascending=True).head(15)
    recs = []
    for _, row in fallback_df.iterrows():
        score = row.get('mean_score', 0) if pd.notna(row.get('mean_score')) else 0
        recs.append({'anime': row.to_dict(), 'score': score})
    return recs

if __name__ == '__main__':
    app.run(debug=True, port=5000)
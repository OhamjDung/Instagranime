import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import random
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

# --- 1. SETUP & DATABASE CONNECTION ---
load_dotenv()
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        ssl_mode = os.getenv('DB_SSLMODE', 'require')
        dsn = (f"dbname='{os.getenv('DB_NAME')}' user='{os.getenv('DB_USER')}' password='{os.getenv('DB_PASSWORD')}' host='{os.getenv('DB_HOST')}' port='{os.getenv('DB_PORT')}' sslmode='{ssl_mode}'")
        connection = psycopg2.connect(dsn)
        print("Database connection successful.")
        return connection
    except psycopg2.OperationalError as err:
        print(f"Error connecting to database: {err}")
        return None

# --- 2. DATA LOADING FUNCTIONS ---
def load_anime_features():
    """Loads the pre-computed feature matrix and anime ID mapping."""
    print("Loading pre-computed anime features...")
    try:
        feature_matrix = np.load('anime_feature_matrix.npy')
        anime_ids_df = pd.read_json('anime_ids.json', typ='series')
        
        # Create a mapping from anime_id to its row index in the matrix for fast lookups
        id_to_index = pd.Series(anime_ids_df.index, index=anime_ids_df.values)
        
        print(f"Loaded feature matrix with shape: {feature_matrix.shape}")
        return feature_matrix, id_to_index
    except FileNotFoundError:
        print("ERROR: Feature files not found. Please run 'feature_engineering.py' first.")
        return None, None

def get_user_watchlists(cursor):
    """Fetches user watchlists with ranks to use as our 'ground truth' for testing."""
    print("Loading user watchlists from database...")
    # We now fetch the user_rank to use for weighted profiling
    query = "SELECT user_id, anime_id, user_rank FROM user_watchlists WHERE user_rank <= 50"
    
    cursor.execute(query)
    
    user_data = {}
    for user_id, anime_id, user_rank in cursor.fetchall():
        if user_id not in user_data:
            user_data[user_id] = []
        user_data[user_id].append({'anime_id': anime_id, 'rank': user_rank})
    print(f"Loaded watchlists for {len(user_data)} users.")
    return user_data

# --- 3. MODEL & EVALUATION LOGIC ---

def build_user_profile_weighted(training_items, feature_matrix, id_to_index):
    """
    Creates a user's taste profile using a weighted average of their liked anime,
    giving more importance to higher-ranked items.
    """
    weighted_vectors = []
    total_weight = 0
    
    for item in training_items:
        anime_id = item['anime_id']
        rank = item['rank']
        
        if anime_id in id_to_index:
            # Weighting function: higher rank (lower number) gets much more weight.
            # We use log to make the drop-off less extreme.
            weight = 1.0 / np.log(rank + 1.1) # Add 1.1 to avoid log(1)=0 and log of numbers < 1
            
            idx = id_to_index[anime_id]
            weighted_vectors.append(feature_matrix[idx] * weight)
            total_weight += weight
            
    if not weighted_vectors or total_weight == 0:
        return None
        
    # The final profile is the sum of weighted vectors divided by the sum of weights
    profile_vector = np.sum(weighted_vectors, axis=0) / total_weight
    return profile_vector

def generate_recommendations(user_profile, feature_matrix, id_to_index, seen_anime_ids, num_recs=100):
    """Generates recommendations by finding the most similar anime vectors."""
    user_profile = user_profile.reshape(1, -1)
    sim_scores = cosine_similarity(user_profile, feature_matrix)[0]
    
    scored_anime = []
    for anime_id, index in id_to_index.items():
        if anime_id not in seen_anime_ids:
            scored_anime.append((anime_id, sim_scores[index]))
            
    scored_anime.sort(key=lambda x: x[1], reverse=True)
    return [anime_id for anime_id, score in scored_anime[:num_recs]]

def calculate_precision_at_k(recommended_items, hold_out_items, k):
    """Calculates Precision@k."""
    top_k_recs = set(recommended_items[:k])
    hold_out_set = set(hold_out_items)
    hits = len(top_k_recs.intersection(hold_out_set))
    return hits / k

# --- 4. MAIN EXECUTION ---

def main():
    K = 20
    
    feature_matrix, id_to_index = load_anime_features()
    if feature_matrix is None: return

    connection = get_db_connection()
    if not connection: return
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        all_users_data = get_user_watchlists(cursor)
        total_precision = 0
        evaluated_users = 0

        print(f"\nStarting evaluation loop for {len(all_users_data)} users...")
        for user_id, liked_anime in tqdm(all_users_data.items()):
            if len(liked_anime) < 4: continue

            random.shuffle(liked_anime)
            split_index = int(0.75 * len(liked_anime))
            training_set_items = liked_anime[:split_index]
            hold_out_set_ids = [item['anime_id'] for item in liked_anime[split_index:]]

            # --- MODIFIED: Use the new weighted profile function ---
            user_profile_vector = build_user_profile_weighted(training_set_items, feature_matrix, id_to_index)

            if user_profile_vector is None: continue

            seen_ids = {item['anime_id'] for item in training_set_items}
            recommendations = generate_recommendations(user_profile_vector, feature_matrix, id_to_index, seen_ids, num_recs=K)
            precision = calculate_precision_at_k(recommendations, hold_out_set_ids, K)
            
            total_precision += precision
            evaluated_users += 1

        print("\n--- EVALUATION COMPLETE ---")
        if evaluated_users > 0:
            average_precision = total_precision / evaluated_users
            print(f"Total Users Evaluated: {evaluated_users}")
            print(f"Average Precision@{K}: {average_precision:.4f} (or {average_precision:.2%})")
            print(f"\nInterpretation: On average, {average_precision:.2%} of the top {K} recommendations were correct.")
        else:
            print("No users with enough data to evaluate.")

    finally:
        if connection and not connection.closed:
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()


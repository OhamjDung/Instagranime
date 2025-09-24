import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import random
import joblib
from tqdm import tqdm

# --- 1. SETUP & DATABASE CONNECTION ---
load_dotenv()
def get_db_connection():
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
def load_evaluation_assets():
    """Loads the pre-trained model and necessary feature data."""
    print("Loading all pre-computed evaluation assets...")
    try:
        # --- MODIFIED: Load the trained model directly ---
        model = joblib.load('random_forest_model.pkl')
        
        feature_matrix = np.load('anime_feature_matrix.npy')
        anime_ids_df = pd.read_json('anime_ids.json', typ='series')
        id_to_index = pd.Series(anime_ids_df.index, index=anime_ids_df.values)
        print("All assets loaded successfully.")
        return model, feature_matrix, id_to_index
    except FileNotFoundError as e:
        print(f"ERROR: A required file was not found: {e.filename}")
        print("Please ensure 'random_forest_model.pkl' and other feature files exist.")
        return None, None, None

def get_user_watchlists_for_test(cursor):
    """Fetches user watchlists to use for the final hold-out test."""
    print("Loading user watchlists for final test...")
    query = "SELECT user_id, anime_id FROM user_watchlists WHERE user_rank <= 50"
    cursor.execute(query)
    user_data = {}
    for user_id, anime_id in cursor.fetchall():
        if user_id not in user_data: user_data[user_id] = []
        user_data[user_id].append(anime_id)
    print(f"Loaded test watchlists for {len(user_data)} users.")
    return user_data

# --- 3. MODEL & EVALUATION LOGIC ---
def calculate_precision_at_k(recommended_items, hold_out_items, k):
    """Calculates Precision@k."""
    top_k_recs = set(recommended_items[:k])
    hold_out_set = set(hold_out_items)
    hits = len(top_k_recs.intersection(hold_out_set))
    return hits / k

# --- 4. MAIN EXECUTION ---
def main():
    K = 20  # We will measure Precision@20
    
    # --- MODIFIED: Load the pre-trained model instead of training a new one ---
    rf_regressor, anime_feature_matrix, id_to_index = load_evaluation_assets()
    if rf_regressor is None: return

    # --- REMOVED: Stage 1 (training and RMSE calculation) is no longer needed here ---

    # --- MODIFIED: This is now the main part of the script ---
    print("\n--- Starting Recommendation Ranking Evaluation (Precision@20) ---")
    connection = get_db_connection()
    if not connection: return
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        test_users = get_user_watchlists_for_test(cursor)
        total_precision = 0
        evaluated_users = 0

        print(f"\nStarting ranking evaluation on a sample of {len(test_users)} users...")
        for user_id, liked_anime in tqdm(test_users.items()):
            if len(liked_anime) < 4: continue

            random.shuffle(liked_anime)
            split_index = int(0.75 * len(liked_anime))
            training_set_ids = liked_anime[:split_index]
            hold_out_set_ids = set(liked_anime[split_index:])

            # Build this user's profile from their "training" items
            liked_vectors = [anime_feature_matrix[id_to_index[anime_id]] for anime_id in training_set_ids if anime_id in id_to_index]
            if not liked_vectors: continue
            user_profile_vector = np.mean(liked_vectors, axis=0)

            # Generate recommendations
            unseen_anime_ids = list(set(id_to_index.index) - set(training_set_ids))
            
            prediction_data = []
            for anime_id in unseen_anime_ids:
                anime_vector = anime_feature_matrix[id_to_index[anime_id]]
                combined_vector = np.concatenate([user_profile_vector, anime_vector])
                prediction_data.append(combined_vector)
            
            # Use the loaded model to predict scores
            predicted_scores = rf_regressor.predict(np.array(prediction_data))
            
            recommendations_with_scores = sorted(zip(unseen_anime_ids, predicted_scores), key=lambda x: x[1], reverse=True)
            ranked_recommendations = [anime_id for anime_id, score in recommendations_with_scores]

            # Calculate Precision@K
            precision = calculate_precision_at_k(ranked_recommendations, hold_out_set_ids, K)
            total_precision += precision
            evaluated_users += 1

        print("\n--- EVALUATION COMPLETE ---")
        if evaluated_users > 0:
            average_precision = total_precision / evaluated_users
            print(f"Total Users Evaluated for Ranking: {evaluated_users}")
            print(f"Average Precision@{K}: {average_precision:.4f} (or {average_precision:.2%})")
            print(f"Interpretation: On average, {average_precision:.2%} of the top {K} recommendations were correct.")
        else:
            print("No users with enough data to evaluate ranking.")

    finally:
        if connection and not connection.closed:
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()


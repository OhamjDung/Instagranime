import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import random
from tqdm import tqdm

# --- 1. SETUP & DATABASE CONNECTION ---
load_dotenv()

def get_db_connection():
    # ... (This function is the same as in your other scripts)
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
    print("Loading pre-computed anime features...")
    try:
        feature_matrix = np.load('anime_feature_matrix.npy')
        anime_ids_df = pd.read_json('anime_ids.json', typ='series')
        id_to_index = pd.Series(anime_ids_df.index, index=anime_ids_df.values)
        return feature_matrix, id_to_index
    except FileNotFoundError:
        print("ERROR: Feature files not found. Please run 'feature_engineering.py' first.")
        return None, None

def get_all_user_watchlists(cursor):
    print("Loading all user watchlists...")
    query = "SELECT user_id, anime_id, user_rank FROM user_watchlists"
    cursor.execute(query)
    user_data = {}
    for user_id, anime_id, user_rank in cursor.fetchall():
        if user_id not in user_data:
            user_data[user_id] = []
        user_data[user_id].append({'anime_id': anime_id, 'rank': user_rank})
    print(f"Loaded watchlists for {len(user_data)} users.")
    return user_data

# --- 3. MAIN SCRIPT ---
if __name__ == "__main__":
    feature_matrix, id_to_index = load_anime_features()
    if feature_matrix is None:
        exit()

    connection = get_db_connection()
    if not connection:
        exit()
    
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    all_users_data = get_all_user_watchlists(cursor)
    all_anime_ids = set(id_to_index.index)
    
    X_data = []  # To store our feature vectors
    y_data = []  # To store our labels (ranks)

    print("\nBuilding training dataset with positive and negative samples...")
    for user_id, watchlist in tqdm(all_users_data.items()):
        
        # Build this user's profile vector (average of their liked anime)
        liked_vectors = [feature_matrix[id_to_index[item['anime_id']]] for item in watchlist if item['anime_id'] in id_to_index]
        if not liked_vectors:
            continue
        user_profile_vector = np.mean(liked_vectors, axis=0)

        seen_anime = {item['anime_id'] for item in watchlist}
        
        # 1. Add Positive Samples
        for item in watchlist:
            anime_id = item['anime_id']
            if anime_id in id_to_index:
                anime_vector = feature_matrix[id_to_index[anime_id]]
                # Combine user profile and anime features into one vector
                combined_vector = np.concatenate([user_profile_vector, anime_vector])
                X_data.append(combined_vector)
                
                # The target is the inverse rank (higher rank = higher score)
                # We add a small constant to avoid division by zero
                y_data.append(1 / (item['rank'] + 0.1))

        # 2. Add Negative Samples
        num_positive_samples = len(watchlist)
        potential_negative_anime = list(all_anime_ids - seen_anime)
        
        if not potential_negative_anime:
            continue
            
        # For each positive sample, create one negative sample
        negative_samples = random.sample(potential_negative_anime, min(num_positive_samples, len(potential_negative_anime)))
        
        for anime_id in negative_samples:
            anime_vector = feature_matrix[id_to_index[anime_id]]
            combined_vector = np.concatenate([user_profile_vector, anime_vector])
            X_data.append(combined_vector)
            y_data.append(0.0) # Label for an unseen anime is 0
            
    connection.close()
    
    # Convert lists to NumPy arrays
    X_train = np.array(X_data)
    y_train = np.array(y_data)

    # Save the final dataset to files
    np.save('training_features.npy', X_train)
    np.save('training_labels.npy', y_train)

    print("\n--- Training Data Creation Complete! ---")
    print(f"Feature matrix (X) shape: {X_train.shape}")
    print(f"Label vector (y) shape: {y_train.shape}")
    print("Saved data to 'training_features.npy' and 'training_labels.npy'")

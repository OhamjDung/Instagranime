import os
import mysql.connector
from dotenv import load_dotenv
import argparse
import json
from collections import Counter
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# --- 1. SETUP ---
load_dotenv()


# --- 2. DATABASE CONNECTION ---
def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            connection_timeout=15
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# --- 3. CORE RECOMMENDATION LOGIC ---

def calculate_derived_rating(rank):
    """Converts a user's rank into a weighted score."""
    if rank is None or rank == 0:
        return 0
    return (1 / rank) * 10

def get_or_create_user_taste_profile(cursor, user_id):
    """
    Fetches a user's taste profile from the DB. If it doesn't exist,
    it calculates it, saves it, and then returns it.
    """
    cursor.execute("SELECT taste_profile FROM user_taste_profiles WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    
    if result:
        print(f"Found existing taste profile for user {user_id}.")
        return json.loads(result[0])

    print(f"No profile found for user {user_id}. Calculating a new one...")
    
    # Fetch user's ranked anime
    # IMPORTANT: This assumes you have a table with user rankings.
    # We will use 'user_watchlists' and its 'user_rank' column as an example.
    cursor.execute("""
        SELECT uw.anime_id, uw.user_rank, a.positive_keywords, a.negative_keywords
        FROM user_watchlists uw
        JOIN animes a ON uw.anime_id = a.anime_id
        WHERE uw.user_id = %s AND uw.user_rank IS NOT NULL
    """, (user_id,))
    
    ranked_anime = cursor.fetchall()
    
    if not ranked_anime:
        print(f"User {user_id} has no ranked anime to build a profile from.")
        return {}

    taste_profile = Counter()

    for anime_id, rank, pos_keys, neg_keys in ranked_anime:
        derived_rating = calculate_derived_rating(rank)
        
        if pos_keys:
            for keyword in pos_keys.split(', '):
                taste_profile[keyword] += derived_rating
        if neg_keys:
            for keyword in neg_keys.split(', '):
                taste_profile[keyword] -= derived_rating

    # Save the newly created profile to the database
    profile_json = json.dumps(dict(taste_profile))
    cursor.execute("""
        INSERT INTO user_taste_profiles (user_id, taste_profile)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE taste_profile = VALUES(taste_profile)
    """, (user_id, profile_json))
    
    print(f"Successfully created and saved profile for user {user_id}.")
    return dict(taste_profile)

def find_taste_neighbors(cursor, target_user_id, target_profile, num_neighbors=50):
    """Finds users with the most similar taste profiles using cosine similarity."""
    cursor.execute("SELECT user_id, taste_profile FROM user_taste_profiles WHERE user_id != %s", (target_user_id,))
    other_users = cursor.fetchall()

    if not other_users:
        return []

    # Prepare data for vectorization
    other_profiles = [json.loads(profile) for _, profile in other_users]
    other_user_ids = [user_id for user_id, _ in other_users]

    # Use pandas to create a feature matrix (keyword vectors)
    df = pd.DataFrame(other_profiles).fillna(0)
    target_df = pd.DataFrame([target_profile]).fillna(0)

    # Align columns so both dataframes have the same "universe" of keywords
    all_columns = df.columns.union(target_df.columns)
    df = df.reindex(columns=all_columns, fill_value=0)
    target_df = target_df.reindex(columns=all_columns, fill_value=0)

    # Calculate cosine similarity
    similarities = cosine_similarity(target_df, df)
    
    # Get the top N neighbors
    neighbor_indices = similarities[0].argsort()[-num_neighbors:][::-1]
    return [other_user_ids[i] for i in neighbor_indices]

def score_candidates(cursor, user_profile, candidate_ids):
    """Scores candidate anime based on the user's taste profile."""
    if not candidate_ids:
        return {}

    query_placeholders = ','.join(['%s'] * len(candidate_ids))
    cursor.execute(f"""
        SELECT anime_id, positive_keywords, negative_keywords
        FROM animes
        WHERE anime_id IN ({query_placeholders})
    """, tuple(candidate_ids))
    
    scored_candidates = {}
    for anime_id, pos_keys, neg_keys in cursor.fetchall():
        score = 0
        if pos_keys:
            for keyword in pos_keys.split(', '):
                score += user_profile.get(keyword, 0)
        if neg_keys:
            for keyword in neg_keys.split(', '):
                score += user_profile.get(keyword, 0) # Add the negative score
        scored_candidates[anime_id] = score
        
    return scored_candidates

# --- 4. MAIN SCRIPT ---
def main():
    parser = argparse.ArgumentParser(description="Generate anime recommendations for a specific user.")
    parser.add_argument("user_id", type=int, help="The ID of the user to generate recommendations for.")
    args = parser.parse_args()

    connection = get_db_connection()
    if not connection:
        return
        
    cursor = connection.cursor()
    connection.autocommit = True # Autocommit changes like profile creation

    try:
        # 1. Get the user's taste profile (create if needed)
        taste_profile = get_or_create_user_taste_profile(cursor, args.user_id)
        if not taste_profile:
            return

        # 2. Find similar users ("taste neighbors")
        neighbors = find_taste_neighbors(cursor, args.user_id, taste_profile)
        print(f"\nFound {len(neighbors)} taste neighbors.")
        if not neighbors:
            print("Cannot generate collaborative recommendations without neighbors.")
            return

        # 3. Generate candidate anime from neighbors' top picks
        cursor.execute("SELECT anime_id FROM user_watchlists WHERE user_id = %s", (args.user_id,))
        user_seen_anime = {item[0] for item in cursor.fetchall()}

        neighbor_placeholders = ','.join(['%s'] * len(neighbors))
        cursor.execute(f"""
            SELECT anime_id FROM user_watchlists
            WHERE user_id IN ({neighbor_placeholders}) AND user_rank <= 20
        """, tuple(neighbors))
        
        candidate_anime_ids = {item[0] for item in cursor.fetchall()} - user_seen_anime
        print(f"Generated {len(candidate_anime_ids)} candidate anime from neighbors.")

        # 4. Score candidates based on content similarity to user's profile
        scored_anime = score_candidates(cursor, taste_profile, list(candidate_anime_ids))
        
        # 5. Get top 10 recommendations and their titles
        sorted_recommendations = sorted(scored_anime.items(), key=lambda item: item[1], reverse=True)[:10]

        print("\n--- TOP 10 RECOMMENDATIONS ---")
        if not sorted_recommendations:
            print("Could not generate any recommendations with the current data.")
        else:
            for anime_id, score in sorted_recommendations:
                cursor.execute("SELECT title FROM animes WHERE anime_id = %s", (anime_id,))
                title = cursor.fetchone()[0]
                print(f"  - {title} (Score: {score:.2f})")

    except mysql.connector.Error as err:
        print(f"An error occurred: {err}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()


    
# ### How to Use the Script

# 1.  **Run your `process_reviews.py` script first** to make sure your `animes` table has all the keywords.
# 2.  **Populate your `user_watchlists` table.** This script relies on that table having data like `(user_id, anime_id, user_rank)` to build the taste profiles.
# 3.  **Run the script from your terminal**, providing the `user_id` you want recommendations for:

#     ```bash
#     # Get recommendations for user with ID 123
#     python get_recommendations.py 123
    
#     # Get recommendations for user with ID 456
#     python get_recommendations.py 456
    

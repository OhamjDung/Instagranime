import os
import mysql.connector
from dotenv import load_dotenv
import json
from collections import Counter

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
        print("-> Successfully connected to the database.")
        return connection
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# --- 3. CORE LOGIC ---

def calculate_derived_rating(rank):
    """Converts a user's rank into a weighted score."""
    if rank is None or rank == 0:
        return 0
    # This inverse function gives high weight to low ranks
    return (1 / rank) * 10

def main():
    """
    Main function to calculate and save taste profiles for ALL users in the database.
    """
    connection = get_db_connection()
    if not connection:
        return
        
    cursor = connection.cursor()

    try:
        # --- Step 1: Fetch all necessary data into memory for efficiency ---
        
        print("\n[Step 1] Fetching all anime keywords and user rankings from DB...")
        
        # Fetch anime keywords into a dictionary for fast lookups
        cursor.execute("SELECT anime_id, positive_keywords, negative_keywords FROM animes")
        anime_keywords_map = {
            anime_id: {'pos': pos_keys, 'neg': neg_keys}
            for anime_id, pos_keys, neg_keys in cursor.fetchall()
        }

        # Fetch all user rankings
        cursor.execute("SELECT user_id, anime_id, user_rank FROM user_watchlists WHERE user_rank IS NOT NULL")
        all_rankings = cursor.fetchall()
        print(f"-> Found {len(anime_keywords_map)} animes with keywords and {len(all_rankings)} user rankings.")

        # --- Step 2: Calculate taste profile for each user ---

        print("\n[Step 2] Calculating taste profiles for each user...")
        user_profiles = {} # A dictionary to hold profiles: {user_id: Counter(), ...}

        for user_id, anime_id, rank in all_rankings:
            if user_id not in user_profiles:
                user_profiles[user_id] = Counter()

            derived_rating = calculate_derived_rating(rank)
            keywords = anime_keywords_map.get(anime_id)

            if keywords:
                if keywords['pos']:
                    for keyword in keywords['pos'].split(', '):
                        if keyword: user_profiles[user_id][keyword] += derived_rating
                if keywords['neg']:
                    for keyword in keywords['neg'].split(', '):
                        if keyword: user_profiles[user_id][keyword] -= derived_rating
        
        print(f"-> Successfully calculated profiles for {len(user_profiles)} unique users.")

        # --- Step 3: Save all profiles to the database in a batch operation ---

        print("\n[Step 3] Saving all calculated profiles to the database...")
        
        # Prepare data for executemany, which is highly efficient
        profiles_to_save = [
            (user_id, json.dumps(dict(profile)))
            for user_id, profile in user_profiles.items()
        ]

        if profiles_to_save:
            save_query = """
                INSERT INTO user_taste_profiles (user_id, taste_profile)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE taste_profile = VALUES(taste_profile)
            """
            cursor.executemany(save_query, profiles_to_save)
            connection.commit()
            print(f"-> Successfully saved or updated {cursor.rowcount} user profiles.")

    except mysql.connector.Error as err:
        print(f"An error occurred: {err}")
    finally:
        # --- 4. CLEANUP ---
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()
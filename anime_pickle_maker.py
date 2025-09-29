import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import pandas as pd

# --- 1. SETUP & DATABASE CONNECTION ---
load_dotenv()

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        ssl_mode = os.getenv('DB_SSLMODE', 'require')
        dsn = (f"dbname='{os.getenv('DB_NAME')}' user='{os.getenv('DB_USER')}' "
               f"password='{os.getenv('DB_PASSWORD')}' host='{os.getenv('DB_HOST')}' "
               f"port='{os.getenv('DB_PORT')}' sslmode='{ssl_mode}'")
        connection = psycopg2.connect(dsn)
        print("✅ Database connection successful.")
        return connection
    except psycopg2.OperationalError as err:
        print(f"❌ Error connecting to database: {err}")
        return None

def load_anime_data(connection):
    """Loads all necessary anime data from the database into a pandas DataFrame."""
    print("⏳ Loading anime data from database...")
    query = """
        SELECT 
            a.anime_id,
            a.title,
            a.title_english,
            a.base_title,
            a.promo_link,
            a.studio,
            a.positive_keywords, 
            a.negative_keywords,
            a.synopsis,
            a.mean_score,
            a.overal_rank,
            STRING_AGG(g.name, ', ') as genres
        FROM animes a
        LEFT JOIN anime_genres ag ON a.anime_id = ag.anime_id
        LEFT JOIN genres g ON ag.genre_id = g.genre_id
        GROUP BY a.anime_id
    """
    df = pd.read_sql_query(query, connection)
    print(f"👍 Loaded {len(df)} anime records.")
    return df

# --- 2. MAIN EXECUTION ---
if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        try:
            # Step 1: Load the data from the database
            anime_df = load_anime_data(conn)
            
            # Step 2: Perform any simple, necessary transformations
            # (e.g., creating a list from the genre string is useful for the app)
            print("⏳ Processing genre list...")
            anime_df['genre_list'] = anime_df['genres'].apply(
                lambda x: x.split(', ') if isinstance(x, str) else []
            )
            print("👍 Genre list processed.")

            # Step 3: Save the final DataFrame to the pickle file
            anime_df.to_pickle('anime_dataframe.pkl')
            
            print("\n--- ✅ Success! ---")
            print(f"Saved DataFrame with {len(anime_df)} records to 'anime_dataframe.pkl'")

        except Exception as e:
            print(f"\n--- ❌ An error occurred ---")
            print(e)
            
        finally:
            # Step 4: Ensure the database connection is closed
            conn.close()
            print("🔌 Database connection closed.")
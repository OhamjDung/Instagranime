import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer
from sentence_transformers import SentenceTransformer
import numpy as np
import joblib
from tqdm import tqdm

# --- 1. SETUP & DATABASE CONNECTION ---
load_dotenv()

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
        print("Database connection successful.")
        return connection
    except psycopg2.OperationalError as err:
        print(f"Error connecting to database: {err}")
        return None

def load_anime_data(connection):
    """Loads all relevant anime data into a pandas DataFrame."""
    print("Loading anime data from database...")
    
    # --- FIX: Updated SQL query to correctly JOIN and aggregate genres ---
    query = """
        SELECT 
            a.anime_id, 
            a.title, 
            a.positive_keywords, 
            a.negative_keywords, 
            a.synopsis,
            STRING_AGG(g.name, ', ') as genres
        FROM animes a
        LEFT JOIN anime_genres ag ON a.anime_id = ag.anime_id
        LEFT JOIN genres g ON ag.genre_id = g.genre_id
        GROUP BY a.anime_id
    """
    
    df = pd.read_sql_query(query, connection)
    print(f"Loaded {len(df)} anime records.")
    return df

# --- 2. FEATURE ENGINEERING FUNCTIONS ---

def create_tfidf_features(df):
    """Generates TF-IDF features from positive and negative keywords."""
    print("\nStarting TF-IDF feature engineering for keywords...")
    # Combine positive and negative keywords into a single text document for each anime
    df['all_keywords'] = df['positive_keywords'].fillna('') + ' ' + df['negative_keywords'].fillna('')
    
    # Initialize the vectorizer. We'll limit it to the top 1000 most important keywords.
    vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    
    # Fit the vectorizer to the keyword data and transform it into a matrix
    tfidf_matrix = vectorizer.fit_transform(df['all_keywords'])
    
    # Save the trained vectorizer model to a file for later use
    joblib.dump(vectorizer, 'tfidf_vectorizer.pkl')
    print("TF-IDF vectorizer trained and saved to 'tfidf_vectorizer.pkl'")
    
    return tfidf_matrix

def create_genre_features(df):
    """Generates one-hot encoded features from genres."""
    print("\nStarting One-Hot Encoding for genres...")
    # Split the comma-separated genre string into a list of genres
    df['genre_list'] = df['genres'].str.split(', ')
    
    # Use MultiLabelBinarizer, which is perfect for this kind of "tag" data
    mlb = MultiLabelBinarizer()
    genre_matrix = mlb.fit_transform(df['genre_list'].fillna(''))
    
    # Save the trained encoder model to a file
    joblib.dump(mlb, 'genre_encoder.pkl')
    print("Genre encoder trained and saved to 'genre_encoder.pkl'")
    
    return genre_matrix

def create_synopsis_embeddings(df):
    """Generates sentence embeddings from the anime synopsis."""
    print("\nStarting synopsis embedding generation (this may take a while)...")
    # Load a powerful, pre-trained model from SentenceTransformers
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # The model needs a list of strings. Fill any missing synopses.
    synopses = df['synopsis'].fillna('No synopsis available.').tolist()
    
    # Generate the embeddings. The 'show_progress_bar' is great for long processes.
    embedding_matrix = model.encode(synopses, show_progress_bar=True)
    
    print("Synopsis embeddings generated successfully.")
    return embedding_matrix

# --- 3. MAIN EXECUTION ---

if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        anime_df = load_anime_data(conn)
        conn.close() # Close the connection once data is loaded

        # Generate each set of features
        tfidf_features = create_tfidf_features(anime_df)
        genre_features = create_genre_features(anime_df)
        synopsis_features = create_synopsis_embeddings(anime_df)

        # Combine all features into a single, final matrix
        print("\nCombining all feature matrices...")
        # Convert sparse matrices (from TF-IDF and genres) to dense arrays before combining
        final_feature_matrix = np.hstack([
            tfidf_features.toarray(), 
            genre_features, 
            synopsis_features
        ])
        
        # Save the final matrix and the corresponding anime IDs
        np.save('anime_feature_matrix.npy', final_feature_matrix)
        anime_df['anime_id'].to_json('anime_ids.json')
        
        print("\n--- Feature Engineering Complete! ---")
        print(f"Final feature matrix shape: {final_feature_matrix.shape}")
        print("Saved final features to 'anime_feature_matrix.npy'")
        print("Saved corresponding anime IDs to 'anime_ids.json'")


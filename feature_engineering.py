import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler
from sentence_transformers import SentenceTransformer
import numpy as np
import joblib
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.manifold import TSNE

# --- 1. SETUP & DATABASE CONNECTION ---
load_dotenv()
FEATURE_WEIGHTS = {
    "tfidf": 0.5, "genres": 2.0, "studios": 0.25, "synopsis": 3.0, "numerical": 1.5
}

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

def load_anime_data(connection):
    print("Loading anime data from database...")
    # MODIFIED: Added title_english and promo_link to ensure they are in the final .pkl file
    query = """
        SELECT 
            a.anime_id,
            a.title,
            a.title_english,       -- <<< ADDED THIS
            a.promo_link,          -- <<< ADDED THIS
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
    print(f"Loaded {len(df)} anime records.")
    return df

# --- 2. FEATURE ENGINEERING FUNCTIONS ---
def create_tfidf_features(df):
    print("\nStarting TF-IDF feature engineering for keywords...")
    df['all_keywords'] = df['positive_keywords'].fillna('') + ' ' + df['negative_keywords'].fillna('')
    vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(df['all_keywords'])
    joblib.dump(vectorizer, 'tfidf_vectorizer.pkl')
    return tfidf_matrix

def create_genre_features(df):
    print("\nStarting One-Hot Encoding for genres...")
    df['genre_list'] = df['genres'].str.split(', ')
    mlb = MultiLabelBinarizer()
    genre_matrix = mlb.fit_transform(df['genre_list'].fillna(''))
    joblib.dump(mlb, 'genre_encoder.pkl')
    return genre_matrix

def create_studio_features(df):
    print("\nStarting One-Hot Encoding for studios...")
    studio_vectorizer = TfidfVectorizer(max_features=200, binary=True)
    studio_matrix = studio_vectorizer.fit_transform(df['studio'].fillna(''))
    joblib.dump(studio_vectorizer, 'studio_vectorizer.pkl')
    return studio_matrix

def create_synopsis_embeddings(df):
    print("\nStarting synopsis embedding generation...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    synopses = df['synopsis'].fillna('No synopsis available.').tolist()
    embedding_matrix = model.encode(synopses, show_progress_bar=True)
    return embedding_matrix

# --- NEW: Function to process numerical features ---
def create_numerical_features(df):
    print("\nProcessing numerical features (score, rank)...")
    # Select the numerical columns and fill any missing values with the median
    numerical_df = df[['mean_score', 'overal_rank']].fillna(df[['mean_score', 'overal_rank']].median())
    scaler = StandardScaler()
    numerical_matrix = scaler.fit_transform(numerical_df)
    joblib.dump(scaler, 'scaler_numerical.pkl')
    print("Numerical features scaled and scaler saved.")
    return numerical_matrix

# --- 3. MAIN EXECUTION ---
if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        anime_df = load_anime_data(conn)
        conn.close()

        tfidf_features = create_tfidf_features(anime_df)
        genre_features = create_genre_features(anime_df)
        studio_features = create_studio_features(anime_df)
        synopsis_features = create_synopsis_embeddings(anime_df)
        numerical_features = create_numerical_features(anime_df) # --- NEW ---

        # Combine all features into a single, final matrix
        print("\nCombining all feature matrices...")
        final_feature_matrix = np.hstack([
            tfidf_features.toarray() * FEATURE_WEIGHTS['tfidf'], 
            genre_features * FEATURE_WEIGHTS['genres'],
            studio_features.toarray() * FEATURE_WEIGHTS['studios'],
            synopsis_features * FEATURE_WEIGHTS['synopsis'],
            numerical_features * FEATURE_WEIGHTS['numerical'] # --- NEW ---
        ])
        
        np.save('anime_feature_matrix.npy', final_feature_matrix)
        anime_df.to_pickle('anime_dataframe.pkl') # Save the whole dataframe for interaction features
        
        print("\n--- Feature Engineering Complete! ---")
        print(f"Final feature matrix shape: {final_feature_matrix.shape}")
        print("Saved final features to 'anime_feature_matrix.npy'")
        print("Saved dataframe to 'anime_dataframe.pkl'")


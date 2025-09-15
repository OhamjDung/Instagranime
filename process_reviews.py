import os
import mysql.connector
from dotenv import load_dotenv
from textblob import TextBlob
import spacy
from collections import Counter
import argparse

# --- 1. SETUP ---
load_dotenv()
print("Loading spaCy model...")
# Load the full model, keeping the parser which is essential for this new logic
nlp = spacy.load("en_core_web_sm")
print("Model loaded.")

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

# --- 3. REBUILT CORE ANALYSIS LOGIC ---
def analyze_review_aspects(text):
    """
    Analyzes review text to extract praised and criticized aspects using
    dependency parsing for higher accuracy.
    """
    positive_keywords = []
    negative_keywords = []

    # Handle potentially very large text blocks from concatenated reviews
    if len(text) > nlp.max_length:
        print(f"Warning: Text length ({len(text)}) exceeds spaCy's max length ({nlp.max_length}). Truncating.")
        text = text[:nlp.max_length]
    
    doc = nlp(text)

    # Pattern 1: Find adjectives describing nouns (e.g., "beautiful art")
    for token in doc:
        # Find adjectives that are not stop words
        if token.dep_ == "amod" and not token.is_stop:
            aspect_token = token.head
            # Ensure the aspect being described is a noun, not a pronoun
            if aspect_token.pos_ in ['NOUN', 'PROPN']:
                aspect = aspect_token.text
                descriptor = token.text
                
                # Get sentiment of the adjective itself
                polarity = TextBlob(descriptor).sentiment.polarity
                
                if polarity > 0.4:
                    positive_keywords.append(aspect.lower())
                elif polarity < -0.4:
                    negative_keywords.append(aspect.lower())

    # Pattern 2: Find nouns that are the subject of opinionated verbs (e.g., "story sucks")
    for token in doc:
        # Find subjects that are NOT pronouns and NOT stop words
        if "subj" in token.dep_ and not token.is_stop and token.pos_ != 'PRON':
            verb = token.head
            if verb.pos_ == 'VERB':
                # Get sentiment of the verb's base form (lemma)
                polarity = TextBlob(verb.lemma_).sentiment.polarity
                if polarity > 0.5:
                    positive_keywords.append(token.text.lower())
                elif polarity < -0.5:
                    negative_keywords.append(token.text.lower())

    # A revised list to filter out generic keywords but keep useful ones like "story"
    boring_keywords = {
        'show', 'series', 'everything', 'one', 'place', 'lot', 'thing', 'way',
        'bit', 'point', 'part', 'things', 'stuff', 'kind', 'review', 'opinion',
        'time', 'end', 'watch'
    }
    positive_keywords = [k for k in positive_keywords if k not in boring_keywords]
    negative_keywords = [k for k in negative_keywords if k not in boring_keywords]

    return positive_keywords, negative_keywords

# --- 4. MAIN SCRIPT ---
def main():
    """
    Main function to orchestrate the fetching, processing,
    and updating of anime reviews. It will always re-process all reviews.
    """
    connection = get_db_connection()
    if not connection:
        return
        
    cursor = connection.cursor()

    try:
        # --- PART A: PROCESS INDIVIDUAL REVIEWS ---
        # The script will now always fetch all reviews to re-process them.
        print("\nFetching ALL reviews for re-analysis.")
        fetch_query = "SELECT review_id, review_text FROM reviews"
        
        cursor.execute(fetch_query)
        unprocessed_reviews = cursor.fetchall()
        
        if not unprocessed_reviews:
            print("\nNo reviews found in the database to process.")
        else:
            print(f"\nFound {len(unprocessed_reviews)} reviews to analyze.")
            for i, (review_id, review_text) in enumerate(unprocessed_reviews):
                if not review_text: continue
                print(f"Processing review {i+1}/{len(unprocessed_reviews)} (ID: {review_id})...")
                
                blob = TextBlob(review_text)
                update_query = """
                    UPDATE reviews 
                    SET sentiment_polarity = %s, sentiment_subjectivity = %s, analyzed_at = NOW()
                    WHERE review_id = %s
                """
                cursor.execute(update_query, (blob.sentiment.polarity, blob.sentiment.subjectivity, review_id))

            connection.commit()
            print(f"\nSuccessfully analyzed and updated {len(unprocessed_reviews)} individual reviews.")

        # --- PART B: AGGREGATE RESULTS FOR EACH ANIME ---
        print("\nAggregating results and updating anime table...")
        
        cursor.execute("SELECT DISTINCT anime_id FROM reviews WHERE anime_id IS NOT NULL")
        anime_ids = [item[0] for item in cursor.fetchall()]

        for anime_id in anime_ids:
            cursor.execute("SELECT AVG(sentiment_polarity) FROM reviews WHERE anime_id = %s", (anime_id,))
            avg_score = cursor.fetchone()[0]

            cursor.execute("SELECT review_text FROM reviews WHERE anime_id = %s and review_text IS NOT NULL", (anime_id,))
            all_reviews_text = " ".join([row[0] for row in cursor.fetchall()])
            
            if not all_reviews_text.strip():
                print(f"No text to analyze for anime_id {anime_id}. Skipping keyword aggregation.")
                continue

            pos_keys, neg_keys = analyze_review_aspects(all_reviews_text)
            
            positive_summary = ", ".join([word for word, count in Counter(pos_keys).most_common(5)])
            negative_summary = ", ".join([word for word, count in Counter(neg_keys).most_common(5)])
            
            update_anime_query = """
                UPDATE animes
                SET avg_sentiment_score = %s, positive_keywords = %s, negative_keywords = %s
                WHERE anime_id = %s
            """
            cursor.execute(update_anime_query, (avg_score, positive_summary, negative_summary, anime_id))

        connection.commit()
        print(f"Successfully aggregated data for {len(anime_ids)} animes.")

    except mysql.connector.Error as err:
        print(f"An error occurred: {err}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()


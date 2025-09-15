require('dotenv').config(); // Loads environment variables from a .env file
const fs = require('fs');
const csv = require('csv-parser');
const mysql = require('mysql2/promise');

// --- 1. DATABASE CONFIGURATION ---
// Credentials are now loaded from the .env file.
// Default values are provided for fallback.
const dbConfig = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'your_username',
    password: process.env.DB_PASSWORD || 'your_password',
    database: process.env.DB_NAME || 'your_database' // Corrected to use DB_NAME from your .env file
};

const CSV_FILE_PATH = 'anime_genre.csv';

/**
 * Reads and parses a CSV file.
 * @param {string} filePath The path to the CSV file.
 * @returns {Promise<Array<Object>>} A promise that resolves with an array of objects representing the CSV rows.
 */
function readCsvFile(filePath) {
    return new Promise((resolve, reject) => {
        if (!fs.existsSync(filePath)) {
            return reject(new Error(`File not found at path: ${filePath}`));
        }
        
        const results = [];
        fs.createReadStream(filePath)
            .pipe(csv())
            .on('data', (data) => results.push(data))
            .on('end', () => resolve(results))
            .on('error', (error) => reject(error));
    });
}

/**
 * Imports anime-genre relationships from a CSV file into the database.
 * @param {mysql.Pool} pool - The database connection pool.
 * @param {string} csvFilePath - The path to the CSV file to import.
 */
async function importAnimeGenres(pool, csvFilePath) {
    console.log(`Reading ${csvFilePath}...`);
    try {
        const animeGenresData = await readCsvFile(csvFilePath);

        if (!animeGenresData || animeGenresData.length === 0) {
            console.log(` -> ${csvFilePath} is empty or could not be read. Nothing to import.`);
            return;
        }

        // Map the data to an array of arrays [[anime_id, genre_id], ...], ensuring values are integers.
        const genresToInsert = animeGenresData
            .map(row => {
                // Ensure the keys match your CSV headers exactly (case-sensitive).
                const animeId = parseInt(row['ANIME ID'], 10);
                const genreId = parseInt(row['GENRE ID'], 10);

                // Skips rows where parsing might have failed (e.g., non-numeric values or empty lines).
                if (isNaN(animeId) || isNaN(genreId)) {
                    console.warn(` -> Skipping invalid row:`, row);
                    return null;
                }
                return [animeId, genreId];
            })
            .filter(row => row !== null); // Remove any null (skipped) rows.

        if (genresToInsert.length === 0) {
            console.log(" -> No valid data found in CSV to import.");
            return;
        }

        const sql = "INSERT IGNORE INTO anime_genres (anime_id, genre_id) VALUES ?";
        
        // The `mysql2` library correctly handles an array of arrays for bulk inserts.
        const [result] = await pool.query(sql, [genresToInsert]);
        
        console.log(` -> Successfully inserted ${result.affectedRows} new anime-genre links.`);
        console.log(` -> (${result.warningStatus} warnings - likely duplicate entries that were ignored)`);

    } catch (error) {
        // This will print the actual error from the file system or database, which is crucial for debugging.
        console.error("ERROR: Failed to import anime-genre links:", error.message);
        // For more detailed SQL errors, you might want to log the full error object
        // console.error(error); 
    }
}

/**
 * Main function to run the script.
 */
async function main() {
    let pool;
    try {
        // Create a connection pool to the database
        pool = mysql.createPool(dbConfig);
        await pool.getConnection(); // Test the connection
        console.log("Database connection successful.");

        // Call the import function
        await importAnimeGenres(pool, CSV_FILE_PATH);

    } catch (error) {
        console.error("A critical error occurred:", error.message);
    } finally {
        if (pool) {
            await pool.end(); // Close all connections in the pool
            console.log("Import process finished. Database connection closed.");
        }
    }
}

// Execute the main function
main();


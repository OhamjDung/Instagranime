const fs = require('fs');
const csv = require('csv-parser');
const pool = require('./database.js'); // Your database connection pool

/**
 * A generic helper function to read any CSV file and return its data.
 * @param {string} filePath - The path to the CSV file.
 * @returns {Promise<object[]>} A promise that resolves to an array of objects from the CSV.
 */
function readCsvFile(filePath) {
    // Check if the file exists before trying to read it.
    if (!fs.existsSync(filePath)) {
        console.warn(`Warning: File not found at ${filePath}. Skipping.`);
        return Promise.resolve([]); // Return an empty array if the file doesn't exist.
    }

    return new Promise((resolve, reject) => {
        const results = [];
        fs.createReadStream(filePath)
            .pipe(csv())
            .on('data', (data) => results.push(data))
            .on('end', () => resolve(results))
            .on('error', (error) => reject(error));
    });
}

/**
 * The main function to orchestrate the import process.
 */
async function main() {
    console.log("Starting CSV to MySQL import process...");

    try {
        // --- 1. Import users.csv ---
        console.log("Reading user.csv...");
        const usersData = await readCsvFile('user.csv');
        if (usersData.length > 0) {
            const usersToInsert = usersData.map(user => [user.USER_ID, user.USERNAME]);
            await pool.query("INSERT IGNORE INTO users (user_id, username) VALUES ?", [usersToInsert]);
            console.log(` -> Imported ${usersData.length} users.`);
        }

        // --- 2. Import anime.csv ---
        console.log("Reading anime.csv...");
        const animeData = await readCsvFile('anime.csv');
        if (animeData.length > 0) {
            // Ensure values that might be null/undefined are handled.
            const animeToInsert = animeData.map(anime => [
                anime.ID,
                anime.TITLE,
                anime['OVERAL RANK'] || null, // Use bracket notation for names with spaces
                anime['MEAN SCORE'] || null
            ]);
            await pool.query("INSERT IGNORE INTO animes (anime_id, title, overal_rank, mean_score) VALUES ?", [animeToInsert]);
            console.log(` -> Imported ${animeData.length} animes.`);
        }

        // --- 3. Import anime_genre.csv ---
        console.log("Reading anime_genre.csv...");
        const animeGenresData = await readCsvFile('anime_genre.csv');
        if (animeGenresData.length > 0) {
            const genresToInsert = animeGenresData.map(ag => [ag['ANIME ID'], ag['GENRE ID']]);
            await pool.query("INSERT IGNORE INTO anime_genres (anime_id, genre_id) VALUES ?", [genresToInsert]);
            console.log(` -> Imported ${animeGenresData.length} anime-genre links.`);
        }

        // --- 4. Import user_watchlists.csv ---
        console.log("Reading user_watchlists.csv...");
        const watchlistsData = await readCsvFile('user_watchlists.csv');
        if (watchlistsData.length > 0) {
            const watchlistsToInsert = watchlistsData.map(uw => [uw.USER_ID, uw['ANIME ID'], uw['USER RANK']]);
            await pool.query("INSERT IGNORE INTO user_watchlists (user_id, anime_id, user_rank) VALUES ?", [watchlistsToInsert]);
            console.log(` -> Imported ${watchlistsData.length} watchlist entries.`);
        }

    } catch (error) {
        console.error("An error occurred during the database import:", error);
    } finally {
        // --- 5. Close the connection ---
        await pool.end();
        console.log("\nImport process complete. Database connection closed.");
        console.log(`[Richardson, TX, ${new Date().toLocaleString('en-US', { timeZone: 'America/Chicago' })}]`);
    }
}

// Start the script
main();
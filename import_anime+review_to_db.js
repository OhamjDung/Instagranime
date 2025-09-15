const fs = require('fs');
const csv = require('csv-parser');
const mysql = require('mysql2/promise');
require('dotenv').config(); // To load credentials from .env file

/**
 * A generic helper function to read any CSV file and return its data.
 * @param {string} filePath - The path to the CSV file.
 * @returns {Promise<object[]>} A promise that resolves to an array of objects from the CSV.
 */
function readCsvFile(filePath) {
    if (!fs.existsSync(filePath)) {
        console.error(`Error: File not found at ${filePath}.`);
        return Promise.resolve([]);
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
    console.log("Starting Scraped CSV to MySQL import process...");
    let connection;

    try {
        // --- 1. Establish Database Connection ---
        connection = await mysql.createConnection({
            host: process.env.DB_HOST || 'localhost',
            user: process.env.DB_USER,
            password: process.env.DB_PASSWORD,
            database: process.env.DB_NAME
        });
        console.log("-> Successfully connected to the database.");

        // --- 2. Read the Scraped Data ---
        const scrapedData = await readCsvFile('D:/MAL/scrapy/useridian/final.csv');
        if (scrapedData.length === 0) {
            console.log("No data found in CSV file. Exiting.");
            return;
        }

        const animesToUpdate = [];
        const reviewsToInsert = [];

        // --- 3. Separate the Data by Type ---
        for (const row of scrapedData) {
            if (row.type === 'anime_details') {
                animesToUpdate.push({
                    anime_id: row.anime_id,
                    studio: row.studio || null,
                    promo_link: row.promo_video_url || null,
                });
            } else if (row.type === 'review') {
                const rating = parseInt(row.rating_score, 10);
                reviewsToInsert.push([
                    row.anime_id,
                    row.username || null,
                    row.date || null,
                    isNaN(rating) ? null : rating,
                    row.review_text || null
                ]);
            }
        }
        console.log(`-> Found ${animesToUpdate.length} anime details and ${reviewsToInsert.length} reviews.`);

        // --- 4. Update Anime Details ---
        if (animesToUpdate.length > 0) {
            console.log('-> Updating existing anime details in the database...');
            // Use a transaction to perform all updates as a single, safe operation
            await connection.beginTransaction();
            try {
                const updateSql = 'UPDATE animes SET studio = ?, promo_link = ? WHERE anime_id = ?';
                let updatedCount = 0;
                for (const anime of animesToUpdate) {
                    // This query only updates the new fields for an existing anime_id
                    const [result] = await connection.execute(updateSql, [
                        anime.studio,
                        anime.promo_link,
                        anime.anime_id
                    ]);
                    if (result.affectedRows > 0) {
                        updatedCount++;
                    }
                }
                await connection.commit();
                console.log(`-> Updated ${updatedCount} existing anime records.`);
            } catch (e) {
                await connection.rollback(); // Undo changes if any error occurs
                throw e; // Pass the error to the main catch block
            }
        }

        // --- 5. Insert Reviews ---
        if (reviewsToInsert.length > 0) {
            // Use INSERT IGNORE to prevent errors if a review has already been inserted
            const reviewSql = "INSERT IGNORE INTO reviews (anime_id, username, review_date, rating_score, review_text) VALUES ?";
            await connection.query(reviewSql, [reviewsToInsert]);
            console.log(`-> Inserted ${reviewsToInsert.length} review records.`);
        }

    } catch (error) {
        console.error("\nAn error occurred during the database import:", error);
    } finally {
        // --- 6. Close the Connection ---
        if (connection) {
            await connection.end();
            console.log("\nImport process complete. Database connection closed.");
            console.log(`[Richardson, TX, ${new Date().toLocaleString('en-US', { timeZone: 'America/Chicago' })}]`);
        }
    }
}

// Start the script
main();


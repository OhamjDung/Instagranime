// --------------------------------------------------------------------------------------THE SAVING-----------------------------------------------------------------------------------------------------------------


// async function addUser(username) {
//     const sql = 'INSERT INTO users (username) VALUES (?)';
//     try {
//         // Get a connection from the pool and execute the query
//         const [result] = await pool.execute(sql, [username]);
//         console.log(`User '${username}' added with ID: ${result.insertId}`);
//         return result.insertId;
//     } catch (err) {
//         // Handle potential errors, like a duplicate username
//         console.error('Error adding user:', err);
//     }
// }

// // Example function to get an anime by its title
// async function getAnime(title) {
//     const sql = 'SELECT * FROM animes WHERE title = ?';
//     try {
//         const [rows] = await pool.execute(sql, [title]);
//         if (rows.length > 0) {
//             console.log('Found anime:', rows[0]);
//             return rows[0];
//         } else {
//             console.log(`No anime found with title: ${title}`);
//             return null;
//         }
//     } catch (err) {
//         console.error('Error fetching anime:', err);
//     }
// }


// // --- RUNNING THE EXAMPLES ---
// async function main() {
//     console.log("--- Running database operations ---");
//     await addUser('Kenshin');
//     await getAnime('Rurouni Kenshin');
    
//     // When your application is shutting down, you can close the pool
//     // This will close all open connections gracefully.
//     // For a long-running server, you would typically not call this until the server stops.
//     await pool.end();
//     console.log("Pool has been closed.");
// }

// main();
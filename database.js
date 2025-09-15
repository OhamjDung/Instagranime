// //ESTABLISING A CONNECTION

// function openection(){
//     const mysql = require('mysql');

// const connection = mysql.createConnection({
//     host: 'localhost',
//     user: 'root',
//     password: 'Monopoly123@',
//     database: 'anime'
// });

// connection.connect(function(err) {
//     if (err) throw err;
//     console.log('Connected to MySQL!');
// });
// }
// //CLOSE THE CONNECTION
// function closection(){
// connection.end(function(err) {
//     if (err) throw err;
//     console.log('Connection closed.');
// });
// }

const mysql = require('mysql2/promise'); // Note the '/promise'

console.log('Creating connection pool...');

// Create a connection pool.
// The pool will manage connections, automatically creating and reusing them.
const pool = mysql.createPool({
    host: 'localhost',
    user: 'root',
    password: 'Monopoly123@',
    database: 'anime',
    waitForConnections: true,
    connectionLimit: 10, // Adjust this number based on your needs
    queueLimit: 0
});

// A simple function to test the connection
async function testConnection() {
    try {
        // Get a connection from the pool
        const connection = await pool.getConnection();
        console.log('Successfully connected to the database using the pool.');
        // Release the connection back to the pool
        connection.release();
    } catch (err) {
        console.error('Error connecting to the database:', err);
    }
}

// Test the connection when the module loads
testConnection();

// Export the pool so other files in your application can use it
module.exports = pool;



/*
  This script is ordered correctly. Tables without foreign keys
  or that are referenced by others come first.


CREATE TABLE users (
    user_id INT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    PRIMARY KEY (user_id)
);

CREATE TABLE genres (
    genre_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    category ENUM('Standard', 'Explicit') NOT NULL DEFAULT 'Standard',
    PRIMARY KEY (genre_id)
);

CREATE TABLE animes (
    anime_id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL UNIQUE,
    overal_rank INT NOT NULL,
    mean_score INT NOT NULL,
    PRIMARY KEY (anime_id)
);

CREATE TABLE anime_genres (
    anime_id INT NOT NULL,
    genre_id INT NOT NULL,
    PRIMARY KEY (anime_id, genre_id),
    FOREIGN KEY (anime_id) REFERENCES animes(anime_id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE
);

CREATE TABLE user_watchlists (
    user_id INT NOT NULL,
    anime_id INT NOT NULL,
    watch_status ENUM('Plan to Watch', 'Watching', 'Completed') DEFAULT 'Plan to Watch',
    score TINYINT, -- User's score, e.g., 1-10
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, anime_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (anime_id) REFERENCES animes(anime_id) ON DELETE CASCADE
);

*/
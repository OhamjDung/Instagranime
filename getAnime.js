const { createObjectCsvWriter } = require('csv-writer');
const fs = require('fs');
const csv = require('csv-parser');
const pool = require('./database.js');

// Your CSV writer setup (unchanged)
const user_writer = createObjectCsvWriter({ path: 'user.csv', header: [ {id: 'user_id', title: 'USER_ID'}, {id: 'username', title: 'USERNAME'} ] });
const anime_writer = createObjectCsvWriter({ path: 'anime.csv', header: [ {id: 'anime_id', title: 'ID'}, {id: 'title', title: 'TITLE'}, {id: 'overal_rank', title: 'OVERAL RANK'}, {id: 'mean_score', title: 'MEAN SCORE'} ] });
const anime_genres_writer = createObjectCsvWriter({ path: 'anime_genre.csv', header:[ {id:'anime_id', title:'ANIME ID'}, {id:'genre_id', title:'GENRE ID'} ] });
const user_watchlists_writer = createObjectCsvWriter({ path: 'user_watchlists.csv', header:[ {id:'user_id', title:'USER_ID'}, {id:'anime_id', title:'ANIME ID'}, {id:'user_rank', title:'USER RANK'} ] });
const genre = { "Action": 1, "Adventure": 2, "Avant Garde": 3, "Award Winning": 4, "Boys Love": 5, "Comedy": 6, "Drama": 7, "Fantasy": 8, "Girls Love": 9, "Gourmet": 10, "Horror": 11, "Mystery": 12, "Romance": 13, "Sci-Fi": 14, "Slice of Life": 15, "Sports": 16, "Supernatural": 17, "Suspense": 18, "Ecchi": 19, "Erotica": 20, "Hentai": 21 };

// Master lists to collect all data
let all_user_watchlists = [];
let all_anime_info = [];
let all_anime_genres = [];
let all_users = [];

// Helpers
const processedAnimeIds = new Set();
const userMap = new Map();
const User = new Set();


// Your getMyList function (unchanged)
async function getMyList(userName) {
    const yourClientId = '17e2649b1094231fce758ebecbe367de';
    const url = `https://api.myanimelist.net/v2/users/${userName}/animelist?status=watching&sort=list_score&limit=100&fields=genres,mean,rank,num_episodes,my_list_status,status,start_date`;
    
    let THE_user_id;
    if (!userMap.has(userName)) {
        let newId = User.size;
        User.add(User.size);
        userMap.set(userName, newId);
        all_users.push({ user_id: newId, username: userName });
    }
    THE_user_id = userMap.get(userName);

    try {
        const response = await fetch(url, { headers: { 'X-MAL-CLIENT-ID': yourClientId } });
        if (!response.ok) {
            console.error(`Error fetching data for ${userName}: ${response.status} ${response.statusText}`);
            return;
        }
        const data = await response.json();
        const animelist = data.data;
        if (!animelist || animelist.length === 0) {
            // console.log(`${userName} has 0 anime in their 'watching' list.`);
            return;
        }

        let temp_ranking = 0;
        animelist.forEach(item => {
            const anime = item.node;
            temp_ranking += 1;
            const genreList = anime.genres ? anime.genres.map(g => g.name) : [];

            genreList.forEach(genreName => {
                if (genre[genreName]) {
                    all_anime_genres.push({ anime_id: anime.id, genre_id: genre[genreName] });
                }
            });

            all_user_watchlists.push({ user_id: THE_user_id, anime_id: anime.id, user_rank: temp_ranking });
            
            if (!processedAnimeIds.has(anime.id)) {
                processedAnimeIds.add(anime.id);
                all_anime_info.push({ anime_id: anime.id, title: anime.title, overal_rank: anime.rank, mean_score: anime.mean });
            }
        });
    } catch (error) {
        console.error(`A critical error occurred while processing ${userName}:`, error);
    }
}

// A helper function to read all users from the CSV first.
function readUsersFromCsv(filePath) {
    return new Promise((resolve, reject) => {
        const usernames = [];
        fs.createReadStream(filePath)
            .pipe(csv())
            .on('data', (row) => {
                if (row.username) {
                    usernames.push(row.username);
                }
            })
            .on('end', () => resolve(usernames))
            .on('error', (error) => reject(error));
    });
}

// ===================================================================
//                 HERE IS THE MAIN FUNCTION
// ===================================================================
// We wrap all the 'action' logic in an async function.
async function main() {
    const inputFile = "scrapy/useridian/output.csv";

    // --- CONFIGURATION FOR BATCHING TO PREVENT CRASHES ---
    const speed = 0.5;

    const BATCH_SIZE = 10 * speed;
    const DELAY_MS = 1000 / speed; // 1 second

    console.log(`[Step 1] Reading all users from ${inputFile}...`);
    const usersToProcess = await readUsersFromCsv(inputFile);
    console.log(`Found ${usersToProcess.length} users.`);

    console.log(`\n[Step 2] Fetching data in batches of ${BATCH_SIZE}...`);
    
    for (let i = 0; i < usersToProcess.length; i += BATCH_SIZE) {
        const batch = usersToProcess.slice(i, i + BATCH_SIZE);
        console.log(`--> Processing batch #${(i / BATCH_SIZE) + 1}...`);
        
        await Promise.all(batch.map(username => getMyList(username)));
        
        if (i + BATCH_SIZE < usersToProcess.length) {
            await new Promise(resolve => setTimeout(resolve, DELAY_MS));
        }
    }

    console.log("\n[Step 3] All data fetched. Writing to output CSV files...");

    try {
        await user_writer.writeRecords(all_users);
        console.log(' -> users.csv was written successfully.');

        await anime_writer.writeRecords(all_anime_info);
        console.log(' -> animes.csv was written successfully.');

        await anime_genres_writer.writeRecords(all_anime_genres);
        console.log(' -> anime_genres.csv was written successfully.');

        await user_watchlists_writer.writeRecords(all_user_watchlists);
        console.log(' -> user_watchlists.csv was written successfully.');

        console.log(`\nExport process complete. [Richardson, TX, ${new Date().toLocaleString('en-US', { timeZone: 'America/Chicago' })}]`);
    } catch (error) {
        console.error('An error occurred during file writing:', error);
    }

}




// This is the very last line of the file. It tells the script to start the 'main' function.
main();

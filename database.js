const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, 'tickets.db'));

// Initialize tables
db.exec(`
  CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT UNIQUE,
    guild_id TEXT,
    creator_id TEXT,
    other_user_id TEXT,
    creator_giving TEXT,
    other_giving TEXT,
    sender_id TEXT,
    receiver_id TEXT,
    amount_usd REAL,
    amount_ltc REAL,
    ltc_address TEXT,
    tx_hash TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS confirmations (
    ticket_id INTEGER,
    user_id TEXT,
    type TEXT,
    confirmed BOOLEAN DEFAULT 0,
    PRIMARY KEY (ticket_id, user_id, type)
  );

  CREATE TABLE IF NOT EXISTS role_settings (
    guild_id TEXT PRIMARY KEY,
    shank_role_id TEXT,
    mercy_role_id TEXT
  );

  CREATE TABLE IF NOT EXISTS used_buttons (
    ticket_id INTEGER,
    button_type TEXT,
    used BOOLEAN DEFAULT 1,
    PRIMARY KEY (ticket_id, button_type)
  );
`);

console.log('✅ Database initialized');

module.exports = db;

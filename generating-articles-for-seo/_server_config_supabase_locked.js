/**
 * Database client — always local PostgreSQL.
 *
 * The old Supabase switch is hard-disabled. Even if USE_LOCAL_PG is set to
 * false or removed, this file still returns the local pg adapter. To go back
 * to Supabase you must edit this file on purpose — that's deliberate, so
 * nobody can accidentally redirect production back to the cloud DB.
 */

console.log('🗄️  Database: local PostgreSQL (Supabase permanently disconnected)');
module.exports = require('./supabase_pg');

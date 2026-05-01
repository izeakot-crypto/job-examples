/**
 * Switcher between Supabase REST client and local PG adapter.
 *
 * Set USE_LOCAL_PG=true in .env to route everything through local PostgreSQL.
 * Default (unset or false) keeps the historical Supabase behaviour.
 */

if (String(process.env.USE_LOCAL_PG || '').toLowerCase() === 'true') {
    console.log('🗄️  Using local PostgreSQL (USE_LOCAL_PG=true)');
    module.exports = require('./supabase_pg');
} else {
    const { createClient } = require('@supabase/supabase-js');

    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
        console.warn('⚠️  Supabase credentials not configured. Using mock data.');
    } else {
        const keyType = process.env.SUPABASE_SERVICE_ROLE_KEY ? 'SERVICE_ROLE' : 'ANON';
        console.log(`✅ Supabase configured with ${keyType} key`);
    }

    const supabase = supabaseUrl && supabaseKey
        ? createClient(supabaseUrl, supabaseKey)
        : null;

    module.exports = supabase;
}

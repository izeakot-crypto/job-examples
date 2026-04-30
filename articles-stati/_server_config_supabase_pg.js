/**
 * PostgreSQL-backed adapter that mimics the subset of the supabase-js client
 * used across the codebase. Replaces '../config/supabase' with a drop-in.
 *
 * Supported: from(t).select/insert/upsert/update/delete
 *   filters: eq, neq, in, is, gt, gte, lt, lte, ilike, like, or, not, contains
 *   modifiers: order, limit, range, single, maybeSingle
 *   options on select: { count: 'exact', head: true }
 *   upsert options: { onConflict: 'col' or 'col1,col2' }
 *
 * Not supported (would throw): .rpc(), .storage, .auth, realtime.
 */
const { Pool } = require('pg');

const LOCAL_DB_URL = process.env.DATABASE_URL
    || `postgresql://${process.env.PG_USER || 'seo_user'}:${encodeURIComponent(process.env.PG_PASSWORD || '')}@${process.env.PG_HOST || 'localhost'}:${process.env.PG_PORT || 5432}/${process.env.PG_DATABASE || 'seo_articles'}`;

const pool = new Pool({
    connectionString: LOCAL_DB_URL,
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 10000,
});

pool.on('error', (err) => {
    console.error('❌ PG Pool error:', err.message);
});

pool.query('SELECT NOW()').then(() => {
    console.log('✅ Local PostgreSQL connected');
}).catch(err => {
    console.error('❌ Local PostgreSQL connection failed:', err.message);
});

// ===========================================================================
// Query builder (thenable)
// ===========================================================================

function quoteIdent(name) {
    // Support comma-separated columns for select; quote each part
    if (name === '*') return '*';
    if (name.includes(',')) {
        return name.split(',').map(s => quoteIdent(s.trim())).join(', ');
    }
    // Allow count(*)-like expressions (used rarely); otherwise quote identifier
    if (/^[a-z_][a-z0-9_]*$/i.test(name)) return `"${name}"`;
    return name; // pass-through for expressions
}

class QueryBuilder {
    constructor(table) {
        this._table = table;
        this._op = null;            // 'select'|'insert'|'update'|'delete'|'upsert'
        this._selectCols = '*';
        this._selectOpts = {};
        this._insertRows = null;
        this._updateData = null;
        this._upsertData = null;
        this._upsertOnConflict = null;
        this._filters = [];         // list of {type, col, val} entries
        this._orders = [];          // list of {col, ascending}
        this._limit = null;
        this._offset = null;
        this._rangeFrom = null;
        this._rangeTo = null;
        this._singleMode = null;    // 'single' | 'maybe'
        this._returning = false;    // did user call .select() after mutation?
    }

    // ----- verb methods -----
    select(cols = '*', opts = {}) {
        // select() can be called as verb OR after insert/update to request RETURNING
        if (this._op === null) {
            this._op = 'select';
            this._selectCols = cols || '*';
            this._selectOpts = opts || {};
        } else {
            this._returning = true;
            // If columns passed post-mutation, remember them
            if (cols && cols !== '*') this._selectCols = cols;
        }
        return this;
    }

    insert(rows) {
        this._op = 'insert';
        this._insertRows = Array.isArray(rows) ? rows : [rows];
        return this;
    }

    upsert(rows, opts = {}) {
        this._op = 'upsert';
        this._upsertData = Array.isArray(rows) ? rows : [rows];
        this._upsertOnConflict = opts.onConflict || 'id';
        return this;
    }

    update(data) {
        this._op = 'update';
        this._updateData = data;
        return this;
    }

    delete() {
        this._op = 'delete';
        return this;
    }

    // ----- filters -----
    _addFilter(type, col, val) {
        this._filters.push({ type, col, val });
        return this;
    }

    eq(col, val) { return this._addFilter('eq', col, val); }
    neq(col, val) { return this._addFilter('neq', col, val); }
    gt(col, val) { return this._addFilter('gt', col, val); }
    gte(col, val) { return this._addFilter('gte', col, val); }
    lt(col, val) { return this._addFilter('lt', col, val); }
    lte(col, val) { return this._addFilter('lte', col, val); }
    is(col, val) { return this._addFilter('is', col, val); }
    in(col, val) { return this._addFilter('in', col, val); }
    like(col, val) { return this._addFilter('like', col, val); }
    ilike(col, val) { return this._addFilter('ilike', col, val); }
    contains(col, val) { return this._addFilter('contains', col, val); }
    not(col, op, val) { return this._addFilter('not', col, { op, val }); }
    or(expr) { return this._addFilter('or', null, expr); }

    // ----- modifiers -----
    order(col, opts = {}) {
        this._orders.push({ col, ascending: opts.ascending !== false });
        return this;
    }

    limit(n) {
        this._limit = n;
        return this;
    }

    range(from, to) {
        this._rangeFrom = from;
        this._rangeTo = to;
        return this;
    }

    single() {
        this._singleMode = 'single';
        return this;
    }

    maybeSingle() {
        this._singleMode = 'maybe';
        return this;
    }

    // ----- thenable: makes `await qb` execute the query -----
    then(resolve, reject) {
        return this._execute().then(resolve, reject);
    }

    catch(reject) {
        return this._execute().catch(reject);
    }

    // ----- build & execute -----
    async _execute() {
        try {
            if (this._op === 'select' || this._op === null) {
                return await this._executeSelect();
            } else if (this._op === 'insert') {
                return await this._executeInsert();
            } else if (this._op === 'upsert') {
                return await this._executeUpsert();
            } else if (this._op === 'update') {
                return await this._executeUpdate();
            } else if (this._op === 'delete') {
                return await this._executeDelete();
            }
            return { data: null, error: new Error(`Unknown op: ${this._op}`) };
        } catch (err) {
            return { data: null, error: err, count: null };
        }
    }

    _buildWhere(startParamIdx = 1) {
        const params = [];
        const conds = [];
        let p = startParamIdx;

        for (const f of this._filters) {
            const col = f.col ? quoteIdent(f.col) : null;
            switch (f.type) {
                case 'eq':
                    if (f.val === null) { conds.push(`${col} IS NULL`); }
                    else { conds.push(`${col} = $${p++}`); params.push(f.val); }
                    break;
                case 'neq':
                    if (f.val === null) { conds.push(`${col} IS NOT NULL`); }
                    else { conds.push(`${col} <> $${p++}`); params.push(f.val); }
                    break;
                case 'gt': conds.push(`${col} > $${p++}`); params.push(f.val); break;
                case 'gte': conds.push(`${col} >= $${p++}`); params.push(f.val); break;
                case 'lt': conds.push(`${col} < $${p++}`); params.push(f.val); break;
                case 'lte': conds.push(`${col} <= $${p++}`); params.push(f.val); break;
                case 'is': {
                    // is(col, null) -> IS NULL; is(col, true) -> IS TRUE
                    if (f.val === null) conds.push(`${col} IS NULL`);
                    else if (f.val === true) conds.push(`${col} IS TRUE`);
                    else if (f.val === false) conds.push(`${col} IS FALSE`);
                    else { conds.push(`${col} = $${p++}`); params.push(f.val); }
                    break;
                }
                case 'in': {
                    const arr = Array.isArray(f.val) ? f.val : [f.val];
                    if (!arr.length) { conds.push('FALSE'); }
                    else {
                        const placeholders = arr.map(() => `$${p++}`).join(',');
                        conds.push(`${col} IN (${placeholders})`);
                        params.push(...arr);
                    }
                    break;
                }
                case 'like': conds.push(`${col} LIKE $${p++}`); params.push(f.val); break;
                case 'ilike': conds.push(`${col} ILIKE $${p++}`); params.push(f.val); break;
                case 'contains': {
                    // For jsonb/array columns
                    conds.push(`${col} @> $${p++}`);
                    params.push(typeof f.val === 'string' ? f.val : JSON.stringify(f.val));
                    break;
                }
                case 'not': {
                    // .not(col, 'eq', val) => col <> val; .not(col, 'is', null) => IS NOT NULL
                    const innerOp = f.val.op;
                    const innerVal = f.val.val;
                    if (innerOp === 'is' && innerVal === null) conds.push(`${col} IS NOT NULL`);
                    else if (innerOp === 'eq') { conds.push(`${col} <> $${p++}`); params.push(innerVal); }
                    else if (innerOp === 'in') {
                        const arr = Array.isArray(innerVal) ? innerVal : [innerVal];
                        const placeholders = arr.map(() => `$${p++}`).join(',');
                        conds.push(`${col} NOT IN (${placeholders})`);
                        params.push(...arr);
                    }
                    else conds.push(`NOT (${col} ${innerOp} $${p++})`), params.push(innerVal);
                    break;
                }
                case 'or': {
                    // Supabase .or('col1.eq.val,col2.eq.val') — minimal parser
                    const parts = String(f.val).split(',').map(s => s.trim()).filter(Boolean);
                    const orConds = [];
                    for (const part of parts) {
                        const m = part.match(/^([a-z_][a-z0-9_]*)\.([a-z]+)\.(.+)$/i);
                        if (!m) continue;
                        const c = quoteIdent(m[1]), op = m[2], v = m[3];
                        if (op === 'eq') { orConds.push(`${c} = $${p++}`); params.push(v); }
                        else if (op === 'ilike') { orConds.push(`${c} ILIKE $${p++}`); params.push(v); }
                        else if (op === 'is' && v === 'null') { orConds.push(`${c} IS NULL`); }
                    }
                    if (orConds.length) conds.push(`(${orConds.join(' OR ')})`);
                    break;
                }
            }
        }
        const whereClause = conds.length ? ` WHERE ${conds.join(' AND ')}` : '';
        return { whereClause, params, nextParam: p };
    }

    _buildOrderLimit() {
        let sql = '';
        if (this._orders.length) {
            sql += ' ORDER BY ' + this._orders.map(o =>
                `${quoteIdent(o.col)} ${o.ascending ? 'ASC' : 'DESC'} NULLS LAST`
            ).join(', ');
        }
        if (this._rangeFrom !== null && this._rangeTo !== null) {
            sql += ` LIMIT ${this._rangeTo - this._rangeFrom + 1} OFFSET ${this._rangeFrom}`;
        } else {
            if (this._limit !== null) sql += ` LIMIT ${this._limit}`;
            if (this._offset !== null) sql += ` OFFSET ${this._offset}`;
        }
        return sql;
    }

    async _executeSelect() {
        const { head, count } = this._selectOpts;
        const cols = this._selectCols === '*' ? '*' : quoteIdent(this._selectCols);
        const { whereClause, params } = this._buildWhere(1);
        const orderLimit = this._buildOrderLimit();

        let countResult = null;
        if (count === 'exact') {
            const countSql = `SELECT COUNT(*)::int AS c FROM ${quoteIdent(this._table)}${whereClause}`;
            const r = await pool.query(countSql, params);
            countResult = r.rows[0].c;
        }

        if (head) {
            return { data: null, error: null, count: countResult };
        }

        const selectSql = `SELECT ${cols} FROM ${quoteIdent(this._table)}${whereClause}${orderLimit}`;
        const res = await pool.query(selectSql, params);
        return this._formatResult(res.rows, countResult);
    }

    async _executeInsert() {
        const rows = this._insertRows;
        if (!rows.length) return { data: [], error: null };
        const cols = Object.keys(rows[0]);
        const placeholders = [];
        const params = [];
        let p = 1;
        for (const row of rows) {
            const rowPlace = cols.map(c => {
                params.push(row[c] === undefined ? null : normalizeValue(row[c]));
                return `$${p++}`;
            });
            placeholders.push(`(${rowPlace.join(',')})`);
        }
        const returning = this._returning ? ' RETURNING *' : '';
        const sql = `INSERT INTO ${quoteIdent(this._table)} (${cols.map(quoteIdent).join(',')}) VALUES ${placeholders.join(',')}${returning}`;
        const res = await pool.query(sql, params);
        return this._formatResult(this._returning ? res.rows : [], null);
    }

    async _executeUpsert() {
        const rows = this._upsertData;
        if (!rows.length) return { data: [], error: null };
        const cols = Object.keys(rows[0]);
        const conflictCols = this._upsertOnConflict.split(',').map(s => s.trim());
        const updateCols = cols.filter(c => !conflictCols.includes(c));

        const placeholders = [];
        const params = [];
        let p = 1;
        for (const row of rows) {
            const rowPlace = cols.map(c => {
                params.push(row[c] === undefined ? null : normalizeValue(row[c]));
                return `$${p++}`;
            });
            placeholders.push(`(${rowPlace.join(',')})`);
        }
        const updateSet = updateCols.length
            ? ' DO UPDATE SET ' + updateCols.map(c => `${quoteIdent(c)} = EXCLUDED.${quoteIdent(c)}`).join(', ')
            : ' DO NOTHING';
        const returning = this._returning ? ' RETURNING *' : '';
        const sql = `INSERT INTO ${quoteIdent(this._table)} (${cols.map(quoteIdent).join(',')}) VALUES ${placeholders.join(',')} ON CONFLICT (${conflictCols.map(quoteIdent).join(',')})${updateSet}${returning}`;
        const res = await pool.query(sql, params);
        return this._formatResult(this._returning ? res.rows : [], null);
    }

    async _executeUpdate() {
        const data = this._updateData;
        const cols = Object.keys(data);
        const params = [];
        let p = 1;
        const setParts = cols.map(c => {
            params.push(data[c] === undefined ? null : normalizeValue(data[c]));
            return `${quoteIdent(c)} = $${p++}`;
        });
        const { whereClause, params: whereParams } = this._buildWhere(p);
        params.push(...whereParams);
        const returning = this._returning ? ' RETURNING *' : '';
        const sql = `UPDATE ${quoteIdent(this._table)} SET ${setParts.join(', ')}${whereClause}${returning}`;
        const res = await pool.query(sql, params);
        return this._formatResult(this._returning ? res.rows : [], null);
    }

    async _executeDelete() {
        const { whereClause, params } = this._buildWhere(1);
        const returning = this._returning ? ' RETURNING *' : '';
        const sql = `DELETE FROM ${quoteIdent(this._table)}${whereClause}${returning}`;
        const res = await pool.query(sql, params);
        return this._formatResult(this._returning ? res.rows : [], null);
    }

    _formatResult(rows, count) {
        if (this._singleMode === 'single') {
            if (rows.length === 0) return { data: null, error: { message: 'PGRST116: Row not found', code: 'PGRST116' }, count };
            if (rows.length > 1) return { data: null, error: { message: 'Multiple rows returned' }, count };
            return { data: rows[0], error: null, count };
        }
        if (this._singleMode === 'maybe') {
            if (rows.length === 0) return { data: null, error: null, count };
            return { data: rows[0], error: null, count };
        }
        return { data: rows, error: null, count };
    }
}

function normalizeValue(v) {
    // Objects/arrays → JSON (our schema uses jsonb, not text[]), Dates → ISO
    if (v === null || v === undefined) return null;
    if (v instanceof Date) return v.toISOString();
    if (typeof v === 'object') return JSON.stringify(v);
    return v;
}

// ===========================================================================
// Client wrapper
// ===========================================================================

const client = {
    from(table) {
        return new QueryBuilder(table);
    },
    rpc(_name, _params) {
        return Promise.resolve({
            data: null,
            error: new Error('rpc() not supported in pg adapter — replace with direct SQL'),
        });
    },
    storage: {
        from() {
            return {
                upload: () => Promise.resolve({ data: null, error: new Error('storage not supported') }),
                remove: () => Promise.resolve({ data: null, error: new Error('storage not supported') }),
                getPublicUrl: () => ({ data: { publicUrl: '' } }),
            };
        },
    },
    _pool: pool, // escape hatch for direct queries if needed
};

module.exports = client;

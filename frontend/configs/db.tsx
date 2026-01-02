// import { neon } from '@neondatabase/serverless';
// import { drizzle } from 'drizzle-orm/neon-http';
// const sql = neon(process.env.NEXT_PUBLIC_DB_CONNECTION_STRING!);
// export const db = drizzle({ client: sql });

import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

const pool = new Pool({
  connectionString: process.env.NEXT_PUBLIC_DB_CONNECTION_STRING,
});

export const db = drizzle(pool, {
  schema,
});

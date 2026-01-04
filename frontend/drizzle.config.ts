import { defineConfig } from "drizzle-kit";
import dotenv from 'dotenv';

// Load variables from .env.local
dotenv.config({ path: '.env.local' });

export default defineConfig({
  schema: "./configs/schema.ts",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.NEXT_PUBLIC_DB_CONNECTION_STRING as string,
  },
});
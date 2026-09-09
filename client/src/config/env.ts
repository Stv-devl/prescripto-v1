/**
 * Environment configuration with dev fallbacks.
 * VITE_API_URL should be the server origin (e.g. "http://localhost:8000").
 */
const origin = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const API_BASE_URL = `${origin.replace(/\/+$/, "")}/api`;

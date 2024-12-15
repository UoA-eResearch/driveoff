/// <reference types="vite/client" />

/**
 * Augmenting type information with env variables defined in various .env files.
 */
interface ImportMetaEnv {
    readonly VITE_API_KEY: string
    readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}
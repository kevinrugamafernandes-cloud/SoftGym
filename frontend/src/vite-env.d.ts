/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  // Agrega aquí otras variables de entorno si usas más
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
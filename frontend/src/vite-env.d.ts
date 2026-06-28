/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USER_API: string;
  readonly VITE_ITEM_API: string;
  readonly VITE_NOTIF_API: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

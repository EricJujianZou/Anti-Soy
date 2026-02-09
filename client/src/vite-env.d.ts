/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Google Analytics gtag global
declare function gtag(command: "event", eventName: string, params?: Record<string, unknown>): void;
declare function gtag(command: "config" | "js", ...args: unknown[]): void;

import { createClient } from "@insforge/sdk";

export const INSFORGE_URL =
  process.env.NEXT_PUBLIC_INSFORGE_URL ||
  "https://wen6ngih.us-east.insforge.app";

export const INSFORGE_ANON_KEY =
  process.env.NEXT_PUBLIC_INSFORGE_ANON_KEY ||
  "anon_72e00885ca16e42bbed0182e83cf911642dd814b6b8340cd39452c6bec2ffbad";

export const insforge = createClient({
  baseUrl: INSFORGE_URL,
  anonKey: INSFORGE_ANON_KEY,
});

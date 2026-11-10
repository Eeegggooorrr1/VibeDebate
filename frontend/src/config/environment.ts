function httpUrl(value: string): string {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol))
    throw new Error("Некорректный адрес сервера входа.");
  return url.href.replace(/\/$/, "");
}

export const environment = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(
    /\/$/,
    "",
  ),
  keycloak: {
    url: httpUrl(import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8180"),
    realm: import.meta.env.VITE_KEYCLOAK_REALM || "vibedebate",
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "vibedebate-web",
  },
};

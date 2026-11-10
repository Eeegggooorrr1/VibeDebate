import Keycloak from "keycloak-js";
import { readonly, ref } from "vue";
import { environment } from "../config/environment";

const keycloak = new Keycloak(environment.keycloak);
const authenticated = ref(false);
const initialized = ref(false);
const sessionError = ref("");
let initialization: Promise<void> | undefined;
let refreshing: Promise<boolean> | undefined;

keycloak.onAuthLogout = () => {
  authenticated.value = false;
};
keycloak.onAuthRefreshError = () => {
  keycloak.clearToken();
  authenticated.value = false;
};
keycloak.onTokenExpired = () => {
  void accessToken().catch(() => undefined);
};

export function initializeSession(): Promise<void> {
  initialization ??= (async () => {
    try {
      authenticated.value = await keycloak.init({
        onLoad: "check-sso",
        pkceMethod: "S256",
        checkLoginIframe: false,
        silentCheckSsoRedirectUri: `${location.origin}/silent-check-sso.html`,
        silentCheckSsoFallback: false,
      });
    } catch {
      sessionError.value = "Не удалось подключиться к серверу входа.";
    } finally {
      initialized.value = true;
    }
  })();
  return initialization;
}

export async function accessToken(): Promise<string> {
  if (!keycloak.authenticated) throw new Error("Войдите в аккаунт.");
  try {
    refreshing ??= keycloak.updateToken(30).finally(() => {
      refreshing = undefined;
    });
    await refreshing;
    if (!keycloak.token) throw new Error("Missing access token");
    return keycloak.token;
  } catch {
    keycloak.clearToken();
    authenticated.value = false;
    throw new Error("Сессия завершена. Войдите снова.");
  }
}

export function endSession() {
  keycloak.clearToken();
  authenticated.value = false;
}

export function useSession() {
  return {
    authenticated: readonly(authenticated),
    initialized: readonly(initialized),
    error: readonly(sessionError),
    login: () =>
      keycloak.login({
        locale: "ru",
        redirectUri: `${location.origin}/auth/callback`,
      }),
    register: () =>
      keycloak.register({
        locale: "ru",
        redirectUri: `${location.origin}/auth/callback`,
      }),
    logout: () => keycloak.logout({ redirectUri: location.origin }),
  };
}

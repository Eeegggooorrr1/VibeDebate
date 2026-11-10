from .base import EnvSettings


class KeycloakAdminSettings(EnvSettings):
    keycloak_admin_api_url: str
    keycloak_admin_token_url: str
    keycloak_service_client_id: str
    keycloak_service_client_secret: str

def create_keycloak_admin_settings() -> KeycloakAdminSettings:
    return KeycloakAdminSettings()

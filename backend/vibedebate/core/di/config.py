from dishka import Provider, Scope, provide
from vibedebate.core.config import create_database_settings, create_user_settings, create_seed_settings, create_keycloak_admin_settings


class ConfigProvider(Provider):
    database = provide(staticmethod(create_database_settings), scope=Scope.APP)
    user = provide(staticmethod(create_user_settings), scope=Scope.APP)
    keycloak_admin = provide(
        staticmethod(create_keycloak_admin_settings), scope=Scope.APP
    )
    seed = provide(staticmethod(create_seed_settings), scope=Scope.APP)

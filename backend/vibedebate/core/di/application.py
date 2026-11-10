from dishka import Provider, Scope, provide
from vibedebate.repositories.user import UserRepository
from vibedebate.repositories.catalog import CategoryRepository
from vibedebate.repositories.audit import AuditRepository
from vibedebate.services.user.tokens import TokenVerifier
from vibedebate.services.user.keycloak import KeycloakUserClient
from vibedebate.services.user.profile import UserService
from vibedebate.services.user.administration import UserAdministrationService
from vibedebate.services.catalog.categories import CategoryService
from vibedebate.cli.bootstrap.seed_service import SeedService


class ApplicationProvider(Provider):
    verifier = provide(TokenVerifier, scope=Scope.APP)
    keycloak_client = provide(KeycloakUserClient, scope=Scope.APP)
    user_repository = provide(UserRepository, scope=Scope.REQUEST)
    category_repository = provide(CategoryRepository, scope=Scope.REQUEST)
    audit_repository = provide(AuditRepository, scope=Scope.REQUEST)
    profile_service = provide(UserService, scope=Scope.REQUEST)
    administration_service = provide(UserAdministrationService, scope=Scope.REQUEST)
    category_service = provide(CategoryService, scope=Scope.REQUEST)
    seed_service = provide(SeedService, scope=Scope.REQUEST)

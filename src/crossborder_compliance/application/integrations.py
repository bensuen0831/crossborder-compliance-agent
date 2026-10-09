"""Integration governance use cases over one northbound identity repository."""
from typing import Protocol

from crossborder_compliance.domain.integrations import IntegrationPolicy


class IntegrationFailure(Exception):
    def __init__(self, code, status=403, *, retryable=False, retry_after=None):
        self.code, self.status = code, status
        self.retryable, self.retry_after = retryable, retry_after
        super().__init__(code)


class IntegrationRepositoryPort(Protocol):
    def authenticate(self, bearer): ...
    def context(self, principal, required, project_id=None): ...
    def token(self, command): ...
    def clients(self): ...
    def create_client(self, command, key): ...
    def update_client(self, client_id, command, key): ...
    def rotate_client(self, client_id, command, key): ...
    def bind_project(self, client_id, command, key): ...


class IntegrationService:
    def __init__(self, repository: IntegrationRepositoryPort, policy: IntegrationPolicy):
        self.repository, self.policy = repository, policy

    def authenticate(self, bearer):
        return self.repository.authenticate(bearer)

    def authorize(self, principal, required, project_id=None):
        return self.repository.context(principal, required, project_id)

    def token(self, command):
        return self.repository.token(command)

    def clients(self):
        return self.repository.clients()

    def create_client(self, command, key):
        return self.repository.create_client(command, key)

    def update_client(self, identity, command, key):
        return self.repository.update_client(identity, command, key)

    def rotate_client(self, identity, command, key):
        return self.repository.rotate_client(identity, command, key)

    def bind_project(self, identity, command, key):
        return self.repository.bind_project(identity, command, key)

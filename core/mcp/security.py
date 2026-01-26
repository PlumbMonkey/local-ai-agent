"""Security middleware for MCP servers."""

import hashlib
import hmac
import logging
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """MCP permission levels."""

    # Tool permissions
    TOOLS_LIST = "tools:list"
    TOOLS_CALL = "tools:call"
    TOOLS_CALL_DANGEROUS = "tools:call:dangerous"

    # Resource permissions
    RESOURCES_LIST = "resources:list"
    RESOURCES_READ = "resources:read"
    RESOURCES_WRITE = "resources:write"

    # Prompt permissions
    PROMPTS_LIST = "prompts:list"
    PROMPTS_GET = "prompts:get"

    # Admin permissions
    ADMIN_CONFIG = "admin:config"
    ADMIN_LOGS = "admin:logs"


class Role(BaseModel):
    """Security role with permissions."""

    name: str
    permissions: Set[Permission] = set()
    tool_whitelist: Optional[Set[str]] = None  # None = all tools
    tool_blacklist: Set[str] = set()


# Predefined roles
ROLE_READONLY = Role(
    name="readonly",
    permissions={
        Permission.TOOLS_LIST,
        Permission.RESOURCES_LIST,
        Permission.RESOURCES_READ,
        Permission.PROMPTS_LIST,
        Permission.PROMPTS_GET,
    },
)

ROLE_USER = Role(
    name="user",
    permissions={
        Permission.TOOLS_LIST,
        Permission.TOOLS_CALL,
        Permission.RESOURCES_LIST,
        Permission.RESOURCES_READ,
        Permission.PROMPTS_LIST,
        Permission.PROMPTS_GET,
    },
)

ROLE_ADMIN = Role(
    name="admin",
    permissions=set(Permission),  # All permissions
)


@dataclass
class AuthContext:
    """Authentication context for a request."""

    client_id: str
    authenticated: bool = False
    role: Optional[Role] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: Permission) -> bool:
        """Check if context has a permission."""
        if not self.authenticated or not self.role:
            return False
        return permission in self.role.permissions

    def can_call_tool(self, tool_name: str) -> bool:
        """Check if context can call a specific tool."""
        if not self.has_permission(Permission.TOOLS_CALL):
            return False

        if self.role:
            # Check blacklist
            if tool_name in self.role.tool_blacklist:
                return False
            # Check whitelist if set
            if self.role.tool_whitelist is not None:
                return tool_name in self.role.tool_whitelist

        return True


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> Optional[AuthContext]:
        """
        Authenticate a client.

        Args:
            credentials: Authentication credentials

        Returns:
            AuthContext if authenticated, None otherwise
        """
        pass


class NoAuthProvider(AuthProvider):
    """
    No authentication provider.

    Grants full access to all clients. Use for local development only.
    """

    def __init__(self, default_role: Role = ROLE_USER):
        self.default_role = default_role

    async def authenticate(self, credentials: Dict[str, Any]) -> Optional[AuthContext]:
        """Grant access with default role."""
        client_id = credentials.get("client_id", "anonymous")
        return AuthContext(
            client_id=client_id,
            authenticated=True,
            role=self.default_role,
        )


class TokenAuthProvider(AuthProvider):
    """
    Bearer token authentication provider.

    Validates tokens against a configured set of valid tokens.
    """

    def __init__(self):
        self._tokens: Dict[str, Role] = {}

    def add_token(self, token: str, role: Role) -> None:
        """Add a valid token with associated role."""
        token_hash = self._hash_token(token)
        self._tokens[token_hash] = role

    def generate_token(self, role: Role) -> str:
        """Generate a new token for a role."""
        token = secrets.token_urlsafe(32)
        self.add_token(token, role)
        return token

    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        token_hash = self._hash_token(token)
        if token_hash in self._tokens:
            del self._tokens[token_hash]
            return True
        return False

    def _hash_token(self, token: str) -> str:
        """Hash a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def authenticate(self, credentials: Dict[str, Any]) -> Optional[AuthContext]:
        """Authenticate using bearer token."""
        token = credentials.get("token") or credentials.get("bearer")
        if not token:
            return None

        token_hash = self._hash_token(token)
        role = self._tokens.get(token_hash)

        if role:
            return AuthContext(
                client_id=token_hash[:16],  # Use part of hash as client ID
                authenticated=True,
                role=role,
            )

        return None


class HMACAuthProvider(AuthProvider):
    """
    HMAC signature authentication for API requests.

    Validates request signatures using shared secrets.
    """

    def __init__(self):
        self._clients: Dict[str, tuple[str, Role]] = {}  # client_id -> (secret, role)

    def add_client(self, client_id: str, secret: str, role: Role) -> None:
        """Add a client with shared secret."""
        self._clients[client_id] = (secret, role)

    def generate_client(self, client_id: str, role: Role) -> str:
        """Generate a new client secret."""
        secret = secrets.token_urlsafe(32)
        self.add_client(client_id, secret, role)
        return secret

    def _compute_signature(self, client_id: str, timestamp: str, body: str) -> str:
        """Compute HMAC signature."""
        secret, _ = self._clients.get(client_id, ("", None))
        message = f"{client_id}:{timestamp}:{body}"
        return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    async def authenticate(self, credentials: Dict[str, Any]) -> Optional[AuthContext]:
        """Authenticate using HMAC signature."""
        client_id = credentials.get("client_id")
        timestamp = credentials.get("timestamp")
        signature = credentials.get("signature")
        body = credentials.get("body", "")

        if not all([client_id, timestamp, signature]):
            return None

        # Check timestamp freshness (5 minute window)
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > 300:
                logger.warning(f"Stale timestamp from client {client_id}")
                return None
        except ValueError:
            return None

        # Verify signature
        if client_id not in self._clients:
            return None

        expected = self._compute_signature(client_id, timestamp, body)
        if not hmac.compare_digest(signature, expected):
            logger.warning(f"Invalid signature from client {client_id}")
            return None

        _, role = self._clients[client_id]
        return AuthContext(
            client_id=client_id,
            authenticated=True,
            role=role,
        )


class SecurityMiddleware:
    """
    Security middleware for MCP servers.

    Provides:
    - Authentication via pluggable providers
    - Authorization via role-based permissions
    - Audit logging
    """

    def __init__(
        self,
        auth_provider: Optional[AuthProvider] = None,
        audit_log: bool = True,
    ):
        """
        Initialize security middleware.

        Args:
            auth_provider: Authentication provider (defaults to NoAuthProvider)
            audit_log: Whether to log security events
        """
        self.auth_provider = auth_provider or NoAuthProvider()
        self.audit_log = audit_log
        self._audit_handlers: List[Callable] = []

    def add_audit_handler(self, handler: Callable) -> None:
        """Add an audit event handler."""
        self._audit_handlers.append(handler)

    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """
        Authenticate a request.

        Returns an unauthenticated context if authentication fails.
        """
        try:
            context = await self.auth_provider.authenticate(credentials)
            if context:
                self._log_audit("auth_success", context.client_id)
                return context
        except Exception as e:
            logger.error(f"Authentication error: {e}")

        client_id = credentials.get("client_id", "unknown")
        self._log_audit("auth_failed", client_id)
        return AuthContext(client_id=client_id, authenticated=False)

    def authorize(
        self,
        context: AuthContext,
        permission: Permission,
        resource: Optional[str] = None,
    ) -> bool:
        """
        Check if context is authorized for an action.

        Args:
            context: Authentication context
            permission: Required permission
            resource: Optional resource identifier (e.g., tool name)

        Returns:
            True if authorized
        """
        if not context.authenticated:
            self._log_audit("authz_denied", context.client_id, permission=permission.value)
            return False

        # Check permission
        if permission == Permission.TOOLS_CALL and resource:
            allowed = context.can_call_tool(resource)
        else:
            allowed = context.has_permission(permission)

        if allowed:
            self._log_audit(
                "authz_granted",
                context.client_id,
                permission=permission.value,
                resource=resource,
            )
        else:
            self._log_audit(
                "authz_denied",
                context.client_id,
                permission=permission.value,
                resource=resource,
            )

        return allowed

    def _log_audit(self, event: str, client_id: str, **kwargs) -> None:
        """Log an audit event."""
        if not self.audit_log:
            return

        entry = {
            "event": event,
            "client_id": client_id,
            "timestamp": time.time(),
            **kwargs,
        }

        logger.info(f"AUDIT: {entry}")

        for handler in self._audit_handlers:
            try:
                handler(entry)
            except Exception as e:
                logger.error(f"Audit handler error: {e}")


# Default security middleware (no auth for local development)
default_security = SecurityMiddleware()

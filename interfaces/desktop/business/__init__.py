"""Business Management Module for Gene.

Provides local database storage and query capabilities for business data:
- Contacts & Clients
- Products & Services
- Invoices & Transactions
- Tasks & Projects
- Notes & Documents
"""

from .database import BusinessDatabase
from .queries import BusinessQueryHandler

__all__ = ["BusinessDatabase", "BusinessQueryHandler"]

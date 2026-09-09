"""Re-export Base and mixins for convenient model imports."""

from app.core.database import Base, TenantMixin, TimestampMixin

__all__ = ["Base", "TenantMixin", "TimestampMixin"]

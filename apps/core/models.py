import uuid

from django.db import models


class BaseModel(models.Model):
    """Abstract base for all domain models.

    Provides consistent UUID primary keys and automatic timestamps.
    Every model in the project should inherit from this (except User,
    which inherits from AbstractBaseUser and defines its own id/created_at).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

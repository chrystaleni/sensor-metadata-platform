from django.db import models


class Department(models.Model):
    """Local fixture model for running the metadata app independently."""

    name = models.CharField(max_length=120, unique=True)

    class Meta:
        swappable = "METADATA_DEPARTMENT_MODEL"

    def __str__(self):
        return self.name

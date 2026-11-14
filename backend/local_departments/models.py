from django.db import models


class Organisation(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    """Local fixture model for running the metadata app independently."""

    name = models.CharField(max_length=120, unique=True)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="departments",
    )

    class Meta:
        swappable = "METADATA_DEPARTMENT_MODEL"

    def __str__(self):
        return self.name

from django.db import models


class OrganisationManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)


class Organisation(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=120, unique=True)
    objects = OrganisationManager()

    def natural_key(self):
        return (self.code,)

    def __str__(self):
        return self.name


class Department(models.Model):
    """Local fixture model for running the metadata app independently."""

    name = models.CharField(max_length=120)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="departments",
    )

    class Meta:
        swappable = "METADATA_DEPARTMENT_MODEL"
        constraints = [
            models.UniqueConstraint(fields=("organisation", "name"), name="local_department_organisation_name_uniq"),
        ]

    def __str__(self):
        return self.name

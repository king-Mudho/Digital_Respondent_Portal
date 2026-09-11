from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """Internal user roles per docs/18_DATA_PRIVACY_AND_COMPLIANCE.md's access
    control matrix. Public respondents never need an account (FR-16,
    docs/02_PRODUCT_REQUIREMENTS.md)."""

    PI_ADMIN = "PI_ADMIN"
    SUPERVISOR_READONLY = "SUPERVISOR_READONLY"
    FIELD_COORDINATOR = "FIELD_COORDINATOR"
    CONTACT_RA = "CONTACT_RA"
    QUAN_QA_RA = "QUAN_QA_RA"
    KII_RA = "KII_RA"
    DOCUMENTARY_RA = "DOCUMENTARY_RA"
    ANALYST = "ANALYST"

    NAME_CHOICES = [
        (PI_ADMIN, "PI / System Admin"),
        (SUPERVISOR_READONLY, "Supervisor (read-only)"),
        (FIELD_COORDINATOR, "Field / Digital Coordinator"),
        (CONTACT_RA, "Contact RA"),
        (QUAN_QA_RA, "QUAN/Kobo QA RA"),
        (KII_RA, "KII RA"),
        (DOCUMENTARY_RA, "Documentary RA"),
        (ANALYST, "Data Analyst"),
    ]

    name = models.CharField(max_length=32, choices=NAME_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()


class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True)

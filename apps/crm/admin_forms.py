"""CRM admin formalar."""

from django import forms

from apps.crm.models import Organization
from apps.crm_core.onboarding import OwnerProvisioningError, validate_organization_owner
from apps.users.models import UserRole


class OrganizationAdminForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        owner = cleaned.get('owner')
        business_type = cleaned.get('business_type')
        if owner and business_type:
            org = Organization(
                owner=owner,
                business_type=business_type,
                name=cleaned.get('name') or '',
                org_type=cleaned.get('org_type') or Organization.OrgType.RESTAURANT,
            )
            try:
                validate_organization_owner(org, exclude_pk=self.instance.pk if self.instance else None)
            except OwnerProvisioningError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return cleaned

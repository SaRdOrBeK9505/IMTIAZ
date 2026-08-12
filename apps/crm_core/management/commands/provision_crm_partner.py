"""Admin: yangi CRM hamkor (owner + organization + filial) yaratish."""

from django.core.management.base import BaseCommand, CommandError

from apps.crm.models import BusinessType
from apps.crm_core.onboarding import OwnerProvisioningError, provision_owner_with_organization


class Command(BaseCommand):
    help = 'CRM hamkor yaratish — owner + organization + birinchi filial (admin workflow).'

    def add_arguments(self, parser):
        parser.add_argument('--phone', required=True)
        parser.add_argument('--password', required=True)
        parser.add_argument('--first-name', required=True)
        parser.add_argument('--last-name', default='')
        parser.add_argument('--organization', required=True)
        parser.add_argument('--business-type', choices=['restaurant', 'travel'], required=True)
        parser.add_argument('--branch', default='Asosiy filial')
        parser.add_argument('--city', default='')

    def handle(self, *args, **options):
        try:
            user, org, branch = provision_owner_with_organization(
                phone=options['phone'],
                password=options['password'],
                first_name=options['first_name'],
                last_name=options['last_name'],
                organization_name=options['organization'],
                business_type=options['business_type'],
                branch_name=options['branch'],
                city=options['city'],
            )
        except OwnerProvisioningError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f'Yaratildi: user={user.id} org={org.name} branch={branch.name}'
        ))

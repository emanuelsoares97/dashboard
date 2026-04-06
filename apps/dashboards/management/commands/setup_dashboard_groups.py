from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.dashboards.permissions import DASHBOARD_ACCESS_GROUPS


class Command(BaseCommand):
    help = 'Cria os grupos base de acesso ao dashboard (idempotente).'

    def handle(self, *args, **options):
        created_count = 0

        for group_name in DASHBOARD_ACCESS_GROUPS:
            _, created = Group.objects.get_or_create(name=group_name)
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Grupo criado: {group_name}'))
            else:
                self.stdout.write(f'Grupo ja existente: {group_name}')

        self.stdout.write(self.style.SUCCESS(f'Concluido. Novos grupos: {created_count}'))

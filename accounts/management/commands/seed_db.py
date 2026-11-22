from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Team, User


class Command(BaseCommand):
    help = "Seed database with 1 Admin user, 2 Teams, and 2 Team Member accounts"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")

        # 1. Create 2 Teams
        team_alpha, _ = Team.objects.get_or_create(
            name="Engineering Team",
            defaults={"description": "Software engineering and backend development team"},
        )
        team_beta, _ = Team.objects.get_or_create(
            name="Marketing Team",
            defaults={"description": "Product marketing and growth strategy team"},
        )

        # 2. Create 1 Admin User (no specific team required)
        admin_user, admin_created = User.objects.get_or_create(
            username="seed_admin",
            defaults={
                "email": "seed_admin@bacbon.com",
                "first_name": "System",
                "last_name": "Admin",
                "role": User.Role.ADMIN,
                "team": None,
                "is_staff": True,
            },
        )
        if admin_created:
            admin_user.set_password("Admin123!")
            admin_user.save()

        # 3. Create 2 Team Member Accounts
        member_one, m1_created = User.objects.get_or_create(
            username="member_eng",
            defaults={
                "email": "member_eng@bacbon.com",
                "first_name": "Arif",
                "last_name": "Hasan",
                "role": User.Role.TEAM_MEMBER,
                "team": team_alpha,
            },
        )
        if m1_created:
            member_one.set_password("Member123!")
            member_one.save()

        member_two, m2_created = User.objects.get_or_create(
            username="member_mkt",
            defaults={
                "email": "member_mkt@bacbon.com",
                "first_name": "Nusrat",
                "last_name": "Jahan",
                "role": User.Role.TEAM_MEMBER,
                "team": team_beta,
            },
        )
        if m2_created:
            member_two.set_password("Member123!")
            member_two.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Database seeded successfully: 2 Teams, 1 Admin (seed_admin), "
                "and 2 Team Members (member_eng, member_mkt)."
            )
        )
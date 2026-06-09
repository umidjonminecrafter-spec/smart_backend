import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from organizations.models import Organization, Tariff
from crm.models import Pipeline, Source, LostReason, Section
from finance.models import ExpenseCategory, ExpenseSubcategory

User = get_user_model()

print("Starting SmartTalim data initialization...")

# 1. Create Tariffs
tariffs = [
    {"name": "Basic", "price": 49.00, "features": {"students_limit": 100, "branches_limit": 1}},
    {"name": "Premium", "price": 99.00, "features": {"students_limit": 500, "branches_limit": 3}},
    {"name": "Enterprise", "price": 249.00, "features": {"students_limit": 5000, "branches_limit": 10}},
]

for t_data in tariffs:
    t, created = Tariff.objects.get_or_create(name=t_data["name"], defaults=t_data)
    if created:
        print(f"Created tariff: {t.name}")

# 2. Create Default Organization for Superuser
org, created = Organization.objects.get_or_create(
    name="SmartTalim HQ",
    defaults={"subdomain": "hq"}
)
if created:
    print(f"Created organization: {org.name}")

# 3. Create Superuser
if not User.objects.filter(username="admin").exists():
    superuser = User.objects.create_superuser(
        username="admin",
        password="adminpassword123",
        email="admin@smarttalim.com",
        first_name="System",
        last_name="Administrator",
        phone="+998901234567",
        role="owner",
        organization=org
    )
    print("Created superuser 'admin' with password 'adminpassword123'")
else:
    print("Superuser 'admin' already exists.")

# 4. Create CRM defaults linked to Organization
# Pipeline stages
stages = [
    ("New Lead", 1),
    ("Contacted", 2),
    ("Meeting Scheduled", 3),
    ("Trial Lesson", 4),
    ("Negotiation", 5),
    ("Closed Won", 6),
    ("Closed Lost", 7)
]
for name, order in stages:
    stage, created = Pipeline.objects.get_or_create(
        organization=org,
        name=name,
        defaults={"order": order}
    )
    if created:
        print(f"Created pipeline stage: {stage.name}")

# Sources
sources = ["Google", "Facebook", "Instagram", "Telegram", "Referral", "Walk-in"]
for name in sources:
    source, created = Source.objects.get_or_create(
        organization=org,
        name=name
    )
    if created:
        print(f"Created source: {source.name}")

# Lost reasons
reasons = ["Too expensive", "Inconvenient location", "Schedule conflict", "No response", "Chose competitor"]
for reason_text in reasons:
    reason, created = LostReason.objects.get_or_create(
        organization=org,
        reason=reason_text
    )
    if created:
        print(f"Created lost reason: {reason.reason}")

# Sections
sections = ["English Language", "Mathematics", "Programming", "Physics"]
for name in sections:
    section, created = Section.objects.get_or_create(
        organization=org,
        name=name
    )
    if created:
        print(f"Created section: {section.name}")

# 5. Create Expense categories and subcategories
expenses = {
    "Rent": [],
    "Salaries": [],
    "Marketing": ["SMM", "Flyers", "Ads"],
    "Utilities": ["Electricity", "Water", "Internet", "Heating"],
    "Office Supplies": ["Stationery", "Books"]
}

for cat_name, subcats in expenses.items():
    cat, created = ExpenseCategory.objects.get_or_create(
        organization=org,
        name=cat_name
    )
    if created:
        print(f"Created expense category: {cat.name}")
    for subcat_name in subcats:
        subcat, sub_created = ExpenseSubcategory.objects.get_or_create(
            organization=org,
            category=cat,
            name=subcat_name
        )
        if sub_created:
            print(f"  Created subcategory: {subcat.name}")

print("SmartTalim data initialization completed successfully!")

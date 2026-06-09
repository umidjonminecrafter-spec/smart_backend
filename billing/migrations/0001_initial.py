import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organizations', '0009_backupsetting'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillingHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('plan_name', models.CharField(max_length=100)),
                ('months', models.IntegerField()),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='Billing_billinghistorys', to='organizations.branch')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='billinghistorys', to='organizations.organization')),
            ],
        ),
    ]

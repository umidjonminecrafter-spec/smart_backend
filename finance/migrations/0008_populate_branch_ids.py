from django.db import migrations

def populate_branches(apps, schema_editor):
    Cashbox = apps.get_model('finance', 'Cashbox')
    Transaction = apps.get_model('finance', 'Transaction')
    Branch = apps.get_model('organizations', 'Branch')

    # 1. Populate Cashbox branch_id
    for cb in Cashbox.objects.filter(branch__isnull=True):
        first_branch = Branch.objects.filter(organization_id=cb.organization_id).first()
        if first_branch:
            cb.branch = first_branch
            cb.save(update_fields=['branch'])

    # 2. Populate Transaction branch_id
    for tx in Transaction.objects.filter(branch__isnull=True):
        branch_id = None
        
        # Check source payment
        try:
            if tx.source_payment:
                branch_id = tx.source_payment.branch_id
        except Exception:
            pass
            
        # Check source expense
        try:
            if not branch_id and tx.source_expense:
                branch_id = tx.source_expense.branch_id
        except Exception:
            pass
            
        # Check source cashtransaction
        try:
            if not branch_id and tx.source_cashtransaction:
                branch_id = tx.source_cashtransaction.branch_id
        except Exception:
            pass
        
        # Fallback to cashbox branch
        if not branch_id and tx.cashbox:
            branch_id = tx.cashbox.branch_id
            
        if branch_id:
            tx.branch_id = branch_id
            tx.save(update_fields=['branch_id'])

def rollback_branches(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_transaction_source_cashtransaction_and_more'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_branches, rollback_branches),
    ]

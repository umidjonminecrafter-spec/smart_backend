from django.db import migrations

def refine_branches(apps, schema_editor):
    Cashbox = apps.get_model('finance', 'Cashbox')
    Payment = apps.get_model('finance', 'Payment')
    Expense = apps.get_model('finance', 'Expense')
    Transaction = apps.get_model('finance', 'Transaction')
    Branch = apps.get_model('organizations', 'Branch')

    for cb in Cashbox.objects.all():
        branch = None
        
        # Try to find a branch from payments
        try:
            payment = Payment.objects.filter(cashbox=cb, branch__isnull=False).first()
            if payment:
                branch = payment.branch
        except Exception:
            pass
            
        # Try to find a branch from expenses
        try:
            if not branch:
                expense = Expense.objects.filter(cashbox=cb, branch__isnull=False).first()
                if expense:
                    branch = expense.branch
        except Exception:
            pass
            
        # Try to find a branch from transactions
        try:
            if not branch:
                tx = Transaction.objects.filter(cashbox=cb, branch__isnull=False).first()
                if tx:
                    branch = tx.branch
        except Exception:
            pass
                    
        # If we found a branch, assign it to the cashbox
        if branch:
            cb.branch = branch
            cb.save(update_fields=['branch'])
            
    # Now sync all Transaction branch_ids based on their source or their cashbox
    for tx in Transaction.objects.all():
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

def rollback_refine(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0008_populate_branch_ids'),
    ]

    operations = [
        migrations.RunPython(refine_branches, rollback_refine),
    ]

from rest_framework import serializers
from finance.models import (
    ExpenseCategory, ExpenseSubcategory, Expense, MonthlyIncome,
    Payment, Sale, Bonus, Fine, Salary, TeacherSalaryRule, TeacherSalaryCalculation, Cashbox
)
from academics.serializers import StudentSerializer
from accounts.serializers import UserSerializer
from .models import FinanceSetting, StaffSalaryPercent,CashTransaction,TransactionCategory
class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class ExpenseSubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = ExpenseSubcategory
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')
import datetime
import json
from .models import Expense, Cashbox

class TransactionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionCategory
        fields = ['id', 'name', 'type', 'created_at']
        read_only_fields = ['id', 'created_at']





class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', default='', read_only=True)
    cashbox_name = serializers.CharField(source='cashbox.name', read_only=True)

    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Frontend fields mapping
        if 'expense_date' in data and 'date' not in data:
            data['date'] = data['expense_date']

        if 'date' in data and data['date']:
            try:
                datetime.date.fromisoformat(str(data['date']))
            except ValueError:
                raise serializers.ValidationError(
                    {"expense_date": "Sana formati noto'g'ri (YYYY-MM-DD bo'lishi kerak)."})

        request = self.context.get('request')
        user = request.user if request else None

        if user and user.is_authenticated:
            full_name = user.get_full_name().strip()
            created_by = full_name if full_name else user.username
        else:
            created_by = "Tizim"

        # 🌟 Eng muhim joyi: Frontend yuborgan payment_type (Kassa ID) ni cashbox maydoniga o'giramiz
        payment_type = data.get('payment_type')
        if payment_type:
            data['cashbox'] = payment_type  # Modelga cashbox_id bo'lib boradi

        recipient = data.get('recipient', '')
        comment = data.get('comment', '') or data.get('izoh', '')
        name = data.get('name', '') or data.get('title', '') or data.get('nomi', '')

        packed_data = {
            'recipient': recipient,
            'payment_type': payment_type,
            'comment': comment,
            'name': name,
            'created_by': created_by
        }
        data['description'] = json.dumps(packed_data, ensure_ascii=False)

        return super().to_internal_value(data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Default fallbacks
        rep['recipient'] = ''
        rep['payment_type'] = instance.cashbox_id if instance.cashbox else None
        rep['comment'] = instance.description or ''
        rep['izoh'] = instance.description or ''
        rep['name'] = instance.description or ''
        rep['title'] = instance.description or ''
        rep['created_by'] = 'Admin'
        rep['expense_date'] = instance.date.isoformat() if instance.date else None

        if instance.description:
            try:
                unpacked = json.loads(instance.description)
                if isinstance(unpacked, dict):
                    rep['recipient'] = unpacked.get('recipient', '')
                    rep['payment_type'] = unpacked.get('payment_type') or instance.cashbox_id
                    rep['comment'] = unpacked.get('comment', '')
                    rep['izoh'] = unpacked.get('comment', '')
                    rep['name'] = unpacked.get('name') or unpacked.get('comment') or (
                        instance.category.name if instance.category else 'Xarajat')
                    rep['title'] = rep['name']
                    rep['created_by'] = unpacked.get('created_by') or 'Admin'
            except json.JSONDecodeError:
                pass

        return rep

class MonthlyIncomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyIncome
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.__str__', read_only=True)
    employee = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

    def get_employee(self, obj):
        if obj.employee:
            parts = [obj.employee.first_name, obj.employee.last_name]
            full_name = " ".join([p for p in parts if p]).strip()
            return full_name if full_name else obj.employee.username
        return None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        method = instance.payment_method
        rep['type'] = method
        rep['payment_type'] = method
        rep['employee_name'] = rep.get('employee') or "Noma'lum"
        rep['note'] = instance.comment or ""
        rep['izoh'] = instance.comment or ""
        return rep

class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class BonusSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)

    class Meta:
        model = Bonus
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class FineSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)

    class Meta:
        model = Fine
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class SalarySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)

    class Meta:
        model = Salary
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class TeacherSalaryRuleSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.get_full_name', default='Standart', read_only=True)

    class Meta:
        model = TeacherSalaryRule
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Map frontend payload fields to database model fields
        percent_per_student = data.get('percent_per_student')
        fixed_bonus = data.get('fixed_bonus')
        
        try:
            val_pct = float(percent_per_student) if percent_per_student is not None else 0
            val_fix = float(fixed_bonus) if fixed_bonus is not None else 0
        except ValueError:
            val_pct = 0
            val_fix = 0
            
        if val_pct > 0:
            data['rule_type'] = 'percentage'
            data['rate'] = val_pct
        elif val_fix > 0:
            data['rule_type'] = 'fixed'
            data['rate'] = val_fix
        else:
            # Fallback values
            if 'rule_type' not in data:
                data['rule_type'] = 'fixed'
            if 'rate' not in data:
                data['rate'] = 0.0
                
        # Set period from effective_from or current month
        if 'period' not in data or not data['period']:
            import datetime
            effective_from = data.get('effective_from')
            if effective_from:
                try:
                    # '2026-05-30' -> '2026-05'
                    parts = effective_from.split('-')
                    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit() or len(parts[0]) != 4 or len(parts[1]) != 2:
                        raise ValueError()
                    data['period'] = f"{parts[0]}-{parts[1]}"
                except Exception:
                    raise serializers.ValidationError({"effective_from": "Sana formati noto'g'ri (YYYY-MM-DD bo'lishi kerak)."})
            else:
                data['period'] = datetime.date.today().strftime('%Y-%m')
                
        return super().to_internal_value(data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        
        # Map database fields back to frontend expected properties
        is_percentage = instance.rule_type == 'percentage'
        
        rep['percent_per_student'] = float(instance.rate) if is_percentage else 0.0
        rep['fixed_bonus'] = float(instance.rate) if not is_percentage else 0.0
        
        # Fallbacks for dates
        rep['effective_from'] = instance.created_at.date().isoformat() if instance.created_at else None
        rep['effective_to'] = None
        
        return rep

class TeacherSalaryCalculationSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)

    class Meta:
        model = TeacherSalaryCalculation
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class CashboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cashbox
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class CashTransactionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    cashbox_name = serializers.CharField(source='cashbox.name', read_only=True)

    class Meta:
        model = CashTransaction
        fields = [
            'id', 'cashbox', 'cashbox_name', 'transaction_type',
            'payment_method', 'amount', 'date', 'student',
            'student_name', 'description'
        ]
class FinanceSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceSetting
        fields = '__all__'
        read_only_fields = ('organization', 'branch', 'created_at', 'updated_at')

    def validate(self, attrs):
        # Hozirgi holatni olish yoki yangi kelayotgan qiymatni tekshirish
        is_bonus = attrs.get('is_bonus_enabled', getattr(self.instance, 'is_bonus_enabled', True))
        is_auto_discount = attrs.get('is_auto_discount_enabled',
                                     getattr(self.instance, 'is_auto_discount_enabled', False))

        # Talab: Bonus turlari o'chirilgan bo'lsa, chegirma yoqishga ruxsat bermaslik
        if not is_bonus and is_auto_discount:
            raise serializers.ValidationError({
                "is_auto_discount_enabled": "Bonus turlari o'chirilgan holatda avtochegirmani yoqish taqiqlanadi!"
            })
        return attrs

from .models import Transaction, FinanceAction
class StaffSalaryPercentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffSalaryPercent
        fields = '__all__'
        read_only_fields = ('organization', 'branch', 'created_at', 'updated_at')
class TransactionSerializer(serializers.ModelSerializer):
    cashbox_name = serializers.CharField(source='cashbox.name', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True, default=None)
    employee_name = serializers.CharField(source='employee.username', read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = [
            'id', 'cashbox', 'cashbox_name', 'amount', 'type',
            'category', 'student', 'student_name', 'employee',
            'employee_name', 'description', 'created_at'
        ]

class FinanceActionSerializer(serializers.ModelSerializer):
    # Bu maydon frontend'da kassani tanlash uchun kerak bo'ladi, lekin modelning o'zida yo'q
    cashbox = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = FinanceAction
        fields = [
            'id', 'action_type', 'target_type', 'student',
            'employee', 'amount', 'reason', 'cashbox', 'created_at'
        ]
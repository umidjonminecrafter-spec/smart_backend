from rest_framework import serializers
from django.contrib.auth import get_user_model
from organizations.models import Organization, Branch

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role', 'position', 'organization',
                  'organization_name', 'branch', 'branch_name', 'photo', 'salary_percentage')
        read_only_fields = ('id', 'role')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    organization_name = serializers.CharField(write_only=True, required=False)
    full_name = serializers.CharField(write_only=True, required=True)
    phone = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('password', 'email', 'phone', 'organization_name', 'full_name')

    def validate(self, attrs):
        phone = attrs.get('phone', '')
        if not phone:
            raise serializers.ValidationError({"phone": "Telefon raqami kiritilishi shart."})

        cleaned = ''.join(c for c in phone if c.isdigit())

        if len(cleaned) == 9:
            cleaned = '998' + cleaned

        if not cleaned.startswith('998') or len(cleaned) != 12:
            raise serializers.ValidationError({
                "phone": "Telefon raqami noto'g'ri formatda. Loyihada O'zbekiston raqamlari (+998XXXXXXXXX) qabul qilinadi."
            })

        formatted_phone = '+' + cleaned
        attrs['phone'] = formatted_phone
        attrs['username'] = formatted_phone

        if User.objects.filter(username=formatted_phone).exists():
            raise serializers.ValidationError({
                "phone": "Ushbu telefon raqamga ega foydalanuvchi allaqachon ro'yxatdan o'tgan."
            })

        full_name = attrs.get('full_name', '')
        if not full_name or not full_name.strip():
            raise serializers.ValidationError({"full_name": "Ism va Familiya kiritilishi shart."})

        return attrs

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', '')
        org_name = validated_data.pop('organization_name', '')

        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')

        if full_name and not (first_name or last_name):
            parts = full_name.split(maxsplit=1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]

        organization = None
        if org_name:
            organization = Organization.objects.create(name=org_name)

        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email', ''),
            first_name=first_name,
            last_name=last_name,
            phone=validated_data.get('phone', ''),
            role='owner',
            organization=organization,
            branch=None
        )
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is not correct.")
        return value


from finance.serializers import StaffSalaryPercentSerializer  # 👈 Moliya serializeridan import qilamiz
from finance.models import StaffSalaryPercent


class EmployeeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True, required=False)

    salary_percentage_detail = StaffSalaryPercentSerializer(source='salary_percentage', read_only=True)
    salary_percentage = serializers.PrimaryKeyRelatedField(
        queryset=StaffSalaryPercent.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'email', 'first_name', 'last_name', 'phone', 'role', 'position',
                  'organization', 'branch', 'birth_date', 'gender', 'photo', 'salary_percentage',
                  'salary_percentage_detail')
        read_only_fields = ('id', 'organization', 'branch')

    # 🚀 1-YANGILIK: Abdulmajidga xatolik chiroyli "400 Bad Request" bo'lib borishi uchun:
    def validate(self, attrs):
        role = attrs.get('role')
        salary_percentage = attrs.get('salary_percentage')

        # to_internal_value dan kelgan rolni ham tekshiramiz
        if role == 'teacher' and not salary_percentage:
            raise serializers.ValidationError({
                "salary_percentage": "O'qituvchi yaratish uchun ish haqi foizini yuborish majburiy!"
            })
        return attrs

    def to_internal_value(self, data):
        # Sizning mavjud to_internal_value kodingiz (o'zgarishsiz qoladi)
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        phone = data.get('phone') or data.get('phone_number')
        if phone:
            phone = phone.strip()
            if phone.startswith('998') and not phone.startswith('+'):
                phone = '+' + phone
            data['phone'] = phone
            if not data.get('username'):
                data['username'] = phone

        full_name = data.get('full_name')
        if full_name and not (data.get('first_name') or data.get('last_name')):
            parts = full_name.split(maxsplit=1)
            data['first_name'] = parts[0]
            data['last_name'] = parts[1] if len(parts) > 1 else ''

        position = data.get('position')
        if position and not data.get('role'):
            pos = position.lower()
            if 'teacher' in pos or "o'qituvchi" in pos or "oʻqituvchi" in pos or "o’qituvchi" in pos or "o`qituvchi" in pos:
                data['role'] = 'teacher'
            elif any(x in pos for x in ['ceo', 'director', 'admin']):
                data['role'] = 'admin'
            elif any(x in pos for x in ['manager', 'marketer']):
                data['role'] = 'manager'
            elif 'reception' in pos:
                data['role'] = 'receptionist'
            else:
                data['role'] = 'employee'

        return super().to_internal_value(data)

    # 🚀 2-YANGILIK: create mantiqini xavfsiz va aniq saqlaydigan qildik
    def create(self, validated_data):
        password = validated_data.pop('password', None) or 'smarttalim123'
        salary_percentage = validated_data.pop('salary_percentage', None)  # alohida sug'urib olamiz

        if not validated_data.get('username'):
            validated_data['username'] = validated_data.get('phone', '')

        # Userni yaratamiz
        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        # Foizni majburiy ravishda bog'lab saqlaymiz
        if salary_percentage:
            user.salary_percentage = salary_percentage
            user.save()

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def to_representation(self, instance):
        # Sizning mavjud to_representation kodingiz (o'zgarishsiz qoladi)
        rep = super().to_representation(instance)
        rep['full_name'] = f"{instance.first_name} {instance.last_name}".strip() or instance.username
        if instance.position:
            rep['position'] = instance.position
        else:
            role_to_pos = {
                'owner': 'Owner',
                'admin': 'Administrator',
                'manager': 'Manager',
                'teacher': 'Teacher',
                'receptionist': 'Receptionist',
                'employee': 'Xodim',
                'student': 'Talaba'
            }
            rep['position'] = role_to_pos.get(instance.role, 'Xodim')
        rep['gender'] = 'Erkak' if instance.gender == 'M' else ('Ayol' if instance.gender == 'F' else 'Erkak')
        return rep
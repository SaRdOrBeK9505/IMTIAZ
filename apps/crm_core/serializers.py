"""crm_core serializers."""

from rest_framework import serializers

from apps.crm.models import Branch, BranchStaff


class BranchStaffListSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source='user.phone', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = BranchStaff
        fields = [
            'id', 'phone', 'full_name', 'branch', 'branch_name',
            'role', 'permissions', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class BranchStaffCreateSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.filter(is_active=True))
    role = serializers.CharField(max_length=50, required=False, allow_blank=True)
    permissions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )

    def validate_branch(self, branch):
        organization = self.context['request'].user.organization
        if branch.organization_id != organization.id:
            raise serializers.ValidationError('Filial ushbu tashkilotga tegishli emas.')
        return branch

    def validate_phone(self, value):
        from apps.users.models import User
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('Bu telefon raqam allaqachon ro\'yxatdan o\'tgan.')
        return value


class BranchStaffUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchStaff
        fields = ['role', 'permissions', 'is_active', 'branch']

    def validate_branch(self, branch):
        organization = self.context['request'].user.organization
        if branch.organization_id != organization.id:
            raise serializers.ValidationError('Filial ushbu tashkilotga tegishli emas.')
        return branch


class LeadListSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True, allow_null=True)

    class Meta:
        from apps.crm_core.models import Lead
        model = Lead
        fields = [
            'id', 'title', 'stage', 'vertical', 'customer_name', 'customer_phone',
            'branch', 'branch_name', 'assigned_to', 'assigned_to_name',
            'booking_id', 'metadata', 'created_at', 'updated_at', 'closed_at',
        ]
        read_only_fields = fields


class LeadUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.crm_core.models import Lead
        model = Lead
        fields = ['stage', 'notes', 'assigned_to']

    def validate_stage(self, value):
        from apps.crm_core.models import Lead
        if value not in Lead.Stage.values:
            raise serializers.ValidationError('Noto\'g\'ri bosqich.')
        return value

    def validate_assigned_to(self, user):
        if user is None:
            return user
        organization = self.context['request'].user.organization
        if not organization:
            raise serializers.ValidationError('Tashkilot topilmadi.')
        if getattr(user, 'owned_organization', None) == organization:
            return user
        profile = getattr(user, 'branch_staff_profile', None)
        if profile and profile.branch.organization_id == organization.id and profile.is_active:
            return user
        raise serializers.ValidationError('Foydalanuvchi ushbu tashkilotga tegishli emas.')

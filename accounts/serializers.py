from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from prospects.models import ServiceProfile

class UserSerializer(serializers.ModelSerializer):
    agency_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'agency_profile']

    def get_agency_profile(self, obj):
        profile = ServiceProfile.objects.filter(user=obj, is_active=True).first()
        if not profile:
            profile = ServiceProfile.objects.filter(is_active=True).first()
        if profile:
            return {
                "id": profile.id,
                "name": profile.name,
                "portfolio_url": profile.portfolio_url,
                "service_description": profile.service_description,
            }
        return None


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    agency_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    portfolio_url = serializers.URLField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def create(self, validated_data):
        username = validated_data['username']
        email = validated_data['email']
        password = validated_data['password']
        full_name = validated_data.get('full_name', '')
        agency_name = validated_data.get('agency_name', '') or f"{username}'s Agency"
        portfolio_url = validated_data.get('portfolio_url', '')
        first_name = full_name.split(' ')[0] if full_name else username
        last_name = ' '.join(full_name.split(' ')[1:]) if (full_name and ' ' in full_name) else ''

        # 1. Create Django User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # 2. Create User's Active ServiceProfile
        ServiceProfile.objects.create(
            user=user,
            name=agency_name,
            portfolio_url=portfolio_url or None,
            service_description="Custom technical development, APIs, and business automation",
            target_icp_criteria="Growing businesses, founders, and companies needing technical automation",
            is_active=True
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username_or_email = data.get('username')
        password = data.get('password')

        # Allow login via username or email
        user = authenticate(username=username_or_email, password=password)
        if not user:
            user_obj = User.objects.filter(email=username_or_email).first()
            if user_obj:
                user = authenticate(username=user_obj.username, password=password)

        if not user:
            raise serializers.ValidationError("Invalid credentials. Please verify your username and password.")

        data['user'] = user
        return data

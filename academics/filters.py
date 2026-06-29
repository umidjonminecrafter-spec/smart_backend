import django_filters
from academics.models import Group


class GroupFilter(django_filters.FilterSet):
    """
    GroupViewSet uchun custom FilterSet.
    teacher='' (bo'sh string) yuborilganda ValueError chiqib 500 bermaslik uchun
    NumberFilter ishlatiladi — bo'sh qiymat avtomatik o'tkazib yuboriladi.
    """
    teacher = django_filters.NumberFilter(field_name='teacher', required=False)
    status = django_filters.CharFilter(field_name='status', required=False)
    education_type = django_filters.CharFilter(field_name='education_type', required=False)

    class Meta:
        model = Group
        fields = ['status', 'education_type', 'teacher']

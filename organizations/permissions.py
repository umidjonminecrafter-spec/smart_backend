from rest_framework import permissions


def _resolve_permission_type(request, view):
    action = getattr(view, 'action', None)
    action_map = getattr(view, 'permission_action_map', {}) or {}
    if action in action_map:
        return action_map[action]

    method = request.method.upper()
    if method in permissions.SAFE_METHODS:
        return 'view'
    if method == 'POST':
        return 'create'
    if method in ('PUT', 'PATCH'):
        return 'edit'
    if method == 'DELETE':
        return 'delete'
    return 'view'


def has_role_page_permission(user, organization, page_name, permission_type):
    if not user or not user.is_authenticated or not page_name:
        return False

    if getattr(user, 'is_superuser', False):
        return True

    role = getattr(user, 'role', None)
    if role == 'owner':
        return True
    if role == 'admin':
        return True

    if role == 'student':
        return permission_type == 'view' and page_name in ('Dashboard', 'Profil')

    if role == 'teacher' and page_name == 'Dashboard':
        return permission_type == 'view'

    if page_name == 'Profil':
        return permission_type == 'view'

    permissions_map = getattr(organization, 'role_permissions', None) or {}
    user_position = getattr(user, 'position', '') or ''

    positions_to_check = set()
    for position in user_position.split(','):
        position = position.strip()
        if position:
            positions_to_check.add(position)

    if role:
        positions_to_check.add(role)
        positions_to_check.add(role[:1].upper() + role[1:])

    for position in positions_to_check:
        role_perm = permissions_map.get(position, {})
        page_perms = (role_perm.get('pages') or {}).get(page_name, {})
        if page_perms.get(permission_type):
            return True
        if permission_type in ('create', 'delete') and page_perms.get('edit'):
            return True
    return False


class HasOrganizationPagePermission(permissions.BasePermission):
    """
    Uses the page name declared on a view/viewset to enforce view/create/edit/delete
    permissions from organization.role_permissions.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        page_name = getattr(view, 'permission_page_name', None)
        if not page_name:
            return True

        permission_type = _resolve_permission_type(request, view)
        organization = getattr(request.user, 'organization', None)
        if organization is None and getattr(view, 'allow_without_organization', False):
            return permission_type == 'create'
        return has_role_page_permission(request.user, organization, page_name, permission_type)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        page_name = getattr(view, 'permission_page_name', None)
        if not page_name:
            return True

        permission_type = _resolve_permission_type(request, view)
        organization = getattr(request.user, 'organization', None)
        return has_role_page_permission(request.user, organization, page_name, permission_type)


class IsSameOrganization(permissions.BasePermission):
    """
    Ensures the user can only access objects belonging to their own organization.
    Works with any model that has an `organization` field.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        user_org_id = getattr(request.user, 'organization_id', None)
        obj_org_id = getattr(obj, 'organization_id', None)

        if not user_org_id or not obj_org_id:
            return False

        return user_org_id == obj_org_id


class IsSameBranch(permissions.BasePermission):
    """
    Ensures the user can only access objects belonging to their own branch.
    Falls back to IsSameOrganization if the object or user has no branch.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        user_org_id = getattr(request.user, 'organization_id', None)
        obj_org_id = getattr(obj, 'organization_id', None)

        # Must be same organization first
        if not user_org_id or not obj_org_id or user_org_id != obj_org_id:
            return False

        # If object has no branch, org-level access is enough
        obj_branch_id = getattr(obj, 'branch_id', None)
        if not obj_branch_id:
            return True

        # If user has no branch assigned, allow (org-level user)
        user_branch_id = getattr(request.user, 'branch_id', None)
        if not user_branch_id:
            return True

        return user_branch_id == obj_branch_id


class IsAdminOrOwnerOrReadOnly(permissions.BasePermission):
    """
    Allows read-only access (GET/HEAD/OPTIONS) to any authenticated user,
    but restricts writes (POST/PUT/PATCH/DELETE) only to owner, admin, or superuser.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        page_name = getattr(view, 'permission_page_name', None)
        if page_name:
            permission_type = _resolve_permission_type(request, view)
            organization = getattr(request.user, 'organization', None)
            return has_role_page_permission(request.user, organization, page_name, permission_type)

        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user.is_superuser or 
            (hasattr(request.user, 'role') and request.user.role in ['owner', 'admin'])
        )


class IsGroupAssignedTeacherForAttendance(permissions.BasePermission):
    """
    Allows read access to all authenticated users, but restricts write operations
    to the group's assigned teacher, admin, or owner.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Superuser always has access
        if request.user.is_superuser:
            return True

        role = getattr(request.user, 'role', None)
        position = getattr(request.user, 'position', '') or ''
        pos = position.lower()
        
        # Check if they are teacher by role or position
        is_teacher = (role == 'teacher') or ('teacher' in pos or "o'qituvchi" in pos or "oʻqituvchi" in pos or "o’qituvchi" in pos or "o`qituvchi" in pos)
        is_admin_owner = role in ['admin', 'owner']
        
        if not (is_teacher or is_admin_owner):
            return False

        # If they are admin or owner, bypass assignment check
        if is_admin_owner:
            return True

        if request.method == 'POST':
            # Check group assignment
            group_id = None
            if isinstance(request.data, list):
                if len(request.data) > 0:
                    group_id = request.data[0].get('group')
            else:
                group_id = request.data.get('group')

            if not group_id:
                return False

            from academics.models import Group, GroupTeacher
            try:
                org_id = None
                if hasattr(view, 'get_organization_id'):
                    org_id = view.get_organization_id()
                elif hasattr(request.user, 'organization_id'):
                    org_id = request.user.organization_id
                
                if org_id:
                    group = Group.objects.get(id=group_id, organization_id=org_id)
                else:
                    group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return False

            is_assigned = (group.teacher == request.user) or GroupTeacher.objects.filter(group=group, teacher=request.user).exists()
            return is_assigned

        return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_superuser:
            return True

        role = getattr(request.user, 'role', None)
        position = getattr(request.user, 'position', '') or ''
        pos = position.lower()
        
        is_teacher = (role == 'teacher') or ('teacher' in pos or "o'qituvchi" in pos or "oʻqituvchi" in pos or "o’qituvchi" in pos or "o`qituvchi" in pos)
        is_admin_owner = role in ['admin', 'owner']
        
        if not (is_teacher or is_admin_owner):
            return False
            
        if is_admin_owner:
            return True

        from academics.models import GroupTeacher
        group = obj.group
        is_assigned = (group.teacher == request.user) or GroupTeacher.objects.filter(group=group, teacher=request.user).exists()
        return is_assigned


class IsGroupAssignedTeacherOrAdminOwnerForExam(permissions.BasePermission):
    """
    Allows read access to all authenticated users, but restricts write operations (create/edit/delete)
    to the group's assigned teacher, admin, owner, or superuser.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
            
        if request.user.is_superuser:
            return True

        role = getattr(request.user, 'role', None)
        if role in ['admin', 'owner']:
            return True

        # Check if teacher role
        position = getattr(request.user, 'position', '') or ''
        pos = position.lower()
        is_teacher = (role == 'teacher') or ('teacher' in pos or "o'qituvchi" in pos or "oʻqituvchi" in pos or "o’qituvchi" in pos)

        if not is_teacher:
            return False

        # If it's a POST request to create an Exam or ExamResult, check group/exam assignment
        if request.method == 'POST':
            group_id = request.data.get('group') or request.data.get('group_id')
            exam_id = request.data.get('exam') or request.data.get('exam_id')
            
            from academics.models import Group, Exam
            if not group_id and exam_id:
                try:
                    exam = Exam.objects.get(id=exam_id)
                    group_id = exam.group_id
                except Exam.DoesNotExist:
                    pass

            if not group_id:
                return True

            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return False

            from academics.models import GroupTeacher
            is_assigned = (group.teacher == request.user) or GroupTeacher.objects.filter(group=group, teacher=request.user).exists()
            return is_assigned

        return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_superuser:
            return True

        role = getattr(request.user, 'role', None)
        if role in ['admin', 'owner']:
            return True

        from academics.models import Exam, ExamResult, GroupTeacher
        group = None
        if isinstance(obj, Exam):
            group = obj.group
        elif isinstance(obj, ExamResult):
            group = obj.exam.group

        if not group:
            return False

        is_assigned = (group.teacher == request.user) or GroupTeacher.objects.filter(group=group, teacher=request.user).exists()
        return is_assigned

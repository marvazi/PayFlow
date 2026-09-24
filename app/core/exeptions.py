

class EmailAlreadyExistsError(Exception):
    pass
class CustomerNotFoundError(Exception):
    pass
class InvalidCredentialsError(Exception):
    pass
class InvalidTokenError(Exception):
    pass
class OrganizationNotFoundError(Exception):
    pass
class PermissionDeniedError(Exception):
    pass
class UserNotFoundError(Exception):
    pass
class MembershipAlreadyExistsError(Exception):
    pass
class InvalidMembershipRoleError(Exception):
    pass
class MembershipNotFoundError(Exception):
    pass

class InvoiceNotFoundError(Exception):
    pass

class CustomerAlreadyExistsError(Exception):
    pass
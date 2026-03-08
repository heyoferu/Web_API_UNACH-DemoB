import enum
import uuid
from datetime import date, datetime, timezone

from pydantic import EmailStr
from sqlalchemy import DateTime, ForeignKey
from sqlmodel import Column, Enum, Field, Relationship, SQLModel

from app.core.encryption import EncryptedString


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# --- Enums ---


class UserRole(str, enum.Enum):
    """Roles available in the system."""

    facilitator = "facilitator"
    admin = "admin"
    superuser = "superuser"


class AdminRole(str, enum.Enum):
    """Sub-roles for administrative users."""

    document_validator = "document_validator"
    application_approver = "application_approver"
    system_administrator = "system_administrator"


class Gender(str, enum.Enum):
    """Biological sex / gender options for beneficiaries."""

    male = "male"
    female = "female"
    other = "other"


class ApplicationStatus(str, enum.Enum):
    """Lifecycle statuses for a welfare application."""

    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class DocumentType(str, enum.Enum):
    """Categories of documents attached to an application."""

    id_document = "id_document"
    proof_of_address = "proof_of_address"
    proof_of_income = "proof_of_income"
    birth_certificate = "birth_certificate"
    curp_document = "curp_document"
    other = "other"


class NotificationType(str, enum.Enum):
    """Categories for user notifications."""

    info = "info"
    warning = "warning"
    success = "success"
    error = "error"


# --- User models ---


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    username: str = Field(unique=True, index=True, max_length=150)
    is_active: bool = True
    role: UserRole = Field(
        default=UserRole.facilitator,
        sa_column=Column(Enum(UserRole), nullable=False, default=UserRole.facilitator),
    )
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


# Properties for public self-registration (facilitator role by default)
class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    username: str = Field(max_length=150)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    username: str | None = Field(default=None, max_length=150)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_login: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    # Relationships
    facilitator_profile: "Facilitator" = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False},
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None
    last_login: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# --- Facilitator models ---


class FacilitatorBase(SQLModel):
    phone: str | None = Field(default=None, max_length=20)
    zone: str | None = Field(default=None, max_length=100)
    organization: str | None = Field(default=None, max_length=200)


class FacilitatorCreate(FacilitatorBase):
    user_id: uuid.UUID


class FacilitatorUpdate(SQLModel):
    phone: str | None = Field(default=None, max_length=20)
    zone: str | None = Field(default=None, max_length=100)
    organization: str | None = Field(default=None, max_length=200)


class Facilitator(FacilitatorBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    # Relationships
    user: User = Relationship(back_populates="facilitator_profile")
    beneficiaries: list["Beneficiary"] = Relationship(back_populates="facilitator")


class FacilitatorPublic(FacilitatorBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime | None = None


class FacilitatorsPublic(SQLModel):
    data: list[FacilitatorPublic]
    count: int


# --- Beneficiary models ---


class BeneficiaryBase(SQLModel):
    """Shared fields for beneficiary schemas.

    Note: ``curp``, ``full_name`` and ``address`` are *plaintext* in schemas
    but stored **encrypted** in the DB via ``EncryptedString``.
    """

    curp: str = Field(max_length=18)
    full_name: str = Field(max_length=255)
    date_of_birth: date | None = None
    gender: Gender | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    community: str | None = Field(default=None, max_length=200)
    is_active: bool = True


class BeneficiaryCreate(BeneficiaryBase):
    facilitator_id: uuid.UUID


class BeneficiaryUpdate(SQLModel):
    curp: str | None = Field(default=None, max_length=18)
    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    gender: Gender | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    community: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class Beneficiary(BeneficiaryBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Encrypted columns — ciphertext is longer than plaintext
    curp: str = Field(
        sa_column=Column(EncryptedString(length=512), nullable=False),
    )
    full_name: str = Field(
        sa_column=Column(EncryptedString(length=512), nullable=False),
    )
    address: str | None = Field(
        default=None,
        sa_column=Column(EncryptedString(length=1024), nullable=True),
    )
    gender: Gender | None = Field(
        default=None,
        sa_column=Column(Enum(Gender), nullable=True),
    )
    facilitator_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("facilitator.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    # Relationships
    facilitator: Facilitator = Relationship(back_populates="beneficiaries")
    applications: list["Application"] = Relationship(back_populates="beneficiary")


class BeneficiaryPublic(BeneficiaryBase):
    id: uuid.UUID
    facilitator_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BeneficiariesPublic(SQLModel):
    data: list[BeneficiaryPublic]
    count: int


# --- Application models ---


class ApplicationBase(SQLModel):
    """Shared fields for application schemas."""

    program_name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ApplicationCreate(ApplicationBase):
    beneficiary_id: uuid.UUID


class ApplicationUpdate(SQLModel):
    program_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class Application(ApplicationBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    beneficiary_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("beneficiary.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    status: ApplicationStatus = Field(
        default=ApplicationStatus.draft,
        sa_column=Column(
            Enum(ApplicationStatus),
            nullable=False,
            default=ApplicationStatus.draft,
            index=True,
        ),
    )
    submitted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    reviewed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    reviewed_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    rejection_reason: str | None = Field(default=None, max_length=1000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    # Relationships
    beneficiary: Beneficiary = Relationship(back_populates="applications")
    reviewer: User = Relationship(
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "[Application.reviewed_by]",
        },
    )
    status_history: list["ApplicationStatusHistory"] = Relationship(
        back_populates="application",
    )
    documents: list["Document"] = Relationship(back_populates="application")


class ApplicationPublic(ApplicationBase):
    id: uuid.UUID
    beneficiary_id: uuid.UUID
    status: ApplicationStatus
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by: uuid.UUID | None = None
    rejection_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApplicationsPublic(SQLModel):
    data: list[ApplicationPublic]
    count: int


# --- Application Status History models ---


class ApplicationStatusHistoryBase(SQLModel):
    """Shared fields for status history schemas."""

    previous_status: ApplicationStatus | None = None
    new_status: ApplicationStatus
    comment: str | None = Field(default=None, max_length=1000)


class ApplicationStatusHistoryCreate(SQLModel):
    """Input for creating a status transition (status + optional comment)."""

    new_status: ApplicationStatus
    comment: str | None = Field(default=None, max_length=1000)
    rejection_reason: str | None = Field(default=None, max_length=1000)


class ApplicationStatusHistory(ApplicationStatusHistoryBase, table=True):
    __tablename__ = "application_status_history"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    application_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("application.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    changed_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    changed_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    # Relationships
    application: Application = Relationship(back_populates="status_history")
    user: User = Relationship(
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "[ApplicationStatusHistory.changed_by]",
        },
    )


class ApplicationStatusHistoryPublic(ApplicationStatusHistoryBase):
    id: uuid.UUID
    application_id: uuid.UUID
    changed_by: uuid.UUID | None = None
    changed_at: datetime | None = None


class ApplicationStatusHistoriesPublic(SQLModel):
    data: list[ApplicationStatusHistoryPublic]
    count: int


# --- Document models ---


class DocumentBase(SQLModel):
    """Shared fields for document schemas."""

    document_type: DocumentType
    file_name: str = Field(max_length=255)
    file_url: str = Field(max_length=1024)
    description: str | None = Field(default=None, max_length=500)


class DocumentCreate(DocumentBase):
    application_id: uuid.UUID


class DocumentUpdate(SQLModel):
    document_type: DocumentType | None = None
    file_name: str | None = Field(default=None, max_length=255)
    file_url: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=500)


class Document(DocumentBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    application_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("application.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    document_type: DocumentType = Field(
        sa_column=Column(Enum(DocumentType), nullable=False),
    )
    uploaded_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    uploaded_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    # Relationships
    application: Application = Relationship(back_populates="documents")
    uploader: User = Relationship(
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "[Document.uploaded_by]",
        },
    )


class DocumentPublic(DocumentBase):
    id: uuid.UUID
    application_id: uuid.UUID
    uploaded_by: uuid.UUID | None = None
    uploaded_at: datetime | None = None


class DocumentsPublic(SQLModel):
    data: list[DocumentPublic]
    count: int


# --- AdminUser models ---


class AdminUserBase(SQLModel):
    """Shared fields for admin user schemas."""

    admin_role: AdminRole
    department: str | None = Field(default=None, max_length=200)


class AdminUserCreate(AdminUserBase):
    user_id: uuid.UUID


class AdminUserUpdate(SQLModel):
    admin_role: AdminRole | None = None
    department: str | None = Field(default=None, max_length=200)


class AdminUser(AdminUserBase, table=True):
    __tablename__ = "admin_user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
    )
    admin_role: AdminRole = Field(
        sa_column=Column(Enum(AdminRole), nullable=False),
    )
    mfa_secret: str | None = Field(
        default=None,
        sa_column=Column(EncryptedString(length=512), nullable=True),
    )
    mfa_enabled: bool = Field(default=False)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    # Relationships
    user: User = Relationship(
        sa_relationship_kwargs={"uselist": False},
    )


class AdminUserPublic(AdminUserBase):
    id: uuid.UUID
    user_id: uuid.UUID
    mfa_enabled: bool = False
    created_at: datetime | None = None


class AdminUsersPublic(SQLModel):
    data: list[AdminUserPublic]
    count: int


# --- AuditLog models ---


class AuditLogBase(SQLModel):
    """Shared fields for audit log schemas."""

    action: str = Field(max_length=255)
    resource_type: str = Field(max_length=100)
    resource_id: uuid.UUID
    details: str | None = Field(default=None, max_length=4000)
    ip_address: str | None = Field(default=None, max_length=45)


class AuditLogCreate(AuditLogBase):
    """Input for creating an audit log entry."""

    pass


class AuditLog(AuditLogBase, table=True):
    __tablename__ = "audit_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    resource_type: str = Field(max_length=100, index=True)
    integrity_hash: str = Field(max_length=128)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )

    # Relationships
    user: User = Relationship(
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "[AuditLog.user_id]",
        },
    )


class AuditLogPublic(AuditLogBase):
    id: uuid.UUID
    user_id: uuid.UUID
    integrity_hash: str
    created_at: datetime | None = None


class AuditLogsPublic(SQLModel):
    data: list[AuditLogPublic]
    count: int


# --- Notification models ---


class NotificationBase(SQLModel):
    """Shared fields for notification schemas."""

    title: str = Field(max_length=255)
    message: str = Field(max_length=2000)
    notification_type: NotificationType


class NotificationCreate(NotificationBase):
    """Input for creating a notification.

    ``user_id`` is set by the endpoint (the target user).
    """

    user_id: uuid.UUID


class NotificationUpdate(SQLModel):
    """Input for updating a notification (mark as read)."""

    is_read: bool | None = None


class Notification(NotificationBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    notification_type: NotificationType = Field(
        sa_column=Column(Enum(NotificationType), nullable=False),
    )
    is_read: bool = Field(default=False, index=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )

    # Relationships
    user: User = Relationship(
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "[Notification.user_id]",
        },
    )


class NotificationPublic(NotificationBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_read: bool
    created_at: datetime | None = None


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int


# --- Generic schemas ---


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None
    mfa_verified: bool = False


class MfaSetupResponse(SQLModel):
    """Returned when an admin initiates MFA setup."""

    secret: str
    provisioning_uri: str


class MfaVerifyRequest(SQLModel):
    """Body for verifying a TOTP code (setup confirmation or login)."""

    code: str = Field(min_length=6, max_length=6)


class MfaLoginRequest(SQLModel):
    """Body for the second step of MFA login."""

    mfa_token: str
    code: str = Field(min_length=6, max_length=6)


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

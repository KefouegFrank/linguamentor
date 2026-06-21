"""add email_verified lockout and mfa fields to users

Revision ID: f095a2fc39eb
Revises: 0fbfab7c074a
Create Date: 2026-03-16 00:38:36.747940

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f095a2fc39eb'
down_revision: Union[str, Sequence[str], None] = '0fbfab7c074a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add email verification flag — default FALSE for all users.
    # Wired to SendGrid when email service is added in a later phase.
    op.add_column(
        'users',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        schema='linguamentor'
    )

    # Account lockout — brute force protection on login.
    # failed_login_attempts increments on wrong password.
    # locked_until is set when attempts hit threshold (5 attempts).
    # Both reset on successful login.
    op.add_column(
        'users',
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        schema='linguamentor'
    )
    op.add_column(
        'users',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        schema='linguamentor'
    )

    # MFA — required for admin accounts (PRD §14.2).
    # mfa_totp_secret stores the base32 TOTP seed.
    # mfa_enabled starts FALSE — admin activates it in settings.
    op.add_column(
        'users',
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false'),
        schema='linguamentor'
    )
    op.add_column(
        'users',
        sa.Column('mfa_totp_secret', sa.String(length=64), nullable=True),
        schema='linguamentor'
    )


def downgrade() -> None:
    # Removes in reverse order — MFA first, then lockout, then email_verified
    op.drop_column('users', 'mfa_totp_secret', schema='linguamentor')
    op.drop_column('users', 'mfa_enabled', schema='linguamentor')
    op.drop_column('users', 'locked_until', schema='linguamentor')
    op.drop_column('users', 'failed_login_attempts', schema='linguamentor')
    op.drop_column('users', 'email_verified', schema='linguamentor')

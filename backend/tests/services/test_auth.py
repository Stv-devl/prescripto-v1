"""Unit tests for the auth service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.services.auth import get_me, login, refresh, signup


def _make_user(
    user_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    hashed_password: str = "$2b$12$fakehash",
    role: str = "owner",
    token_version: int = 0,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.tenant_id = tenant_id or uuid.uuid4()
    user.email = email
    user.hashed_password = hashed_password
    user.role = role
    user.token_version = token_version
    return user


def _make_db(scalar_result: object = None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    db.execute.return_value = result
    return db


class TestSignup:
    async def test_signup_success(self) -> None:
        db = _make_db(scalar_result=None)

        with (
            patch("app.services.auth.hash_password", return_value="hashed"),
            patch("app.services.auth.create_access_token", return_value="at"),
            patch("app.services.auth.create_refresh_token", return_value="rt"),
        ):
            user, access, refresh_tok = await signup(db, "new@test.com", "password123", "Cabinet")

        assert access == "at"
        assert refresh_tok == "rt"
        assert db.add.call_count == 2  # tenant + user
        db.commit.assert_awaited_once()

    async def test_signup_duplicate_email(self) -> None:
        existing_user = _make_user()
        db = _make_db(scalar_result=existing_user)

        with pytest.raises(ConflictError, match="email already registered"):
            await signup(db, "existing@test.com", "password123", "Cabinet")


class TestLogin:
    async def test_login_success(self) -> None:
        user = _make_user()
        db = _make_db(scalar_result=user)

        with (
            patch("app.services.auth.verify_password", return_value=True),
            patch("app.services.auth.create_access_token", return_value="at"),
            patch("app.services.auth.create_refresh_token", return_value="rt"),
        ):
            result_user, access, refresh_tok = await login(db, "test@example.com", "password")

        assert result_user is user
        assert access == "at"
        assert refresh_tok == "rt"

    async def test_login_user_not_found(self) -> None:
        db = _make_db(scalar_result=None)

        with pytest.raises(UnauthorizedError, match="invalid login credentials"):
            await login(db, "unknown@test.com", "password")

    async def test_login_wrong_password(self) -> None:
        user = _make_user()
        db = _make_db(scalar_result=user)

        with patch("app.services.auth.verify_password", return_value=False):
            with pytest.raises(UnauthorizedError, match="invalid login credentials"):
                await login(db, "test@example.com", "wrongpass")


class TestRefresh:
    async def test_refresh_success(self) -> None:
        user = _make_user()
        db = _make_db(scalar_result=user)

        with (
            patch(
                "app.services.auth.decode_token",
                return_value={
                    "user_id": str(user.id),
                    "tenant_id": str(user.tenant_id),
                    "type": "refresh",
                    "token_version": 0,
                },
            ),
            patch("app.services.auth.create_access_token", return_value="new_at"),
            patch("app.services.auth.create_refresh_token", return_value="new_rt"),
        ):
            access, refresh_tok = await refresh(db, "old_refresh_token")

        assert access == "new_at"
        assert refresh_tok == "new_rt"

    async def test_refresh_wrong_token_type(self) -> None:
        db = _make_db()

        with patch(
            "app.services.auth.decode_token",
            return_value={"user_id": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4()), "type": "access"},
        ):
            with pytest.raises(UnauthorizedError, match="Invalid token type"):
                await refresh(db, "access_token_not_refresh")

    async def test_refresh_user_deleted(self) -> None:
        db = _make_db(scalar_result=None)

        with patch(
            "app.services.auth.decode_token",
            return_value={"user_id": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4()), "type": "refresh"},
        ):
            with pytest.raises(UnauthorizedError, match="User no longer exists"):
                await refresh(db, "refresh_token_for_deleted_user")


class TestGetMe:
    async def test_get_me_success(self) -> None:
        user = _make_user()
        db = _make_db(scalar_result=user)

        result = await get_me(db, user.id)
        assert result is user

    async def test_get_me_not_found(self) -> None:
        db = _make_db(scalar_result=None)

        with pytest.raises(NotFoundError, match="User not found"):
            await get_me(db, uuid.uuid4())


class TestChangePasswordRevokesRefreshTokens:
    async def test_refresh_rejected_for_token_issued_before_change_password(self) -> None:
        from app.services.auth import change_password

        user = _make_user()
        db = _make_db(scalar_result=user)

        with (
            patch("app.services.auth.verify_password", return_value=True),
            patch("app.services.auth.hash_password", return_value="new_hashed_password"),
        ):
            await change_password(db, user.id, "old_password123", "new_password456")

        with (
            patch(
                "app.services.auth.decode_token",
                return_value={
                    "user_id": str(user.id),
                    "tenant_id": str(user.tenant_id),
                    "type": "refresh",
                },
            ),
            patch("app.services.auth.create_access_token", return_value="new_at"),
            patch("app.services.auth.create_refresh_token", return_value="new_rt"),
        ):
            with pytest.raises(UnauthorizedError, match="revoked"):
                await refresh(db, "refresh_token_issued_before_change_password")

    async def test_refresh_accepted_when_token_version_matches(self) -> None:
        user = _make_user(token_version=0)
        db = _make_db(scalar_result=user)

        with (
            patch(
                "app.services.auth.decode_token",
                return_value={
                    "user_id": str(user.id),
                    "tenant_id": str(user.tenant_id),
                    "type": "refresh",
                    "token_version": 0,
                },
            ),
            patch("app.services.auth.create_access_token", return_value="new_at"),
            patch("app.services.auth.create_refresh_token", return_value="new_rt"),
        ):
            access, refresh_tok = await refresh(db, "refresh_token_current_version")

        assert access == "new_at"
        assert refresh_tok == "new_rt"

    async def test_change_password_increments_token_version(self) -> None:
        from app.services.auth import change_password

        user = _make_user(token_version=0)
        db = _make_db(scalar_result=user)

        with (
            patch("app.services.auth.verify_password", return_value=True),
            patch("app.services.auth.hash_password", return_value="new_hashed_password"),
        ):
            await change_password(db, user.id, "old_password123", "new_password456")

        assert user.token_version == 1

    async def test_reset_password_increments_token_version(self) -> None:
        from app.services.auth import reset_password

        user = _make_user(token_version=0)
        db = _make_db(scalar_result=user)

        with (
            patch("app.services.auth.decode_reset_token", return_value=user.id),
            patch("app.services.auth.hash_password", return_value="new_hashed_password"),
        ):
            await reset_password(db, "reset_tok", "new_password456")

        assert user.token_version == 1

    async def test_refresh_rejected_for_token_issued_before_reset_password(self) -> None:
        from app.services.auth import reset_password

        user = _make_user(token_version=0)
        db = _make_db(scalar_result=user)

        with (
            patch("app.services.auth.decode_reset_token", return_value=user.id),
            patch("app.services.auth.hash_password", return_value="new_hashed_password"),
        ):
            await reset_password(db, "reset_tok", "new_password456")

        with (
            patch(
                "app.services.auth.decode_token",
                return_value={
                    "user_id": str(user.id),
                    "tenant_id": str(user.tenant_id),
                    "type": "refresh",
                    "token_version": 0,
                },
            ),
            patch("app.services.auth.create_access_token", return_value="new_at"),
            patch("app.services.auth.create_refresh_token", return_value="new_rt"),
        ):
            with pytest.raises(UnauthorizedError, match="revoked"):
                await refresh(db, "refresh_token_issued_before_reset_password")

    async def test_login_issues_tokens_with_current_token_version(self) -> None:
        user = _make_user(token_version=3)
        db = _make_db(scalar_result=user)

        with (
            patch("app.services.auth.verify_password", return_value=True),
            patch("app.services.auth.create_access_token", return_value="at") as mock_access,
            patch("app.services.auth.create_refresh_token", return_value="rt") as mock_refresh,
        ):
            await login(db, "test@example.com", "password")

        mock_access.assert_called_once_with(user.id, user.tenant_id, 3)
        mock_refresh.assert_called_once_with(user.id, user.tenant_id, 3)


async def _real_user(db: object, tenant: object, token_version: int = 0) -> object:
    """A persisted User row.

    Deliberately NOT _make_db()/_make_user(): that double answers every query
    with a preset value without ever evaluating the WHERE clause, so a lookup
    written with no tenant_id filter would satisfy the cross-tenant case below
    just as well as a correct one — and freeze it that way forever.
    """
    from app.models.user import User

    user = User(
        tenant_id=tenant.id,
        email="eco@cabinet.fr",
        hashed_password="not-a-real-hash",
        token_version=token_version,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestVerifyAccessTokenVersion:
    async def test_access_token_issued_before_change_password_is_refused(
        self, db: object, tenant_a: object
    ) -> None:
        from app.services.auth import change_password, verify_access_token_version

        user = await _real_user(db, tenant_a)

        with (
            patch("app.services.auth.verify_password", return_value=True),
            patch("app.services.auth.hash_password", return_value="new_hashed_password"),
        ):
            await change_password(db, user.id, "old_password123", "new_password456")

        with pytest.raises(UnauthorizedError, match="revoked"):
            await verify_access_token_version(db, user.id, tenant_a.id, 0)

    async def test_matching_version_is_accepted(self, db: object, tenant_a: object) -> None:
        from app.services.auth import verify_access_token_version

        user = await _real_user(db, tenant_a, token_version=2)

        assert await verify_access_token_version(db, user.id, tenant_a.id, 2) is None

    async def test_lower_version_is_refused(self, db: object, tenant_a: object) -> None:
        from app.services.auth import verify_access_token_version

        user = await _real_user(db, tenant_a, token_version=5)

        with pytest.raises(UnauthorizedError, match="revoked"):
            await verify_access_token_version(db, user.id, tenant_a.id, 4)

    async def test_access_token_issued_before_reset_password_is_refused(
        self, db: object, tenant_a: object
    ) -> None:
        from app.services.auth import reset_password, verify_access_token_version

        user = await _real_user(db, tenant_a)

        with (
            patch("app.services.auth.decode_reset_token", return_value=user.id),
            patch("app.services.auth.hash_password", return_value="new_hashed_password"),
        ):
            await reset_password(db, "reset_tok", "new_password456")

        with pytest.raises(UnauthorizedError, match="revoked"):
            await verify_access_token_version(db, user.id, tenant_a.id, 0)

    async def test_vanished_user_is_refused(self, db: object, tenant_a: object) -> None:
        from app.services.auth import verify_access_token_version

        with pytest.raises(UnauthorizedError, match="Invalid token"):
            await verify_access_token_version(db, uuid.uuid4(), tenant_a.id, 0)

    async def test_token_without_version_claim_is_refused(
        self, db: object, tenant_a: object
    ) -> None:
        from app.services.auth import verify_access_token_version

        user = await _real_user(db, tenant_a)

        with pytest.raises(UnauthorizedError, match="revoked"):
            await verify_access_token_version(db, user.id, tenant_a.id, None)

    async def test_token_claiming_another_tenant_is_refused(
        self, db: object, tenant_a: object, tenant_b: object
    ) -> None:
        """The cross-tenant case. Nothing but the WHERE clause enforces isolation.

        The user exists and the version is current, so a lookup filtering on the
        id alone finds the row, matches, and returns — this case is the only
        thing that tells the two implementations apart.
        """
        from app.services.auth import verify_access_token_version

        user = await _real_user(db, tenant_a, token_version=3)

        with pytest.raises(UnauthorizedError, match="Invalid token"):
            await verify_access_token_version(db, user.id, tenant_b.id, 3)

    async def test_higher_version_is_refused_too(self, db: object, tenant_a: object) -> None:
        from app.services.auth import verify_access_token_version

        user = await _real_user(db, tenant_a, token_version=1)

        with pytest.raises(UnauthorizedError, match="revoked"):
            await verify_access_token_version(db, user.id, tenant_a.id, 2)


class TestLoginEqualisesBothBranches:
    async def test_unknown_email_still_runs_a_password_verification(self) -> None:
        """Asserting the call is the exception 05-testing.md allows.

        The only externally observable effect of the equalisation is elapsed
        time, and asserting on milliseconds is flaky. Nothing else traces it.
        """
        db = _make_db(scalar_result=None)

        with patch("app.services.auth.verify_password", return_value=False) as verify:
            with pytest.raises(UnauthorizedError, match="invalid login credentials"):
                await login(db, "unknown@test.com", "password")

        verify.assert_called_once()

    async def test_unknown_email_keeps_the_same_refusal(self) -> None:
        db = _make_db(scalar_result=None)

        with patch("app.services.auth.verify_password", return_value=False):
            with pytest.raises(UnauthorizedError, match="invalid login credentials"):
                await login(db, "unknown@test.com", "password")

    def test_the_dummy_hash_is_a_real_cost_12_bcrypt_hash(self) -> None:
        """Two defects, not one.

        A malformed constant makes verify_password raise, turning every unknown
        address into a 500 — the very oracle this change closes. A cost-4
        constant returns False without raising but verifies in about 5 ms
        instead of 169, so it equalises nothing.
        """
        import bcrypt

        from app.services.auth import _DUMMY_PASSWORD_HASH

        assert _DUMMY_PASSWORD_HASH.startswith("$2b$12$")
        assert len(_DUMMY_PASSWORD_HASH) == 60
        assert bcrypt.checkpw(b"anything at all", _DUMMY_PASSWORD_HASH.encode()) is False


async def _user_with_role(db: object, tenant: object, email: str, role: str) -> object:
    """A persisted User row with a chosen address and role.

    Not _real_user(): it hardcodes email="eco@cabinet.fr" and takes no role,
    while users.email is unique globally — the cases below need several
    addresses and both roles. Real rows, not a double, for the same reason as
    _real_user: a double never evaluates the WHERE clause, so it would accept a
    guard written without its tenant_id predicate.
    """
    from app.models.user import User

    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password="not-a-real-hash",
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _listed(monkeypatch: object, *emails: str) -> None:
    """Pin the effective admin list to exactly these addresses.

    The environment moves to production because conftest.py:12 pins
    ENVIRONMENT=local for the whole suite, and in dev_mode
    effective_admin_emails() adds DEV_SEED_EMAIL — every expectation below
    would then carry an address its case never listed. dev_mode is a property
    with no setter, so the environment is what moves (motive spelled out in
    tests/services/test_email.py).
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "admin_emails", ",".join(emails))
    monkeypatch.setattr(settings, "environment", "production")


class TestVerifyAdminRole:
    async def test_an_admin_of_tenant_a_presented_with_the_tenant_id_of_tenant_b_is_refused(
        self, db: object, tenant_a: object, tenant_b: object
    ) -> None:
        """The cross-tenant case, on two real User rows.

        The row exists and carries role="admin", so a lookup filtering on the id
        alone finds it, reads "admin" and lets the caller through. This is the
        only case that tells the two implementations apart.
        """
        from app.core.exceptions import ForbiddenError
        from app.services.auth import verify_admin_role

        admin = await _user_with_role(db, tenant_a, "boss.a@cabinet.fr", "admin")

        with pytest.raises(ForbiddenError):
            await verify_admin_role(db, admin.id, tenant_b.id)

    async def test_an_admin_of_the_presented_tenant_passes_the_guard_without_raising(
        self, db: object, tenant_a: object
    ) -> None:
        from app.services.auth import verify_admin_role

        admin = await _user_with_role(db, tenant_a, "boss.a@cabinet.fr", "admin")

        assert await verify_admin_role(db, admin.id, tenant_a.id) is None

    async def test_an_owner_of_the_presented_tenant_is_refused_by_forbidden_error(
        self, db: object, tenant_a: object
    ) -> None:
        from app.core.exceptions import ForbiddenError
        from app.services.auth import verify_admin_role

        user = await _user_with_role(db, tenant_a, "eco@cabinet.fr", "owner")

        with pytest.raises(ForbiddenError):
            await verify_admin_role(db, user.id, tenant_a.id)

    async def test_a_user_id_that_exists_in_no_tenant_is_refused(
        self, db: object, tenant_a: object
    ) -> None:
        """The row-not-found path, distinct from the role that does not match."""
        from app.core.exceptions import ForbiddenError
        from app.services.auth import verify_admin_role

        with pytest.raises(ForbiddenError):
            await verify_admin_role(db, uuid.uuid4(), tenant_a.id)

    async def test_an_unknown_role_member_is_refused(
        self, db: object, tenant_a: object
    ) -> None:
        """The guard compares to "admin"; it does not accept "anything but owner"."""
        from app.core.exceptions import ForbiddenError
        from app.services.auth import verify_admin_role

        user = await _user_with_role(db, tenant_a, "eco@cabinet.fr", "member")

        with pytest.raises(ForbiddenError):
            await verify_admin_role(db, user.id, tenant_a.id)


class TestReconcileAdminRoles:
    async def test_the_writes_survive_a_rollback_of_the_calling_session(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        """First case of the class on purpose: a missing commit fails only here.

        The db fixture yields ONE session built with expire_on_commit=False
        (conftest.py:64-77). An implementation that sets user.role and never
        commits still answers "admin" to every later read of that session, out
        of the identity map — "comes out admin", "appears in promoted",
        idempotence, all of them would pass and freeze that way. In production
        the transaction would be discarded and nobody promoted. Rolling back and
        re-reading from the database is what separates the two.
        """
        from sqlalchemy import select

        from app.models.user import User
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss@cabinet.fr")
        await _user_with_role(db, tenant_a, "boss@cabinet.fr", "owner")

        await reconcile_admin_roles(db)
        await db.rollback()
        db.expunge_all()

        rows = await db.execute(select(User).where(User.email == "boss@cabinet.fr"))
        assert rows.scalar_one().role == "admin"

    async def test_a_listed_owner_comes_out_admin_and_the_address_is_in_promoted(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss@cabinet.fr")
        user = await _user_with_role(db, tenant_a, "boss@cabinet.fr", "owner")

        result = await reconcile_admin_roles(db)

        assert result.promoted == ("boss@cabinet.fr",)
        await db.refresh(user)
        assert user.role == "admin"

    async def test_an_admin_whose_address_is_not_listed_comes_out_owner_and_is_in_demoted(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss@cabinet.fr")
        await _user_with_role(db, tenant_a, "boss@cabinet.fr", "admin")
        ex_boss = await _user_with_role(db, tenant_a, "ex.boss@cabinet.fr", "admin")

        result = await reconcile_admin_roles(db)

        assert result.demoted == ("ex.boss@cabinet.fr",)
        await db.refresh(ex_boss)
        assert ex_boss.role == "owner"

    async def test_a_listed_address_matching_no_account_is_in_unknown_and_raises_nothing(
        self, db: object, monkeypatch: object
    ) -> None:
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "ghost@cabinet.fr")

        result = await reconcile_admin_roles(db)

        assert result.unknown == ("ghost@cabinet.fr",)
        assert result.promoted == ()
        assert result.demoted == ()

    async def test_an_unlisted_owner_is_untouched_and_appears_in_none_of_the_three_lists(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss@cabinet.fr")
        await _user_with_role(db, tenant_a, "boss@cabinet.fr", "admin")
        eco = await _user_with_role(db, tenant_a, "eco@cabinet.fr", "owner")

        result = await reconcile_admin_roles(db)

        assert result.promoted == ()
        assert result.demoted == ()
        assert result.unknown == ()
        await db.refresh(eco)
        assert eco.role == "owner"

    async def test_two_listed_accounts_in_two_different_tenants_are_both_promoted(
        self, db: object, tenant_a: object, tenant_b: object, monkeypatch: object
    ) -> None:
        """The reconciliation is deliberately cross-tenant — the one query of the
        repository with no tenant_id predicate."""
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss.a@cabinet.fr", "boss.b@cabinet.fr")
        boss_a = await _user_with_role(db, tenant_a, "boss.a@cabinet.fr", "owner")
        boss_b = await _user_with_role(db, tenant_b, "boss.b@cabinet.fr", "owner")

        result = await reconcile_admin_roles(db)

        assert set(result.promoted) == {"boss.a@cabinet.fr", "boss.b@cabinet.fr"}
        await db.refresh(boss_a)
        await db.refresh(boss_b)
        assert boss_a.role == "admin"
        assert boss_b.role == "admin"

    async def test_an_address_differing_only_by_case_does_not_promote_and_is_in_unknown(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        """The security case: users.email is unique but case-sensitive and signup
        normalises nothing, so a case-insensitive match would let the account
        Boss@cabinet.fr be promoted by the entry boss@cabinet.fr."""
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss@cabinet.fr")
        lookalike = await _user_with_role(db, tenant_a, "Boss@cabinet.fr", "owner")

        result = await reconcile_admin_roles(db)

        assert result.unknown == ("boss@cabinet.fr",)
        assert result.promoted == ()
        await db.refresh(lookalike)
        assert lookalike.role == "owner"

    async def test_a_case_variant_that_is_already_admin_is_demoted(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        """The demotion half of the exactness rule, which no other case reaches.

        The lookalike of the case above is an owner, so `email.in_(listed)`
        never returns it and the Python membership test is never asked to
        disagree with the SQL. Give the lookalike role="admin" and the row comes
        back through the second disjunct instead: an implementation that folds
        case in Python keeps it admin, and nothing else in this suite notices.
        """
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss@cabinet.fr")
        lookalike = await _user_with_role(db, tenant_a, "Boss@cabinet.fr", "admin")

        result = await reconcile_admin_roles(db)

        assert result.demoted == ("Boss@cabinet.fr",)
        assert result.unknown == ("boss@cabinet.fr",)
        await db.refresh(lookalike)
        assert lookalike.role == "owner"

    async def test_a_second_run_on_the_same_list_reports_no_promotion_and_no_demotion(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch, "boss@cabinet.fr")
        user = await _user_with_role(db, tenant_a, "boss@cabinet.fr", "owner")

        await reconcile_admin_roles(db)
        second = await reconcile_admin_roles(db)

        assert second.promoted == ()
        assert second.demoted == ()
        await db.refresh(user)
        assert user.role == "admin"

    async def test_an_empty_list_demotes_every_admin_and_promotes_none(
        self, db: object, tenant_a: object, tenant_b: object, monkeypatch: object
    ) -> None:
        """A deployed environment with the variable unset: no firm is admin."""
        from app.services.auth import reconcile_admin_roles

        _listed(monkeypatch)
        boss_a = await _user_with_role(db, tenant_a, "boss.a@cabinet.fr", "admin")
        boss_b = await _user_with_role(db, tenant_b, "boss.b@cabinet.fr", "admin")

        result = await reconcile_admin_roles(db)

        assert set(result.demoted) == {"boss.a@cabinet.fr", "boss.b@cabinet.fr"}
        assert result.promoted == ()
        await db.refresh(boss_a)
        await db.refresh(boss_b)
        assert boss_a.role == "owner"
        assert boss_b.role == "owner"


class TestSignupRefusesAListedAddress:
    async def test_signup_on_an_address_in_the_effective_list_raises_conflict_error(
        self, db: object, monkeypatch: object
    ) -> None:
        """Without this refusal, a listed address with no account is an admin
        seat the first signup claims at the next restart: /api/auth/signup is
        public and email_verified is read nowhere."""
        _listed(monkeypatch, "boss@cabinet.fr")

        with pytest.raises(ConflictError):
            await signup(db, "boss@cabinet.fr", "password123", "Cabinet")

    async def test_the_message_is_exactly_the_one_of_an_address_already_taken(
        self, db: object, tenant_a: object, monkeypatch: object
    ) -> None:
        """Indiscernible, so no oracle: a message of its own would tell any
        caller which addresses are administrator seats."""
        _listed(monkeypatch, "boss@cabinet.fr")
        await _user_with_role(db, tenant_a, "taken@cabinet.fr", "owner")

        with pytest.raises(ConflictError) as taken:
            await signup(db, "taken@cabinet.fr", "password123", "Cabinet")

        with pytest.raises(ConflictError) as listed:
            await signup(db, "boss@cabinet.fr", "password123", "Cabinet")

        assert "email already registered" in taken.value.message
        assert listed.value.message == taken.value.message
        assert listed.value.status_code == 409

    async def test_the_refusal_creates_no_user_row_and_no_tenant_row(
        self, db: object, monkeypatch: object
    ) -> None:
        from sqlalchemy import func, select

        from app.models.tenant import Tenant
        from app.models.user import User

        _listed(monkeypatch, "boss@cabinet.fr")

        with pytest.raises(ConflictError):
            await signup(db, "boss@cabinet.fr", "password123", "Cabinet")

        users = await db.execute(select(func.count()).select_from(User))
        tenants = await db.execute(select(func.count()).select_from(Tenant))
        assert users.scalar_one() == 0
        assert tenants.scalar_one() == 0

    async def test_an_address_absent_from_the_list_signs_up_normally_and_is_born_owner(
        self, db: object, monkeypatch: object
    ) -> None:
        """The case that keeps the refusal from being too broad."""
        _listed(monkeypatch, "boss@cabinet.fr")

        with patch("app.services.auth.hash_password", return_value="hashed"):
            user, _access, _refresh = await signup(
                db, "eco@cabinet.fr", "password123", "Cabinet"
            )

        assert user.email == "eco@cabinet.fr"
        assert user.role == "owner"


def _blocking(order: list[str], started: object, released: object, result: object) -> object:
    """A stand-in for bcrypt that announces it has begun, then holds.

    `started` is what makes the case discriminate. Waiting on `released` alone
    proved nothing: login awaits db.execute BEFORE reaching bcrypt, and that
    await already hands the loop over, so the other coroutine ran first whether
    or not the hash was deported. Signalling from inside the call means the
    other coroutine can only proceed while the password work is in flight —
    which is possible off the event loop and impossible on it.

    The wait is bounded inside the double, not around the gather: on the unfixed
    code the loop is blocked by this very call, so an asyncio.wait_for could
    never arm itself and the case would hang instead of failing.
    pytest-timeout is not installed here.
    """

    def double(*_args: object, **_kwargs: object) -> object:
        started.set()
        released.wait(timeout=5)
        order.append("password work")
        return result

    return double


async def _once_password_work_is_in_flight(order: list[str], started: object, released: object):
    """Records itself only while the double is blocked, then frees it."""
    import asyncio

    for _ in range(20_000):
        if started.is_set():
            break
        await asyncio.sleep(0)
    order.append("other coroutine")
    released.set()


class TestPasswordWorkLeavesTheEventLoop:
    """No duration is asserted anywhere below — only the order of two events.

    This file already records at TestLoginEqualisesBothBranches that asserting
    on milliseconds is flaky. An order is deterministic, and it inverts the
    moment the bcrypt call stops being handed to a worker thread.
    """

    async def test_login_lets_another_coroutine_finish_first(
        self, db: object, tenant_a: object
    ) -> None:
        import asyncio
        import threading

        from app.services.auth import login

        order: list[str] = []
        started = threading.Event()
        released = threading.Event()
        other = _once_password_work_is_in_flight(order, started, released)

        user = await _user_with_role(db, tenant_a, "eco@cabinet.fr", "owner")

        with patch("app.services.auth.verify_password", _blocking(order, started, released,True)):
            await asyncio.gather(login(db, user.email, "whatever"), other)

        assert order == ["other coroutine", "password work"]

    async def test_signup_lets_another_coroutine_finish_first(self, db: object) -> None:
        import asyncio
        import threading

        from app.services.auth import signup

        order: list[str] = []
        started = threading.Event()
        released = threading.Event()
        other = _once_password_work_is_in_flight(order, started, released)

        with patch("app.services.auth.hash_password", _blocking(order, started, released,"hashed")):
            await asyncio.gather(signup(db, "neuf@cabinet.fr", "password123", "Cabinet"), other)

        assert order == ["other coroutine", "password work"]

    async def test_change_password_lets_another_coroutine_finish_first(
        self, db: object, tenant_a: object
    ) -> None:
        import asyncio
        import threading

        from app.services.auth import change_password

        order: list[str] = []
        started = threading.Event()
        released = threading.Event()
        other = _once_password_work_is_in_flight(order, started, released)

        user = await _user_with_role(db, tenant_a, "eco@cabinet.fr", "owner")

        with patch("app.services.auth.verify_password", _blocking(order, started, released,True)):
            await asyncio.gather(
                change_password(db, user.id, "current", "nouveaumotdepasse1"), other
            )

        assert order == ["other coroutine", "password work"]

    async def test_reset_password_lets_another_coroutine_finish_first(
        self, db: object, tenant_a: object
    ) -> None:
        import asyncio
        import threading

        from app.core.auth import create_reset_token
        from app.services.auth import reset_password

        order: list[str] = []
        started = threading.Event()
        released = threading.Event()
        other = _once_password_work_is_in_flight(order, started, released)

        user = await _user_with_role(db, tenant_a, "eco@cabinet.fr", "owner")
        token = create_reset_token(user.id)

        with patch("app.services.auth.hash_password", _blocking(order, started, released,"hashed")):
            await asyncio.gather(reset_password(db, token, "nouveaumotdepasse1"), other)

        assert order == ["other coroutine", "password work"]

    async def test_the_unknown_email_branch_also_pays_off_the_loop(self, db: object) -> None:
        """The dummy verification that closes the timing oracle must survive the
        move, and cost its time off the event loop like the real one."""
        import asyncio
        import threading

        from app.services.auth import login

        order: list[str] = []
        started = threading.Event()
        released = threading.Event()
        other = _once_password_work_is_in_flight(order, started, released)

        with patch("app.services.auth.verify_password", _blocking(order, started, released,False)):
            with pytest.raises(UnauthorizedError):
                await asyncio.gather(login(db, "personne@cabinet.fr", "whatever"), other)

        assert order == ["other coroutine", "password work"]

    async def test_change_password_hashes_the_new_one_off_the_loop_too(
        self, db: object, tenant_a: object
    ) -> None:
        """The sixth site. The case above it blocks only the verification, so
        bringing this one back onto the loop left the whole suite green."""
        import asyncio
        import threading

        from app.services.auth import change_password

        order: list[str] = []
        started = threading.Event()
        released = threading.Event()
        other = _once_password_work_is_in_flight(order, started, released)

        user = await _user_with_role(db, tenant_a, "eco@cabinet.fr", "owner")

        with patch("app.services.auth.verify_password", return_value=True):
            with patch(
                "app.services.auth.hash_password",
                _blocking(order, started, released, "hashed"),
            ):
                await asyncio.gather(
                    change_password(db, user.id, "current", "nouveaumotdepasse1"), other
                )

        assert order == ["other coroutine", "password work"]

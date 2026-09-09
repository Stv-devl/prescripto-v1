"""The two password primitives, called for real.

Every other test in this repository patches them — eighteen sites do. So until
this file existed, nothing asserted that hashing then verifying actually works,
and a chantier moving all six call sites off the event loop would have had no
ground truth to move away from.

Two bcrypt operations at cost 12, so this file costs roughly a third of a second
and no more.
"""

from app.core.auth import hash_password, verify_password


class TestHashingRoundTrip:
    def test_a_password_verifies_against_its_own_hash(self) -> None:
        assert verify_password("motdepasse-du-cabinet", hash_password("motdepasse-du-cabinet"))

    def test_another_password_does_not(self) -> None:
        assert not verify_password("presque-le-bon", hash_password("motdepasse-du-cabinet"))

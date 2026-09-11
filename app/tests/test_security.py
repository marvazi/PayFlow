from app.core.security import hash_password, verify_password

def test_correct_password():
    hashed_password = hash_password("Secret123")
    assert verify_password("Secret123", hashed_password)

def test_incorrect_password():
    hashed_password = hash_password("Secret123")
    assert not verify_password("Secret1232", hashed_password)

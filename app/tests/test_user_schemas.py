import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate


def test_normalize_email_and_username():
    user = UserCreate(name=" Максим ", email=" Max@Example.COM ", password=" 123456757 ")
    assert user.email == "max@example.com"
    assert user.name == "Максим"


def test_reject_whitespace_only_name():
    with pytest.raises(ValidationError):
        UserCreate(name="  ", email=" Max@Example.COM ", password=" 123456757 ")

def test_password_not_change():
    user = UserCreate(name=" Максим ", email=" Max@Example.COM ", password=" 123456757 ")
    assert user.password == " 123456757 "



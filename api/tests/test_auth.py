# api/tests/test_auth.py
import pytest
from fastapi import HTTPException
from api.auth import User, create_token, get_current_user, require_student, require_teacher


def test_token_creation_and_parsing():
    token = create_token("user_123", "teacher", name="Prof. Turing")
    user = get_current_user(auth_token=token)
    assert user.id == "user_123"
    assert user.role == "teacher"
    assert user.name == "Prof. Turing"


def test_role_guards():
    teacher_user = User(id="t1", role="teacher", name="Teacher")
    student_user = User(id="s1", role="student", name="Student")

    assert require_teacher(teacher_user).id == "t1"
    with pytest.raises(HTTPException) as exc:
        require_teacher(student_user)
    assert exc.value.status_code == 403

    assert require_student(student_user).id == "s1"
    with pytest.raises(HTTPException) as exc:
        require_student(teacher_user)
    assert exc.value.status_code == 403

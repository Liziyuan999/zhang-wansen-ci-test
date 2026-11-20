# -*- coding: utf-8 -*-
"""种子数据：创建默认部门与管理员账号。
用法：python scripts/seed_data.py
"""
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Department, User  # noqa: E402


def main() -> None:
    db: Session = SessionLocal()
    try:
        dept = db.query(Department).filter(Department.dept_name == "默认部门").first()
        if not dept:
            dept = Department(dept_name="默认部门")
            db.add(dept)
            db.flush()
        admin = db.query(User).filter(User.email == "admin@knowseek.com").first()
        if not admin:
            # 不硬编码弱密码：优先读环境变量 ADMIN_INIT_PASSWORD，否则生成随机密码
            password = os.environ.get("ADMIN_INIT_PASSWORD") or secrets.token_urlsafe(9)
            admin = User(
                username="admin",
                email="admin@knowseek.com",
                password_hash=hash_password(password),
                role="admin",
                dept_id=dept.id,
                status="active",
            )
            db.add(admin)
            db.commit()
            if os.environ.get("ADMIN_INIT_PASSWORD"):
                print("已创建管理员账号: admin@knowseek.com（初始密码来自环境变量 ADMIN_INIT_PASSWORD）")
            else:
                print(f"已创建管理员账号: admin@knowseek.com / 初始密码 {password}（随机生成，请立即登录修改并妥善保存）")
        else:
            print("管理员账号已存在，跳过")
    finally:
        db.close()


if __name__ == "__main__":
    main()

from auth_service.users_db import SessionLocal, Base, engine
from auth_service.users_models import User, RoleEnum
from passlib.hash import bcrypt
import uuid

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Comprueba si ya existe un admin
    if not db.query(User).filter_by(role=RoleEnum.admin).first():
        admin = User(
            id=str(uuid.uuid4()),
            email="admin@taller.com",
            password_hash=bcrypt.hash("changeme"),
            full_name="Administrador",
            role=RoleEnum.admin
        )
        db.add(admin)
        db.commit()
    db.close()

if __name__ == "__main__":
    seed()

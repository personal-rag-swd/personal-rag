import asyncio
from beanie import init_beanie
from app.core.database import init_db
from app.users.models import User
from app.core.security import hash_password

async def main():
    mongo_client = await init_db()
    db = mongo_client.get_default_database()
    await init_beanie(database=db, document_models=[User])
    
    email = "admin@example.com"
    password = "password123"
    
    existing = await User.find_one({"email": email})
    if existing:
        print(f"User {email} already exists!")
        return
        
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role="admin",
        is_active=True
    )
    await user.insert()
    print(f"Successfully created dev user: {email} / {password}")

if __name__ == "__main__":
    asyncio.run(main())

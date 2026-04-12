from backend.db.database import engine
from backend.db.models import Base

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done.")
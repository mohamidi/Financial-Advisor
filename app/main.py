from fastapi import Depends, FastAPI

from app.auth.dependencies import AuthenticatedUser, get_current_user

app = FastAPI(title="Financial Advisor Agent")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/protected-ping")
def protected_ping(user: AuthenticatedUser = Depends(get_current_user)):
    return {"message": f"hello {user.email or user.id}, you are authenticated"}

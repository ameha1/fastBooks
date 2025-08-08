from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy import and_

from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException, Query, status, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel


app = FastAPI()


# Security configurations
SECRET_KEY = "iowehim"  # Change this to a strong secret in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create User Models

class UserBase(SQLModel):
    username: str = Field(index=True)
    email: str = Field(index=True)
    full_name: str | None = None

class UserCreate(UserBase):
    password: str

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    disabled: bool = False

class UserInDB(UserBase):
    hashed_password: str

# Create Token Models

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

# Create Password Utilities Functionalities

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

# Create User Authentication Functionalities

def get_user(session: Session, username: str):
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    return user

def authenticate_user(session: Session, username: str, password: str):
    user = get_user(session, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# Create Tokens

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Current Users Dependency

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(lambda: next(get_session()))
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user(session, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Creating a Model

class BookCreate(SQLModel):
    name: str
    author: str
    year: int

class Book(SQLModel, table=True):
    id : int | None = Field(default=None, primary_key=True)
    name : str = Field(index=True)
    author : str = Field(index=True)
    year : int

# Creating an Engine

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


# Creating the Tables


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


# Creating a Session Dependecy

def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# Creating DataBase Tables at StartUp

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Endpoints

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
):
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=UserBase)
async def create_user(user: UserCreate, session: SessionDep):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.post('/books/')
async def create_books(
    book_data: BookCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> Book:
    """
    Create a new book (ID will be automatically assigned)
    """
    # Convert BookCreate to Book (ID will be auto-generated)
    db_book = Book.from_orm(book_data)
    
    session.add(db_book)
    session.commit()
    session.refresh(db_book)
    return db_book


@app.get('/books/')
async def getBooks(
    session : SessionDep,
    offset : int = 0,
    limit : Annotated[int, Query(le=100)] = 100,

    # search and filter parameter

    name: Optional[str] = Query(None, description="Search by book name (partial match)"),
    author: Optional[str] = Query(None, description="Filter by exact author name"),
    min_year: Optional[int] = Query(None, description="Minimum publication year"),
    max_year: Optional[int] = Query(None, description="Maximum publication year")
    ) -> list[Book]:
    

    # getting books with optional search and  filtering

    query = select(Book)

    filters = []

    if name:
        filters.append(Book.name.ilike(f"%{name}%"))
                       
    if author:
        filters.append(Book.author == author)

    if min_year is not None:
        filters.append(Book.year >= min_year)
    if max_year is not None:
        filters.append(Book.year <= max_year)

    # Combine all filters with AND logic
    if filters:
        query = query.where(and_(*filters))


     # Apply pagination
    books = session.exec(query.offset(offset).limit(limit)).all()
    return books


@app.get("/books/{book_id}")
async def getBookById(book_id : int, session : SessionDep) -> Book:

    book = session.get(Book, book_id)

    if not book:
        raise HTTPException(status_code=404, detail='Book not Found!')

    return book

@app.delete("/books/{book_id}")
async def deleteBook(book_id :int, session:SessionDep) -> Book:

    book = session.get(Book, book_id)

    if not book:
        raise HTTPException(status_code=404, detail='Book not Found!')
    
    session.delete(book)
    session.commit()

    return {"ok", True}

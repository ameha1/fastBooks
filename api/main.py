from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy import and_



app = FastAPI()

# Creating a Model

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


@app.post('/books/')
async def createBooks(book : Book, session: SessionDep) -> Book:

    session.add(book)
    session.commit()
    session.refresh(book)
    return book


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

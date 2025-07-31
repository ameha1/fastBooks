from fastapi import FastAPI

from pydantic import BaseModel

app = FastAPI()

# books = { "1" : ["Name : HarryPotter","Author : JK Rowling","Year : 1987"],
#          "2" : ["Name : GameOfThrones","Author : George R.R Martin","Year : 1979"],
#          "3" : ["Name : LordOfTheRings","Author : John R.R Tolkein","Year : 1956"]
#           }

books = []

class Book(BaseModel):
    id : int
    name : str
    author : str
    year : int

@app.post('/books/')
async def createBooks(book : Book):

    books.append(book)

    return book


@app.get('/books/')
async def getBooks():

    return(books)
    
@app.get("/books/{bookId}")
async def getBookById(bookId : int):

    return (books[bookId])

